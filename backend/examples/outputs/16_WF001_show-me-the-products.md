# Edge case: ambiguous request → asks which workflow

**User request:** “show me the products”

## Selected workflow
**WF001 — Inventory Restock Check** (confidence 100%, user router)

> Confirmed by the user.

**Inputs:** Inventory file: `inventory.csv`

_Router was unsure (40% for WF002), so it asked:_ I'm not sure which workflow you mean. Pick one to continue. Options: WF002 Product Price Validation, WF004 Product Description Generator, WF006 Duplicate Product Detection, WF001 Inventory Restock Check

## Steps executed
   - ❓ **Asked the user:** I'm not sure which workflow you mean. Pick one to continue.
     Options offered: WF002 Product Price Validation, WF004 Product Description Generator, WF006 Duplicate Product Detection, WF001 Inventory Restock Check
1. ✓ **Load inventory** (`load_table`) — Loaded 15 rows × 8 columns from inventory.csv
2. – **Limit to the requested category** (`filter_rows`) — Skipped: `exists(inputs.category)` is false
3. – **Limit to the requested product** (`filter_rows`) — Skipped: `exists(inputs.product)` is false
4. ✓ **Requested product in inventory?** (decision) — `exists(inputs.product) and len(inventory) == 0` → false → continue
5. ✓ **Compare current stock with minimum threshold** (`compute_column`) — Computed threshold, stock_gap for 15 rows
6. ✓ **Apply restock rule** (`flag_rows`) — Flagged 6 of 15 rows
7. ✓ **Any products below threshold?** (decision) — `count(inventory, 'needs_restock') == 0` → false → continue
8. ✓ **Identify low-stock products** (`filter_rows`) — 6 of 15 rows match `needs_restock`
9. ✓ **Calculate reorder quantity** (`compute_column`) — Computed suggested_reorder_qty, reorder_basis, urgency, cover_ratio for 6 rows
10. ✓ **Generate restock list** (`sort_rows`) — Sorted by cover_ratio (asc)
11. ✓ **Export restock list** (`export_table`) — Exported 6 rows to restock_list.csv

## Result
**6 products need restocking** — status: `completed`

_Checked 15 products against each product’s minimum stock_

Products checked: **15** · Need restock: **6** · Out of stock: **1** · Units to reorder: **452**

**Restock list**
| SKU | Product | Category | Current stock | Minimum | Suggested reorder | Basis | Urgency |
|---|---|---|---|---|---|---|---|
| TS-1003 | Linen Overshirt | Shirts | 0 | 20 | 100 | Up to max stock (100) | Out of stock |
| AC-5002 | Wool Beanie | Accessories | 4 | 30 | 146 | Up to max stock (150) | Critical |
| KN-2002 | Cable Knit Cardigan | Knitwear | 7 | 15 | 23 | No max set: 2× minimum | Critical |
| TS-1001 | Classic Linen Shirt | Shirts | 12 | 25 | 108 | Up to max stock (120) | Critical |
| OW-3002 | Quilted Liner Vest | Outerwear | 9 | 12 | 41 | Up to max stock (50) | Low |
| HM-6001 | Linen Duvet Cover | Home | 6 | 8 | 34 | Up to max stock (40) | Low |

**Exactly at minimum (not flagged)**
| SKU | Product | Current stock | Minimum |
|---|---|---|---|
| KN-2001 | Merino Crew Sweater | 18 | 18 |

> Rule from the workflow sheet: a product is restocked only when current stock is below the minimum. Products exactly at the minimum are listed above but not flagged.

- 📎 Restock list (CSV) (6 rows)
