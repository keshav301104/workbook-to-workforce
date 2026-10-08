"""All 10 workflows, driven through the real engine with the Excel test questions,
plus the edge cases each decision rule implies."""
from .conftest import events_of, result_of, section


def rows(result, title):
    return section(result, title)["rows"]


def asks(events):
    return events_of(events, "ask")


# ------------------------------------------------------------------ WF001
def test_wf001_restock_threshold_logic(engine):
    ev, st = engine.run_to_end("Which products need restocking?")
    assert events_of(ev, "route")[0]["workflow_id"] == "WF001"
    r = result_of(ev)
    assert r["status"] == "completed"
    restock = {x["sku"]: x for x in rows(r, "Restock list")}
    assert set(restock) == {"TS-1003", "AC-5002", "KN-2002", "TS-1001", "OW-3002", "HM-6001"}
    assert "KN-2001" not in restock                       # stock == minimum is NOT below minimum
    assert restock["TS-1003"]["suggested_reorder_qty"] == 100   # up to max_stock
    assert restock["TS-1003"]["urgency"] == "Out of stock"
    assert restock["KN-2002"]["suggested_reorder_qty"] == 23    # no max_stock: 2 × 15 − 7
    assert [x["sku"] for x in rows(r, "Exactly at minimum (not flagged)")] == ["KN-2001"]


def test_wf001_category_and_threshold_from_request(engine):
    ev, _ = engine.run_to_end("Show low stock in knitwear")
    assert {x["sku"] for x in rows(result_of(ev), "Restock list")} == {"KN-2002"}
    ev, _ = engine.run_to_end("Which products need restocking if the threshold is 10?")
    assert {x["sku"] for x in rows(result_of(ev), "Restock list")} == {"TS-1003", "KN-2002", "OW-3002", "AC-5002", "HM-6001"}


# ------------------------------------------------------------------ WF002
def test_wf002_flags_only_differences_exceeding_10pct(engine):
    ev, _ = engine.run_to_end("Find products where vendor price differs by more than 10%.")
    r = result_of(ev)
    exc = {x["sku"]: x["pct_diff"] for x in rows(r, "Exceptions")}
    assert set(exc) == {"OW-3001", "KN-2001", "HM-6002", "TR-4002", "TS-1003"}
    assert "TS-1002" not in exc and "AC-5002" not in exc     # exactly ±10% does not exceed 10%
    matched = {x["sku"]: x for x in rows(r, "All matched products")}
    assert matched["KN-2001"]["vendor_sku"] == "KN2001"      # SKU format drift still matches
    assert [x["sku"] for x in rows(r, "In our catalog but missing from the vendor list")] == ["AC-5003", "HM-6003"]
    assert [x["vendor_sku"] for x in rows(r, "On the vendor list but not in our catalog")] == ["XX-9001"]


def test_wf002_threshold_can_be_overridden_by_request(engine):
    ev, _ = engine.run_to_end("Flag vendor prices that differ by more than 5%")
    assert events_of(ev, "params")[0]["params"][0] == {"name": "threshold_pct", "value": 5, "source": "request",
                                                        "description": "Flag a product when the price difference exceeds this percentage"}
    assert len(rows(result_of(ev), "Exceptions")) == 9


# ------------------------------------------------------------------ WF003
def test_wf003_asks_for_file_then_validates(engine):
    ev, _ = engine.run_to_end("Process this vendor spreadsheet and show invalid rows.", answers=[{"vendor_file": "__sample__"}])
    q = asks(ev)[0]
    assert q["kind"] == "inputs" and q["fields"][0]["name"] == "vendor_file"
    r = result_of(ev)
    assert r["status"] == "completed"
    invalid = {x["source_row"]: x["issue"] for x in rows(r, "Invalid rows")}
    assert invalid == {4: "Missing SKU", 5: "Missing product name", 6: "Missing product name", 13: "Missing SKU and product name"}
    warnings = rows(r, "Warnings (rows kept)")
    assert any(w["value"] == "N/A" and w["field"] == "unit_cost" for w in warnings)
    assert any("duplicate" in w["issue"] for w in warnings)
    clean = {x["sku"]: x for x in rows(r, "Cleaned dataset")}
    assert "NS-708" in clean and clean["NS-709"]["unit_cost"] == 29.99      # trimmed/upper-cased SKU, '$29.99' parsed
    assert section(r, "Detected columns")["rows"][0]["source_column"] in {"Item Code", "Qty Available", "Product Title", "Unit Cost ($)", "Colour", "Dept."}


