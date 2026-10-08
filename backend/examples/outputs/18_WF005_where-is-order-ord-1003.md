# Edge case: simulated API outage → retry

**User request:** “Where is order ORD-1003?”

## Selected workflow
**WF005 — Customer Order Status** (confidence 97%, lexical router)

> Matched on: 1003, ord, order.

**Inputs:** Order ID or email: `ORD-1003`

## Steps executed
1. ✓ **Validate identifier** (`validate_identifier`) — 'ORD-1003' is a valid order id
2. ✓ **Identifier format valid?** (decision) — `not ident.valid` → false → continue
3. ✓ **Connect to order database** (`load_table`) — Loaded 6 rows × 7 columns from orders.csv
   - ↻ retry: Order API returned 503 Service Unavailable (simulated fault)
4. ✓ **Search order data** (`lookup_records`) — 1 record(s) where order_id = ORD-1003
5. ✓ **Order found?** (decision) — `not order.found` → false → continue
6. ✓ **Retrieve order status** (`select_columns`) — Prepared 1 rows with 7 columns
7. ✓ **Connect to shipment service** (`load_table`) — Loaded 4 rows × 7 columns from shipments.csv
   - ↻ retry: Shipment API returned 503 Service Unavailable (simulated fault)
8. ✓ **Retrieve shipment information** (`lookup_records`) — 0 record(s) where order_id = ORD-1003
9. ✓ **Combine order and shipment** (`join_tables`) — 0 matched, 1 only in left, 0 only in right
10. ✓ **Summarize current status** (`compute_column`) — Computed tracking, shipment, summary for 1 rows

## Result
**Order ORD-1003: Processing** — status: `completed`

_ORD-1003: Processing · not shipped yet_

- **Customer:** Sofia Reyes
- **Order date:** Oct 06, 2026
- **Order status:** Processing
- **Items:** Merino Crew Sweater x2
- **Order total:** $238.00
- **Shipment:** Not shipped yet
- **Carrier:** —
- **Tracking number:** Not available yet
- **Last location:** —
- **Estimated delivery:** —
- **Last update:** —
