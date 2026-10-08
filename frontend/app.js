// Flowline console — streams backend events and renders them live.
// No build step: plain ES module. The backend API runs separately (default http://127.0.0.1:8000).

const API = (window.FLOWLINE_API || "http://127.0.0.1:8000").replace(/\/$/, "");

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const sleep = (ms) => new Promise((r) => setTimeout(r, REDUCED ? 0 : ms));

function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

const I = {
  check: '<path d="M5 10.5l3 3 7-7"/>',
  x: '<path d="M6 6l8 8M14 6l-8 8"/>',
  dash: '<path d="M6 10h8"/>',
  dot: '<circle cx="10" cy="10" r="2.2" fill="currentColor" stroke="none"/>',
  q: '<path d="M7.5 7.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .8-1 1.5v.4M10 14.5v.1"/>',
  info: '<circle cx="10" cy="10" r="7.5"/><path d="M10 9v4.5M10 6.5v.1"/>',
  warn: '<path d="M10 3.5 17.5 16h-15L10 3.5z"/><path d="M10 8.5v3.5M10 14.2v.1"/>',
  danger: '<circle cx="10" cy="10" r="7.5"/><path d="M7.5 7.5l5 5M12.5 7.5l-5 5"/>',
  ok: '<circle cx="10" cy="10" r="7.5"/><path d="M6.8 10.2l2.2 2.2 4.2-4.4"/>',
  copy: '<rect x="7" y="7" width="9" height="9" rx="1.5"/><path d="M13 7V5.5A1.5 1.5 0 0 0 11.5 4h-6A1.5 1.5 0 0 0 4 5.5v6A1.5 1.5 0 0 0 5.5 13H7"/>',
  down: '<path d="M10 3.5v9M6 9l4 4 4-4M4 16.5h12"/>',
  chev: '<path d="M8 5l5 5-5 5"/>',
  retry: '<path d="M16 10a6 6 0 1 1-2-4.5M16 3v4h-4"/>',
  file: '<path d="M5 2.5h6.5L15 6v11.5H5z"/><path d="M11 2.5V6h4"/>',
  sheet: '<rect x="3" y="3" width="14" height="14" rx="2"/><path d="M3 8h14M3 12.5h14M8 3v14"/>',
  tool: '<path d="M12.5 3.5a3.5 3.5 0 0 0-3.3 4.7L3.5 13.9 6.1 16.5l5.7-5.7a3.5 3.5 0 0 0 4.7-3.3l-2 2-2.2-.5-.5-2.2 2-2z"/>',
  close: '<path d="M6 6l8 8M14 6l-8 8"/>',
  person: '<circle cx="10" cy="7" r="3"/><path d="M4 16.5a6 6 0 0 1 12 0"/>',
};
const icon = (name, cls = "") => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 20 20");
  if (cls) s.setAttribute("class", cls);
  s.innerHTML = I[name] || "";
  return s;
};

const state = { status: null, workflows: [], attachments: [], busy: false };

