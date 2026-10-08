"""Adding an 11th workflow = one Excel row + one plan file. No Python changes."""
import shutil

import openpyxl
import yaml

from flowline.compiler import draft
from flowline.engine import graph
from flowline.llm import get_llm
from flowline.spec import loader

from .conftest import ROOT, result_of, section

ROW = ["WF011", "Low Margin Alert", "User asks which products have low profit margins",
       "Product CSV with prices and unit costs; minimum margin",
       "Load products → calculate gross margin → flag low-margin products → rank by margin → generate alert list",
       "Flag products whose gross margin is below 62%", "CSV reader; calculator",
       "List of low-margin products with price, cost, margin and gap to target"]


def _setup(tmp_path, settings, with_plan=True):
    xlsx = tmp_path / "workflows.xlsx"
    shutil.copy(settings.workflow_file, xlsx)
    wb = openpyxl.load_workbook(xlsx)
    wb["Workflows"].append(ROW)
    wb.save(xlsx)
    plans = tmp_path / "plans"
    shutil.copytree(settings.plans_dir, plans)
    if with_plan:
        shutil.copy(ROOT / "examples" / "wf011" / "WF011.yaml", plans / "WF011.yaml")
    settings.workflow_file, settings.plans_dir = xlsx, plans
    graph._engine = None
    return loader.reset_registry(settings)


def test_new_excel_row_plus_plan_is_routable_and_runnable(tmp_path, settings):
    reg = _setup(tmp_path, settings)
    wf = reg.get("WF011")
    assert wf.executable and wf.warnings == []
    assert wf.params["min_margin_pct"] == 62 and wf.param_sources["min_margin_pct"] == "Excel decision logic"
    ev, _ = graph.get_engine().run_to_end("Which products have low margins?")
    route = [e for e in ev if e["type"] == "route"][0]
    assert route["workflow_id"] == "WF011"
    r = result_of(ev)
    assert {x["sku"] for x in section(r, "Low-margin products")["rows"]} == {"KN-2002", "TR-4002", "OW-3001"}
    # existing workflows still route correctly
    ev, _ = graph.get_engine().run_to_end("Which products need restocking?")
    assert [e for e in ev if e["type"] == "route"][0]["workflow_id"] == "WF001"


def test_row_without_plan_is_listed_but_not_runnable(tmp_path, settings):
    reg = _setup(tmp_path, settings, with_plan=False)
    assert not reg.get("WF011").executable
    ev, _ = graph.get_engine().run_to_end("Which products have low margins?")
    assert result_of(ev)["status"] == "not_executable"


def test_compiler_drafts_a_skeleton_plan_offline(tmp_path, settings):
    reg = _setup(tmp_path, settings, with_plan=False)
    text, method, issues = draft(reg.get("WF011").spec, get_llm(), settings.plans_dir / "WF001.yaml")
    assert method == "skeleton"
    plan = yaml.safe_load(text)
    assert plan["workflow_id"] == "WF011"
    assert [s["excel_step"] for s in plan["steps"]] == [1, 2, 3, 4, 5]
    assert plan["steps"][0]["tool"] == "load_table"