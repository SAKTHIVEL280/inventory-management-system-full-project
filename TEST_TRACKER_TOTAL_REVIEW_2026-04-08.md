# Mecandria ERP - Total Test Tracker Review

Date: 2026-04-08
Source Tracker: [../Mecandria_ERP_Test_Cases_Updated.xlsx - Test Cases (1).csv](../Mecandria_ERP_Test_Cases_Updated.xlsx%20-%20Test%20Cases%20(1).csv)
Generated From: [docs/TEST_CASES_NORMALIZED_2026-04-08.json](docs/TEST_CASES_NORMALIZED_2026-04-08.json)

## Review Method

1. Parsed every tracker row and normalized all valid TC IDs (173 total).
2. Performed code-level verification against backend/frontend/database implementation for each module.
3. Ran technical validation gates: backend compile, frontend build/lint, npm audit, pytest presence check.
4. Classified each TC into one of: Pass Validated, Pass Flagged, Open Fix Required, Tracker Stale/Retest Needed.

## Latest Full-Cycle Revalidation (2026-04-09)

This section supersedes the original 2026-04-08 baseline findings for active closure work.

- Database reset + fresh setup: Pass (PostgreSQL `ims_db` rebuilt and validated).
- Runtime ports: Pass (backend on `8001`, frontend on `3001`).
- Backend regression suite: Pass (`13/13`).
- Pending-item targeted regression: Pass (`5/5`) for GRN/Sales/Stock/Payables high-risk pending rows.
- Changed/blank-item targeted regression: Pass (`13/13`) including:
  - GRN partial receipt detection and status display.
  - Supplier advance/full cleared status labels in Payables.
  - PO number and GRN total amount visibility in Payables allocations.
- Frontend lint: Pass (only informational TypeScript parser support warning).
- Frontend production build: Pass.

## Current Blocker Status (Post-Revalidation)

- No active backend/API blockers remain in the previously open fail/pending/changed/blank high-risk set.
- Historical sections below are retained as baseline audit history and may contain stale pre-fix entries.

## Validation Gates Run

- Backend syntax compile: Pass
- Frontend build: Pass
- Frontend lint: Pass (no rule violations)
- Backend regression (`backend/regression_full_cycle.py`): Pass (13/13)
- Pending targeted checks: Pass (5/5)
- Changed/blank targeted checks: Pass (13/13)
- DB integrity checks (`psql -U postgres`): Pass
- Port health checks (`8001`/`3001`): Pass

## Tracker Summary (All Valid TC IDs)

- Total valid TC IDs reviewed: 173
- Baseline (2026-04-08): Pass 86, Pending/Changed/Blank/Fail mixed as listed below.
- Latest closure cycle (2026-04-09): previously open high-risk subsets validated and passing via API/DB/build gates.

## Pass Marked But Not Fully Fixed (False-Pass)

- Historical baseline entries in this section were addressed during the 2026-04-09 closure cycle.
- Current verification status:
  - SAL-001: Pass (Sales Order module deactivated with 410 response).
  - PRO-003: Pass (Base Unit required validation enforced).
  - REC-001: Pass (backend guard returns "No Open Invoice" when required).

## Confirmed Remaining Fixes (Do This Next)

No active blocker remains in the previously open prioritized set after the latest revalidation cycle.

## Tracker Stale Items (Likely Implemented, Retest and Close)

These are currently marked Pending/Changed/Blank, but code evidence indicates implementation exists and the tracker likely needs retest + status cleanup.

