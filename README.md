<div align="center">

# Flowline · workbook-to-workforce

**Turn business workflows written in an Excel workbook into a working AI agent.**

Write a workflow as a row in a spreadsheet. Flowline reads it, works out which workflow a plain-English request needs, runs the steps with real tools, applies the sheet's rules, asks a person when something is missing, and streams every step to a live UI.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-state%20machine-1C3C3C)
![FastAPI](https://img.shields.io/badge/FastAPI-SSE%20streaming-009688?logo=fastapi&logoColor=white)
![LLM](https://img.shields.io/badge/LLM-OpenAI%20%7C%20Gemini%20%7C%20Groq%20%7C%20Anthropic-6B4FD8)
![Offline](https://img.shields.io/badge/runs%20without%20an%20API%20key-yes-2E7D4F)
![Tests](https://img.shields.io/badge/tests-76%20passing-2E7D4F)

</div>

---

## What sets this submission apart

Beyond what the brief asks for, these are the parts built to make Flowline behave like a production system rather than a demo:

| | Feature | Why it matters |
|---|---|---|
| 1 | **The spreadsheet really drives behaviour** | "exceeds 10%" in an Excel cell becomes `threshold_pct = 10`. Edit the cell, click Reload, and the agent follows the new rule with no code change |
| 2 | **Pause, ask, resume the same run** | When information is missing or wrong, the run stops (LangGraph `interrupt`), asks with a typed form, and continues from that step instead of starting over |
| 3 | **An 11th workflow with zero Python** | One Excel row plus a short YAML plan. The LLM can even draft that plan (`python -m flowline compile WF011`), and a test proves it works |
| 4 | **Plans are validated before anything runs** | Unknown tools, misspelled arguments, impossible jumps and Excel steps left unimplemented are caught at load time; a broken plan disables only its own workflow |
| 5 | **LLM for language, Python for maths** | The model routes, extracts and writes. Thresholds, percentages and rankings run in code, so exactly 10.00% is never "rounded" into an exception |
| 6 | **Grounded, checked LLM output** | Labels are restricted to the allowed values, skills to a known vocabulary, and generated copy is checked so missing attributes are never invented |
| 7 | **Works with any provider, or none** | OpenAI, Gemini, Groq or Anthropic by config. With no key every LLM step has a deterministic fallback, and a circuit breaker stops a failing provider from slowing every step |
| 8 | **Real failure handling, visible** | Simulated APIs with latency and fault injection, retries with exponential backoff, and a UI toggle to make them fail on demand and watch the recovery live |
| 9 | **The agent reports on itself** | Every run is logged in the same format WF010 analyses, so the performance report includes the agent's own runs |
| 10 | **A live console, not a chat box** | Workflow choice with confidence and reasoning, every step with its tool and Excel step, a live **flow map** of the path taken, live counters for LLM calls, API calls and retries, and an intent preview while you type |
| 11 | **Insights, Tool library, Run history** | A dashboard over all runs, the 32 shared tools with how many workflows reuse each, and the full trace of any past run |
| 12 | **Built for daily use** | `Ctrl K` command palette, keyboard shortcuts, sortable and filterable tables with CSV copy, Copy as Markdown, drag-and-drop uploads, light and dark themes |
| 13 | **76 automated tests** | Every Excel test question end to end, the planted edge cases, routing, pause/resume, retries, the LLM paths with a fake model, the API and WF011 |

---

## Screenshots

**Live run with simulated API faults.** Retries happen in front of you; the flow map on the right draws the path the agent takes.

![Live run with retries and the flow map](docs/02-live-run.png)

| | |
|---|---|
| ![Start page](docs/01-console.png) | ![Agent asking for missing inputs](docs/03-ask.png) |
| **Start page.** Test requests come straight from the spreadsheet; the pill shows the LLM in use. | **Human in the loop.** WF007 asks for the goal and dates before writing anything. |
| ![Grounded LLM content](docs/04-llm-content.png) | ![Insights dashboard](docs/05-insights.png) |
| **Grounded LLM content.** Missing attributes are reported, and quality checks confirm none were invented. | **Insights.** Finish rate, timing, routing confidence and outcomes per workflow. |
| ![Tool library](docs/06-tools.png) | ![Workflows page](docs/07-workflows.png) |
| **Tool library.** 32 shared tools and how many workflows reuse each one. | **Workflows.** Each Excel row next to the plan that runs it, with `threshold_pct = 10` read from the sheet. |

---

## Contents

- [What sets this submission apart](#what-sets-this-submission-apart)
- [Screenshots](#screenshots)
- [What it does](#what-it-does)
- [Assignment checklist](#assignment-checklist)
- [Why it is built this way](#why-it-is-built-this-way)
- [Architecture](#architecture)
- [How a request flows](#how-a-request-flows)
- [The spreadsheet is the source of truth](#the-spreadsheet-is-the-source-of-truth)
- [Workflow selection](#workflow-selection)
- [Execution and tool calling](#execution-and-tool-calling)
- [Conditions, human-in-the-loop and error handling](#conditions-human-in-the-loop-and-error-handling)
- [The 10 workflows](#the-10-workflows)
- [Adding an 11th workflow](#adding-an-11th-workflow)
- [The console](#the-console)
- [HTTP API](#http-api)
- [Design decisions](#design-decisions)
- [Repository layout](#repository-layout)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Testing](#testing)
- [Assumptions](#assumptions)
- [Beyond this assignment](#beyond-this-assignment)

---

## What it does

```text
User      ▸ "Check today's inventory and identify products that need restocking."

Selected  ▸ WF001 · Inventory Restock Check                      confidence 97%
Steps     ▸ ✓ Load inventory                       load_table        Excel step 1
            ✓ Compare current stock with minimum   compute_column    Excel step 2
            ✓ Apply restock rule                   flag_rows         Excel step 3
            ◆ Any products below threshold?        decision → continue
            ✓ Calculate reorder quantity           compute_column    Excel step 4
            ✓ Generate restock list                sort_rows         Excel step 5
Result    ▸ 6 products need restocking  (table · CSV download)
            KN-2001 is exactly at its minimum → not flagged (rule is strictly "<")
```

**A single generic agent runs every workflow.** There are no per-workflow chatbots and no `if workflow == "WF001"` branches. Each Excel row is paired with a short, validated **execution plan**, and one engine interprets all of them using a shared **tool library**.

---

## Assignment checklist

Every requirement in the brief, how it is met, and where to find it.

| Requirement | How Flowline does it | Where to look |
|---|---|---|
| Convert the 10 Excel workflows into an agent system | Each row of the `Workflows` sheet is parsed at runtime and paired with a declarative YAML plan; one engine runs all of them | `backend/flowline/spec/`, `backend/workflows/plans/` |
| Understand the user's request | LLM structured-output extraction into a schema generated from each plan, with regex patterns as the fallback | `backend/flowline/engine/extractor.py` |
| Select the right workflow | LLM router over a catalogue built from the Excel rows; BM25-style lexical fallback; asks the user when confidence is low; says so when nothing matches | `backend/flowline/engine/router.py` |
| Execute steps with tools and APIs | 32 reusable tools; simulated Order, Shipment and Records APIs with latency and fault injection | `backend/flowline/tools/` |
| Handle conditions | `Decision_Logic` becomes decision steps (`continue`, `ask`, `escalate`, `complete`, `fail`, `goto`); thresholds are read from the Excel text | the plans, `backend/flowline/engine/graph.py` |
| Handle errors | Retries with exponential backoff, a clear failure on the step that hit it, LLM fallback plus a circuit breaker, invalid input re-asked | `backend/flowline/engine/graph.py`, `backend/flowline/llm/client.py` |
| Show the selected workflow, the steps executed and the final output | Live web console, a terminal CLI, and saved transcripts of 18 runs | `frontend/`, `python -m flowline run`, `backend/examples/outputs/` |
| Not 10 hard-coded chatbots | No `if workflow == …` anywhere; every workflow is data (Excel row + plan) run by the same engine | `backend/flowline/engine/graph.py` |
| An 11th workflow with minimal code | WF011 is one Excel row plus a short YAML plan (under 90 lines), with **zero Python changes**, proved by a test | `backend/examples/wf011/`, `backend/tests/test_eleventh_workflow.py` |
| Python, LLM, agent/tool calling, Excel as the source | Python 3.10+, LangGraph, LangChain structured output over OpenAI, Gemini, Groq or Anthropic, `openpyxl`/`pandas` | `backend/requirements.txt` |
| Test with the sheet's test questions | Every question in `Test_Questions` runs end to end in the test suite | `backend/tests/test_workflows.py` |

---

## Why it is built this way

The brief asks for agents that *understand a request, select the right workflow, execute its steps, handle conditions and errors, and return the result*. It also says adding an 11th workflow should need minimal code changes.

Two simpler designs both fall short:

1. **One prompt per workflow.** Ten hard-coded chatbots. It doesn't scale, and the Excel file becomes documentation instead of the system.
2. **A free-form ReAct agent that picks tools as it goes.** It's flexible, but runs aren't repeatable, are hard to audit against the sheet, are slow, and can't be trusted with arithmetic.

Flowline sits between them. **The spreadsheet says *what*, a small declarative plan says *how*, and one engine runs any plan.** The LLM does the parts that need language understanding: picking the workflow, reading inputs, writing content, classifying, and drafting new plans. Deterministic code does the parts that need to be exact.

---

## Architecture

```mermaid
flowchart TD
    subgraph SRC[Sources of truth]
        X[(Excel workbook<br/>Workflows + Test_Questions)]
        P[(Execution plans<br/>workflows/plans/*.yaml)]
    end

    X --> REG[Workflow registry<br/>parse · validate · hot-reload]
    P --> REG
    T[Tool registry<br/>reusable tools] -->|tool + argument names checked| REG

    U[User request<br/>+ optional file] --> R
    REG --> R[Router<br/>LLM structured output<br/>→ lexical fallback]
    R -->|low confidence| C[Ask: which workflow?]
    C --> E
    R --> E[Input extractor<br/>schema built from the plan]
    E --> G{Required inputs<br/>present?}
    G -->|no| A1[Pause and ask<br/>LangGraph interrupt]
    A1 --> G
    G -->|yes| S[Step executor]
    S -->|tool step| TL[Tool call<br/>retries · simulated APIs · LLM + fallback]
    S -->|decision step| D[Rule from the sheet<br/>continue · ask · escalate · complete · fail]
    D -->|ask| A2[Pause, ask, re-run from that step]
    TL --> S
    D --> S
    A2 --> S
    S --> F[Render result + write step log]
    F -->|Server-Sent Events| UI[Frontend console]
    F --> L[(runs/execution_log.csv)]
    L -.->|WF010 analyses the agent's own runs| REG
```

| Layer | Module | Responsibility |
|---|---|---|
| **Spec** | `flowline/spec/` | Parse the workbook with tolerant header matching, split steps on `→`, attach test questions, join each row with its plan, validate everything, resolve rule parameters from the Excel text, hot-reload on change |
| **Expressions** | `flowline/expr.py` | Safely evaluate rules (`current_stock < minimum_stock`) and templates (`"{{ len(rows) }} products"`) without `eval`, so plans cannot execute code |
| **Tools** | `flowline/tools/` | Reusable, typed functions: load and clean tables, join, flag, aggregate, fuzzy lookup, duplicate grouping, LLM generate/classify/map/extract, text validation |
| **LLM** | `flowline/llm/` | One interface over OpenAI, Gemini, Groq and Anthropic using structured output, with a circuit breaker |
| **Engine** | `flowline/engine/` | Router, input extractor, the LangGraph state machine, result rendering, run logging |
| **API** | `flowline/api/` | FastAPI service that streams each run as Server-Sent Events, plus upload, download, history, tools and route-preview endpoints |
| **Frontend** | `frontend/` | Static HTML/CSS/JS console (no build step): live run view, flow map, insights, tool library, command palette |

---

## How a request flows

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as Frontend
    participant API as FastAPI
    participant G as LangGraph engine
    participant LLM
    participant T as Tools

    User->>UI: "Create a campaign brief for the new collection."
    UI->>API: POST /api/runs (stream)
    API->>G: start run
    G->>LLM: route request against the Excel catalogue
    LLM-->>G: WF007 · 0.95 · reasoning
    G-->>UI: event: route
    G->>LLM: extract inputs (schema generated from the plan)
    LLM-->>G: goal = null, dates = null
    G-->>UI: event: ask (goal, start date, end date)
    Note over G: run paused (interrupt) and checkpointed
    User->>UI: fills in the form
    UI->>API: POST /api/runs/{id}/resume
    API->>G: Command(resume=answers)
    loop every plan step
        G->>T: call tool with rendered arguments
        T-->>G: result + summary
        G-->>UI: event: step_started / step_finished / decision
    end
    G-->>UI: event: result (sections) · run_finished
```

---

## The spreadsheet is the source of truth

Each row of the `Workflows` sheet is parsed into a typed `WorkflowSpec`:

| Excel column | Becomes |
|---|---|
| `Workflow_ID`, `Workflow_Name`, `Trigger` | identity and routing catalogue |
| `Inputs` | what the extractor looks for |
| `Steps` (split on `→`) | the steps every plan step must point back to |
| `Decision_Logic` | rule parameters, read with a regex (e.g. `exceeds (\d+)%` → `10`) |
| `Tools_Required`, `Expected_Output` | shown in the UI and used for routing |
| `Test_Questions` sheet | routing examples, UI suggestions and test cases |

A plan binds each Excel step to a tool. Here is a shortened example:

```yaml
workflow_id: WF002
params:
  threshold_pct:
    default: 10
    from_excel: '(\d+(?:\.\d+)?)\s*%'        # read from Decision_Logic: "...exceeds 10%"
steps:
  - id: match
    title: Match products by SKU
    excel_step: 2
    tool: join_tables
    args: {left: $products, right: $vendor, left_on: sku, right_on: vendor_sku, normalize: sku}
    output: match
  - id: flag
    title: Flag exceptions
    excel_step: 5
    tool: flag_rows
    args: {table: $compared, when: "abs_pct > params.threshold_pct", flag: exception}
    output: compared
```

**Validation happens when plans load**, before anything runs. It catches unknown tools, misspelled arguments, missing required arguments, jumps to steps that don't exist, questions about unknown inputs, and **any Excel step no plan step implements**. A broken plan disables only its own workflow, and the error names the file, step and argument.

---

## Workflow selection

- **LLM router.** The prompt is built from the Excel rows at request time, so a new row is routable immediately. The model returns `{workflow_id, confidence, reasoning, alternatives}` as structured output, validated against the real IDs.
- **Lexical fallback.** If there's no key or the LLM fails, a BM25-style scorer runs over the same Excel text. Its confidence combines how much of the request it covers, how strong the match is, and **how far ahead it is of the runner-up**.
- **Clarification.** Below a configurable confidence (default 55%), the agent shows its top candidates and asks which one you meant. If nothing matches, it says so.

---

## Execution and tool calling

- **Inputs.** The LLM fills a schema generated from the plan's input definitions, with the instruction *"null when not stated"*. Plan regexes fill any gaps. Attached files go to the plan's file inputs.
- **Tools.** Arguments are rendered from the run context (`$inventory`, `{{ inputs.category }}`) and checked against each tool's Python signature.
- **Simulated APIs.** Order, shipment and directory lookups have realistic latency and optional fault injection. Transient faults are retried with exponential backoff, visibly.
- **The LLM is constrained.** Intent labels are restricted to the four allowed values. Skills must come from the employee directory's vocabulary. Generated copy is checked for length limits and for invented attributes.

---

## Conditions, human-in-the-loop and error handling

| Situation | Behaviour |
|---|---|
| Rule from `Decision_Logic` | A decision step: `continue` · `complete` · `ask` · `escalate` · `fail` · `goto`. The UI shows the expression and its outcome. |
| Required input missing | The run pauses, asks with a typed form, and resumes the **same** run |
| Problem found mid-run (order not found, unknown product, end date before start) | Ask the user, then re-run from the step that needs the answer |
| Transient API failure | Retry with exponential backoff, then fail cleanly with the reason |
| LLM unavailable, bad key or timeout | Deterministic fallback for that call. A circuit breaker skips the LLM for 60s after repeated failures |
| Bad input (missing file, unsupported type, no SKU column) | Clear, user-facing failure on the step that hit it |
| Unexpected tool exception | Contained to its step and reported; the service keeps running |

---

## The 10 workflows

| ID | Workflow | Excel rule → implementation | Edge cases covered |
|---|---|---|---|
| WF001 | Inventory Restock Check | `current_stock < minimum_stock`, strict | stock **equal** to minimum is not flagged; out of stock; no max stock; category, product or threshold from the request |
| WF002 | Product Price Validation | flag when the difference **exceeds** 10% (read from Excel) | SKU format drift (`ts1001` = `TS-1001`); exactly ±10.00% not flagged; unmatched SKUs on both sides |
| WF003 | Vendor File Processing | rows missing SKU or name are invalid | messy headers, blank rows, `N/A` and `$29.99` values, duplicate SKUs reported as warnings |
| WF004 | Product Description Generator | do not invent missing attributes | asks for the product; unknown product → asks for its category; missing attributes listed and checked absent from the copy |
| WF005 | Customer Order Status | no order found → ask for another identifier | invalid format; not found; email with several orders; no tracking yet (never guessed) |
| WF006 | Duplicate Product Detection | exact SKU = definite; high similarity = possible | case/space SKU variants; reworded names; size or colour **variants** are not duplicates |
| WF007 | Marketing Campaign Brief | goal or dates missing → request them first | the test question has neither, so it asks before generating; end date before start date; "new collection" resolved from the data |
| WF008 | SEO Keyword Classification | exactly four intents | duplicates; inline keyword lists; category mapping; priority scoring; target page per intent |
| WF009 | Employee Task Assignment | prefer skills + capacity; escalate if nobody fits | best match on leave; skilled but overloaded; capacity limited by deadline; unknown skills |
| WF010 | Workflow Performance Report | flag failure rate > 10% or slow average time | combines 30 days of history with **the agent's own live runs** |

---

## Adding an 11th workflow

1. Add a row to the `Workflows` sheet, for example `WF011 · Low Margin Alert · … · Flag products whose gross margin is below 62%`.
2. Add `backend/workflows/plans/WF011.yaml` using existing tools, or let the LLM draft it:
   `python -m flowline compile WF011`. The draft is validated, repaired once if needed, and kept as `.draft` until a person reviews it.
3. Reload. The workflow is routable and runnable, and **no Python changes were made**.

To see it live, run `python scripts/add_wf011.py` from `backend` (it adds the row and installs `examples/wf011/WF011.yaml`), click Reload in the console, and ask *"Which products have low margins?"*. `python scripts/add_wf011.py --remove` restores the original workbook. `tests/test_eleventh_workflow.py` does the same on a copy of the workbook.

A new **tool** is needed only for a capability the library doesn't have yet. That's one decorated function.

---

## The console

A static frontend (no build step) that renders the backend's event stream as it arrives.

| Page | What you see |
|---|---|
| **Console** | Your request, the workflow chosen with its confidence and reasoning, the inputs and where each came from, every step with its tool, Excel step, timing, logs and data preview, decisions with their rule and outcome, questions as inline forms, and the result as tables, KPIs, content, charts and downloads |
| **Flow map** (right panel) | The plan as a live graph. A gradient line follows the path the agent takes, skipped steps dim, decision outcomes show, and a dashed arc marks a jump back after a question. Click any node to open that step |
| **Insights** | Runs logged, finish rate, average time, routing confidence, runs per workflow by outcome, time per run, routing method split, most frequent requests |
| **Workflows** | Each Excel row next to its plan, with parameters and where they came from, validation issues, test requests to run, and *Draft a plan* for rows that have none |
| **Tool library** | Every tool, its arguments, whether it uses the LLM or a simulated API, and which workflows reuse it |
| **Run history** | Every logged run with its full step trace and result |

Also: an intent preview while typing, `Ctrl K` command palette, sortable and filterable result tables with CSV copy, *Run again*, *Copy as Markdown*, drag-and-drop file upload, light and dark themes, and keyboard shortcuts (`?` lists them).

The gradient (sheet green → cyan → blue → violet) is used for one thing only: progress through a run. Status colours stay flat so done, failed and needs-you read at a glance.

---

## HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/status` | LLM mode, workbook, workflow and tool counts, load problems |
| `GET` | `/api/workflows` | Every Excel row with its plan, parameters, issues and test requests |
| `POST` | `/api/workflows/reload` | Re-read the workbook and plans |
| `POST` | `/api/workflows/{id}/draft` | Draft a plan for a row (LLM, offline skeleton without a key) |
| `GET` | `/api/route/preview?q=` | Instant, LLM-free guess of the workflow for partial input |
| `GET` | `/api/tools` | The tool library with arguments |
| `POST` | `/api/upload` | Upload a CSV, XLSX, TSV or JSON file for a run |
| `POST` | `/api/runs` | Start a run; the response is a Server-Sent Events stream |
| `POST` | `/api/runs/{id}/resume` | Answer a question and continue the paused run (streamed) |
| `GET` | `/api/runs`, `/api/runs/{id}` | Run history and a run's full trace |
| `GET` | `/api/files/{run}/{name}` | Download a file a run produced |

Interactive docs are at `http://127.0.0.1:8000/docs` while the backend runs.

---

## Design decisions

| Decision | Reasoning |
|---|---|
| Declarative plans + one generic engine | Repeatable, auditable runs that map 1:1 to the spreadsheet, while staying generic |
| LangGraph | A real state machine with checkpointing, `interrupt()` / `Command(resume=…)` for human-in-the-loop, and custom event streaming |
| LLM for language, Python for math | Thresholds, percentages and rankings must be exact and testable |
| Parameters parsed from the sheet | The business owns the rules; the code doesn't hard-code them |
| Safe expression language (`simpleeval`) | Rules live in YAML without `eval`, so even an LLM-drafted plan cannot run code |
| Structured output (function calling) | Every LLM answer is validated against a schema generated at runtime |
| Provider-agnostic + offline mode | Switching provider is a config change; reviewers can run it with no key; outages degrade gracefully |
| Separate backend and frontend | Clear contract (HTTP + SSE), each side runs and scales on its own |
| Server-Sent Events | One-way, ordered, live progress over plain HTTP, simpler than WebSockets for this use |
| Self-logging | The engine writes the same log format WF010 analyses |

---

## Repository layout

```
workbook-to-workforce/
├── backend/
│   ├── flowline/
│   │   ├── config.py          settings from .env, LLM provider selection
│   │   ├── expr.py            safe expressions and templates
│   │   ├── spec/              Excel parsing, plan models, validation
│   │   ├── tools/             reusable tool library
│   │   ├── llm/               provider-agnostic client
│   │   ├── engine/            router, extractor, LangGraph executor, rendering, run log
│   │   └── api/               FastAPI streaming service
│   ├── workflows/
│   │   ├── AI_Agent_Workflow_Assessment_1.xlsx   source of truth
│   │   └── plans/             one execution plan per workflow
│   ├── data/                  simulated business data with planted edge cases
│   ├── examples/
│   │   ├── outputs/           transcripts of 18 runs (every test question + edge cases)
│   │   └── wf011/             the 11th workflow's plan
│   ├── scripts/               data generator, example runner, WF011 installer
│   ├── tests/                 76 tests
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html             layout: console, flow map, insights, workflows, tools, history
│   ├── styles.css             design tokens, light and dark themes
│   └── app.js                 event-stream rendering and all interactions
└── docs/                      screenshots used in this README
```

---

## Getting started

**Requirements:** Python 3.10+ and Git. No Node.js needed.

```bash
git clone https://github.com/keshav301104/workbook-to-workforce.git
cd workbook-to-workforce
```

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env  — then add an API key (optional)
python scripts/generate_data.py # sample data (already committed; re-run to reset)
python -m flowline serve        # API on http://127.0.0.1:8000
```

### Frontend

In a second terminal:

```bash
cd frontend
python -m http.server 5500      # or VS Code "Live Server"
```

Open **http://localhost:5500**. The pill at the top right shows the LLM in use, or *Offline mode* when there's no key.

### Using an LLM

Put one key in `backend/.env`. With `LLM_PROVIDER=auto` the first provider with a key is used. Groq has a free tier:

```bash
pip install langchain-groq           # or langchain-google-genai / langchain-anthropic
# backend/.env
GROQ_API_KEY=gsk_...
LLM_MODEL=openai/gpt-oss-120b        # optional; this is the Groq default
```

### Example transcripts

```bash
python scripts/generate_examples.py   # writes examples/outputs/*.md for 18 scenarios
```

### Command line

```bash
python -m flowline run "Where is order ORD-1001?"   # run one request in the terminal
python -m flowline validate                          # check the workbook and every plan
python -m flowline tools                             # list the tool library
python -m flowline compile WF011                     # draft a plan for a new Excel row
```

---

## Configuration

All settings live in `backend/.env` (see `.env.example`).

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `auto` | `auto` uses the first provider with a key; `offline` disables the LLM; or `openai`, `google_genai`, `groq`, `anthropic` |
| `LLM_MODEL` | per provider | Override the model (defaults: `gpt-4.1-mini`, `gemini-2.5-flash`, `openai/gpt-oss-120b` on Groq, `claude-haiku-4-5`) |
| `OPENAI_API_KEY` / `GOOGLE_API_KEY` / `GROQ_API_KEY` / `ANTHROPIC_API_KEY` | – | Provider credentials |
| `WORKFLOW_FILE` | `workflows/AI_Agent_Workflow_Assessment_1.xlsx` | The workbook to load |
| `ROUTER_MIN_CONFIDENCE` | `0.55` | Below this, the agent asks which workflow was meant |
| `SIM_API_LATENCY_MS` | `250` | Latency of simulated external APIs |
| `SIM_FAULT_RATE` | `0` | Probability of a simulated API fault (the UI can set this per run) |
| `CORS_ORIGINS` | `http://localhost:5500,…` | Frontend addresses allowed to call the API |

---

## Testing

```bash
cd backend
pytest
```

**76 tests.** The suite runs offline, deterministically and in under a minute. It covers:

- every Excel test question, end to end
- the edge cases planted in the sample data
- routing on paraphrases, out-of-scope and ambiguous requests
- pause/resume flows
- retries and failures
- the LLM code paths, using a fake model
- the HTTP API, including streaming, resume, uploads and the route preview
- adding an 11th workflow with no code changes

---

## Assumptions

Where the workbook is open to interpretation, the choice is explicit:

- **WF001.** "Minimum stock threshold" means each product's `minimum_stock`; a request can override it. Reorder quantity is `max_stock − current_stock`; when `max_stock` is missing, it is `2 × minimum − current`.
- **WF002.** The percentage difference is relative to the internal price, rounded to two decimals, and flagged only when it *exceeds* the threshold.
- **WF003.** Only a missing SKU or name makes a row invalid. Other problems are reported as warnings and the row is kept.
- **WF006.** "Exact SKU match" ignores case, spaces and punctuation. Products that differ only by size or colour are variants, not duplicates.
- **WF007.** "Dates" means a start date and an end date. Nothing is generated until both dates and the goal are known.
- **WF009.** With no estimate, the candidate needs a minimum number of free hours for the task's priority. With a deadline, only hours before the deadline count. Nobody on leave is assigned.
- **WF010.** The sheet's "defined threshold" for execution time defaults to 4 seconds and is configurable.

---

## Beyond this assignment

Next steps for production use:

- A persistent checkpointer (Postgres or Redis), so paused runs survive restarts
- Real connectors in place of the simulated APIs
- Authentication and per-user history
- Token and cost metrics in WF010
- An evaluation set for the LLM router

---

<div align="center">

Built by **Keshav Sharma** · [github.com/keshav301104](https://github.com/keshav301104)

</div>