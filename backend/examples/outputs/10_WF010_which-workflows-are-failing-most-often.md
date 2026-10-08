# Excel test question

**User request:** “Which workflows are failing most often?”

## Selected workflow
**WF010 — Workflow Performance Report** (confidence 97%, lexical router)

> Matched on: failing, often, workflows.

**Inputs:** Execution log: `execution_logs.csv` · Log source: `all`

## Steps executed
1. ✓ **Load execution logs** (`load_table`) — Loaded 1524 rows × 12 columns from execution_logs.csv
2. ✓ **Load live run log** (`load_table`) — Loaded 73 rows × 12 columns from execution_log.csv
3. ✓ **Combine log sources** (`concat_tables`) — Combined 2 sources into 1597 rows
4. – **Apply filters** (`filter_rows`) — Skipped: `inputs.source != 'all' or exists(inputs.workflow)` is false
5. ✓ **Collapse steps into runs** (`aggregate`) — 299 group(s) by run_id
6. ✓ **Calculate success/failure rate** (`aggregate`) — 10 group(s) by workflow_id
7. ✓ **Calculate average execution time** (`compute_column`) — Computed failure_rate, success_rate, avg_seconds, failures, escalations for 10 rows
8. ✓ **Identify frequent errors** (`top_values`) — Top 8 value(s) of error_message
9. ✓ **Identify slow steps** (`aggregate`) — 84 group(s) by workflow_id, step_name
10. ✓ **Rank slow steps** (`sort_rows`) — Sorted by avg_seconds (desc), top 6
11. ✓ **Round step timings** (`compute_column`) — Computed avg_seconds for 6 rows
12. ✓ **Flag problem workflows** (`flag_rows`) — Flagged 4 of 10 rows
13. ✓ **Sort by failure rate** (`sort_rows`) — Sorted by failure_rate, avg_seconds (desc)
14. ✓ **Generate recommendations** (`rule_recommendations`) — 4 recommendation(s) generated from 3 rule(s)

## Result
**Customer Order Status fails most often (17.0%)** — status: `completed`

_299 runs across 10 workflows · 4 flagged · thresholds: failure > 10%, avg time > 4s_

Runs analysed: **299** · Overall success rate: **93.3%** · Avg run time: **3.37s** · Workflows flagged: **4** · Live runs included: **9**

**Failure rate by workflow**
- Customer Order Status: 17.0%
- Marketing Campaign Brief: 8.7%
- Product Price Validation: 6.2%
- SEO Keyword Classification: 5.0%
- Product Description Generator: 5.0%
- Inventory Restock Check: 4.3%
- Employee Task Assignment: 4.0%
- Vendor File Processing: 3.4%
- Duplicate Product Detection: 0.0%
- Workflow Performance Report: 0.0%

**Workflow metrics**
| ID | Workflow | Runs | Failures | Failure % | Success % | Avg time (s) | Flagged | Why |
|---|---|---|---|---|---|---|---|---|
| WF005 | Customer Order Status | 53 | 9 | 17 | 83 | 1.63 | True | failure rate 17.0% > 10% |
| WF007 | Marketing Campaign Brief | 23 | 2 | 8.7 | 91.3 | 14.18 | True | avg 14.18s > 4s |
| WF002 | Product Price Validation | 32 | 2 | 6.2 | 93.8 | 0.82 | False | — |
| WF008 | SEO Keyword Classification | 20 | 1 | 5 | 95 | 6.23 | True | avg 6.23s > 4s |
| WF004 | Product Description Generator | 40 | 2 | 5 | 95 | 6.04 | True | avg 6.04s > 4s |
| WF001 | Inventory Restock Check | 47 | 2 | 4.3 | 95.7 | 0.62 | False | — |
| WF009 | Employee Task Assignment | 25 | 1 | 4 | 96 | 0.97 | False | — |
| WF003 | Vendor File Processing | 29 | 1 | 3.4 | 96.6 | 3.35 | False | — |
| WF006 | Duplicate Product Detection | 18 | 0 | 0 | 100 | 2.5 | False | — |
| WF010 | Workflow Performance Report | 12 | 0 | 0 | 100 | 0.66 | False | — |

**Most frequent errors**
| Workflow | Error | Count |
|---|---|---|
| WF005 | Order API timeout (504) | 5 |
| WF005 | Shipment API rate limited (429) | 4 |
| WF001 | Inventory file not found | 2 |
| WF004 | LLM timeout after 30s | 2 |
| WF002 | SKU column missing in vendor price list | 2 |
| WF007 | LLM returned invalid JSON | 2 |
| WF003 | Unsupported file encoding | 1 |
| WF008 | LLM returned an unknown intent label | 1 |

**Slowest steps**
| Workflow | Step | Avg time (s) | Executions |
|---|---|---|---|
| WF007 | Create messaging | 4.35 | 23 |
| WF008 | Classify search intent | 3.09 | 20 |
| WF004 | Create product description | 2.69 | 39 |
| WF003 | Read file | 2.17 | 29 |
| WF007 | Validate inputs | 2.08 | 23 |
| WF007 | Create campaign checklist | 2.06 | 22 |

**Recommendations**
| Workflow | Area | Recommendation |
|---|---|---|
| Customer Order Status | Reliability | Failure rate is 17%. Most common error: “Order API timeout (504)”. Add retries with backoff around that call and validate inputs before it runs. |
| Marketing Campaign Brief | Speed | Average run takes 14.18s (threshold 4s). Slowest step: “Create messaging”. Cache its inputs or run it asynchronously. |
| SEO Keyword Classification | Speed | Average run takes 6.23s (threshold 4s). Slowest step: “Classify search intent”. Cache its inputs or run it asynchronously. |
| Product Description Generator | Speed | Average run takes 6.04s (threshold 4s). Slowest step: “Create product description”. Cache its inputs or run it asynchronously. |
