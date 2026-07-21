# Aslab Replacement Workflow Design

## Objective

Provide an auditable workflow for ending an assistant laboratory member's assignment before the practicum period ends and filling the same course slot with a replacement. The workflow must preserve historical activity, enforce the campus limit of two aslab slots per course, handle monthly honor reassignment, and require a directly nominated student to consent and complete the required registration data before receiving aslab access.

The feature uses the label **Ganti/Akhiri Masa Tugas**. Permanent deletion is not a replacement mechanism and remains limited to correcting unused records created by mistake.

## Business Rules

- A course has at most two active aslab slots in one practicum period.
- Replacing a person does not create a third slot. The replacement continues the old person's slot.
- Ending an assignment changes the old aslab to inactive.
- The old user's role returns to `mahasiswa` only when the user has no other active aslab assignment.
- An aslab who does not finish the period receives no aslab experience record for that assignment.
- Historical attendance, grading, reports, schedules already completed, and operational activity remain attributed to the person who performed them.
- Future schedules move to the replacement only after the replacement becomes active.
- A nominated student does not become an aslab merely because a laboran sent an offer.
- Every termination, offer, response, verification, activation, and honor reassignment is auditable.

## Monthly Honor Rules

Honor ownership is based on whole calendar months, with no daily prorating.

- The old aslab keeps honor for every month before the effective termination month.
- The effective termination month and all later months in the period belong to the replacement.
- This rule applies even when the replacement accepts and becomes active in a later month.
- Until a replacement becomes active, affected honor is held and must not be included as payable to the old aslab.
- When the replacement becomes active, held honor is assigned retroactively from the effective termination month.
- Existing paid or locked payment letters are never silently rewritten.
- If an affected honor entry is already locked in a payment letter, the workflow creates an explicit correction-required state for a laboran or authorized financial operator.
- The system retains the original recipient, final recipient, reassignment reason, actor, and timestamps.
- Reassignment must be idempotent so retries cannot duplicate honor or correction records.

Example: an aslab is terminated on October 15 and the replacement becomes active on November 5. January through September remain payable to the old aslab. October and later months are payable to the replacement.

## Recommended Domain Model

The existing `Asleb` record represents a person and currently has a unique NIM. It should not be overwritten to represent a different person. The replacement workflow adds assignment-level records around the existing person records.

### AslabSlot

Represents one of the maximum two positions for a course in a practicum period.

Suggested fields:

- practicum period;
- course;
- slot number, restricted to `1` or `2`;
- status: `active`, `vacant`, or `closed`;
- created and updated timestamps.

There must be a database uniqueness constraint on period, course, and slot number. Slot limits must not rely only on form validation.

### AslabAssignment

Represents one person's occupancy of a slot.

Suggested fields:

- slot;
- aslab/person;
- source registration when applicable;
- start date;
- end date;
- status: `pending`, `active`, `resigned`, `terminated`, `replaced`, `completed`, or `cancelled`;
- end reason category and required explanation;
- ended by;
- replacement assignment link;
- created and updated timestamps.

Only one assignment may be active in a slot. Historical assignments remain attached to that slot.

### AslabReplacement

Owns the replacement process and its audit state.

Suggested fields:

- slot and outgoing assignment;
- effective termination date;
- honor transfer month, derived from the termination date;
- replacement method: `direct_offer`, `limited_registration`, or `undecided`;
- workflow status;
- selected candidate and resulting assignment;
- offer deadline;
- termination and replacement actors;
- timestamps.

The transfer month should be stored for auditability but validated against the effective date.

### AslabOffer

Represents an offer to a registered student.

Suggested fields:

- replacement process;
- candidate user;
- status: `waiting`, `accepted_incomplete`, `submitted`, `verified`, `declined`, `expired`, or `cancelled`;
- response deadline;
- response and submission timestamps;
- decline reason, optional;
- verification actor, timestamp, and notes.

Only one live offer may exist for a replacement process. Previous declined, expired, or cancelled offers remain in history.

