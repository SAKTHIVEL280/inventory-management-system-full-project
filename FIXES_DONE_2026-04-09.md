# Fixes Done Today - 2026-04-09

## Backend fixes completed

- Sales Order module deactivated from active workflow and endpoints now return module removed response.
- Sales Invoice due date manual override enabled during create and update.
- Quotation and Invoice email sending implemented with SMTP delivery and local outbox fallback.
- Sales MFG and EXP date guards tightened to reject invalid date ranges.
- GRN validation updated: MFG must be past date, EXP must be future date.
- GRN create and update now persist resolved PO line linkage when product-based mapping is used.
- GRN partial receipt status calculation corrected via reliable PO line mapping.
- Payables status derivation improved for advance and full payment cleared states.
- Payables API responses include PO and GRN metadata needed for correct UI display.
- Final payables gap closed: GRN Value is now exposed in payables list response for closure validation.
- Customer payment guard enforced: payment blocked when there is no open invoice.
- Customer billing defaults now auto-fill from company profile when values are missing.
- Supplier state_code input contract cleaned up and state code derived from state logic.
- Dashboard cash-in-flow filtering tightened to exclude non-receivable statuses.
- Migration defaults hardened for customization_options table to support clean DB rebuilds.

## Frontend fixes completed

- Sales Orders route/page removed from active app navigation and redirects aligned.
- Sales client API/types cleaned of Sales Order methods and interfaces.
- Invoice form supports editable due date override behavior.
- Invoice line item validations added for MFG and EXP date rules.
- GRN form date validations aligned with backend rules.
- Payables page status handling and PO/GRN display behavior improved.
- Customer page updated for billing defaults and hook stability improvements.
- Supplier page updated to remove state_code field usage and improve hook stability.
- Product and inventory pages updated to satisfy lint and hook dependency rules.
- Lint warning fixes completed across affected pages.

## Validation completed today

- Backend regression suite: backend/regression_full_cycle.py -> 13/13 pass.
- Pending high-risk targeted checks -> 5/5 pass.
- Changed and blank targeted checks -> 13/13 pass.
- Full unresolved closure suite: backend/full_non_pass_closure_suite.py -> 85/85 pass (100%).
- Frontend lint -> pass (only informational TypeScript parser support warning).
- Frontend build -> pass.
- PostgreSQL checks with postgres/root on ims_db -> pass.
- Runtime checks -> backend on 8001 is healthy, frontend on 3001 is reachable.

## Completion verdict

- High-priority and previously failing implementation issues are completed and revalidated.
- Every single thing completed for the attached unresolved/non-pass scope: yes (85/85 passed in full closure suite).
- Engineering fix scope for active failures and high-risk pending/changed items: completed.
- Full 173-row manual UI sign-off remains a QA tracking activity; engineering closure for unresolved rows is complete.