// ------------------------------------------------------------------ formatting
const MONEY_KEYS = /(^|_)(price|cost|total|amount)(_|$)|internal|vendor_price/i;
function fmt(v, key = "") {
  if (v === null || v === undefined || v === "") return h("span", { class: "null" }, "—");
  if (typeof v === "boolean") return h("span", { class: v ? "bool-t" : "bool-f" }, v ? "Yes" : "No");
  if (typeof v === "number") {
    if (MONEY_KEYS.test(key) && !/diff|pct/.test(key)) return "$" + v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (Number.isInteger(v)) return v.toLocaleString();
    return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
const isNumCol = (rows, key) => rows.length > 0 && rows.every((r) => r[key] === null || r[key] === undefined || typeof r[key] === "number");
const ms = (n) => (n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + "s" : `${n}ms`);
const toast = (msg) => {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 2200);
};

// ------------------------------------------------------------------ tables
function table(columns, rows, { tones = null, limit = 10, total = null, empty = "No rows" } = {}) {
  const wrap = h("div", { class: "preview" });
  if (!rows.length) {
    wrap.append(h("div", { class: "empty", style: { padding: "16px" } }, empty));
    return wrap;
  }
  const cols = columns.map((c) => (typeof c === "string" ? { key: c, label: c.replace(/_/g, " ") } : c));
  const numeric = Object.fromEntries(cols.map((c) => [c.key, isNumCol(rows, c.key)]));
  const tbl = h("table", { class: "tbl" },
    h("thead", {}, h("tr", {}, cols.map((c) => h("th", { class: numeric[c.key] ? "num" : "" }, c.label)))));
  const body = h("tbody");
  const draw = (n) => {
    body.innerHTML = "";
    rows.slice(0, n).forEach((r, i) => {
      const tone = tones && tones[i];
      body.append(h("tr", { class: tone ? `tone-${tone}` : "" },
        cols.map((c) => {
          const v = r[c.key];
          const long = typeof v === "string" && v.length > 48;
          const short = typeof v === "string" && v.length <= 14;
          return h("td", { class: (numeric[c.key] ? "num" : "") + (long ? " wrap" : "") + (short ? " nowrap" : "") }, fmt(v, c.key));
        })));
    });
  };
  draw(limit);
  tbl.append(body);
  wrap.append(tbl);
  const count = total ?? rows.length;
  if (count > limit || count > rows.length) {
    const more = h("div", { class: "tbl-more" });
    let expanded = false;
    const btn = h("button", { class: "link-btn", type: "button" }, `Show all ${rows.length}`);
    btn.onclick = () => {
      expanded = !expanded;
      draw(expanded ? rows.length : limit);
      btn.textContent = expanded ? "Show fewer" : `Show all ${rows.length}`;
    };
    more.append(h("span", {}, `${Math.min(limit, rows.length)} of ${count} rows`), rows.length > limit ? btn : "");
    wrap.after(more);
    const box = h("div", {}, wrap, more);
    return box;
  }
  return wrap;
}

function previewEl(p) {
  if (!p) return null;
  if (p.kind === "table") return table(p.columns, p.rows, { total: p.total, limit: 5, empty: "Empty table" });
  if (p.kind === "list") return h("div", { class: "preview" }, h("div", { class: "kv" }, h("dt", {}, `${p.total} items`), h("dd", {}, p.items.join(", "))));
  if (p.kind === "text") return h("div", { class: "preview" }, h("div", { class: "kv" }, h("dt", {}, "value"), h("dd", {}, String(p.text ?? "—"))));
  if (p.kind === "object") {
    const dl = h("dl", { class: "kv" });
    for (const [k, v] of Object.entries(p.fields)) {
      let txt;
      if (v.kind === "table") txt = `table · ${v.total} rows`;
      else if (v.kind === "list") txt = v.items.length ? v.items.join(", ") : "[]";
      else txt = v.text === null || v.text === undefined ? "—" : String(v.text);
      dl.append(h("dt", {}, k), h("dd", {}, txt));
    }
    return h("div", { class: "preview" }, dl);
  }
  return null;
}

// ------------------------------------------------------------------ result sections
function sectionEl(s) {
  const title = s.title ? h("h4", { class: "sec-title" }, s.title, s.type === "table" && s.total ? h("span", { class: "count" }, `${s.total} rows`) : "") : null;
  switch (s.type) {
    case "kpis":
      return h("div", { class: "kpis" }, s.items.map((k) => h("div", { class: `kpi ${k.tone || ""}` }, h("div", { class: "kpi-v" }, k.value), h("div", { class: "kpi-l" }, k.label))));
    case "alert":
    case "summary": {
      const tone = s.tone || "info";
      const ic = { warn: "warn", danger: "danger", success: "ok", info: "info" }[tone] || "info";
      return h("div", { class: `alert ${tone}` }, icon(ic), h("div", {}, s.title ? h("b", {}, s.title) : null, s.text));
    }
    case "table":
      return h("div", {}, title, table(s.columns, s.rows, { tones: s.tones, total: s.total, empty: s.empty }));
    case "content":
      return h("div", {}, title, h("div", { class: "content-fields" }, s.fields.map((f) => {
        const copy = h("button", { class: "copy-btn", type: "button", title: "Copy", "aria-label": `Copy ${f.label}` }, icon("copy"));
        copy.onclick = () => navigator.clipboard?.writeText(f.value).then(() => toast(`${f.label} copied`));
        return h("div", { class: "cfield" }, h("div", { class: "cfield-top" }, h("span", { class: "cfield-label" }, f.label), f.meta ? h("span", { class: "cfield-meta" }, f.meta) : null, f.copy !== false ? copy : null), h("div", { class: "cfield-value" }, f.value));
      })));
    case "record":
      return h("div", {}, title, h("div", { class: "record" }, s.items.map((i) => h("div", { class: `rec-item ${i.tone || ""}` }, h("div", { class: "rec-l" }, i.label), h("div", { class: "rec-v" }, i.value || "—")))));
    case "list":
      return h("div", {}, title, h("ul", { class: "plain-list" }, s.items.map((i) => h("li", {}, i))));
    case "bars": {
      const max = Math.max(...s.items.map((i) => i.value), Number(s.threshold) || 0, 1) * 1.1;
      const box = h("div", { class: "bars" });
      s.items.forEach((i) => {
        const over = s.threshold !== null && s.threshold !== undefined && i.value > Number(s.threshold);
        const fill = h("div", { class: `bar-fill ${over ? "over" : ""}` });
        const track = h("div", { class: "bar-track" }, fill);
        if (s.threshold !== null && s.threshold !== undefined) track.append(h("div", { class: "bar-thr", style: { left: `${(Number(s.threshold) / max) * 100}%` } }));
        box.append(h("div", { class: "bar-row" }, h("div", { class: "bar-label", title: i.label }, i.label), track, h("div", { class: "bar-val" }, s.format === "pct" ? `${i.value.toFixed(1)}%` : fmt(i.value))));
        requestAnimationFrame(() => requestAnimationFrame(() => (fill.style.width = `${(i.value / max) * 100}%`)));
      });
      if (s.threshold !== null && s.threshold !== undefined) box.append(h("div", { class: "bar-legend" }, `Dashed line: threshold ${s.threshold}${s.format === "pct" ? "%" : ""}. Red bars are above it.`));
      return h("div", {}, title, box);
    }
    case "download":
      return h("div", { class: "downloads" }, s.files.map((f) => h("a", { class: "btn", href: API + f.url, download: f.filename }, icon("down"), f.label, f.rows !== undefined ? h("span", { class: "muted" }, `· ${f.rows} rows`) : "")));
    default:
      return null;
  }
}

function resultEl(r, status) {
  const label = { completed: "Completed", escalated: "Escalated", failed: "Failed", no_match: "No match", not_executable: "Not runnable" }[status] || status;
  return h("div", {},
    h("div", { class: "result-head" }, h("div", {}, h("h3", { class: "result-title" }, r.title || "Result"), r.subtitle ? h("p", { class: "result-sub" }, r.subtitle) : null), h("span", { class: `status-pill ${status}` }, label)),
    h("div", { class: "sections" }, (r.sections || []).map(sectionEl)));
}

// ------------------------------------------------------------------ streaming
async function stream(url, body, onEvent) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok || !res.body) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      for (const line of chunk.split("\n")) if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)));
    }
  }
}

// ------------------------------------------------------------------ run view
const STAGES = [["route", "Select workflow"], ["inputs", "Check inputs"], ["exec", "Run steps"], ["result", "Result"]];

