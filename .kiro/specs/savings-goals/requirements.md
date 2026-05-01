# Requirements Document

## Introduction

The Savings Goals feature extends SpendWise with a dedicated savings management system. It splits savings into two distinct concepts: **Monthly Savings** (auto-calculated from income minus expenses for the current month, already surfaced as `total_saved` on the dashboard) and **Target Savings Goals** (user-created named goals with a target amount and tracked progress). The feature adds a new `/savings/` page, a sidebar navigation icon, and an updated dashboard widget that summarises both savings types side by side.

The app is built with Django 6, SQLite/MySQL, and vanilla JS with no frontend frameworks. Existing models are `UserProfile` (salary, target_savings) and `Transaction`.

---

## Glossary

- **Savings_Page**: The new `/savings/` page that lists and manages all savings goals for the authenticated user.
- **Goal**: A user-created named savings target, stored as a `SavingsGoal` model instance, with a name, target amount, and a running saved amount.
- **Monthly_Savings**: The auto-calculated value `total_income − total_expense` for the current calendar month, derived from `Transaction` records. Already computed as `total_saved` in the dashboard view.
- **Dashboard**: The existing `/dashboard/` page rendered by the `dashboard` view.
- **Dashboard_Widget**: The savings summary section in the right panel of the Dashboard that shows both Monthly Savings and a Target Savings Goals summary.
- **Sidebar**: The vertical icon navigation bar present on all authenticated pages.
- **Goal_Modal**: The modal dialog used to create or edit a Goal on the Savings_Page.
- **Contribution_Modal**: The modal dialog used to add money toward a Goal's saved amount.
- **Progress_Ring**: An SVG circular progress indicator showing the percentage of a Goal's target that has been saved.
- **Progress_Bar**: A horizontal bar showing the same percentage as the Progress_Ring.
- **SpendWise**: The Django web application being extended.
- **Authenticated_User**: A Django `User` instance with an active session (i.e., `request.user.is_authenticated` is `True`).

---

## Requirements

### Requirement 1: Savings Goal Data Model

**User Story:** As a developer, I want a `SavingsGoal` model, so that named savings goals can be persisted per user with a target amount and a running saved amount.

#### Acceptance Criteria

1. THE `SavingsGoal` model SHALL have a `ForeignKey` to `django.contrib.auth.models.User` with `on_delete=CASCADE`.
2. THE `SavingsGoal` model SHALL have a `name` field of type `CharField` with a maximum length of 120 characters.
3. THE `SavingsGoal` model SHALL have a `target_amount` field of type `DecimalField` with a maximum of 12 digits and 2 decimal places.
4. THE `SavingsGoal` model SHALL have a `saved_amount` field of type `DecimalField` with a maximum of 12 digits and 2 decimal places, defaulting to `0.00`.
5. THE `SavingsGoal` model SHALL have a `created_at` field of type `DateTimeField` with `auto_now_add=True`.
6. THE `SavingsGoal` model SHALL be registered in `login/admin.py` so that it is accessible via the Django admin interface.
7. WHEN a `SavingsGoal` is deleted, THE `SavingsGoal` model SHALL cascade-delete all associated records without leaving orphaned data.

---

### Requirement 2: Savings Goals Page

**User Story:** As an Authenticated_User, I want a dedicated Savings_Page at `/savings/`, so that I can view and manage all my savings goals in one place.

#### Acceptance Criteria

1. WHEN an Authenticated_User navigates to `/savings/`, THE Savings_Page SHALL render a list of all Goals belonging to that user.
2. WHEN an Authenticated_User navigates to `/savings/` and has no Goals, THE Savings_Page SHALL display an empty-state message prompting the user to create their first goal.
3. WHEN an unauthenticated user navigates to `/savings/`, THE Savings_Page SHALL redirect the user to `/login/`.
4. THE Savings_Page SHALL display each Goal as a card containing: the goal name, the saved amount, the target amount, a Progress_Ring, and a Progress_Bar.
5. THE Savings_Page SHALL display an "Add Goal" button that opens the Goal_Modal when clicked.
6. THE Savings_Page SHALL include the Sidebar with the savings icon marked as active.
7. THE Savings_Page SHALL apply the same Apple-inspired glass-card visual style defined in `dashboard.css` (CSS variables, `--glass`, `--radius-lg`, `--shadow-md`, etc.).

---

### Requirement 3: Create and Edit Savings Goal

**User Story:** As an Authenticated_User, I want to create and edit named savings goals, so that I can track progress toward specific financial targets.

#### Acceptance Criteria

1. WHEN an Authenticated_User submits the Goal_Modal with a valid name and target amount, THE Savings_Page SHALL create a new Goal and display it in the goal list without a full page reload.
2. WHEN an Authenticated_User submits the Goal_Modal with an empty name, THE Goal_Modal SHALL display an inline validation error and SHALL NOT submit the form.
3. WHEN an Authenticated_User submits the Goal_Modal with a target amount of zero or less, THE Goal_Modal SHALL display an inline validation error and SHALL NOT submit the form.
4. WHEN an Authenticated_User clicks an edit action on an existing Goal card, THE Goal_Modal SHALL open pre-populated with the goal's current name and target amount.
5. WHEN an Authenticated_User submits the Goal_Modal with updated values for an existing Goal, THE Savings_Page SHALL update the Goal card in place without a full page reload.
6. THE Goal_Modal SHALL be dismissible by clicking outside the modal overlay or pressing the Escape key.

---

### Requirement 4: Delete Savings Goal

**User Story:** As an Authenticated_User, I want to delete a savings goal, so that I can remove goals I no longer need.

#### Acceptance Criteria

