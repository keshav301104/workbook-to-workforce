# Excel test question

**User request:** “Where is order ORD-1001?”

## Selected workflow
**WF005 — Customer Order Status** (confidence 97%, lexical router)

> Matched on: 1001, ord, order.

**Inputs:** Order ID or email: `ORD-1001`

## Steps executed
1. ✓ **Validate identifier** (`validate_identifier`) — 'ORD-1001' is a valid order id
2. ✓ **Identifier format valid?** (decision) — `not ident.valid` → false → continue
3. ✓ **Connect to order database** (`load_table`) — Loaded 6 rows × 7 columns from orders.csv
4. ✓ **Search order data** (`lookup_records`) — 1 record(s) where order_id = ORD-1001
5. ✓ **Order found?** (decision) — `not order.found` → false → continue
6. ✓ **Retrieve order status** (`select_columns`) — Prepared 1 rows with 7 columns
7. ✓ **Connect to shipment service** (`load_table`) — Loaded 4 rows × 7 columns from shipments.csv
8. ✓ **Retrieve shipment information** (`lookup_records`) — 1 record(s) where order_id = ORD-1001
9. ✓ **Combine order and shipment** (`join_tables`) — 1 matched, 0 only in left, 0 only in right
10. ✓ **Summarize current status** (`compute_column`) — Computed tracking, shipment, summary for 1 rows

## Result
**Order ORD-1001: Shipped** — status: `completed`

_ORD-1001: Shipped · UPS · In transit · ETA Oct 09, 2026_

- **Customer:** Maya Patel
- **Order date:** Oct 01, 2026
- **Order status:** Shipped
- **Items:** Classic Linen Shirt x1; Leather Belt x1
- **Order total:** $108.00
- **Shipment:** In transit
- **Carrier:** UPS
- **Tracking number:** 1Z999AA10123456784
- **Last location:** Jacksonville, FL
- **Estimated delivery:** Oct 09, 2026
- **Last update:** 2026-10-07 08:42