class RunView {
  constructor(request, files) {
    this.queue = [];
    this.pumping = false;
    this.steps = new Map();
    this.total = 0;
    this.started = performance.now();
    this.runId = null;
    this.finished = false;
    this.shownAt = {};

    const stagesEl = h("div", { class: "stages" });
    this.stageEls = {};
    STAGES.forEach(([k, label], i) => {
      if (i) stagesEl.append(h("span", { class: "stage-sep" }));
      const el = h("span", { class: "stage" }, h("span", { class: "s-dot" }), label);
      this.stageEls[k] = el;
      stagesEl.append(el);
    });
    this.clock = h("span", { class: "run-clock" }, "0.0s");
    this.bar = h("div", { class: "progress-bar" });
    this.body = h("div", { class: "run-body" });
    this.el = h("div", { class: "turn" },
      h("div", { class: "req" }, h("div", {}, h("div", { class: "req-bubble" }, request), files.length ? h("div", { class: "req-files" }, files.map((f) => h("span", { class: "chip" }, icon("file"), f.name))) : null)),
      h("div", { class: "run" }, h("div", { class: "run-head" }, stagesEl, this.clock), h("div", { class: "progress" }, this.bar), this.body));
    this.tick = setInterval(() => {
      if (!this.waiting) this.clock.textContent = ((performance.now() - this.started) / 1000).toFixed(1) + "s";
    }, 100);
  }

  stage(key, cls) {
    const el = this.stageEls[key];
    el.classList.remove("active", "done", "wait", "fail");
    if (cls) el.classList.add(cls);
  }

  push(e) {
    this.queue.push(e);
    if (!this.pumping) this.pump();
  }

  async pump() {
    this.pumping = true;
    while (this.queue.length) {
      const e = this.queue.shift();
      if (e.type === "step_finished" && this.shownAt[e.step_id]) {
        const wait = 260 - (performance.now() - this.shownAt[e.step_id]);
        if (wait > 0) await sleep(wait);
      }
      if (e.type === "route") await sleep(Math.max(0, 420 - (performance.now() - this.started)));
      try {
        this.handle(e);
      } catch (err) {
        console.error("render error", err, e);
      }
      if (e.type === "step_started") await sleep(40);
      scrollThread();
    }
    this.pumping = false;
  }

  block(label, aside) {
    const b = h("div", { class: "block" });
    if (label) b.append(h("div", { class: "block-label" }, label, aside ? h("span", { class: "aside" }, aside) : null));
    this.body.append(b);
    return b;
  }

  handle(e) {
    if (e.run_id) this.runId = e.run_id;
    switch (e.type) {
      case "run_started":
        this.stage("route", "active");
        this.routeBlock = this.block("Workflow selection");
        this.routeBlock.append(h("div", { class: "step-summary shimmer" }, `Matching your request against the spreadsheet · ${e.llm}`));
        break;
      case "stage":
        if (e.stage === "extracting") this.stage("inputs", "active");
        if (e.stage === "executing") this.stage("exec", "active");
        break;
      case "route":
        this.renderRoute(e);
        break;
      case "inputs":
      case "input_check":
        this.renderInputs(e);
        break;
      case "params":
        this.params = e.params;
        this.renderParams();
        break;
      case "plan":
        this.renderPlan(e);
        break;
      case "step_started":
        this.stepState(e.step_id, "running", { summary: e.kind === "decision" ? "Evaluating rule…" : `Running ${e.tool}…`, shimmer: true });
        this.shownAt[e.step_id] = performance.now();
        break;
      case "step_log": {
        const s = this.steps.get(e.step_id);
        if (s) {
          s.logs.append(h("li", { class: e.level === "warn" ? "warn" : "" }, e.message));
          s.logs.style.display = "";
        }
        break;
      }
      case "step_retry": {
        const s = this.steps.get(e.step_id);
        if (s) {
          s.li.classList.add("retrying");
          s.retry.innerHTML = "";
          s.retry.append(icon("retry"), `Attempt ${e.attempt} failed — ${e.error}. Retrying in ${e.backoff_s}s`);
          s.retry.style.display = "";
        }
        break;
      }
      case "step_finished":
        this.finishStep(e);
        break;
      case "decision":
        this.renderDecision(e);
        break;
      case "rewind":
        this.rewind(e.to_step);
        break;
      case "ask":
        this.renderAsk(e);
        break;
      case "resumed":
        this.waiting = false;
        break;
      case "result":
        this.renderResult(e);
        break;
      case "run_finished":
        this.done(e.status);
        break;
      case "error":
        this.block().append(h("div", { class: "alert danger" }, icon("danger"), h("div", {}, h("b", {}, "Something went wrong"), e.message)));
        this.done("failed");
        break;
      case "warning":
        this.block().append(h("div", { class: "alert warn" }, icon("warn"), e.message));
        break;
    }
  }

  renderRoute(e) {
    const b = this.routeBlock;
    b.innerHTML = "";
    b.append(h("div", { class: "block-label" }, "Workflow selection", h("span", { class: "aside" }, `${e.method === "llm" ? "LLM router" : e.method === "lexical" ? "Lexical router (offline)" : e.method === "user" ? "Chosen by you" : "Manual"}${e.duration_ms !== undefined ? " · " + ms(e.duration_ms) : ""}`)));
    if (!e.workflow_id) {
      b.append(h("div", { class: "route" }, h("div", { class: "route-title" }, h("span", { class: "route-name" }, "No matching workflow")), h("div", { class: "route-why" }, e.reasoning)));
      this.stage("route", "fail");
      return;
    }
    const pct = Math.round(e.confidence * 100);
    const low = e.status === "clarify";
    const fill = h("div", { class: `conf-fill ${low ? "low" : ""}` });
    const track = h("div", { class: "conf-track" }, fill, e.threshold ? h("div", { class: "conf-mark", style: { left: `${e.threshold * 100}%` }, title: `Ask below ${Math.round(e.threshold * 100)}%` }) : null);
    const grid = h("div", { class: "route" },
      h("div", { class: "route-title" }, h("span", { class: "route-id" }, e.workflow_id), h("span", { class: "route-name" }, e.workflow_name)),
      h("div", { class: "conf" }, h("div", { class: "conf-num" }, `${pct}%`), h("div", { class: "conf-cap" }, low ? "Low confidence: asking you" : "confidence"), track),
      h("div", { class: "route-why" }, e.reasoning),
      e.note ? h("div", { class: "route-note" }, e.note) : null,
      e.alternatives?.length ? h("div", { class: "alts" }, "Also considered:", e.alternatives.map((a) => h("span", { class: "chip" }, h("code", {}, a.id), a.name || ""))) : null);
    b.append(grid);
    requestAnimationFrame(() => requestAnimationFrame(() => (fill.style.width = `${pct}%`)));
    this.stage("route", low ? "wait" : "done");
    if (e.status === "not_executable") this.stage("inputs", "fail");
  }

