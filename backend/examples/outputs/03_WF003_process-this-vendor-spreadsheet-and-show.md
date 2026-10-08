# Excel test question (asks for the file)

**User request:** “Process this vendor spreadsheet and show invalid rows.”

## Selected workflow
**WF003 — Vendor File Processing** (confidence 97%, lexical router)

> Matched on: invalid, process, rows, spreadsheet, vendor.

**Inputs:** Vendor file: `vendor_upload_sample.xlsx`

## Steps executed
   - ❓ **Asked the user:** Attach the vendor file (CSV or XLSX) you want processed, or use the sample vendor feed.
1. ✓ **Read file** (`load_table`) — Loaded 12 rows × 6 columns from vendor_upload_sample.xlsx
2. ✓ **Detect columns** (`detect_columns` · rules) — Detected 6 of 6 schema fields
3. ✓ **Required columns present?** (decision) — `len(columns.missing_required) > 0` → false → continue
4. ✓ **Normalize column names** (`rename_columns`) — Normalized column names: sku, product_name, unit_cost, quantity, color, category
5. ✓ **Clean values** (`clean_values`) — Cleaned 11 rows, dropped 1 empty row(s), 2 value warning(s)
6. ✓ **Validate required fields** (`validate_required`) — 7 valid, 4 invalid (required: sku, product_name)
7. ✓ **Produce cleaned dataset** (`export_table`) — Exported 7 rows to vendor_clean.csv
8. ✓ **Export invalid-row report** (`export_table`) — Exported 4 rows to vendor_invalid_rows.csv

## Result
**7 clean rows, 4 invalid** — status: `completed`

_12 rows read from vendor_upload_sample.xlsx_

Rows read: **12** · Valid rows: **7** · Invalid rows: **4** · Warnings: **2** · Blank rows dropped: **1**

**Invalid rows**
| Row | SKU | Product name | Problem |
|---|---|---|---|
| 4 | — | Ribbed Tank Top | Missing SKU |
| 5 | NS-704 | — | Missing product name |
| 6 | NS-705 | — | Missing product name |
| 13 | — | — | Missing SKU and product name |

**Detected columns**
| Standard field | Column in file | Match |
|---|---|---|
| unit_cost | Unit Cost ($) | 100% |
| sku | Item Code | 100% |
| quantity | Qty Available | 100% |
| product_name | Product Title | 100% |
| color | Colour | 100% |
| category | Dept. | 100% |

**Warnings (rows kept)**
| Row | Field | Value | Issue |
|---|---|---|---|
| 8 | unit_cost | N/A | 'N/A' is not a number |
| 10 | sku | NS-702 | duplicate sku (first seen earlier in the file) |

**Cleaned dataset**
| Row | SKU | Product name | Unit cost | Quantity | Color | Category |
|---|---|---|---|---|---|---|
| 2 | NS-701 | Garment-Dyed Tee | 18.5 | 120 | Bone | Tops |
| 3 | NS-702 | Heavyweight Hoodie | 42 | 60 | Black | Tops |
| 8 | NS-706 | Fleece Joggers | — | 50 | Heather | Bottoms |
| 9 | NS-707 | Utility Cargo Pants | 48 | — | Khaki | Bottoms |
| 10 | NS-702 | Heavyweight Hoodie | 42 | 60 | Black | Tops |
| 11 | NS-708 | Corduroy Cap | 22 | 90 | Rust | Accessories |
| 12 | NS-709 | Waffle Knit Henley | 29.99 | 70 | Oat | Tops |

- 📎 Cleaned file (CSV) (7 rows)
- 📎 Invalid rows (CSV) (4 rows)