### LimitedReplacementOpening

Represents a targeted replacement registration rather than reopening regular period registration.

Suggested fields:

- replacement process;
- opening and closing timestamps;
- optional study program and cohort filters;
- optional candidate allowlist;
- additional requirements;
- status: `draft`, `open`, `closed`, or `filled`.

It always has a quota of one because it fills one existing slot.

## Ending an Assignment

Only a laboran with the existing laboratory operations permission may initiate the action.

The form requires:

- action type: resignation, dismissal, or another documented reason;
- explanation;
- effective termination date;
- replacement method;
- candidate and offer deadline when direct nomination is selected.

Before confirmation, the UI shows:

- the outgoing person and course slot;
- role and experience consequences;
- the last honor month retained by the old aslab;
- the first month reserved for a replacement;
- future schedules that will require reassignment;
- warnings for locked payment letters.

Confirmation is performed in a transaction. The system ends the outgoing assignment, marks the slot vacant, downgrades the user's role when appropriate, suppresses completion experience, holds affected honor, creates the replacement process, writes the audit event, and sends notifications.

The existing service that deactivates membership can be reused where its behavior matches these rules, but the new transaction service owns slot, honor, and replacement consistency.

## Direct Offer Workflow

1. A laboran searches registered student accounts by name or NIM.
2. The system validates account status and assignment eligibility.
3. The laboran sends an offer with a configurable deadline, defaulting to three days.
4. The replacement status becomes `waiting_for_consent`.
5. The student may accept or decline.
6. Accepting changes the offer to `accepted_incomplete`; it does not change the user's role.
7. The student completes the same required identity, academic, banking, and supporting data used by regular aslab registration.
8. Submitted data enters `waiting_for_verification`.
9. A laboran verifies or returns the submission for correction.
10. Approval creates and activates the assignment, changes the role when necessary, fills the slot, transfers future schedules, and releases held honor to the replacement.

An expired or declined offer allows the laboran to nominate another candidate or open limited registration. The system must prevent two candidates from accepting the same slot concurrently.

## Limited Registration Workflow

- A laboran opens registration for one specific vacant slot.
- The course and period are inherited from the replacement process and cannot be changed.
- The laboran sets a deadline and may restrict eligibility by study program, cohort, or candidate allowlist.
- Eligible students see a replacement-specific opening, separate from regular aslab registration.
- Applications reuse the regular data requirements where practical.
- The laboran selects one candidate; non-selected applications remain in history with a clear outcome.
- Selection still requires candidate consent and complete data. Selection is not immediate activation.
- Once one candidate is activated, the opening is filled and all other live applications close atomically.

## Workflow States

Replacement process states:

- `waiting_for_action`;
- `searching_candidate`;
- `waiting_for_consent`;
- `candidate_completing_data`;
- `waiting_for_verification`;
- `active`;
- `cancelled`.

Offer-level declined and expired states remain on the offer rather than ending the whole replacement process. The parent process returns to `waiting_for_action` or `searching_candidate` so another candidate can be selected.

State transitions occur through domain services, not direct view-level field updates. Invalid transitions return a user-facing validation error and write no partial changes.

## Schedule and Activity Handling

- Completed schedules and attendance are never moved to the replacement.
- Future schedules are transferred when the replacement assignment becomes active.
- Schedules occurring while the slot is vacant remain visibly unassigned.
- A laboran may assign a temporary operational substitute, but that person does not acquire the slot, role, experience, or honor.
- Reports and grades retain their original actor for audit purposes.
- Activation displays a preview of future schedules to be transferred.

## Experience Handling

- Ending an assignment before period completion suppresses experience creation for the outgoing aslab.
- The replacement receives experience only after completing the remaining period.
- The experience records the actual assignment start date and indicates that it was a replacement assignment.
- If a replacement is later terminated, that person also receives no completion experience and the same slot may begin another replacement process.
- A complete replacement chain remains queryable from the slot history.

## User Interface