  renderInputs(e) {
    if (!this.inputsBlock) this.inputsBlock = this.block("Inputs");
    const b = this.inputsBlock;
    b.innerHTML = "";
    b.append(h("div", { class: "block-label" }, "Inputs", h("span", { class: "aside" }, e.method === "llm" ? "Extracted by the LLM" : e.method === "user" ? "Updated with your answer" : e.method === "patterns" ? "Extracted with plan patterns" : "")));
    const missing = new Set(e.missing || []);
    const chips = h("div", { class: "inputs" });
    const srcLabel = { request: "from request", attachment: "attached", default: "default", you: "you" };
    (e.inputs || []).forEach((i) => {
      const has = i.value !== null && i.value !== undefined && i.value !== "" && !(Array.isArray(i.value) && !i.value.length);
      if (!has && !missing.has(i.name)) return;
      const src = (e.sources || {})[i.name];
      chips.append(h("span", { class: `input-chip ${missing.has(i.name) ? "missing" : ""} from-${src || ""}` },
        h("span", { class: "k" }, i.label), h("span", { class: "v", title: has ? String(i.value) : "" }, has ? fmt(i.value) : "needed"), src ? h("span", { class: "src" }, srcLabel[src] || src) : null));
    });
    if (!chips.children.length) chips.append(h("span", { class: "muted", style: { fontSize: "13.5px" } }, "No inputs needed beyond the defaults."));
    b.append(chips);
    this.paramsEl = h("div", { class: "params" });
    b.append(this.paramsEl);
    this.renderParams();
    if (e.type === "input_check") this.stage("inputs", e.ok ? "done" : "wait");
  }

  renderParams() {
    if (!this.paramsEl || !this.params?.length) return;
    this.paramsEl.innerHTML = "";
    this.paramsEl.append(h("span", {}, "Decision parameters:"));
    this.params.forEach((p) => this.paramsEl.append(h("span", { title: p.description }, h("b", {}, p.name.replace(/_/g, " ")), " = ", typeof p.value === "object" ? JSON.stringify(p.value) : String(p.value), " ", h("span", { class: p.source === "Excel decision logic" ? "from-excel" : "" }, `(${p.source === "Excel decision logic" ? "from Excel" : p.source})`))));
  }

  renderPlan(e) {
    this.total = e.steps.length;
    const b = this.block("Execution", `${e.plan_file} · ${e.steps.length} steps`);
    if (e.decision_logic) b.append(h("div", { class: "note" }, h("b", {}, "Rule from the spreadsheet: "), e.decision_logic));
    const rail = h("ol", { class: "rail" });
    e.steps.forEach((s) => {
      const node = h("span", { class: "node" }, icon(s.kind === "decision" ? "q" : "dot"));
      const summary = h("div", { class: "step-summary" });
      const meta = h("span", { class: "step-meta" });
      const logs = h("ul", { class: "logs", style: { display: "none" } });
      const retry = h("div", { class: "retry-line", style: { display: "none" } });
      const detail = h("div", { class: "step-detail" }, s.note ? h("div", { class: "note" }, s.note) : null, logs);
      const top = h("div", { class: "step-top", role: "button", tabindex: "0", "aria-expanded": "false" },
        icon("chev", "caret"), h("span", { class: "step-title" }, s.title),
        s.kind === "decision" ? h("span", { class: "step-tool" }, "decision") : h("span", { class: "step-tool" }, s.tool), meta);
      const li = h("li", { class: `step pending ${s.kind === "decision" ? "decision" : ""}` }, node,
        h("div", { class: "step-main" }, top,
          s.excel_text?.length ? h("div", { class: "step-excel" }, h("span", { class: "xl" }, `Excel ${s.excel_steps.join(", ")}`), s.excel_text.join(" · ")) : null,
          summary, retry, detail));
      const toggle = () => {
        li.classList.toggle("open");
        top.setAttribute("aria-expanded", li.classList.contains("open"));
      };
      top.onclick = toggle;
      top.onkeydown = (ev) => (ev.key === "Enter" || ev.key === " ") && (ev.preventDefault(), toggle());
      this.steps.set(s.id, { li, node, summary, meta, logs, retry, detail, def: s, previewEl: null });
      rail.append(li);
    });
    b.append(rail);
    this.rail = rail;
  }

  stepState(id, st, { summary, shimmer } = {}) {
    const s = this.steps.get(id);
    if (!s) return;
    s.li.classList.remove("pending", "running", "done", "failed", "skipped", "waiting", "retrying");
    s.li.classList.add(st);
    s.node.innerHTML = "";
    s.node.append(icon({ done: "check", failed: "x", skipped: "dash", waiting: "q", running: s.def.kind === "decision" ? "q" : "dot", pending: s.def.kind === "decision" ? "q" : "dot" }[st]));
    if (summary !== undefined) {
      s.summary.textContent = summary;
      s.summary.classList.toggle("shimmer", !!shimmer);
    }
  }

