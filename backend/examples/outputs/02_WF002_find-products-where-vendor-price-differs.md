# Excel test question

**User request:** “Find products where vendor price differs by more than 10%.”

## Selected workflow
**WF002 — Product Price Validation** (confidence 97%, lexical router)

> Matched on: 10, differs, price, products, vendor.

**Inputs:** Product price file: `products.csv` · Vendor price list: `vendor_prices.csv`

## Steps executed
1. ✓ **Load product prices** (`load_table`) — Loaded 15 rows × 13 columns from products.csv
2. ✓ **Load vendor price list** (`load_table`) — Loaded 14 rows × 4 columns from vendor_prices.csv
3. ✓ **Match products by SKU** (`join_tables`) — 13 matched, 2 only in left, 1 only in right
4. ✓ **Compare internal and vendor prices** (`compute_column`) — Computed price_diff for 13 rows
5. ✓ **Calculate percentage difference** (`compute_column`) — Computed pct_diff, abs_pct for 13 rows
6. ✓ **Flag exceptions** (`flag_rows`) — Flagged 5 of 13 rows
7. ✓ **Collect exceptions** (`filter_rows`) — 5 of 13 rows match `exception`
8. ✓ **Rank exceptions by size** (`sort_rows`) — Sorted by abs_pct (desc)
9. ✓ **Export validation report** (`export_table`) — Exported 13 rows to price_validation_report.csv

## Result
**5 price exceptions above 10%** — status: `completed`

_13 of 15 products matched to the vendor list by SKU_

Products: **15** · Matched by SKU: **13** · Exceptions (> 10%): **5** · Unmatched: **3**

**Exceptions**
| SKU | Product | Vendor | Internal | Vendor price | Difference % | Reason |
|---|---|---|---|---|---|---|
| OW-3001 | Waxed Field Jacket | Fieldcraft Supply | 249 | 311.25 | 25 | Vendor higher by 25% |
| KN-2001 | Merino Crew Sweater | Highland Knits | 119 | 101.15 | -15 | Vendor lower by 15% |
| HM-6002 | Stoneware Mug Set | Casa Linen | 45 | 39 | -13.33 | Vendor lower by 13.33% |
| TR-4002 | Pleated Wool Trousers | Highland Knits | 149 | 133 | -10.74 | Vendor lower by 10.74% |
| TS-1003 | Linen Overshirt | Northshore Textiles | 89 | 98.5 | 10.67 | Vendor higher by 10.67% |

**All matched products**
| SKU | Vendor SKU | Product | Internal | Vendor price | Difference | Difference % | Flagged |
|---|---|---|---|---|---|---|---|
| AC-5001 | AC-5001 | Leather Belt | 49 | 52 | 3 | 6.12 | False |
| AC-5002 | AC-5002 | Wool Beanie | 35 | 31.5 | -3.5 | -10 | False |
| HM-6001 | HM-6001 | Linen Duvet Cover | 189 | 204 | 15 | 7.94 | False |
| HM-6002 | HM-6002 | Stoneware Mug Set | 45 | 39 | -6 | -13.33 | True |
| KN-2001 | KN2001 | Merino Crew Sweater | 119 | 101.15 | -17.85 | -15 | True |
| KN-2002 | KN-2002 | Cable Knit Cardigan | 139 | 141 | 2 | 1.44 | False |
| OW-3001 | ow 3001 | Waxed Field Jacket | 249 | 311.25 | 62.25 | 25 | True |
| OW-3002 | OW-3002 | Quilted Liner Vest | 129 | 125 | -4 | -3.1 | False |
| TR-4001 | TR-4001 | Relaxed Chino Trousers | 79 | 79 | 0 | 0 | False |
| TR-4002 | TR-4002 | Pleated Wool Trousers | 149 | 133 | -16 | -10.74 | True |
| TS-1001 | ts1001 | Classic Linen Shirt | 59 | 61.95 | 2.95 | 5 | False |
| TS-1002 | TS-1002 | Oxford Button-Down Shirt | 64 | 70.4 | 6.4 | 10 | False |
| TS-1003 | ts-1003 | Linen Overshirt | 89 | 98.5 | 9.5 | 10.67 | True |

> 2 products differ by exactly 10% (AC-5002, TS-1002). The rule flags differences that exceed the threshold, so these are not exceptions.

**In our catalog but missing from the vendor list**
| SKU | Product | Internal price |
|---|---|---|
| AC-5003 | Canvas Tote Bag | 39 |
| HM-6003 | Wool Throw Blanket | 129 |

**On the vendor list but not in our catalog**
| Vendor SKU | Vendor | Vendor price |
|---|---|---|
| XX-9001 | Casa Linen | 22 |

- 📎 Validation report (CSV) (13 rows)
