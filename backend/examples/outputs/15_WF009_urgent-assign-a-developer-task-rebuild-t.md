# Edge case: nobody suitable → escalate

**User request:** “Urgent: assign a developer. task: rebuild the React checkout with Stripe, 30 hours”

## Selected workflow
**WF009 — Employee Task Assignment** (confidence 88%, lexical router)

> Matched on: assign, checkout, developer, react, task, urgent.

**Inputs:** Task description: `rebuild the React checkout with Stripe, 30 hours` · Priority: `Urgent` · Role: `Developer` · Estimated hours: `30`

## Steps executed
1. ✓ **Load employee directory** (`load_table`) — Loaded 10 rows × 8 columns from employees.csv
2. ✓ **Understand task requirements** (`llm_extract` · rules) — Extracted: required_skills=['react', 'stripe']; unlisted_skills=[]
3. ✓ **Settle required skills** (`merge_record`) — Record has 1 populated field(s)
4. ✓ **Required skills identified?** (decision) — `len(need.skills) == 0` → false → continue
5. ✓ **Compare employee skills** (`compute_column`) — Computed skill_match, matched_skills, missing_skills, role_match for 10 rows
6. ✓ **Check current workload** (`compute_column`) — Computed free_hours, needed_hours, days_left, usable_hours, has_capacity for 10 rows
7. ✓ **Rank candidates** (`compute_column`) — Computed eligible, score, blockers for 10 rows
8. ✓ **Order by eligibility and score** (`sort_rows`) — Sorted by eligible, score (desc)
9. ✓ **Select employee** (`select_best`) — No row satisfies the eligibility rule
10. ✓ **Suitable employee available?** (decision) — `not pick.found` → true → escalate

## Result
**Escalated: no suitable developer** — status: `escalated`

_Urgent priority · no deadline given · needs react, stripe_

**Escalated**
> No suitable developer is available for this urgent task (needs react, stripe). Closest match: Hannah Weiss — on leave. Escalating to the team lead to re-prioritise or bring in help.

**Candidate ranking**
| Name | Role | Skill match % | Matched | Free h | Status | Score | Eligible | Blockers |
|---|---|---|---|---|---|---|---|---|
| Hannah Weiss | Developer | 100 | react, stripe | 30 | on_leave | 100 | False | on leave |
| Daniel Ortiz | Developer | 100 | react, stripe | 22 | available | 91 | False | only 22h free, needs 30h |
| Priya Nair | Developer | 100 | react, stripe | 4 | available | 70 | False | only 4h free, needs 30h |
| Lucas Brown | Designer | 0 |  | 25 | available | 29 | False | only 25h free, needs 30h; missing react, stripe; not a developer |
| Kenji Sato | Developer | 0 |  | 18 | available | 21 | False | only 18h free, needs 30h; missing react, stripe |
| Grace Liu | Data Analyst | 0 |  | 15 | available | 18 | False | only 15h free, needs 30h; missing react, stripe; not a developer |
| Arjun Mehta | Developer | 0 |  | 12 | available | 14 | False | only 12h free, needs 30h; missing react, stripe |
| Chloe Martin | Marketer | 0 |  | 12 | available | 14 | False | only 12h free, needs 30h; missing react, stripe; not a developer |
| Omar Haddad | Developer | 0 |  | 10 | available | 12 | False | only 10h free, needs 30h; missing react, stripe |
| Fatima Zahra | Developer | 0 |  | 1 | available | 1 | False | only 1h free, needs 30h; missing react, stripe |