### Laboran

The aslab list exposes **Ganti/Akhiri Masa Tugas** for active assignments. Hard delete is hidden or rejected when an aslab has related operational history.

A **Pergantian Aslab** dashboard section shows:

- course and slot;
- outgoing aslab;
- workflow status;
- current candidate;
- offer deadline;
- unassigned future schedules;
- held honor months;
- required payment corrections.

Laboran pages provide candidate search, offer creation, limited-opening management, submission verification, and an audit timeline.

### Student

A **Tawaran Aslab** page shows:

- course and period;
- expected start and remaining schedules;
- honor transfer month;
- response deadline;
- required data and documents;
- accept and decline actions.

After acceptance, the student can save the required form as a draft. Aslab navigation and permissions remain unavailable until final verification and activation.

## Notifications

Notifications are sent when:

- an assignment is ended;
- a direct offer is sent, nearing expiration, accepted, declined, or expired;
- candidate data is submitted, returned, approved, or rejected;
- limited registration opens or closes;
- a replacement becomes active;
- schedules and honor are transferred;
- a locked payment letter requires correction.

Notification failures must not roll back valid domain changes. They are logged and can be retried independently.

## Authorization and Audit

- Only authorized laboran users may terminate, nominate, open limited registration, verify, or activate.
- Students may respond only to their own live offers and edit only their own candidate submission.
- Audit entries include actor, action, previous state, new state, affected slot, timestamp, and reason.
- Sensitive banking and identity fields follow existing access restrictions and are not duplicated into audit payloads.
- Concurrency-sensitive operations use database transactions and row locks for the slot, live offer, and affected honor records.

## Compatibility and Migration

Existing active `Asleb` records need a data migration into slots and active assignments. The migration groups records by practicum period and course and assigns deterministic slot numbers. Ambiguous legacy records must be reported for manual review rather than guessed silently.

Existing historical and inactive records remain intact. The new assignment layer references them without rewriting old attendance, honor, or report ownership.

The current manual membership-ending endpoint should delegate to the new workflow service. Existing hard-delete behavior must be guarded so related honor or operational history cannot be cascaded accidentally.

## Failure Handling

- Repeated form submission cannot create multiple replacement processes or assignments.
- Activation fails cleanly when the slot was filled by another transaction.
- An offer cannot be accepted after expiration or cancellation.
- A candidate who becomes ineligible before verification cannot be activated.
- Honor transfer failure prevents activation from committing, because financial ownership must match the active replacement.
- Notification failure is recorded but does not invalidate activation.
- Locked honor produces a correction task instead of destructive modification.

## Testing Strategy

Model and service tests cover:

- the two-slot database constraint;
- exactly one active assignment per slot;
- role downgrade only when no other active assignment exists;
- no experience for early termination;
- experience for a replacement who completes the period;
- month-based honor ownership, including cross-month delayed activation;
- held honor release and locked-payment correction handling;
- offer acceptance, decline, expiration, and resubmission protection;
- concurrent offer acceptance and concurrent activation;
- future-only schedule transfer;
- preservation of historical attendance, grades, reports, and honor;
- authorization for laboran and student actions;
- notification creation;
- migration behavior for representative legacy records.

Integration tests cover both direct nomination and limited registration from termination through activation. Browser-level tests verify the confirmation summary, student consent and data completion, laboran verification, dashboard status, and user role transition.

## Acceptance Criteria

- A laboran can end an active assignment without deleting historical data.
- The outgoing user returns to `mahasiswa` when they have no other active assignment.
- The outgoing aslab receives no completion experience.
- The system preserves a maximum of two slots per course and period across any number of replacements.
- A directly nominated student must consent, complete required data, and pass laboran verification before activation.
- The outgoing aslab keeps honor for earlier months, while the replacement receives the effective month and later months.
- Delayed activation applies held honor retroactively to the replacement.
- Completed activity remains with the old aslab and only future schedules transfer.
- Every state change and financial reassignment is auditable.
