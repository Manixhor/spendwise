# Design Document: Extra Savings Button

## Overview

This feature adds a manual "extra savings" flow to the Savings Goals page. A new "+ Add Extra Savings" button sits next to the existing "+ New Goal" button. Clicking it opens a modal where the user picks an active goal and enters an amount; the backend adds that amount to the goal's `saved_amount` (capped at `target_amount`). The Allocation Card gains a session-tracked "Extra" row that accumulates all manual additions made during the current browser session.

The design deliberately stays minimal: no new database field is required for the session-level display (it is tracked in a JS variable), and the backend endpoint closely mirrors the existing `api_contribute_goal` view.

---

## Architecture

The feature spans three layers:

```
Browser (savings.html)
  │
  ├── "+ Add Extra Savings" button  →  opens Extra_Savings_Modal
  │
  └── Extra_Savings_Modal
        │  POST /api/goals/{id}/add-savings/
        ▼
Django view: api_add_extra_savings
  │
  ├── Validates amount > 0
  ├── Fetches SavingsGoal (owner check)
  ├── Adds amount to saved_amount (capped at target_amount)
  ├── Sets is_active = False if goal is now complete
  └── Returns updated goal JSON
        │
        ▼
Browser
  ├── Updates goal card in-place (saved_amount, progress ring, remaining)
  └── Increments session-level extra total → updates/shows Extra_Row in Allocation Card
```

The new endpoint is structurally identical to `api_contribute_goal` (which already exists for the per-card "Contribute" button). The key difference is that `api_add_extra_savings` is the canonical entry point for the new modal flow and will be the one referenced by the Allocation Card's Extra_Row logic.

---

## Components and Interfaces

### 1. Backend — `api_add_extra_savings` view

**File:** `login/views.py`

```python
@login_required(login_url="/login/")
@require_POST
def api_add_extra_savings(request: HttpRequest, goal_id: int) -> JsonResponse:
    ...
```

**Request:** `POST /api/goals/{goal_id}/add-savings/`  
**Body:** `{ "amount": <positive number> }`  
**Auth:** Django `@login_required` — unauthenticated requests redirect to `/login/` (HTTP 302).

**Response (success):**
```json
{
  "success": true,
  "goal": {
    "id": 3,
    "name": "Emergency Fund",
    "target_amount": 50000.0,
    "saved_amount": 12500.0,
    "remaining": 37500.0,
    "progress_pct": 25.0,
    "is_complete": false,
    "is_active": true,
    "priority": "high",
    "allocation_percentage": 70,
    "ring_dash": 65.975,
    "ring_gap": 197.925
  }
}
```

**Error responses:**

| Condition | Status | Body |
|---|---|---|
| `amount <= 0` | 400 | `{"error": "Amount must be greater than zero."}` |
| Goal not found / wrong user | 404 | `{"error": "Not found."}` |
| Unauthenticated | 302 | Redirect to `/login/` |

**URL registration** in `login/urls.py`:
```python
path("api/goals/<int:goal_id>/add-savings/", api_add_extra_savings, name="api_add_extra_savings"),
```

---

### 2. Frontend — Extra Savings Button

**File:** `templates/login/savings.html`

Added to the existing `.header-actions` div, after the `#addGoalBtn`:

```html
<button class="add-goal-btn extra-savings-btn"
        id="addExtraSavingsBtn"
        type="button"
        {% if not has_active_goals %}disabled title="Create a goal first"{% endif %}>
  + Add Extra Savings
</button>
```

`has_active_goals` is a boolean passed from the `savings` view — `True` when at least one `SavingsGoal` with `is_active=True` and `saved_amount < target_amount` exists for the user.

When `disabled`, the button receives a `title` tooltip. CSS for the disabled state reuses the existing `.add-goal-btn:disabled` rule (opacity + cursor).

---

### 3. Frontend — Extra Savings Modal

**File:** `templates/login/savings.html`

New modal HTML block (mirrors the existing `#goalModal` structure):

```html
<div class="modal-overlay" id="extraSavingsModal" role="dialog" aria-modal="true"
     aria-labelledby="extraSavingsModalTitle">
  <div class="modal-card">
    <div class="modal-header">
      <h2 class="modal-title" id="extraSavingsModalTitle">Add Extra Savings</h2>
      <button class="modal-close" id="extraSavingsModalClose" aria-label="Close">&times;</button>
    </div>
    <p class="modal-sub">Choose a goal and enter the amount you want to add.</p>

    <label class="modal-field-label" for="extraSavingsGoal">Goal</label>
    <div class="modal-field-wrap">
      <select id="extraSavingsGoal" class="modal-input"></select>
    </div>

    <label class="modal-field-label" for="extraSavingsAmount">Amount</label>
    <div class="modal-field-wrap">
      <span class="modal-currency">₹</span>
      <input type="number" id="extraSavingsAmount" class="modal-input"
             placeholder="e.g. 2000" min="0.01" step="0.01" />
    </div>

    <p class="modal-error" id="extraSavingsError"></p>
    <button class="modal-save-btn" id="extraSavingsSave">Add Savings</button>
  </div>
</div>
```

