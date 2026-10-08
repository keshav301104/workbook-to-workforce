# Excel test question (asks for goal and dates)

**User request:** “Create a campaign brief for the new collection.”

## Selected workflow
**WF007 — Marketing Campaign Brief** (confidence 97%, lexical router)

> Matched on: campaign, collection, create, new.

**Inputs:** Campaign goal: `drive launch-week sales of the autumn range` · Start date: `2026-10-12` · End date: `2026-11-02` · Products: `new collection`

## Steps executed
   - ❓ **Asked the user:** Before I write the brief I need the campaign goal and dates (the workflow rule says not to generate without them). What should the campaign achieve? When does it start? When does it end?
1. ✓ **Validate inputs** (`check_fields`) — All required fields present; missing optional: target_audience, promotion
2. ✓ **Dates in the right order?** (decision) — `days_between(inputs.start_date, inputs.end_date) < 0` → false → continue
3. ✓ **Identify campaign objective** (`llm_generate` · rules) — Generated 3 field(s) from templates
4. ✓ **Read product data** (`load_table`) — Loaded 15 rows × 13 columns from products.csv
5. ✓ **Select campaign products** (`match_rows`) — 8 products in Autumn 2026
6. ✓ **Summarize products** (`llm_generate` · rules) — Generated 2 field(s) from templates
7. ✓ **Create messaging** (`llm_generate` · rules) — Generated 4 field(s) from templates
8. ✓ **Create channel recommendations** (`llm_generate` · rules) — Generated 1 field(s) from templates
9. ✓ **Build campaign timeline** (`build_timeline`) — 4 phases over 22 days
10. ✓ **Create campaign checklist** (`llm_generate` · rules) — Generated 1 field(s) from templates

## Result
**Campaign brief: Autumn 2026 is here** — status: `completed`

_Conversion campaign · Oct 12, 2026 – Nov 02, 2026 (22 days)_

**Overview**
- **Objective:** Drive launch-week sales of the autumn range between Oct 12, 2026 and Nov 02, 2026.
- **Objective type:** Conversion
- **Primary KPI:** Revenue and conversion rate
- **Audience:** Not specified — define before launch
- **Promotion:** None
- **Products:** The campaign features 8 products from Autumn 2026 across Shirts, Knitwear, Outerwear, Trousers, Accessories, Home, priced $35.00–$249.00.

**Messaging**
- **Headline:** Autumn 2026 is here
- **Key message:** Our new collection for every customer, Oct 12, 2026 to Nov 02, 2026.
- **Supporting points:** • Hero pieces: Waxed Field Jacket, Pleated Wool Trousers, Cable Knit Cardigan • Made in materials like Linen, Merino Wool, Waxed Cotton • Runs Oct 12, 2026 – Nov 02, 2026
- **Call to action:** Shop the collection

**Channel recommendations**
- Email + SMS to subscribers — fastest path to revenue
- Retargeting ads — bring back recent visitors
- Search (brand + product) — capture high-intent demand
- Homepage and category banners — make the offer visible

**Timeline**
| Phase | Start | End | Days | Focus |
|---|---|---|---|---|
| Tease | 2026-10-12 | 2026-10-15 | 4 | Build anticipation; preview hero products |
| Launch | 2026-10-16 | 2026-10-22 | 7 | Full push across all channels |
| Sustain | 2026-10-23 | 2026-10-29 | 7 | Retarget engaged visitors; social proof |
| Last chance | 2026-10-30 | 2026-11-02 | 4 | Urgency messaging before the end date |

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
- Finalise creative for Email + SMS to subscribers, Retargeting ads, Search (brand + product)
- Set up tracking for Revenue and conversion rate
- Check stock levels for hero products
- Confirm whether an offer is needed
- Schedule emails and posts for each timeline phase
- QA landing page on mobile and desktop
- Book a results review for Nov 02, 2026