def test_wf003_attached_file_is_used_directly(engine, settings):
    f = settings.data_dir / "vendor_upload_sample.csv"
    ev, _ = engine.run_to_end("Clean up this supplier file", files=[{"name": f.name, "path": str(f)}])
    assert not asks(ev)
    assert result_of(ev)["title"] == "7 clean rows, 4 invalid"


def test_wf003_file_without_required_columns_fails_cleanly(engine, settings):
    f = settings.data_dir / "keywords.csv"
    ev, _ = engine.run_to_end("Process this vendor file", files=[{"name": f.name, "path": str(f)}])
    r = result_of(ev)
    assert r["status"] == "failed"
    assert "no column that looks like sku or product_name" in r["sections"][0]["text"]


# ------------------------------------------------------------------ WF004
def test_wf004_asks_for_product_and_never_invents_missing_attributes(engine):
    ev, _ = engine.run_to_end("Generate SEO content for this product.", answers=[{"product": "Quilted Liner Vest"}])
    assert asks(ev)[0]["fields"][0]["name"] == "product"
    r = result_of(ev)
    missing = section(r, "Missing information")["text"]
    assert "color" in missing and "target audience" in missing
    content = {f["label"]: f["value"] for f in section(r, type_="content")["fields"]}
    assert set(content) == {"Product description", "Short description", "SEO title", "Meta description"}
    assert len(content["SEO title"]) <= 60 and len(content["Meta description"]) <= 160
    checks = section(r, "Quality checks")["rows"]
    assert all(c["result"] == "Pass" for c in checks)


def test_wf004_unknown_product_asks_for_category(engine):
    ev, _ = engine.run_to_end("Write a product description for the Bamboo lounge pants, color: charcoal",
                              answers=[{"category": "Loungewear"}])
    q = asks(ev)[0]
    assert q["kind"] == "step" and q["fields"][0]["name"] == "category"
    r = result_of(ev)
    assert r["subtitle"].startswith("Not in the catalog")
    assert "material" in section(r, "Missing information")["text"]


# ------------------------------------------------------------------ WF005
def test_wf005_order_found_with_tracking(engine):
    ev, _ = engine.run_to_end("Where is order ORD-1001?")
    r = result_of(ev)
    rec = {i["label"]: i["value"] for i in section(r, type_="record")["items"]}
    assert rec["Order status"] == "Shipped" and rec["Tracking number"] == "1Z999AA10123456784"
    assert rec["Items"] == "Classic Linen Shirt x1; Leather Belt x1"


def test_wf005_missing_order_asks_for_another_identifier(engine):
    ev, _ = engine.run_to_end("Where is order ORD-9999?",
                              answers=[{"identifier": "not-an-id"}, {"identifier": "sofia.reyes@example.com"}])
    qs = asks(ev)
    assert "couldn't find an order" in qs[0]["message"]
    assert "isn't an order ID or an email" in qs[1]["message"]
    rec = {i["label"]: i["value"] for i in section(result_of(ev), type_="record")["items"]}
    assert rec["Order status"] == "Processing"
    assert rec["Tracking number"] == "Not available yet"           # never guessed


def test_wf005_email_with_several_orders(engine):
    ev, _ = engine.run_to_end("Track orders for maya.patel@example.com")
    r = result_of(ev)
    assert r["title"] == "2 orders for maya.patel@example.com"
    assert [x["order_id"] for x in rows(r, "Orders")] == ["ORD-1005", "ORD-1001"]