  finishStep(e) {
    const s = this.steps.get(e.step_id);
    if (!s) return;
    const st = e.status === "ok" ? "done" : e.status === "failed" ? "failed" : "skipped";
    // decision steps keep the rule line rendered by the "decision" event
    this.stepState(e.step_id, st, e.kind === "decision" && e.status === "ok" ? {} : { summary: e.summary });
    s.retry.style.display = e.attempts > 1 ? "" : "none";
    if (e.attempts > 1) {
      s.retry.innerHTML = "";
      s.retry.append(icon("ok"), `Succeeded on attempt ${e.attempts}`);
      s.retry.style.color = "var(--ok)";
    }
    s.meta.innerHTML = "";
    if (e.engine === "llm") s.meta.append(h("span", { class: "chip llm" }, "LLM"));
    if (e.engine === "rules" && s.def.llm) s.meta.append(h("span", { class: "chip warn", title: "LLM not available: deterministic fallback used" }, "Fallback"));
    if (s.def.api) s.meta.append(h("span", { class: "chip step-tool-chip" }, s.def.api));
    s.meta.append(h("span", {}, ms(e.duration_ms || 0)));
    if (s.previewEl) s.previewEl.remove();
    s.previewEl = e.preview ? previewEl(e.preview) : null;
    if (s.previewEl) s.detail.append(s.previewEl);
    if (e.status === "failed") s.li.classList.add("open");
    const done = [...this.steps.values()].filter((x) => x.li.classList.contains("done") || x.li.classList.contains("skipped")).length;
    this.bar.style.width = `${Math.min(100, (done / Math.max(1, this.total)) * 100)}%`;
  }

  renderDecision(e) {
    const s = this.steps.get(e.step_id);
    if (!s) return;
    const actionChip = { continue: ["Continue", "ok"], complete: ["Stop: done", "ok"], ask: ["Ask you", "ask"], escalate: ["Escalate", "warn"], fail: ["Fail", "danger"], goto: ["Jump", "run"] }[e.action] || [e.action, ""];
    s.summary.innerHTML = "";
    s.summary.classList.remove("shimmer");
    s.summary.append(h("div", { class: "decision-line" }, h("code", {}, e.expression), "→", h("span", { class: `chip ${e.result ? "run" : ""}` }, e.result ? "true" : "false"), "→", h("span", { class: `chip ${actionChip[1]}` }, actionChip[0])));
    if (e.message && e.action !== "ask") s.summary.append(h("div", { class: "decision-msg" }, e.message));
  }

  rewind(toStep) {
    let hit = false;
    for (const [id, s] of this.steps) {
      if (id === toStep) hit = true;
      if (hit) {
        this.stepState(id, "pending", { summary: "" });
        s.meta.innerHTML = "";
        s.logs.innerHTML = "";
        s.logs.style.display = "none";
        s.retry.style.display = "none";
        if (s.previewEl) s.previewEl.remove();
        s.li.classList.remove("open");
      }
    }
    this.stage("exec", "active");
    this.bar.classList.remove("wait");
  }

  renderAsk(e) {
    this.waiting = true;
    this.clock.textContent = "Waiting for you";
    this.bar.classList.add("wait");
    if (e.kind === "workflow") this.stage("route", "wait");
    else if (e.kind === "inputs") this.stage("inputs", "wait");
    else {
      this.stage("exec", "wait");
      const s = this.steps.get(e.step_id);
      if (s) this.stepState(e.step_id, "waiting");
    }
    const card = h("div", { class: "ask-card" }, h("div", { class: "ask-head" }, icon("q"), h("div", { class: "ask-msg" }, e.message)));
    const b = this.block();
    b.append(card);
    const collect = {};
    const finish = async (value, summaryText) => {
      b.innerHTML = "";
      b.append(h("div", { class: "ask-answered" }, icon("person"), h("span", {}, "You answered:"), summaryText));
      this.waiting = false;
      this.bar.classList.remove("wait");
      if (e.kind === "inputs") this.stage("inputs", "active");
      if (e.kind === "workflow") this.stage("route", "done");
      await runStream(this, `${API}/api/runs/${this.runId}/resume`, { value });
    };
    if (e.kind === "workflow") {
      const opts = h("div", { class: "options" });
      e.options.forEach((o) => opts.append(h("button", { class: "option-btn", type: "button", onclick: () => finish({ workflow_id: o.id }, h("span", { class: "chip" }, h("code", {}, o.id), o.name)) }, h("span", { class: "route-id" }, o.id), o.name)));
      card.append(opts);
      return;
    }
    const form = h("form", { class: "ask-form" });
    const fields = e.fields.map((f) => this.fieldEl(f, collect));
    const dates = fields.filter((x) => x.dataset.type === "date");
    if (dates.length > 1) {
      const row = h("div", { class: "field-row" });
      fields.forEach((x) => x.dataset.type === "date" && row.append(x));
      form.append(...fields.filter((x) => x.dataset.type !== "date"), row);
    } else form.append(...fields);
    const submit = h("button", { class: "btn ask", type: "submit" }, "Continue");
    form.append(h("div", { class: "ask-actions" }, submit));
    form.onsubmit = (ev) => {
      ev.preventDefault();
      const value = {};
      for (const f of e.fields) {
        const v = collect[f.name]?.();
        if (f.required !== false && (v === undefined || v === null || v === "")) {
          toast(`Please fill in ${f.label.toLowerCase()}`);
          return;
        }
        value[f.name] = v;
      }
      submit.disabled = true;
      const summary = h("span", {}, e.fields.map((f) => h("span", { class: "chip ask", style: { marginRight: "6px" } }, `${f.label}: ${collect[f.name]?.label?.() ?? value[f.name]}`)));
      finish(value, summary);
    };
    card.append(form);
    setTimeout(() => form.querySelector("input, textarea")?.focus({ preventScroll: true }), 50);
  }

