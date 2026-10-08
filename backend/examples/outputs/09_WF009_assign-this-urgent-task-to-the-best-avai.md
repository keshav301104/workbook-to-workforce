# Excel test question (asks for the task)

**User request:** “Assign this urgent task to the best available developer.”

## Selected workflow
**WF009 — Employee Task Assignment** (confidence 97%, lexical router)

> Matched on: assign, available, best, developer, task, urgent.

**Inputs:** Task description: `Fix the checkout payment bug in our React frontend (Stripe), about 6 hours` · Priority: `Urgent` · Role: `Developer` · Estimated hours: `6`

## Steps executed
   - ❓ **Asked the user:** Describe the task: what needs to be built or fixed? Mention the technologies involved, and an estimate or deadline if you have one.
1. ✓ **Load employee directory** (`load_table`) — Loaded 10 rows × 8 columns from employees.csv
2. ✓ **Understand task requirements** (`llm_extract` · rules) — Extracted: required_skills=['react', 'stripe']; unlisted_skills=[]
3. ✓ **Settle required skills** (`merge_record`) — Record has 1 populated field(s)
4. ✓ **Required skills identified?** (decision) — `len(need.skills) == 0` → false → continue
5. ✓ **Compare employee skills** (`compute_column`) — Computed skill_match, matched_skills, missing_skills, role_match for 10 rows
6. ✓ **Check current workload** (`compute_column`) — Computed free_hours, needed_hours, days_left, usable_hours, has_capacity for 10 rows
7. ✓ **Rank candidates** (`compute_column`) — Computed eligible, score, blockers for 10 rows
8. ✓ **Order by eligibility and score** (`sort_rows`) — Sorted by eligible, score (desc)
9. ✓ **Select employee** (`select_best`) — Selected 1 of 1 eligible row(s)
10. ✓ **Suitable employee available?** (decision) — `not pick.found` → false → continue
11. ✓ **Generate assignment summary** (`llm_generate` · rules) — Generated 2 field(s) from templates

## Result
**Assign to Daniel Ortiz** — status: `completed`

_Urgent priority · no deadline given · needs react, stripe_

**Recommendation**
- **Employee:** Daniel Ortiz (E-103)
- **Role:** Senior Developer
- **Matched skills:** react, stripe
- **Free this week:** 22h of 40h
- **Priority:** Urgent
- **Deadline:** Not specified
- **Score:** 100 / 100

**Assignment summary**
- **Task:** Fix the checkout payment bug in our React frontend (Stripe), about 6 hours
- **Why this person:** Daniel Ortiz has 100% of the required skills (react, stripe) and 22 free hours this week against the 6 needed. Not chosen despite a strong skill match: Hannah Weiss (on leave); Priya Nair (only 4h free, needs 6h).

**Candidate ranking**
| Name | Role | Skill match % | Matched | Free h | Status | Score | Eligible | Blockers |
|---|---|---|---|---|---|---|---|---|
| Daniel Ortiz | Developer | 100 | react, stripe | 22 | available | 100 | True | none |
| Hannah Weiss | Developer | 100 | react, stripe | 30 | on_leave | 100 | False | on leave |
| Priya Nair | Developer | 100 | react, stripe | 4 | available | 88 | False | only 4h free, needs 6h |
| Arjun Mehta | Developer | 0 |  | 12 | available | 35 | False | missing react, stripe |
| Kenji Sato | Developer | 0 |  | 18 | available | 35 | False | missing react, stripe |
| Lucas Brown | Designer | 0 |  | 25 | available | 35 | False | missing react, stripe; not a developer |
| Chloe Martin | Marketer | 0 |  | 12 | available | 35 | False | missing react, stripe; not a developer |
| Omar Haddad | Developer | 0 |  | 10 | available | 35 | False | missing react, stripe |
| Grace Liu | Data Analyst | 0 |  | 15 | available | 35 | False | missing react, stripe; not a developer |
| Fatima Zahra | Developer | 0 |  | 1 | available | 6 | False | only 1h free, needs 6h; missing react, stripe |
