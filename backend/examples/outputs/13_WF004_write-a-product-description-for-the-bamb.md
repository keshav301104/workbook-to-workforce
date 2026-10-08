# Edge case: product not in catalog, missing attributes

**User request:** “Write a product description for the Bamboo lounge pants, color: charcoal”

## Selected workflow
**WF004 — Product Description Generator** (confidence 82%, lexical router)

> Matched on: color, description, product, write.

**Inputs:** Product: `Bamboo lounge pants` · Category: `Loungewear` · Color: `charcoal`

## Steps executed
1. ✓ **Load product catalog** (`load_table`) — Loaded 15 rows × 13 columns from products.csv
2. ✓ **Find product in catalog** (`fuzzy_lookup`) — No confident match for 'Bamboo lounge pants' (best 45%)
3. ✓ **Collect product attributes** (`merge_record`) — Record has 2 populated field(s); from request: color
4. ✓ **Validate required attributes** (`check_fields`) — Missing required: category; missing optional: material, target_audience, features
5. ✓ **Category known?** (decision) — `not fields.ok` → true → ask
   - ❓ **Asked the user:** “Bamboo lounge pants” isn't in the catalog, so I need its category. Attributes I don't have will be marked missing rather than invented.
   - ↺ resumed from step `merge` with the user's answer
6. ✓ **Collect product attributes** (`merge_record`) — Record has 3 populated field(s); from request: category, color
7. ✓ **Validate required attributes** (`check_fields`) — All required fields present; missing optional: material, target_audience, features
8. ✓ **Category known?** (decision) — `not fields.ok` → false → continue
9. ✓ **Create product description** (`llm_generate` · rules) — Generated 1 field(s) from templates
10. ✓ **Generate short description** (`llm_generate` · rules) — Generated 1 field(s) from templates
11. ✓ **Generate SEO title** (`llm_generate` · rules) — Generated 1 field(s) from templates
12. ✓ **Generate meta description** (`llm_generate` · rules) — Generated 1 field(s) from templates
13. ✓ **Validate generated text** (`validate_text`) — All text checks passed

## Result
**Content for Bamboo lounge pants** — status: `completed`

_Not in the catalog — written from the details you gave_

**Missing information**
> Not provided, so not used in the copy: material, target audience, features. Add them to the catalog or your request to enrich the content.

- **Product description:** Meet the Bamboo lounge pants, part of our loungewear range in charcoal. An easy, reliable addition to your loungewear lineup.
- **Short description:** Bamboo lounge pants in charcoal — from our loungewear range.
- **SEO title:** Bamboo lounge pants – charcoal | Loungewear
- **Meta description:** Shop the Bamboo lounge pants in charcoal. Explore our loungewear collection online.

**Facts used**
- **Product:** Bamboo lounge pants
- **Category:** Loungewear
- **Material:** Missing
- **Color:** charcoal
- **Target audience:** Missing
- **Features:** Missing

**Quality checks**
| Field | Check | Result | Detail |
|---|---|---|---|
| description | No invented material | Pass | none mentioned |
| short_description | Length ≤ 150 | Pass | 60 characters |
| short_description | No invented material | Pass | none mentioned |
| seo_title | Length ≤ 60 | Pass | 43 characters |
| seo_title | No invented material | Pass | none mentioned |
| meta_description | Length ≤ 160 | Pass | 83 characters |
| meta_description | No invented material | Pass | none mentioned |