  fieldEl(f, collect) {
    const id = `f-${Math.random().toString(36).slice(2, 8)}`;
    const wrap = h("div", { class: "field" });
    wrap.dataset.type = f.type;
    wrap.append(h("label", { for: id }, f.label));
    if (f.type === "file") {
      let chosen = null;
      const status = h("span", { class: "muted", style: { fontSize: "13px" } });
      const picker = h("input", { type: "file", hidden: true, accept: (f.accept || []).join(",") });
      const up = h("button", { class: "btn", type: "button" }, icon("file"), "Upload file");
      up.onclick = () => picker.click();
      picker.onchange = async () => {
        const file = picker.files[0];
        if (!file) return;
        status.textContent = "Uploading…";
        try {
          const meta = await uploadFile(file);
          chosen = { value: `upload:${meta.id}`, label: meta.name };
          status.textContent = `Attached ${meta.name}`;
        } catch (err) {
          status.textContent = err.message;
        }
      };
      const row = h("div", { class: "file-field" }, up, picker);
      if (f.sample) {
        const sample = h("button", { class: "btn", type: "button" }, icon("sheet"), `Use sample (${f.sample})`);
        sample.onclick = () => {
          chosen = { value: "__sample__", label: f.sample };
          status.textContent = `Using ${f.sample}`;
        };
        row.append(sample);
      }
      row.append(status);
      wrap.append(row);
      collect[f.name] = () => chosen?.value;
      collect[f.name].label = () => chosen?.label;
      return wrap;
    }
    if (f.type === "choice" && f.choices?.length) {
      let val = null;
      const seg = h("div", { class: "seg", role: "radiogroup" });
      f.choices.forEach((c) => {
        const btn = h("button", { type: "button", role: "radio", "aria-checked": "false" }, c);
        btn.onclick = () => {
          val = c;
          $$("button", seg).forEach((x) => (x.classList.remove("on"), x.setAttribute("aria-checked", "false")));
          btn.classList.add("on");
          btn.setAttribute("aria-checked", "true");
        };
        seg.append(btn);
      });
      wrap.append(seg);
      collect[f.name] = () => val;
      return wrap;
    }
    let input;
    if (f.multiline) input = h("textarea", { id, rows: 3, placeholder: f.description || "" });
    else if (f.type === "date") input = h("input", { id, type: "date" });
    else if (f.type === "number") input = h("input", { id, type: "number", step: "any" });
    else input = h("input", { id, type: "text", placeholder: f.type === "list" ? "Comma-separated" : f.description || "" });
    input.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey && input.tagName === "TEXTAREA") {
        ev.preventDefault();
        input.form?.requestSubmit();
      }
    });
    wrap.append(input);
    if (f.description && f.type !== "text" && !f.multiline) wrap.append(h("span", { class: "hint" }, f.description));
    collect[f.name] = () => input.value.trim();
    return wrap;
  }

  renderResult(e) {
    this.stage("exec", e.status === "failed" ? "fail" : this.total ? "done" : "");
    this.stage("result", e.status === "failed" ? "fail" : "done");
    const b = this.block();
    b.append(resultEl(e, e.status));
  }

  done(status) {
    if (this.finished) return;
    this.finished = true;
    this.waiting = false;
    clearInterval(this.tick);
    this.clock.textContent = ((performance.now() - this.started) / 1000).toFixed(1) + "s";
    this.bar.style.width = "100%";
    this.bar.classList.remove("wait");
    this.bar.classList.add(status === "failed" ? "fail" : "ok");
    ["route", "inputs", "exec"].forEach((k) => {
      if (this.stageEls[k].classList.contains("active")) this.stage(k, status === "failed" ? "fail" : "done");
    });
    setBusy(false);
  }
}

async function runStream(view, url, body) {
  setBusy(true);
  try {
    await stream(url, body, (e) => view.push(e));
  } catch (err) {
    view.push({ type: "error", message: err.message });
  }
  // stream closed: if the run is waiting for input we stay "not busy" so the user can answer
  const waitDone = () => (view.pumping ? setTimeout(waitDone, 60) : (!view.finished && view.waiting && setBusy(false)));
  waitDone();
}

function scrollThread() {
  const t = $("#thread");
  const nearBottom = t.scrollHeight - t.scrollTop - t.clientHeight < 260;
  if (nearBottom) t.scrollTop = t.scrollHeight;
}

function setBusy(b) {
  state.busy = b;
  $("#sendBtn").disabled = b;
}

async function uploadFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(API + "/api/upload", { method: "POST", body: fd });
  if (!res.ok) throw new Error((await res.json()).detail || "Upload failed");
  return res.json();
}

async function submit(text) {
  text = (text ?? $("#input").value).trim();
  if (!text || state.busy) return;
  $("#intro")?.remove();
  const files = state.attachments.slice();
  const view = new RunView(text, files);
  $("#thread").append(view.el);
  $("#thread").scrollTop = $("#thread").scrollHeight;
  $("#input").value = "";
  autosize();
  state.attachments = [];
  renderAttachments();
  const options = $("#faultToggle").checked ? { fault_rate: 1.0 } : {};
  await runStream(view, API + "/api/runs", { message: text, files: files.map((f) => f.id), options });
}

// ------------------------------------------------------------------ composer
function autosize() {
  const t = $("#input");
  t.style.height = "auto";
  t.style.height = Math.min(180, t.scrollHeight) + "px";
}
function renderAttachments() {
  const box = $("#attachments");
  box.innerHTML = "";
  state.attachments.forEach((f, i) => {
    const rm = h("button", { type: "button", "aria-label": `Remove ${f.name}` }, icon("close"));
    rm.onclick = () => (state.attachments.splice(i, 1), renderAttachments());
    box.append(h("span", { class: "file-chip" }, icon("file"), f.name, rm));
  });
}