1. WHEN an Authenticated_User confirms deletion of a Goal, THE Savings_Page SHALL remove the Goal from the database and remove the Goal card from the list without a full page reload.
2. WHEN an Authenticated_User triggers deletion of a Goal, THE Savings_Page SHALL display a confirmation prompt before permanently deleting the Goal.
3. IF a Goal deletion request is made for a Goal that does not belong to the Authenticated_User, THEN THE API SHALL return an HTTP 404 response and SHALL NOT delete any data.

---

### Requirement 5: Add Contribution to a Goal

**User Story:** As an Authenticated_User, I want to add money toward a savings goal, so that I can track how much I have saved against each target.

#### Acceptance Criteria

1. WHEN an Authenticated_User submits the Contribution_Modal with a valid positive amount, THE Savings_Page SHALL increment the Goal's `saved_amount` by that amount and update the Goal card's Progress_Ring and Progress_Bar without a full page reload.
2. WHEN an Authenticated_User submits the Contribution_Modal with an amount of zero or less, THE Contribution_Modal SHALL display an inline validation error and SHALL NOT submit the form.
3. WHEN the `saved_amount` of a Goal equals or exceeds the `target_amount`, THE Savings_Page SHALL display a visual completion indicator (e.g., a "Goal reached!" badge) on the Goal card.
4. THE Contribution_Modal SHALL display the Goal name and current saved amount so the user has context before contributing.
5. IF a contribution request is made for a Goal that does not belong to the Authenticated_User, THEN THE API SHALL return an HTTP 404 response and SHALL NOT modify any data.

---

### Requirement 6: Goal Progress Visualisation

**User Story:** As an Authenticated_User, I want to see a progress ring and progress bar for each goal, so that I can quickly understand how close I am to reaching each target.

#### Acceptance Criteria

1. THE Progress_Ring SHALL be an SVG circle rendered with a filled arc proportional to `(saved_amount / target_amount) × 100`, capped at 100%.
2. THE Progress_Ring SHALL display the percentage value as a centred label inside the ring.
3. THE Progress_Bar SHALL be a horizontal bar whose filled width is proportional to `(saved_amount / target_amount) × 100`, capped at 100%.
4. WHEN `target_amount` is greater than zero, THE Progress_Ring and Progress_Bar SHALL reflect the correct percentage without requiring a page reload after a contribution is added.
5. WHEN `saved_amount` is zero, THE Progress_Ring SHALL render an empty track and SHALL display "0%" as the centred label.

---

### Requirement 7: Sidebar Navigation Icon

**User Story:** As an Authenticated_User, I want a savings icon in the Sidebar, so that I can navigate to the Savings_Page from any page in the app.

#### Acceptance Criteria

1. THE Sidebar SHALL include a savings icon link that navigates to `/savings/`.
2. WHEN the Authenticated_User is on the Savings_Page, THE Sidebar SHALL render the savings icon with the `active` CSS class applied.
3. WHEN the Authenticated_User is on any page other than the Savings_Page, THE Sidebar SHALL render the savings icon without the `active` CSS class.
4. THE savings icon SHALL have an `aria-label` attribute with the value `"Savings Goals"` for accessibility.
5. THE Sidebar savings icon SHALL be consistent in size and style with the existing nav icons defined in `dashboard.css` (42×42 px, `--radius-sm` border-radius, `--muted` default colour, `--accent` active colour).

---

### Requirement 8: Dashboard Widget — Savings Summary

**User Story:** As an Authenticated_User, I want the Dashboard to show both my Monthly Savings and a summary of my Target Savings Goals, so that I have a complete savings overview without leaving the Dashboard.

#### Acceptance Criteria

1. THE Dashboard_Widget SHALL display the Monthly_Savings value (income minus expenses for the current month) as a labelled card.
2. THE Dashboard_Widget SHALL display the total number of active Goals and the total `saved_amount` across all Goals as a labelled summary.
3. THE Dashboard_Widget SHALL include a link to the Savings_Page.
4. WHEN an Authenticated_User has no Goals, THE Dashboard_Widget SHALL display a "No goals yet" placeholder in the goals summary area.
5. WHEN the Monthly_Savings value is negative (expenses exceed income), THE Dashboard_Widget SHALL display the value in the negative colour (`--negative: #ff453a`) defined in `dashboard.css`.
6. WHEN the Monthly_Savings value is zero or positive, THE Dashboard_Widget SHALL display the value in the positive colour (`--positive: #30d158`) defined in `dashboard.css`.

---

### Requirement 9: JSON API Endpoints

**User Story:** As a developer, I want JSON API endpoints for savings goal CRUD and contributions, so that the Savings_Page can update dynamically without full page reloads.

#### Acceptance Criteria

1. THE API SHALL expose a `POST /savings/api/goals/` endpoint that creates a new Goal for the Authenticated_User and returns the created Goal as JSON.
2. THE API SHALL expose a `PUT /savings/api/goals/<id>/` endpoint that updates the name and target amount of an existing Goal owned by the Authenticated_User and returns the updated Goal as JSON.
3. THE API SHALL expose a `DELETE /savings/api/goals/<id>/` endpoint that deletes a Goal owned by the Authenticated_User and returns `{"success": true}`.
4. THE API SHALL expose a `POST /savings/api/goals/<id>/contribute/` endpoint that increments `saved_amount` by the provided amount for a Goal owned by the Authenticated_User and returns the updated Goal as JSON including the new `saved_amount` and computed `progress_pct`.
5. IF any API endpoint receives a request from an unauthenticated user, THEN THE API SHALL return an HTTP 401 response.
6. IF any API endpoint receives invalid or missing required fields, THEN THE API SHALL return an HTTP 400 response with a descriptive `error` field in the JSON body.
7. THE API SHALL use Django's CSRF protection; all mutating endpoints SHALL require a valid `X-CSRFToken` header.
