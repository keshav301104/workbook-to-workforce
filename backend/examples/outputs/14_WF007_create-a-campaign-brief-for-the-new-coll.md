# Edge case: end date before start date

**User request:** “Create a campaign brief for the new collection.”

## Selected workflow
**WF007 — Marketing Campaign Brief** (confidence 97%, lexical router)

> Matched on: campaign, collection, create, new.

**Inputs:** Campaign goal: `grow email signups` · Start date: `2026-11-01` · End date: `2026-11-20` · Products: `new collection`

## Steps executed
   - ❓ **Asked the user:** Before I write the brief I need the campaign goal and dates (the workflow rule says not to generate without them). What should the campaign achieve? When does it start? When does it end?
1. ✓ **Validate inputs** (`check_fields`) — All required fields present; missing optional: target_audience, promotion
2. ✓ **Dates in the right order?** (decision) — `days_between(inputs.start_date, inputs.end_date) < 0` → true → ask
   - ❓ **Asked the user:** The end date (Nov 01, 2026) is before the start date (Nov 20, 2026). Please re-enter the campaign dates.
   - ↺ resumed from step `validate` with the user's answer
3. ✓ **Validate inputs** (`check_fields`) — All required fields present; missing optional: target_audience, promotion
4. ✓ **Dates in the right order?** (decision) — `days_between(inputs.start_date, inputs.end_date) < 0` → false → continue
5. ✓ **Identify campaign objective** (`llm_generate` · rules) — Generated 3 field(s) from templates
6. ✓ **Read product data** (`load_table`) — Loaded 15 rows × 13 columns from products.csv
7. ✓ **Select campaign products** (`match_rows`) — 8 products in Autumn 2026
8. ✓ **Summarize products** (`llm_generate` · rules) — Generated 2 field(s) from templates
9. ✓ **Create messaging** (`llm_generate` · rules) — Generated 4 field(s) from templates
10. ✓ **Create channel recommendations** (`llm_generate` · rules) — Generated 1 field(s) from templates
11. ✓ **Build campaign timeline** (`build_timeline`) — 4 phases over 20 days
12. ✓ **Create campaign checklist** (`llm_generate` · rules) — Generated 1 field(s) from templates

## Result
**Campaign brief: Discover New Collection** — status: `completed`

_Acquisition campaign · Nov 01, 2026 – Nov 20, 2026 (20 days)_

**Overview**
- **Objective:** Grow email signups between Nov 01, 2026 and Nov 20, 2026.
- **Objective type:** Acquisition
- **Primary KPI:** New customers / sign-ups
- **Audience:** Not specified — define before launch
- **Promotion:** None
- **Products:** The campaign features 8 products from Autumn 2026 across Shirts, Knitwear, Outerwear, Trousers, Accessories, Home, priced $35.00–$249.00.

**Messaging**
- **Headline:** Discover New Collection
- **Key message:** Our new collection for every customer, Nov 01, 2026 to Nov 20, 2026.
- **Supporting points:** • Hero pieces: Waxed Field Jacket, Pleated Wool Trousers, Cable Knit Cardigan • Made in materials like Linen, Merino Wool, Waxed Cotton • Runs Nov 01, 2026 – Nov 20, 2026
- **Call to action:** Sign up today

**Channel recommendations**
- Paid social lead ads — capture sign-ups at low cost
- Search (non-brand) — reach shoppers looking for the category
- Referral offer — turn customers into acquisition
- Pop-up signup on site — convert visitors

**Timeline**
| Phase | Start | End | Days | Focus |
|---|---|---|---|---|
| Tease | 2026-11-01 | 2026-11-03 | 3 | Build anticipation; preview hero products |
| Launch | 2026-11-04 | 2026-11-10 | 7 | Full push across all channels |
| Sustain | 2026-11-11 | 2026-11-17 | 7 | Retarget engaged visitors; social proof |
| Last chance | 2026-11-18 | 2026-11-20 | 3 | Urgency messaging before the end date |

**Featured products**
| SKU | Product | Category | Collection | Price |
|---|---|---|---|---|
| TS-1003 | Linen Overshirt | Shirts | Autumn 2026 | 89 |
| KN-2001 | Merino Crew Sweater | Knitwear | Autumn 2026 | 119 |
| KN-2002 | Cable Knit Cardigan | Knitwear | Autumn 2026 | 139 |
| OW-3001 | Waxed Field Jacket | Outerwear | Autumn 2026 | 249 |
| OW-3002 | Quilted Liner Vest | Outerwear | Autumn 2026 | 129 |
| TR-4002 | Pleated Wool Trousers | Trousers | Autumn 2026 | 149 |
| AC-5002 | Wool Beanie | Accessories | Autumn 2026 | 35 |
| HM-6003 | Wool Throw Blanket | Home | Autumn 2026 | 129 |

**Campaign checklist**
- Confirm budget and owner per channel
- Finalise creative for Paid social lead ads, Search (non-brand), Referral offer
- Set up tracking for New customers / sign-ups
- Check stock levels for hero products
- Confirm whether an offer is needed
- Schedule emails and posts for each timeline phase
- QA landing page on mobile and desktop
- Book a results review for Nov 20, 2026
