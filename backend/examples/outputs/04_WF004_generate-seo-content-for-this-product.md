# Excel test question (asks for the product)

**User request:** “Generate SEO content for this product.”

## Selected workflow
**WF004 — Product Description Generator** (confidence 97%, lexical router)

> Matched on: content, generate, product, seo.

**Inputs:** Product: `Quilted Liner Vest`

## Steps executed
   - ❓ **Asked the user:** Which product should I write content for? Give a product name or SKU (attributes you add, like material or color, will be used).
1. ✓ **Load product catalog** (`load_table`) — Loaded 15 rows × 13 columns from products.csv
2. ✓ **Find product in catalog** (`fuzzy_lookup`) — Matched 'Quilted Liner Vest' to Quilted Liner Vest (100% similarity)
3. ✓ **Collect product attributes** (`merge_record`) — Record has 11 populated field(s)
4. ✓ **Validate required attributes** (`check_fields`) — All required fields present; missing optional: color, target_audience
5. ✓ **Category known?** (decision) — `not fields.ok` → false → continue
6. ✓ **Create product description** (`llm_generate` · rules) — Generated 1 field(s) from templates
7. ✓ **Generate short description** (`llm_generate` · rules) — Generated 1 field(s) from templates
8. ✓ **Generate SEO title** (`llm_generate` · rules) — Generated 1 field(s) from templates
9. ✓ **Generate meta description** (`llm_generate` · rules) — Generated 1 field(s) from templates
10. ✓ **Validate generated text** (`validate_text`) — All text checks passed

## Result
**Content for Quilted Liner Vest** — status: `completed`

_Catalog match: OW-3002 (100% name match)_

**Missing information**
> Not provided, so not used in the copy: color, target audience. Add them to the catalog or your request to enrich the content.

- **Product description:** Meet the Quilted Liner Vest, part of our outerwear range, made from recycled polyester. Packable. An easy, reliable addition to your outerwear lineup.
- **Short description:** Quilted Liner Vest, recycled polyester — from our outerwear range.
- **SEO title:** Quilted Liner Vest | Outerwear
- **Meta description:** Shop the Quilted Liner Vest, made from recycled polyester. Explore our outerwear collection online.

**Facts used**
- **Product:** Quilted Liner Vest
- **Category:** Outerwear
- **Material:** Recycled Polyester
- **Color:** Missing
- **Target audience:** Missing
- **Features:** Packable

**Quality checks**
| Field | Check | Result | Detail |
|---|---|---|---|
| description | No invented color | Pass | none mentioned |
| short_description | Length ≤ 150 | Pass | 66 characters |
| short_description | No invented color | Pass | none mentioned |
| seo_title | Length ≤ 60 | Pass | 30 characters |
| seo_title | No invented color | Pass | none mentioned |
| meta_description | Length ≤ 160 | Pass | 99 characters |
| meta_description | No invented color | Pass | none mentioned |
