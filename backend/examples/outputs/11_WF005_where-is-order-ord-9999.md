# Edge case: order not found → ask again

**User request:** “Where is order ORD-9999?”

## Selected workflow
**WF005 — Customer Order Status** (confidence 91%, lexical router)

> Matched on: ord, order.

**Inputs:** Order ID or email: `sofia.reyes@example.com`

## Steps executed
1. ✓ **Validate identifier** (`validate_identifier`) — 'ORD-9999' is a valid order id
2. ✓ **Identifier format valid?** (decision) — `not ident.valid` → false → continue
3. ✓ **Connect to order database** (`load_table`) — Loaded 6 rows × 7 columns from orders.csv
4. ✓ **Search order data** (`lookup_records`) — 0 record(s) where order_id = ORD-9999
5. ✓ **Order found?** (decision) — `not order.found` → true → ask
   - ❓ **Asked the user:** I couldn't find an order for “ORD-9999”. Please give another order ID or the customer's email address.
   - ↺ resumed from step `validate` with the user's answer
6. ✓ **Validate identifier** (`validate_identifier`) — 'hello' is not a valid order id or order number or email
7. ✓ **Identifier format valid?** (decision) — `not ident.valid` → true → ask
   - ❓ **Asked the user:** “hello” isn't an order ID or an email address. Enter an order ID like ORD-1001 or the customer's email.
   - ↺ resumed from step `validate` with the user's answer
8. ✓ **Validate identifier** (`validate_identifier`) — 'sofia.reyes@example.com' is a valid email
9. ✓ **Identifier format valid?** (decision) — `not ident.valid` → false → continue
10. ✓ **Connect to order database** (`load_table`) — Loaded 6 rows × 7 columns from orders.csv
11. ✓ **Search order data** (`lookup_records`) — 1 record(s) where customer_email = sofia.reyes@example.com
12. ✓ **Order found?** (decision) — `not order.found` → false → continue
13. ✓ **Retrieve order status** (`select_columns`) — Prepared 1 rows with 7 columns
14. ✓ **Connect to shipment service** (`load_table`) — Loaded 4 rows × 7 columns from shipments.csv
15. ✓ **Retrieve shipment information** (`lookup_records`) — 0 record(s) where order_id = ORD-1003
16. ✓ **Combine order and shipment** (`join_tables`) — 0 matched, 1 only in left, 0 only in right
17. ✓ **Summarize current status** (`compute_column`) — Computed tracking, shipment, summary for 1 rows

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
