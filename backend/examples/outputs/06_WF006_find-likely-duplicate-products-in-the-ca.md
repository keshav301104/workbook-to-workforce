# Excel test question

**User request:** “Find likely duplicate products in the catalog.”

## Selected workflow
**WF006 — Duplicate Product Detection** (confidence 97%, lexical router)

> Matched on: catalog, duplicate, likely, products.

**Inputs:** Product catalog: `catalog.csv`

## Steps executed
1. ✓ **Load products** (`load_table`) — Loaded 21 rows × 8 columns from catalog.csv
2. ✓ **Normalize names and SKUs** (`compute_column`) — Computed sku_key, name_key for 21 rows
3. ✓ **Compare identifiers** (`aggregate`) — 19 group(s) by sku_key
4. ✓ **Find repeated identifiers** (`filter_rows`) — 2 of 19 rows match `records > 1`
5. ✓ **Compare attributes, group duplicates and assign confidence** (`group_duplicates`) — 5 duplicate group(s): 2 definite, 3 possible
6. ✓ **Export duplicate report** (`export_table`) — Exported 5 rows to duplicate_groups.csv

## Result
**5 duplicate groups found in 21 records** — status: `completed`

_2 definite (same SKU) · 3 possible (similar attributes)_

Records scanned: **21** · Definite duplicates: **2** · High confidence: **3** · Medium confidence: **0**

**Duplicate groups**
| Group | Confidence | Score | Match type | SKUs | Names | Sources | Matching fields | Reason |
|---|---|---|---|---|---|---|---|---|
| G1 | Definite | 100 | Exact SKU match | TS-1001 / ts-1001 | Classic Linen Shirt / Classic Linen Shirt - White | Main store / Marketplace import | sku | Same SKU 'TS1001' after normalising case/spacing |
| G2 | Definite | 100 | Exact SKU match | KN-2001 / KN-2001 | Merino Crew Sweater / Merino Crewneck Sweater Charcoal | Main store / Wholesale feed | sku | Same SKU 'KN2001' after normalising case/spacing |
| G3 | High | 97 | Attribute similarity | TS-1002 / MK-88213 | Oxford Button-Down Shirt / Oxford Button Down Shirt Light Blue | Main store / Marketplace import | product_name, brand, category, color, size | Name similarity with matching brand, category, color, size |
| G4 | High | 97 | Attribute similarity | OW-3001 / WH-55120 | Waxed Field Jacket / Field Jacket, Waxed - Olive | Main store / Wholesale feed | product_name, brand, category, color, size | Name similarity with matching brand, category, color, size |
| G5 | High | 94 | Attribute similarity | AC-5002 / MK-90021 | Wool Beanie / Lambswool Beanie Rust | Main store / Marketplace import | product_name, brand, category, color, size | Name similarity with matching brand, category, color, size |

> Size and color variants of the same product (e.g. Merino Crew Sweater M vs L) are not reported as duplicates. Score = 60% name similarity + 40% matching brand/category/color/size.

- 📎 Duplicate groups (CSV) (5 rows)