// ------------------------------------------------------------------ sidebar / status
async function loadAll() {
  const [st, wf] = await Promise.all([fetch(API + "/api/status").then((r) => r.json()), fetch(API + "/api/workflows").then((r) => r.json())]);
  state.status = st;
  state.workflows = wf.workflows;
  const pill = $("#modePill");
  pill.className = `mode-pill ${st.llm_enabled ? "llm" : "offline"}`;
  $(".label", pill).textContent = st.llm_enabled ? st.llm : "Offline mode";
  pill.title = st.llm_enabled ? "LLM routing, extraction and generation" : "No API key configured: lexical routing and template fallbacks";
  const list = $("#wfList");
  list.innerHTML = "";
  wf.workflows.forEach((w) => {
    const btn = h("button", { type: "button", title: w.trigger }, h("span", { class: "wf-id" }, w.id), h("span", { class: "wf-name" }, w.name), h("span", { class: `wf-dot ${w.executable ? "" : "off"}`, title: w.executable ? "Ready" : "No valid plan" }));
    btn.onclick = () => {
      showView("console");
      const req = w.test_requests[0]?.request || w.examples[0] || w.trigger;
      $("#input").value = req;
      autosize();
      $("#input").focus();
      $("#sidebar").classList.remove("open");
    };
    list.append(h("li", {}, btn));
  });
  $("#sideFoot").innerHTML = "";
  $("#sideFoot").append(
    h("div", {}, h("b", {}, st.workflow_file)),
    h("div", {}, `${st.executable} of ${st.workflows} workflows ready · ${st.tools} tools`));
  if (st.problems.length) $("#sideFoot").append(h("div", { style: { color: "#E2A84B" } }, `${st.problems.length} problem(s) loading plans`));
  const src = $("#introSource");
  if (src) {
    src.innerHTML = "";
    src.append(h("span", {}, icon("sheet"), `${st.workflows} workflows from ${st.workflow_file}`), h("span", {}, icon("tool"), `${st.tools} reusable tools`), h("span", {}, icon("info"), st.llm_enabled ? st.llm : "Offline mode: deterministic fallbacks"));
    const sug = $("#suggestions");
    sug.innerHTML = "";
    wf.workflows.forEach((w) => {
      const t = w.test_requests[0];
      if (!t) return;
      sug.append(h("button", { class: "suggestion", type: "button", onclick: () => submit(t.request) }, h("span", { class: "s-text" }, t.request), h("span", { class: "s-meta" }, h("code", {}, w.id), ` ${t.check}`)));
    });
  }
  renderWorkflowsPage(wf);
}

async function reload() {
  await fetch(API + "/api/workflows/reload", { method: "POST" });
  await loadAll();
  toast("Workflows reloaded from Excel");
}

// ------------------------------------------------------------------ workflows page
function renderWorkflowsPage(wf) {
  $("#wfPageSub").textContent = `Each row of ${wf.workflow_file}, next to the execution plan that runs it. Adding a row plus a plan file adds a workflow — no code changes.`;
  const probs = $("#problems");
  probs.innerHTML = "";
  wf.problems.forEach((p) => probs.append(h("div", { class: "alert danger", style: { marginBottom: "10px" } }, icon("danger"), p)));
  const list = $("#wfDetails");
  const open = new Set($$(".wfd.open", list).map((x) => x.dataset.id));
  list.innerHTML = "";
  wf.workflows.forEach((w) => {
    const card = h("div", { class: `wfd ${open.has(w.id) ? "open" : ""}`, "data-id": w.id });
    const head = h("div", { class: "wfd-head", role: "button", tabindex: "0" }, icon("chev", "caret"), h("span", { class: "route-id" }, w.id),
      h("div", { class: "grow" }, h("h3", {}, w.name), h("div", { class: "trig" }, w.trigger)),
      w.executable ? h("span", { class: "chip ok" }, `${w.steps.length} plan steps`) : h("span", { class: "chip warn" }, "Needs a plan"));
    head.onclick = () => card.classList.toggle("open");
    head.onkeydown = (ev) => ev.key === "Enter" && card.classList.toggle("open");
    const xl = h("div", { class: "wfd-col" },
      h("div", { class: "col-label" }, icon("sheet"), `Excel row ${w.excel_row}`),
      h("dl", { class: "xl-meta" }, h("dt", {}, "Inputs"), h("dd", {}, w.inputs_text), h("dt", {}, "Decision logic"), h("dd", {}, w.decision_logic), h("dt", {}, "Tools"), h("dd", {}, w.tools.join(", ")), h("dt", {}, "Expected output"), h("dd", {}, w.expected_output)),
      h("div", { class: "col-label" }, "Steps"),
      h("ol", { class: "xl-steps" }, w.excel_steps.map((s) => h("li", {}, s))));
    const plan = h("div", { class: "wfd-col" }, h("div", { class: "col-label" }, icon("tool"), w.plan_file ? `Execution plan · ${w.plan_file}` : "No execution plan"));
    if (w.steps.length) {
      plan.append(h("ul", { class: "plan-steps" }, w.steps.map((s) => h("li", { class: `kind-${s.kind}` }, h("span", { class: "xl" }, s.excel_steps.length ? `XL ${s.excel_steps.join(",")}` : ""), h("span", {}, s.title, s.when ? h("span", { class: "muted" }, ` · if ${s.when}`) : ""), h("span", { class: "tool" }, s.kind === "decision" ? "decision" : s.tool, s.llm ? " · LLM" : "")))));
    }
    if (w.params.length) plan.append(h("div", { class: "params", style: { marginTop: "12px" } }, "Parameters:", w.params.map((p) => h("span", { title: p.description }, h("b", {}, p.name), " = ", typeof p.value === "object" ? JSON.stringify(p.value) : String(p.value), " ", h("span", { class: p.source === "Excel decision logic" ? "from-excel" : "" }, `(${p.source === "Excel decision logic" ? "from Excel" : p.source})`)))));
    if (w.issues.length) plan.append(h("ul", { class: "issue-list" }, w.issues.map((i) => h("li", {}, i))));
    if (w.warnings.length) plan.append(h("ul", { class: "warn-list" }, w.warnings.map((i) => h("li", {}, i))));
    const foot = h("div", { class: "wfd-foot" });
    w.test_requests.forEach((t) => foot.append(h("button", { class: "btn", type: "button", onclick: () => (showView("console"), submit(t.request)), disabled: !w.executable }, "Run: ", h("span", { class: "muted" }, `“${t.request}”`))));
    if (!w.executable) {
      const draftBox = h("div");
      const btn = h("button", { class: "btn primary", type: "button" }, icon("tool"), "Draft a plan");
      btn.onclick = async () => {
        btn.disabled = true;
        btn.lastChild.textContent = "Drafting…";
        const d = await fetch(`${API}/api/workflows/${w.id}/draft`, { method: "POST" }).then((r) => r.json());
        draftBox.innerHTML = "";
        draftBox.append(h("div", { class: "muted", style: { fontSize: "13px", marginTop: "8px" } }, `Saved as workflows/plans/${d.file} (${d.method === "llm" ? "written by the LLM" : "offline skeleton"}). Review it, then rename to ${w.id}.yaml.`), d.issues?.length ? h("ul", { class: "warn-list" }, d.issues.slice(0, 8).map((i) => h("li", {}, i))) : null, h("pre", { class: "draft" }, d.yaml));
        btn.disabled = false;
        btn.lastChild.textContent = "Draft again";
      };
      foot.append(btn);
      plan.append(draftBox);
    }
    card.append(head, h("div", { class: "wfd-body" }, xl, plan), foot);
    list.append(card);
  });
}