# ------------------------------------------------------------------ WF006
def test_wf006_definite_and_possible_duplicates(engine):
    ev, _ = engine.run_to_end("Find likely duplicate products in the catalog.")
    groups = rows(result_of(ev), "Duplicate groups")
    definite = [g for g in groups if g["confidence"] == "Definite"]
    possible = [g for g in groups if g["confidence"] != "Definite"]
    assert len(definite) == 2 and len(possible) == 3
    assert {g["skus"] for g in definite} == {"TS-1001 | ts-1001", "KN-2001 | KN-2001"}
    joined = " ".join(g["skus"] for g in groups)
    assert "KN-2001-L" not in joined and "TR-4001B" not in joined    # size/colour variants are not duplicates
    assert all(0 < g["score"] <= 100 for g in groups)


# ------------------------------------------------------------------ WF007
def test_wf007_requests_goal_and_dates_before_generating(engine):
    ev, _ = engine.run_to_end("Create a campaign brief for the new collection.", answers=[
        {"campaign_goal": "drive launch-week sales", "start_date": "2026-10-20", "end_date": "2026-10-10"},
        {"start_date": "2026-10-12", "end_date": "2026-11-02"},
    ])
    q1, q2 = asks(ev)[:2]
    assert {f["name"] for f in q1["fields"]} == {"campaign_goal", "start_date", "end_date"}
    assert not [e for e in ev[: ev.index(q1)] if e["type"] == "step_started"]   # nothing generated before asking
    assert "before the start date" in q2["message"]
    r = result_of(ev)
    assert r["status"] == "completed"
    timeline = rows(r, "Timeline")
    assert timeline[0]["start"] == "2026-10-12" and timeline[-1]["end"] == "2026-11-02"
    assert all(p["collection"] == "Autumn 2026" for p in rows(r, "Featured products"))   # 'new collection' resolved
    assert len(section(r, "Campaign checklist")["items"]) >= 6


def test_wf007_complete_request_runs_without_questions(engine):
    ev, _ = engine.run_to_end("Plan a campaign for our knitwear to clear winter stock from Nov 1 to Nov 30, 20% off everything, targeting existing customers")
    assert not asks(ev)
    r = result_of(ev)
    overview = {i["label"]: i["value"] for i in section(r, "Overview")["items"]}
    assert overview["Objective type"] == "Conversion" and overview["Promotion"] == "20% off everything"


# ------------------------------------------------------------------ WF008
def test_wf008_classifies_into_exactly_four_intents(engine):
    ev, _ = engine.run_to_end("Classify these keywords and map them to pages.", answers=[{"keyword_file": "__sample__"}])
    r = result_of(ev)
    report = {x["keyword"]: x for x in rows(r, "Keyword report")}
    assert len(report) == 25                                       # 27 rows, 2 duplicates removed
    assert {x["intent"] for x in report.values()} <= {"informational", "commercial", "transactional", "navigational"}
    assert report["how to wash linen shirts"]["intent"] == "informational"
    assert report["buy linen shirt online"]["intent"] == "transactional"
    assert report["halden login"]["intent"] == "navigational"
    assert report["best linen shirts 2026"]["intent"] == "commercial"
    assert report["how to wash linen shirts"]["category"] == "Shirts"
    assert report["how to wash linen shirts"]["target_page"].startswith("/blogs/guides/")
    assert report["linen shirt"]["target_page"] == "/collections/shirts"
    assert {x["priority"] for x in report.values()} == {"High", "Medium", "Low"}


def test_wf008_inline_keywords(engine):
    ev, _ = engine.run_to_end("keywords: linen shirt, how to wash linen, Linen Shirt")
    r = result_of(ev)
    assert len(rows(r, "Keyword report")) == 2