The `<select>` is populated dynamically from a JS array `ACTIVE_GOALS` injected by the Django template (see Data Models section). Only active, incomplete goals appear.

---

### 4. Frontend — Allocation Card Extra Row

**File:** `templates/login/savings.html` (JS section)

A session-level JS variable `sessionExtraTotal` (number, starts at `0`) accumulates every successful submission. After each success:

```js
sessionExtraTotal += amount;
renderExtraRow(sessionExtraTotal);
```

`renderExtraRow` inserts (or updates) a single `.alloc-goal-row.extra-row` element inside `#allocationBreakdown`:

```html
<div class="alloc-goal-row extra-row" id="extraSavingsRow">
  <div class="alloc-goal-info">
    <span class="alloc-goal-name extra-label">⚡ Extra</span>
    <span class="alloc-goal-meta">Manual contribution · this session</span>
  </div>
  <span class="alloc-goal-amount extra-amount">₹2,000.00</span>
</div>
```

The row is hidden on page load (not rendered server-side) and only appears after the first successful submission.

---

## Data Models

### No new database field required

The session-level Extra_Row total is tracked purely in JavaScript (`sessionExtraTotal`). The backend simply adds to `saved_amount` — the same field used by automatic allocation and the existing Contribute button.

This matches the agreed design decision: "just add the amount to `saved_amount` directly." The `extra_saved` field approach was considered but rejected to keep the migration surface minimal and avoid double-counting concerns with the existing allocation logic.

### Template context additions

The `savings` view passes one new context variable:

| Variable | Type | Description |
|---|---|---|
| `has_active_goals` | `bool` | `True` if ≥1 active, incomplete goal exists |
| `active_goals_json` | `str` (JSON) | JSON array of `{id, name}` for active, incomplete goals — used to populate the modal dropdown |

Example:
```python
active_goals = [
    {"id": g.id, "name": g.name}
    for g in goals
    if g.is_active and not g.is_complete
]
context["has_active_goals"] = bool(active_goals)
context["active_goals_json"] = json.dumps(active_goals)
```

In the template, this is injected as a JS constant:
```html
<script>
const ACTIVE_GOALS = {{ active_goals_json|safe }};
</script>
```

### `SavingsGoal` model — no changes

The existing `saved_amount`, `target_amount`, and `is_active` fields are sufficient. The `_goal_json` helper already serialises all fields needed by the frontend update logic.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Add-savings caps at target

*For any* `SavingsGoal` with `saved_amount < target_amount`, and *for any* positive `amount`, after calling `api_add_extra_savings`, the goal's `saved_amount` SHALL equal `min(old_saved_amount + amount, target_amount)` and SHALL NOT exceed `target_amount`.

**Validates: Requirements 3.2, 3.3**

---

### Property 2: Goal completion on target reached

*For any* `SavingsGoal` where `saved_amount + amount >= target_amount` (i.e., the addition fills or overfills the goal), after calling `api_add_extra_savings`, the goal's `is_active` field SHALL be `False`.

**Validates: Requirements 3.4**

---

### Property 3: Invalid amount rejected

*For any* `amount` that is less than or equal to zero, `api_add_extra_savings` SHALL return HTTP 400 with `{"error": "Amount must be greater than zero."}` and the goal's `saved_amount` SHALL remain unchanged.

**Validates: Requirements 2.4, 3.5**

---

### Property 4: Active-goals dropdown invariant

*For any* collection of `SavingsGoal` objects belonging to a user (with varying `is_active` and `saved_amount` values), the goal selector dropdown in the Extra_Savings_Modal SHALL contain exactly the goals where `is_active = True` AND `saved_amount < target_amount` — no more, no less.

**Validates: Requirements 2.2**

---

### Property 5: Session extra total accumulates correctly

*For any* sequence of successful extra-savings submissions in a single browser session (each with a positive amount), the value displayed in the Allocation Card's Extra_Row SHALL equal the arithmetic sum of all submitted amounts.

**Validates: Requirements 5.1, 5.3**

---

### Property 6: Success response contains updated goal