// ------------------------------------------------------------------ runs page
async function renderRuns() {
  const data = await fetch(API + "/api/runs").then((r) => r.json());
  const box = $("#runsTable");
  box.innerHTML = "";
  $("#runDetail").innerHTML = "";
  if (!data.runs.length) {
    box.append(h("div", { class: "runs-wrap" }, h("div", { class: "empty" }, "No runs yet. Run a request from the console and it will appear here.")));
    return;
  }
  const label = { completed: "Completed", escalated: "Escalated", failed: "Failed", no_match: "No match", not_executable: "Not runnable" };
  const tbl = h("table", { class: "tbl runs-tbl" }, h("thead", {}, h("tr", {}, ["When", "Request", "Workflow", "Status", "Active time", "Routing"].map((c) => h("th", {}, c)))));
  const body = h("tbody");
  data.runs.forEach((r) => {
    const tr = h("tr", {},
      h("td", { class: "muted" }, r.finished_at?.slice(5, 16)), h("td", { class: "wrap" }, r.request),
      h("td", {}, r.workflow_id ? h("span", {}, h("code", {}, r.workflow_id), " ", r.workflow_name) : "—"),
      h("td", {}, h("span", { class: `status-pill ${r.status}`, style: { marginLeft: 0 } }, label[r.status] || r.status)),
      h("td", { class: "num" }, ms(r.active_ms || 0)),
      h("td", { class: "muted" }, r.route_method ? `${r.route_method} · ${Math.round((r.confidence || 0) * 100)}%` : "—"));
    tr.onclick = () => showRun(r.run_id);
    body.append(tr);
  });
  tbl.append(body);
  box.append(h("div", { class: "runs-wrap" }, tbl));
}

async function showRun(id) {
  const r = await fetch(`${API}/api/runs/${id}`).then((x) => x.json());
  const det = $("#runDetail");
  det.innerHTML = "";
  const rail = h("ol", { class: "rail" });
  r.trace.forEach((s) => {
    const st = s.status === "ok" ? "done" : s.status === "failed" ? "failed" : "skipped";
    rail.append(h("li", { class: `step ${st} ${s.kind === "decision" ? "decision" : ""}` }, h("span", { class: "node" }, icon({ done: "check", failed: "x", skipped: "dash" }[st])),
      h("div", { class: "step-main" }, h("div", { class: "step-top" }, h("span", { class: "step-title" }, s.title), h("span", { class: "step-tool" }, s.tool || "decision"), h("span", { class: "step-meta" }, ms(s.duration_ms || 0))), h("div", { class: "step-summary" }, s.error || s.summary || ""))));
  });
  det.append(h("div", { class: "run detail-card" }, h("div", { class: "run-body" },
    h("div", { class: "block" }, h("div", { class: "block-label" }, "Request", h("span", { class: "aside" }, `${r.run_id} · ${r.finished_at}`)), h("div", { class: "req-bubble", style: { display: "inline-block", maxWidth: "100%" } }, r.request)),
    r.trace.length ? h("div", { class: "block" }, h("div", { class: "block-label" }, `Steps executed · ${r.workflow_id} ${r.workflow_name}`), rail) : null,
    h("div", { class: "block" }, resultEl(r.result, r.status)))));
  det.scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "start" });
}

// ------------------------------------------------------------------ navigation & boot
function showView(v) {
  $$(".view").forEach((x) => x.classList.toggle("active", x.id === `view-${v}`));
  $$(".nav-item").forEach((x) => x.classList.toggle("active", x.dataset.view === v));
  $("#viewTitle").textContent = { console: "Console", workflows: "Workflows", runs: "Run history" }[v];
  if (v === "runs") renderRuns();
  $("#sidebar").classList.remove("open");
}

function initTheme() {
  let t = null;
  try { t = localStorage.getItem("flowline-theme"); } catch { /* storage unavailable */ }
  if (t) document.documentElement.dataset.theme = t;
  $("#themeBtn").onclick = () => {
    const dark = document.documentElement.dataset.theme === "dark" || (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
    const next = dark ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("flowline-theme", next); } catch { /* ignore */ }
  };
}

function boot() {
  initTheme();
  $$(".nav-item").forEach((b) => (b.onclick = () => showView(b.dataset.view)));
  $("#menuBtn").onclick = () => $("#sidebar").classList.toggle("open");
  $("#reloadBtn").onclick = reload;
  $("#reloadBtn2").onclick = reload;
  $("#refreshRuns").onclick = renderRuns;
  $("#composer").onsubmit = (e) => (e.preventDefault(), submit());
  $("#input").addEventListener("input", autosize);
  $("#input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  });
  $("#fileInput").onchange = async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    try {
      const meta = await uploadFile(file);
      state.attachments.push(meta);
      renderAttachments();
    } catch (err) {
      toast(err.message);
    }
  };
  loadAll().catch((err) => {
    $(".label", $("#modePill")).textContent = "Backend unreachable";
    toast(`Could not reach the backend: ${err.message}`);
  });
}

boot();