# ------------------------------------------------------------------ WF009
def test_wf009_asks_for_task_then_picks_best_available(engine):
    ev, _ = engine.run_to_end("Assign this urgent task to the best available developer.",
                              answers=[{"task_description": "Fix the checkout payment bug in our React frontend, about 6 hours"}])
    assert asks(ev)[0]["fields"][0]["name"] == "task_description"
    r = result_of(ev)
    assert r["status"] == "completed" and r["title"] == "Assign to Daniel Ortiz"
    ranking = {x["name"]: x for x in rows(r, "Candidate ranking")}
    assert ranking["Hannah Weiss"]["blockers"] == "on leave"           # best skills but unavailable
    assert ranking["Priya Nair"]["eligible"] is False                  # right skills, no capacity
    reasoning = section(r, "Assignment summary")["fields"][1]["value"]
    assert "Hannah Weiss" in reasoning


def test_wf009_escalates_when_nobody_fits(engine):
    ev, _ = engine.run_to_end("Urgent: assign a developer. task: rebuild the React checkout with Stripe, 30 hours")
    r = result_of(ev)
    assert r["status"] == "escalated"
    assert "Escalating to the team lead" in r["sections"][0]["text"]


def test_wf009_unknown_skills_are_asked_then_escalated(engine):
    ev, _ = engine.run_to_end("Assign a developer. task: build a Rust and Kubernetes pipeline",
                              answers=[{"required_skills": "rust, kubernetes"}])
    assert asks(ev)[0]["fields"][0]["name"] == "required_skills"
    assert result_of(ev)["status"] == "escalated"


# ------------------------------------------------------------------ WF010
def test_wf010_reports_failure_rates_from_seed_and_live_logs(engine):
    engine.run_to_end("Which products need restocking?")            # creates a live run
    ev, _ = engine.run_to_end("Which workflows are failing most often?")
    r = result_of(ev)
    assert r["title"].startswith("Customer Order Status fails most often")
    metrics = rows(r, "Workflow metrics")
    assert metrics[0]["workflow_id"] == "WF005" and metrics[0]["needs_attention"] is True
    assert all(m["failure_rate"] >= n["failure_rate"] for m, n in zip(metrics, metrics[1:]))
    kpis = {k["label"]: k["value"] for k in section(r, type_="kpis")["items"]}
    assert int(kpis["Live runs included"]) >= 1
    assert any(x["area"] == "Reliability" for x in rows(r, "Recommendations"))


# ------------------------------------------------------------------ regression tests from review
def test_wf001_single_product_question(engine):
    ev, _ = engine.run_to_end("Do we have enough stock of wool beanies?")
    r = result_of(ev)
    assert [x["sku"] for x in rows(r, "Restock list")] == ["AC-5002"]
    ev, _ = engine.run_to_end("What is the stock level of the leather belt?")
    r = result_of(ev)
    assert "does not need restocking" in r["sections"][0]["text"]


def test_wf004_lowercase_catalog_names_match(engine):
    for q, sku in [("write copy for the leather belt", "AC-5001"), ("Generate a meta description for our quilted vest", "OW-3002")]:
        ev, _ = engine.run_to_end(q)
        assert not asks(ev), q
        assert sku in result_of(ev)["subtitle"]


def test_wf005_bare_order_number_is_normalised(engine):
    ev, _ = engine.run_to_end("What's the status of order 1004?")
    assert result_of(ev)["title"] == "Order ORD-1004: Cancelled"


def test_wf009_deadline_limits_capacity(engine):
    ev, _ = engine.run_to_end("I need someone to build a FastAPI endpoint with Python and Docker, 10 hours, by tomorrow")
    assert not asks(ev)
    r = result_of(ev)
    assert r["status"] == "escalated"                       # 12h free this week, but only ~2h before tomorrow
    assert "before the deadline" in r["sections"][0]["text"]
    ev, _ = engine.run_to_end("I need someone to build a FastAPI endpoint with Python and Docker, 10 hours")
    assert result_of(ev)["title"] == "Assign to Arjun Mehta"


def test_wf008_terms_prefix_and_account_page(engine):
    ev, _ = engine.run_to_end("Classify these terms: halden login, merino sweater sale")
    report = {x["keyword"]: x for x in rows(result_of(ev), "Keyword report")}
    assert report["halden login"]["target_page"] == "/account/login"