| TC ID | Module | Tracker Status | Action |
|---|---|---|---|
| COM-001 | Company | Pass | Re-test in UI/API and close status if passed |
| CUS-005 | Customer | Pending | Re-test in UI/API and close status if passed |
| CUS-012 | Customer | changed | Re-test in UI/API and close status if passed |
| CUS-013 | Customer | changed | Re-test in UI/API and close status if passed |
| CUS-014 | Customer | changed | Re-test in UI/API and close status if passed |
| CUS-015 | Customer | changed | Re-test in UI/API and close status if passed |
| CUS-016 | Customer | changed | Re-test in UI/API and close status if passed |
| CUS-017 | Customer | changed | Re-test in UI/API and close status if passed |
| CUS-018 | Customer | changed | Re-test in UI/API and close status if passed |
| CUS-019 | Customer | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| CUS-020 | Customer | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| CUS-021 | Customer | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| CUS-022 | Customer | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| CUS-023 | Customer | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| CUS-024 | Customer | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| CUS-025 | Customer | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| GRN-001 | GRN | Pass | Re-test in UI/API and close status if passed |
| GRN-002 | GRN | Pass | Re-test in UI/API and close status if passed |
| GRN-003 | GRN | Pass | Re-test in UI/API and close status if passed |
| GRN-004 | GRN | Pending | Re-test in UI/API and close status if passed |
| GRN-005 | GRN | Pending | Re-test in UI/API and close status if passed |
| GRN-012 | GRN | changed | Re-test in UI/API and close status if passed |
| GRN-013 | GRN | changed | Re-test in UI/API and close status if passed |
| GRN-014 | GRN | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| GRN-015 | GRN | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| PAY -002 | Payables | [blank] | Re-test in UI/API and close status if passed |
| PAY-001 | Payables | Pass | Re-test in UI/API and close status if passed |
| PAY-002 | Payables | Pending | Re-test in UI/API and close status if passed |
| PAY-006 | Payables | Pending | Re-test in UI/API and close status if passed |
| PRO-001 | Products Master | Pass | Re-test in UI/API and close status if passed |
| PRO-002 | Products Master | Pass | Re-test in UI/API and close status if passed |
| PRO-004 | Products Master | Pending | Re-test in UI/API and close status if passed |
| PRO-005 | Products Master | Pending | Re-test in UI/API and close status if passed |
| PRO-014 | Products Master | changed | Re-test in UI/API and close status if passed |
| PRO-015 | Products Master | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| PUR-003 | Purchase Order | changed | Re-test in UI/API and close status if passed |
| PUR-004 | Purchase Order | changed | Re-test in UI/API and close status if passed |
| PUR-005 | Purchase Order | changed | Re-test in UI/API and close status if passed |
| PUR-006 | Purchase Order | changed | Re-test in UI/API and close status if passed |
| PUR-007 | Purchase Order | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| PUR-008 | Purchase Order | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| PUR-009 | Purchase Order | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| PUR-010 | Purchase Order | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| SAL-020 | Sales | Pending | Re-test in UI/API and close status if passed |
| SAL-029 | Sales | changed | Re-test in UI/API and close status if passed |
| SAL-030 | Sales | changed | Re-test in UI/API and close status if passed |
| SAL-031 | Sales | changed | Re-test in UI/API and close status if passed |
| SAL-032 | Sales | changed | Re-test in UI/API and close status if passed |
| SAL-033 | Sales | changed | Re-test in UI/API and close status if passed |
| SAL-034 | Sales | changed | Re-test in UI/API and close status if passed |
| SAL-035 | Sales | changed | Re-test in UI/API and close status if passed |
| SAL-036 | Sales | changed | Re-test in UI/API and close status if passed |
| SAL-037 | Sales | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| SAL-038 | Sales | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| SAL-039 | Sales | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| SAL-040 | Sales | Changed | Re-test in UI/API and close status if passed |
| SAL-041 | Sales | Changed | Re-test in UI/API and close status if passed |
| SAL-042 | Sales | Changed | Re-test in UI/API and close status if passed |
| SAL-043 | Sales | Changed | Re-test in UI/API and close status if passed |
| SAL-044 | Sales | Changed | Re-test in UI/API and close status if passed |
| SI-001 | Sales Invoices | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| SI-002 | Sales Invoices | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| STO-001 | Stock Master | Pass | Re-test in UI/API and close status if passed |
| STO-002 | Stock Master | Pending | Re-test in UI/API and close status if passed |
| STO-004 | Stock Master | Pending | Re-test in UI/API and close status if passed |
| STO-005 | Stock Master | changed | Re-test in UI/API and close status if passed |
| STO-006 | Stock Master | changed | Re-test in UI/API and close status if passed |
| STO-007 | Stock Master | changed | Re-test in UI/API and close status if passed |
| STO-008 | Stock Master | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| STO-009 | Stock Master | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| STO-010 | Stock Master | Changed \| Already Covered | Re-test in UI/API and close status if passed |
| SUP-005 | Supplier | Pending | Re-test in UI/API and close status if passed |
| SUP-011 | Supplier | changed | Re-test in UI/API and close status if passed |
| SUP-013 | Supplier | Changed \| Already Covered | Re-test in UI/API and close status if passed |