*For any* valid POST to `api_add_extra_savings` (positive amount, goal belongs to user), the response SHALL be HTTP 200 with `success = true` and a `goal` object whose `saved_amount` reflects the capped addition and whose `progress_pct`, `remaining`, `ring_dash`, and `is_complete` fields are consistent with the new `saved_amount`.

**Validates: Requirements 3.8, 4.1**

---

**Property Reflection — redundancy check:**

- Properties 1 and 2 are complementary, not redundant: Property 1 covers the arithmetic cap; Property 2 covers the `is_active` side-effect. Both are needed.
- Property 3 (invalid amount) is distinct from Properties 1/2 (valid amount path).
- Property 6 partially overlaps with Property 1 (both check `saved_amount`), but Property 6 additionally verifies the full response shape and derived fields (`progress_pct`, `ring_dash`). Keeping both because they test different layers (model logic vs. serialisation).
- Properties 4 and 5 cover the frontend layer and have no overlap with backend properties.

---

## Error Handling

| Scenario | Handling |
|---|---|
| `amount <= 0` (frontend) | Modal JS validates before fetch; shows inline error, does not call API |
| No goal selected (frontend) | Modal JS validates; shows "Please select a goal." inline error |
| `amount <= 0` (backend) | Returns 400 `{"error": "Amount must be greater than zero."}` |
| Goal not found / wrong user | Returns 404 `{"error": "Not found."}` |
| Unauthenticated request | `@login_required` redirects to `/login/` (302) |
| Network / server error | Modal catches fetch exception; shows "Network error." inline |
| API returns error JSON | Modal displays `data.error` inline; modal stays open |
| Goal already complete | The dropdown excludes complete goals, so this path is unreachable from the UI; the backend still caps correctly if called directly |

---

## Testing Strategy

### Unit / example-based tests (`login/tests.py`)

These cover concrete scenarios and edge cases:

- **Button rendering:** Page renders with the button present; button is disabled when no active goals exist.
- **Modal structure:** Modal HTML contains amount input, goal select, and submit button.
- **Pre-selection:** Modal opens with the first active goal pre-selected.
- **Close behaviour:** Modal closes on `×` click and Escape key without submitting.
- **No-goal-selected error:** Submitting with empty select shows "Please select a goal."
- **API auth:** Unauthenticated POST to `/api/goals/{id}/add-savings/` returns 302.
- **API 404:** POST with a goal belonging to another user returns 404.
- **Goal card update:** After success response, goal card DOM reflects new `saved_amount` and progress.
- **Completion state:** After success response with `is_complete: true`, card shows "🎉 Goal reached!" badge.
- **Error display:** API error response keeps modal open and shows error text.
- **Extra_Row absent on load:** Allocation Card has no Extra_Row before any submission.
- **Extra_Row visual distinction:** Extra_Row has the `.extra-row` CSS class.

### Property-based tests

Using **Hypothesis** (Python property-based testing library for Django).

Each property test runs a minimum of **100 iterations**.

Tag format: `# Feature: extra-savings-button, Property {N}: {property_text}`

| Property | Test description |
|---|---|
| **P1** — Add-savings caps at target | Generate random `SavingsGoal` (varying `saved_amount`, `target_amount`) and random positive `amount`; assert `saved_amount` after API call equals `min(old + amount, target)` |
| **P2** — Goal completion | Generate goals where `saved_amount + amount >= target_amount`; assert `is_active = False` after call |
| **P3** — Invalid amount rejected | Generate amounts ≤ 0 (including 0, negatives, very large negatives); assert 400 response and unchanged `saved_amount` |
| **P4** — Dropdown invariant | Generate lists of goals with random `is_active`/`saved_amount`/`target_amount`; assert `ACTIVE_GOALS` JS array matches filter `is_active=True AND saved < target` |
| **P5** — Session total accumulates | Generate sequences of 1–10 positive amounts; simulate submissions and assert displayed total equals `sum(amounts)` |
| **P6** — Success response shape | Generate valid inputs; assert response is 200, `success=true`, and all derived fields are consistent |

**Configuration:**
```python
from hypothesis import given, settings
from hypothesis import strategies as st

@settings(max_examples=100)
@given(...)
def test_add_savings_caps_at_target(...):
    # Feature: extra-savings-button, Property 1: Add-savings caps at target
    ...
```

### Integration tests

- End-to-end: Submit the modal in a browser-like test (Django test client); verify DB `saved_amount` is updated and response JSON is correct.
- Allocation Card refresh: After extra savings submission, verify the allocation card still renders correctly alongside the new Extra_Row.
