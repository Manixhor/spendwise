# Requirements Document

## Introduction

This feature adds an "Extra Savings" button to the Savings Goals page, allowing users to manually add a one-off savings amount directly to any of their existing goals. The button appears alongside the existing "+ New Goal" button in the page header. Clicking it opens a modal where the user selects a goal and enters an amount; on submission the backend adds the amount to the goal's `saved_amount` (capped at `target_amount`). The manually added amount is also surfaced in the "This Month's Allocation" card as a distinct "Extra" row so users can see their ad-hoc contributions alongside automatic allocations.

## Glossary

- **Savings_Page**: The Django-rendered page at `/savings/` (`templates/login/savings.html`).
- **Extra_Savings_Modal**: The dialog that opens when the user clicks "+ Add Extra Savings".
- **Add_Savings_API**: The new backend endpoint `POST /api/goals/{id}/add-savings/` that applies an extra savings amount to a goal.
- **Goal**: A `SavingsGoal` model instance belonging to the authenticated user.
- **Allocation_Card**: The "This Month's Allocation" card on the Savings_Page that shows salary, expenses, available funds, and per-goal allocations.
- **Extra_Row**: A row in the Allocation_Card that displays the total manually added extra savings for the current month.
- **saved_amount**: The `SavingsGoal.saved_amount` field representing how much has been saved toward a goal.
- **target_amount**: The `SavingsGoal.target_amount` field representing the goal's savings target.

---

## Requirements

### Requirement 1: Extra Savings Button in Page Header

**User Story:** As a user, I want an "+ Add Extra Savings" button next to the "+ New Goal" button, so that I can quickly add a one-off savings contribution without creating a new goal.

#### Acceptance Criteria

1. THE Savings_Page SHALL render an "+ Add Extra Savings" button in the header actions area, adjacent to the existing "+ New Goal" button.
2. WHEN the user activates the "+ Add Extra Savings" button, THE Savings_Page SHALL open the Extra_Savings_Modal.
3. WHILE no Goals exist for the authenticated user, THE Savings_Page SHALL disable the "+ Add Extra Savings" button and display a tooltip indicating that a goal must be created first.

---

### Requirement 2: Extra Savings Modal

**User Story:** As a user, I want a modal where I can enter an amount and choose which goal to apply it to, so that I can direct my extra savings precisely.

#### Acceptance Criteria

1. WHEN the Extra_Savings_Modal opens, THE Extra_Savings_Modal SHALL display an amount input field, a goal selection dropdown, and a submit button.
2. THE Extra_Savings_Modal SHALL populate the goal selection dropdown with the names of all active, incomplete Goals belonging to the authenticated user.
3. WHEN the Extra_Savings_Modal opens and at least one active Goal exists, THE Extra_Savings_Modal SHALL pre-select the first Goal in the dropdown.
4. WHEN the user submits the Extra_Savings_Modal with an amount less than or equal to zero, THE Extra_Savings_Modal SHALL display the error message "Amount must be greater than zero." and SHALL NOT submit the form.
5. WHEN the user submits the Extra_Savings_Modal with no goal selected, THE Extra_Savings_Modal SHALL display the error message "Please select a goal." and SHALL NOT submit the form.
6. WHEN the user activates the modal close control or presses the Escape key, THE Extra_Savings_Modal SHALL close without submitting.

---

### Requirement 3: Add Savings API Endpoint

**User Story:** As a developer, I want a dedicated API endpoint to add extra savings to a goal, so that the frontend can apply manual contributions independently of the automatic monthly allocation.

#### Acceptance Criteria

1. THE Add_Savings_API SHALL accept HTTP POST requests at `/api/goals/{id}/add-savings/` from authenticated users only.
2. WHEN a POST request is received with a valid `amount` (a positive number) and the Goal identified by `{id}` belongs to the authenticated user, THE Add_Savings_API SHALL add the `amount` to the Goal's `saved_amount`.
3. WHEN adding the `amount` would cause `saved_amount` to exceed `target_amount`, THE Add_Savings_API SHALL cap `saved_amount` at `target_amount`.
4. WHEN `saved_amount` reaches `target_amount` after the addition, THE Add_Savings_API SHALL set the Goal's `is_active` field to `False`.
5. WHEN a POST request is received with an `amount` less than or equal to zero, THE Add_Savings_API SHALL return HTTP 400 with `{"error": "Amount must be greater than zero."}`.
6. WHEN a POST request references a Goal that does not belong to the authenticated user or does not exist, THE Add_Savings_API SHALL return HTTP 404 with `{"error": "Not found."}`.
7. WHEN a POST request is received from an unauthenticated user, THE Add_Savings_API SHALL return HTTP 302 redirecting to the login page.
8. WHEN the addition succeeds, THE Add_Savings_API SHALL return HTTP 200 with `{"success": true, "goal": <updated goal object>}`.

---

### Requirement 4: Savings Page Reflects Updated Goal After Submission

**User Story:** As a user, I want the savings page to reflect the updated goal progress immediately after I add extra savings, so that I can see the impact of my contribution without manually refreshing.

#### Acceptance Criteria

1. WHEN the Add_Savings_API returns a success response, THE Savings_Page SHALL update the affected Goal card's `saved_amount`, progress percentage, progress bar, and remaining amount without a full page reload.
2. WHEN the Add_Savings_API returns a success response and the Goal is now complete, THE Savings_Page SHALL update the Goal card to display the completion state (e.g., "🎉 Goal reached!" badge and completed styling).
3. IF the Add_Savings_API returns an error response, THEN THE Extra_Savings_Modal SHALL display the error message returned by the API and SHALL remain open.

---

### Requirement 5: Extra Row in This Month's Allocation Card

**User Story:** As a user, I want to see my manually added extra savings reflected in the "This Month's Allocation" card, so that I have a complete picture of all savings activity for the month.

#### Acceptance Criteria

1. WHEN the user successfully submits the Extra_Savings_Modal, THE Allocation_Card SHALL display an Extra_Row labelled "Extra" showing the total amount added via extra savings in the current session.
2. WHEN no extra savings have been added in the current session, THE Allocation_Card SHALL NOT display an Extra_Row.
3. WHEN multiple extra savings submissions are made in the same session, THE Allocation_Card SHALL accumulate the amounts and display the running total in the Extra_Row.
4. THE Extra_Row SHALL be visually distinct from the automatic allocation rows (e.g., using a different label style or accent colour) to indicate it represents a manual contribution.