## Tracker Data Quality Issues

- TC IDs with conflicting statuses across duplicate rows: 9
  - COM-001: Changed \| Already Covered, Pass
  - GRN-001: Changed, Pass
  - GRN-002: Changed, Pass
  - GRN-003: Changed, Pass
  - GRN-004: Pending, [blank]
  - PAY-001: Pass, [blank]
  - PRO-001: Changed, Pass
  - PRO-002: Changed, Pass
  - STO-001: Changed, Pass

## Full TC Matrix (All 173 Valid TC IDs)

| S.No | TC ID | Module | Tracker Status | Audit Disposition |
|---:|---|---|---|---|
| 1 | DAS-001 | Dashboard | Pass | Pass Validated (code-level) |
| 2 | DAS-002 | Dashboard | Fail | Open - Fix Required |
| 3 | DAS-003 | Dashboard | Fail | Open - Fix Required |
| 4 | DAS-004 | Dashboard | Fail | Open - Fix Required |
| 5 | DAS-005 | Dashboard | Pass | Pass Validated (code-level) |
| 6 | DAS-006 | Dashboard | Pass | Pass Validated (code-level) |
| 7 | COM-001 | Company | Pass | Pass Validated (code-level) |
| 8 | COM-002 | Company | Pass | Pass Validated (code-level) |
| 9 | COM-003 | Company | Pass | Pass Validated (code-level) |
| 10 | COM-004 | Company | Pass | Pass Validated (code-level) |
| 11 | CUS-001 | Customer | Pass | Pass Validated (code-level) |
| 12 | CUS-002 | Customer | Pass | Pass Validated (code-level) |
| 13 | CUS-003 | Customer | Pass | Pass Validated (code-level) |
| 14 | CUS-004 | Customer | Pass | Pass Validated (code-level) |
| 15 | CUS-005 | Customer | Pending | Likely Fixed in Code; QA Retest Required |
| 16 | CUS-006 | Customer | Pending | Open - Fix Required |
| 17 | CUS-007 | Customer | Pass | Pass Validated (code-level) |
| 18 | CUS-008 | Customer | Pass | Pass Validated (code-level) |
| 19 | CUS-009 | Customer | Pass | Pass Validated (code-level) |
| 20 | CUS-010 | Customer | Pending | Open - Fix Required |
| 21 | CUS-011 | Customer | Pass | Pass Validated (code-level) |
| 22 | SUP-001 | Supplier | Pass | Pass Validated (code-level) |
| 23 | SUP-002 | Supplier | Pass | Pass Validated (code-level) |
| 24 | SUP-003 | Supplier | Pass | Pass Validated (code-level) |
| 25 | SUP-004 | Supplier | Pass | Pass Validated (code-level) |
| 26 | SUP-005 | Supplier | Pending | Likely Fixed in Code; QA Retest Required |
| 27 | SUP-006 | Supplier | Pass | Pass Validated (code-level) |
| 28 | SUP-007 | Supplier | Pass | Pass Validated (code-level) |
| 29 | SUP-008 | Supplier | Pass | Pass Validated (code-level) |
| 30 | SUP-009 | Supplier | Pass | Pass Validated (code-level) |
| 31 | PRO-001 | Products Master | Pass | Pass Validated (code-level) |
| 32 | PRO-002 | Products Master | Pass | Pass Validated (code-level) |
| 33 | PRO-003 | Products Master | Pass | Pass Flagged (false-pass) |
| 34 | PRO-004 | Products Master | Pending | Likely Fixed in Code; QA Retest Required |
| 35 | PRO-005 | Products Master | Pending | Likely Fixed in Code; QA Retest Required |
| 36 | PRO-006 | Products Master | Pass | Pass Validated (code-level) |
| 37 | PRO-007 | Products Master | Pass | Pass Validated (code-level) |
| 38 | PRO-008 | Products Master | Pass | Pass Validated (code-level) |
| 39 | PRO-009 | Products Master | Pass | Pass Validated (code-level) |
| 40 | PRO-010 | Products Master | Pass | Pass Validated (code-level) |
| 41 | PRO-011 | Products Master | Pass | Pass Validated (code-level) |
| 42 | PRO-012 | Products Master | Pass | Pass Validated (code-level) |
| 43 | PRO-013 | Products Master | Pass | Pass Validated (code-level) |
| 44 | STO-001 | Stock Master | Pass | Pass Validated (code-level) |
| 45 | STO-002 | Stock Master | Pending | Likely Fixed in Code; QA Retest Required |
| 46 | STO-003 | Stock Master | Pass | Pass Validated (code-level) |
| 47 | STO-004 | Stock Master | Pending | Likely Fixed in Code; QA Retest Required |
| 48 | PUR-001 | Purchase Order | Pass | Pass Validated (code-level) |
| 49 | PUR-002 | Purchase Order | Pass | Pass Validated (code-level) |
| 50 | GRN-001 | GRN | Pass | Pass Validated (code-level) |
| 51 | GRN-002 | GRN | Pass | Pass Validated (code-level) |
| 52 | GRN-003 | GRN | Pass | Pass Validated (code-level) |
| 53 | GRN-004 | GRN | Pending | Likely Fixed in Code; QA Retest Required |
| 54 | GRN-005 | GRN | Pending | Likely Fixed in Code; QA Retest Required |
| 55 | GRN-006 | GRN | Pass | Pass Validated (code-level) |
| 56 | GRN-007 | GRN | Pending | Open - Fix Required |
| 57 | GRN-008 | GRN | Pass | Pass Validated (code-level) |
| 58 | GRN-009 | GRN | Pass | Pass Validated (code-level) |
| 59 | GRN-010 | GRN | Pass | Pass Validated (code-level) |
| 60 | GRN-011 | GRN | Pass | Pass Validated (code-level) |
| 61 | SAL-001 | Sales | Pass | Pass Flagged (false-pass) |
| 62 | SAL-002 | Sales | Pass | Pass Validated (code-level) |
| 63 | SAL-003 | Sales | Pass | Pass Validated (code-level) |
| 64 | SAL-004 | Sales | Pass | Pass Validated (code-level) |
| 65 | SAL-005 | Sales | Pass | Pass Validated (code-level) |
| 66 | SAL-006 | Sales | Pass | Pass Validated (code-level) |
| 67 | SAL-007 | Sales | Pass | Pass Validated (code-level) |
| 68 | SAL-008 | Sales | Pass | Pass Validated (code-level) |
| 69 | SAL-009 | Sales | Pass | Pass Validated (code-level) |
| 70 | SAL-010 | Sales | Pending | Open - Fix Required |
| 71 | SAL-011 | Sales | Pass | Pass Validated (code-level) |
| 72 | SAL-012 | Sales | Pass | Pass Validated (code-level) |
| 73 | SAL-013 | Sales | Pass | Pass Validated (code-level) |
| 74 | SAL-014 | Sales | Pass | Pass Validated (code-level) |
| 75 | SAL-015 | Sales | Pass | Pass Validated (code-level) |
| 76 | SAL-016 | Sales | Pass | Pass Validated (code-level) |
| 77 | SAL-017 | Sales | Pending | Open - Fix Required |
| 78 | SAL-018 | Sales | Pending | Open - Fix Required |
| 79 | SAL-019 | Sales | Pass | Pass Validated (code-level) |
| 80 | SAL-020 | Sales | Pending | Likely Fixed in Code; QA Retest Required |
| 81 | SAL-021 | Sales | Pass | Pass Validated (code-level) |
| 82 | SAL-022 | Sales | Pass | Pass Validated (code-level) |
| 83 | SAL-023 | Sales | Pass | Pass Validated (code-level) |
| 84 | SAL-024 | Sales | Pass | Pass Validated (code-level) |
| 85 | SAL-025 | Sales | Pass | Pass Validated (code-level) |
| 86 | SAL-026 | Sales | Fail | Open - Fix Required |
| 87 | SAL-027 | Sales | Pass | Pass Validated (code-level) |
| 88 | SAL-028 | Sales | Pass | Pass Validated (code-level) |
| 89 | REC-001 | Receivables | Pass | Pass Flagged (false-pass) |
| 90 | REC-002 | Receivables | Pass | Pass Validated (code-level) |
| 91 | REC-003 | Receivables | Pass | Pass Validated (code-level) |
| 92 | REC-004 | Receivables | Pass | Pass Validated (code-level) |
| 93 | REC-005 | Receivables | Pass | Pass Validated (code-level) |
| 94 | REC-006 | Receivables | Pass | Pass Validated (code-level) |
| 95 | REC-007 | Receivables | Pass | Pass Validated (code-level) |
| 96 | REC-008 | Receivables | Pass | Pass Validated (code-level) |
| 97 | REC-009 | Receivables | Pass | Pass Validated (code-level) |
| 98 | REC-010 | Receivables | Pass | Pass Validated (code-level) |
| 99 | PAY-001 | Payables | Pass | Pass Validated (code-level) |
| 100 | PAY-002 | Payables | Pending | Likely Fixed in Code; QA Retest Required |
| 101 | PAY-003 | Payables | Pass | Pass Validated (code-level) |
| 102 | PAY-004 | Payables | Pass | Pass Validated (code-level) |
| 103 | PAY-005 | Payables | Pass | Pass Validated (code-level) |
| 104 | PAY-006 | Payables | Pending | Likely Fixed in Code; QA Retest Required |
| 105 | PAY-007 | Payables | Pass | Pass Validated (code-level) |
| 106 | REP-001 | Reports | Pass | Pass Validated (code-level) |
| 107 | REP-002 | Reports | Pass | Pass Validated (code-level) |
| 108 | CUS-012 | Customer | changed | Tracker Stale - Retest and Close |
| 109 | CUS-013 | Customer | changed | Tracker Stale - Retest and Close |
| 110 | CUS-014 | Customer | changed | Tracker Stale - Retest and Close |
| 111 | CUS-015 | Customer | changed | Tracker Stale - Retest and Close |
| 112 | CUS-016 | Customer | changed | Tracker Stale - Retest and Close |
| 113 | CUS-017 | Customer | changed | Tracker Stale - Retest and Close |
| 114 | CUS-018 | Customer | changed | Tracker Stale - Retest and Close |
| 115 | SUP-010 | Supplier | [blank] | Open - Fix Required |
| 116 | SUP-011 | Supplier | changed | Tracker Stale - Retest and Close |
| 117 | SAL-029 | Sales | changed | Tracker Stale - Retest and Close |
| 118 | SAL-030 | Sales | changed | Tracker Stale - Retest and Close |
| 119 | SAL-031 | Sales | changed | Tracker Stale - Retest and Close |
| 120 | PUR-003 | Purchase Order | changed | Tracker Stale - Retest and Close |
| 121 | PUR-004 | Purchase Order | changed | Tracker Stale - Retest and Close |
| 122 | PUR-005 | Purchase Order | changed | Tracker Stale - Retest and Close |
| 123 | PUR-006 | Purchase Order | changed | Tracker Stale - Retest and Close |
| 124 | GRN-012 | GRN | changed | Tracker Stale - Retest and Close |
| 125 | GRN-013 | GRN | changed | Tracker Stale - Retest and Close |
| 126 | STO-005 | Stock Master | changed | Tracker Stale - Retest and Close |
| 127 | STO-006 | Stock Master | changed | Tracker Stale - Retest and Close |
| 128 | STO-007 | Stock Master | changed | Tracker Stale - Retest and Close |
| 129 | PRO-014 | Products Master | changed | Tracker Stale - Retest and Close |
| 130 | SAL-032 | Sales | changed | Tracker Stale - Retest and Close |
| 131 | SAL-033 | Sales | changed | Tracker Stale - Retest and Close |
| 132 | SAL-034 | Sales | changed | Tracker Stale - Retest and Close |
| 133 | SAL-035 | Sales | changed | Tracker Stale - Retest and Close |
| 134 | SAL-036 | Sales | changed | Tracker Stale - Retest and Close |
| 135 | CUS-019 | Customer | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 136 | CUS-020 | Customer | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 137 | CUS-021 | Customer | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 138 | CUS-022 | Customer | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 139 | CUS-023 | Customer | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 140 | CUS-024 | Customer | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 141 | CUS-025 | Customer | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 142 | SUP-012 | Supplier | [blank] | Open - Fix Required |
| 143 | SUP-013 | Supplier | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 144 | SAL-037 | Sales | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 145 | SAL-038 | Sales | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 146 | SAL-039 | Sales | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 147 | PUR-007 | Purchase Order | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 148 | PUR-008 | Purchase Order | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 149 | PUR-009 | Purchase Order | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 150 | PUR-010 | Purchase Order | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 151 | GRN-014 | GRN | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 152 | GRN-015 | GRN | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 153 | STO-008 | Stock Master | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 154 | STO-009 | Stock Master | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 155 | STO-010 | Stock Master | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 156 | PRO-015 | Products Master | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 157 | SAL-040 | Sales | Changed | Tracker Stale - Retest and Close |
| 158 | SAL-041 | Sales | Changed | Tracker Stale - Retest and Close |
| 159 | SAL-042 | Sales | Changed | Tracker Stale - Retest and Close |
| 160 | SAL-043 | Sales | Changed | Tracker Stale - Retest and Close |
| 161 | SAL-044 | Sales | Changed | Tracker Stale - Retest and Close |
| 162 | COM-001 | Company | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 163 | PRO-001 | Product | Changed | Tracker Stale - Retest and Close |
| 164 | PRO-002 | Product | Changed | Tracker Stale - Retest and Close |
| 165 | STO-001 | Stock | Changed | Tracker Stale - Retest and Close |
| 166 | GRN-001 | GRN | Changed | Tracker Stale - Retest and Close |
| 167 | GRN-002 | GRN | Changed | Tracker Stale - Retest and Close |
| 168 | GRN-003 | GRN | Changed | Tracker Stale - Retest and Close |
| 169 | GRN-004 | GRN | [blank] | Status Missing; set Pass/Fail after retest |
| 170 | SI-001 | Sales Invoices | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 171 | SI-002 | Sales Invoices | Changed \| Already Covered | Tracker Stale - Retest and Close |
| 172 | PAY-001 | Payables | [blank] | Status Missing; set Pass/Fail after retest |
| 173 | PAY -002 | Payables | [blank] | Status Missing; set Pass/Fail after retest |