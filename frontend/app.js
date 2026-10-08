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
  search: '<circle cx="9" cy="9" r="5.5"/><path d="M13 13l4 4"/>',
  play: '<path d="M6.5 4.5v11l9-5.5z"/>',
  console: '<path d="M3 5h14M3 10h9M3 15h6"/>',
  chart: '<path d="M3 16.5h14M5.5 13V9M10 13V5M14.5 13v-6"/>',
  history: '<circle cx="10" cy="10" r="7"/><path d="M10 6v4l3 2"/>',
  map: '<circle cx="5" cy="4.5" r="2"/><circle cx="5" cy="15.5" r="2"/><circle cx="15" cy="10" r="2"/><path d="M5 6.5v7M6.8 5.5 13.3 9M6.8 14.5l6.5-3.5"/>',
  bolt: '<path d="M11 2.5 4.5 11H10l-1 6.5L15.5 9H10z"/>',
  moon: '<path d="M10 3a7 7 0 1 0 7 7 5.5 5.5 0 0 1-7-7z"/>',
  expand: '<path d="M4 8V4h4M16 8V4h-4M4 12v4h4M16 12v4h-4"/>',
  md: '<rect x="2.5" y="4.5" width="15" height="11" rx="2"/><path d="M5.5 12.5v-5l2 2.5 2-2.5v5M13.5 7.5v5M11.8 10.8l1.7 1.7 1.7-1.7"/>',
  trash: '<path d="M4 6h12M8 6V4.5h4V6M6 6l.8 10h6.4L14 6"/>',
  keys: '<rect x="2.5" y="5" width="15" height="10" rx="2"/><path d="M5.5 8h1M8.5 8h1M11.5 8h1M6.5 12h7"/>',
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
const toast = (msg, ic = "ok") => {
  const t = $("#toast");
  t.innerHTML = "";
  t.append(icon(ic), msg);
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 2200);
};

const copyText = (text, msg) =>
  (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject(new Error("no clipboard")))
    .then(() => toast(msg))
    .catch(() => toast("The browser blocked copying. Select the text and copy it manually.", "warn"));

// ------------------------------------------------------------------ smart tables
const csvCell = (v) => {
  if (v === null || v === undefined) return "";
  const t = Array.isArray(v) ? v.join("; ") : typeof v === "object" ? JSON.stringify(v) : String(v);
  return /[",\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t;
};
const cmp = (a, b) => {
  const na = a === null || a === undefined || a === "", nb = b === null || b === undefined || b === "";
  if (na || nb) return na === nb ? 0 : na ? 1 : -1;            // empty values always last
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
};

// Sortable, filterable table with CSV copy. `tools` adds the toolbar for bigger tables.
function table(columns, rows, { tones = null, limit = 10, total = null, empty = "No rows", tools = true, title = "table" } = {}) {
  if (!rows.length) return h("div", { class: "preview" }, h("div", { class: "empty", style: { padding: "16px" } }, empty));
  const cols = columns.map((c) => (typeof c === "string" ? { key: c, label: c.replace(/_/g, " ") } : c));
  const numeric = Object.fromEntries(cols.map((c) => [c.key, isNumCol(rows, c.key)]));
  let order = rows.map((_, i) => i);
  let sortKey = null, dir = 1, query = "", expanded = false;
  const body = h("tbody");
  const foot = h("div", { class: "tbl-more" });
  const ths = cols.map((c) => {
    const ind = h("span", { class: "sort-ind" });
    const th = h("th", { class: `${numeric[c.key] ? "num " : ""}sortable`, tabindex: "0", "aria-sort": "none", title: "Sort" }, c.label, ind);
    const go = () => {
      if (sortKey === c.key) dir = -dir;
      else (sortKey = c.key), (dir = numeric[c.key] ? -1 : 1);
      order = rows.map((_, i) => i).sort((a, b) => cmp(rows[a][c.key], rows[b][c.key]) * dir);
      ths.forEach((x) => (x.setAttribute("aria-sort", "none"), (x.lastChild.textContent = "")));
      th.setAttribute("aria-sort", dir > 0 ? "ascending" : "descending");
      ind.textContent = dir > 0 ? "▲" : "▼";
      draw();
    };
    th.onclick = go;
    th.onkeydown = (ev) => (ev.key === "Enter" || ev.key === " ") && (ev.preventDefault(), go());
    return th;
  });
  const visible = () => (query ? order.filter((i) => cols.some((c) => String(rows[i][c.key] ?? "").toLowerCase().includes(query))) : order);
  const draw = () => {
    body.innerHTML = "";
    const vis = visible();
    const n = expanded ? vis.length : Math.min(limit, vis.length);
    vis.slice(0, n).forEach((i) => {
      const r = rows[i];
      const tone = tones && tones[i];
      body.append(h("tr", { class: tone ? `tone-${tone}` : "" }, cols.map((c) => {
        const v = r[c.key];
        const long = typeof v === "string" && v.length > 48;
        const short = typeof v === "string" && v.length <= 14;
        return h("td", { class: (numeric[c.key] ? "num" : "") + (long ? " wrap" : "") + (short ? " nowrap" : "") }, fmt(v, c.key));
      })));
    });
    if (!vis.length) body.append(h("tr", {}, h("td", { colspan: cols.length, class: "muted" }, `Nothing matches “${query}”`)));
    foot.innerHTML = "";
    const count = query ? vis.length : (total ?? rows.length);
    const shown = h("span", {}, `${n} of ${count} rows${query ? " matching" : ""}${total && total > rows.length && !query ? ` (first ${rows.length} included)` : ""}`);
    foot.append(shown);
    if (vis.length > limit) {
      const btn = h("button", { class: "link-btn", type: "button" }, expanded ? "Show fewer" : `Show all ${vis.length}`);
      btn.onclick = () => ((expanded = !expanded), draw());
      foot.append(btn);
    }
    foot.style.display = count > limit || query || (total && total > rows.length) ? "" : "none";
  };
  const tbl = h("table", { class: "tbl" }, h("thead", {}, h("tr", {}, ths)), body);
  draw();
  const box = h("div", { class: "tbl-box" });
  if (tools && rows.length > 5) {
    const inp = h("input", { type: "search", placeholder: `Filter ${rows.length} rows`, "aria-label": "Filter rows" });
    inp.oninput = () => ((query = inp.value.trim().toLowerCase()), draw());
    const copy = h("button", { class: "btn ghost", type: "button", title: "Copy as CSV" }, icon("copy"), "Copy CSV");
    copy.onclick = () => {
      const lines = [cols.map((c) => csvCell(c.label)).join(","), ...visible().map((i) => cols.map((c) => csvCell(rows[i][c.key])).join(","))];
      copyText(lines.join("\n"), `Copied ${lines.length - 1} rows of ${title} as CSV`);
    };
    box.append(h("div", { class: "tbl-tools" }, h("label", { class: "filter" }, icon("search"), inp), h("span", { class: "spacer" }), copy));
  }
  box.append(h("div", { class: "preview" }, tbl), foot);
  return box;
}

function previewEl(p) {
  if (!p) return null;
  if (p.kind === "table") return table(p.columns, p.rows, { total: p.total, limit: 5, empty: "Empty table", tools: false });
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
      return h("div", {}, title, table(s.columns, s.rows, { tones: s.tones, total: s.total, empty: s.empty, title: s.title || "table" }));
    case "content":
      return h("div", {}, title, h("div", { class: "content-fields" }, s.fields.map((f) => {
        const copy = h("button", { class: "copy-btn", type: "button", title: "Copy", "aria-label": `Copy ${f.label}` }, icon("copy"));
        copy.onclick = () => copyText(f.value, `${f.label} copied`);
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

// ------------------------------------------------------------------ flow map
// The live graph beside the console. It follows the most recent run: nodes light up as
// steps run, the spectrum fill grows down the path actually taken, skipped steps dim,
// decisions show their outcome, and jumps (goto / resume after a question) draw an arc.
class FlowMap {
  constructor(el) {
    this.el = el;
    this.owner = null;
    this.empty();
  }

  legend() {
    return h("div", { class: "fm-foot" }, [["Done", "var(--s2)"], ["Running", "var(--s3)"], ["Needs you", "var(--ask)"], ["Skipped", "var(--rule-strong)"]]
      .map(([l, c]) => h("span", {}, h("i", { style: { background: c } }), l)));
  }

  empty() {
    this.el.innerHTML = "";
    this.el.append(
      h("div", { class: "fm-head" }, h("div", { class: "fm-kicker" }, h("span", { class: "live" }), "Flow map"), h("h3", { class: "fm-title" }, "Waiting for a request")),
      h("div", { class: "fm-body" }, h("div", { class: "fm-empty" },
        "Run a request and its plan appears here as a live graph: the path the agent takes, the rules it checks and the steps it skips.",
        h("div", { class: "ghost" }, ["72%", "54%", "63%", "47%", "58%"].map((w) => h("i", { style: { "--w": w } }))),
        "Click any step to jump to its details.")),
      this.legend());
  }

  attach(view) {
    this.owner = view;
    this.nodes = new Map();
    this.order = [];
    this.reached = -1;
    this.planned = null;
    this.el.innerHTML = "";
    this.live = h("span", { class: "live on" });
    this.kicker = h("div", { class: "fm-kicker" }, this.live, h("span", {}, "Live run"));
    this.title = h("h3", { class: "fm-title" }, "Selecting a workflow…");
    this.statEls = {};
    const stats = h("div", { class: "fm-stats" }, [["steps", "steps"], ["llm", "LLM"], ["api", "API"], ["retries", "retries"]].map(([k, l]) => {
      const b = h("b", {}, k === "steps" ? "–" : "0");
      this.statEls[k] = b;
      return h("div", { class: `fm-stat ${k === "llm" ? "llm" : k === "retries" ? "retry" : ""}` }, b, h("span", {}, l));
    }));
    this.body = h("div", { class: "fm-body" }, h("div", { class: "fm-empty" }, h("span", { class: "shimmer" }, `Matching “${view.request}” against the spreadsheet…`)));
    this.el.append(h("div", { class: "fm-head" }, this.kicker, this.title, stats), this.body, this.legend());
  }

  stats(c, total) {
    if (!this.statEls) return;
    this.statEls.steps.textContent = total ? `${c.steps}/${total}` : "–";
    this.statEls.llm.textContent = c.llm;
    this.statEls.api.textContent = c.api;
    this.statEls.retries.textContent = c.retries;
  }

  route(e) {
    this.title.innerHTML = "";
    if (!e.workflow_id) {
      this.title.append("No matching workflow");
      this.body.innerHTML = "";
      this.body.append(h("div", { class: "fm-empty" }, e.reasoning || "Nothing in the spreadsheet fits this request."));
      return;
    }
    this.title.append(h("code", {}, e.workflow_id), e.workflow_name);
    if (e.status === "clarify") {
      this.status("wait", "Waiting for you to pick a workflow");
      this.body.innerHTML = "";
      this.body.append(h("div", { class: "fm-empty" }, `Not sure enough to start: the best match is ${e.workflow_id} at ${Math.round((e.confidence || 0) * 100)}%. Pick a workflow in the console and its plan appears here.`));
      return;
    }
    // Draw the plan straight away from the catalogue, so it is visible while inputs are checked.
    const wf = state.workflows.find((w) => w.id === e.workflow_id);
    if (wf?.executable && wf.steps.length && this.planned !== wf.id) {
      this.plan(wf.steps);
      this.planned = wf.id;
    }
  }

  plan(steps) {
    this.body.innerHTML = "";
    const graph = h("div", { class: "fm-graph" });
    this.spine = h("div", { class: "fm-spine" });
    this.fill = h("div", { class: "fm-fill" });
    this.jumps = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    this.jumps.setAttribute("class", "fm-jumps");
    graph.append(this.spine, this.fill, this.jumps);
    steps.forEach((s, i) => {
      const dot = h("span", { class: "fm-dot" }, icon(s.kind === "decision" ? "q" : "dot"));
      const t = h("span", { class: "t" });
      const node = h("button", { class: `fm-node pending ${s.kind === "decision" ? "decision" : ""}`, type: "button", title: `${s.title} — show details` },
        dot, h("span", { class: "fm-label" }, h("span", { class: "fm-name" }, s.title),
          h("span", { class: "fm-sub" }, s.kind === "decision" ? "rule" : s.tool, s.llm ? h("span", { class: "fm-badge llm" }, "LLM") : null, s.api ? h("span", { class: "fm-badge api" }, "API") : null, t)));
      node.onclick = () => this.owner?.focusStep(s.id);
      this.nodes.set(s.id, { node, dot, t, i, kind: s.kind });
      this.order.push(s.id);
      graph.append(node);
    });
    this.body.append(graph);
    this.graph = graph;
    requestAnimationFrame(() => this.layout());
  }

  y(id) {
    const n = this.nodes.get(id);
    return n ? n.node.offsetTop + 19 : 0;
  }

  layout() {
    if (!this.order.length) return;
    const first = this.y(this.order[0]);
    this.spine.style.top = `${first}px`;
    this.spine.style.height = `${this.y(this.order[this.order.length - 1]) - first}px`;
    this.fill.style.top = `${first}px`;
  }

  reach(id) {
    const n = this.nodes.get(id);
    if (!n) return;
    if (this.reached >= 0 && Math.abs(n.i - this.reached) > 1) this.arc(this.order[this.reached], id);
    this.reached = n.i;
    this.fill.style.height = `${this.y(id) - this.y(this.order[0])}px`;
    const box = this.body;
    const top = n.node.offsetTop - box.clientHeight / 2;
    box.scrollTo({ top: Math.max(0, top), behavior: REDUCED ? "auto" : "smooth" });
  }

  arc(fromId, toId) {
    const a = this.y(fromId), b = this.y(toId);
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const bulge = -16 - Math.min(10, Math.abs(b - a) / 30);
    p.setAttribute("d", `M14 ${a} C ${bulge} ${a}, ${bulge} ${b}, 14 ${b}`);
    this.jumps.append(p);
  }

  set(id, st, ms_) {
    const n = this.nodes.get(id);
    if (!n) return;
    n.node.classList.remove("pending", "running", "done", "failed", "skipped", "waiting", "retrying");
    n.node.classList.add(st);
    n.dot.innerHTML = "";
    n.dot.append(icon({ done: "check", failed: "x", skipped: "dash", waiting: "q", retrying: "retry" }[st] || (n.kind === "decision" ? "q" : "dot")));
    if (ms_ !== undefined) n.t.textContent = ms(ms_);
    if (st === "running") {
      this.reach(id);
      this.fill.classList.add("moving");
      this.status("on", "Live run");
    }
  }

  decision(id, truth) {
    this.nodes.get(id)?.node.classList.toggle("dtrue", !!truth);
  }

  rewind(toId) {
    let hit = false;
    for (const id of this.order) {
      if (id === toId) hit = true;
      if (hit) {
        this.set(id, "pending");
        this.nodes.get(id).t.textContent = "";
      }
    }
  }

  status(cls, label) {
    if (!this.live) return;
    this.live.className = `live ${cls}`;
    this.kicker.lastChild.textContent = label;
    if (cls !== "on") this.fill?.classList.remove("moving");
  }

  done(status) {
    const label = { completed: "Completed", escalated: "Escalated", failed: "Failed", no_match: "No match", not_executable: "Not runnable" }[status] || status;
    this.status(status === "failed" ? "fail" : status === "completed" ? "done" : "wait", label);
  }
}
const flow = new FlowMap(document.getElementById("flowmap"));

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
    this.request = request;
    this.counts = { steps: 0, llm: 0, api: 0, retries: 0 };

    const stagesEl = h("div", { class: "stages" });
    this.stageEls = {};
    STAGES.forEach(([k, label], i) => {
      if (i) stagesEl.append(h("span", { class: "stage-sep" }));
      const el = h("span", { class: "stage" }, h("span", { class: "s-dot" }), label);
      this.stageEls[k] = el;
      stagesEl.append(el);
    });
    this.clock = h("span", { class: "run-clock" }, "0.0s");
    this.tm = {};
    const tmEl = h("div", { class: "telemetry" });
    [["steps", "Steps", "–"], ["llm", "LLM calls", "0"], ["api", "API calls", "0"], ["retries", "Retries", "0"]].forEach(([k, l, v]) => {
      const b = h("b", {}, v);
      const el = h("span", { class: `tm ${k === "llm" ? "llm" : k === "retries" ? "retry" : ""}` }, l, b);
      this.tm[k] = { el, b };
      tmEl.append(el);
    });
    this.bar = h("div", { class: "progress-bar running" });
    this.body = h("div", { class: "run-body" });
    this.el = h("div", { class: "turn" },
      h("div", { class: "req" }, h("div", {}, h("div", { class: "req-bubble" }, request), files.length ? h("div", { class: "req-files" }, files.map((f) => h("span", { class: "chip" }, icon("file"), f.name))) : null)),
      h("div", { class: "run" }, h("div", { class: "run-head" }, stagesEl, this.clock, tmEl), h("div", { class: "progress" }, this.bar), this.body));
    this.actions = h("div", { class: "run-actions", style: { display: "none" } });
    $(".run", this.el).append(this.actions);
    flow.attach(this);
    this.tick = setInterval(() => {
      if (!this.waiting) this.clock.textContent = ((performance.now() - this.started) / 1000).toFixed(1) + "s";
    }, 100);
  }

  stage(key, cls) {
    const el = this.stageEls[key];
    el.classList.remove("active", "done", "wait", "fail");
    if (cls) el.classList.add(cls);
  }

  get fm() {
    return flow.owner === this ? flow : null;
  }

  count(k, n = 1) {
    this.counts[k] += n;
    const t = this.tm[k];
    t.b.textContent = k === "steps" ? `${this.counts.steps}/${this.total || "–"}` : this.counts[k];
    t.el.classList.remove("bump");
    void t.el.offsetWidth;
    t.el.classList.add("bump");
    this.fm?.stats(this.counts, this.total);
  }

  focusStep(id) {
    const s = this.steps.get(id);
    if (!s) return;
    s.li.classList.add("open");
    s.li.scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "center" });
    s.li.classList.remove("flash");
    void s.li.offsetWidth;
    s.li.classList.add("flash");
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
        this.fm?.route(e);
        if (e.method === "llm") this.count("llm");
        markLive(e.workflow_id);
        break;
      case "inputs":
      case "input_check":
        this.renderInputs(e);
        if (e.type === "inputs" && e.method === "llm") this.count("llm");
        break;
      case "params":
        this.params = e.params;
        this.renderParams();
        break;
      case "plan":
        this.renderPlan(e);
        if (flow.planned !== e.workflow_id) this.fm?.plan(e.steps);
        if (this.fm) flow.planned = e.workflow_id;
        this.count("steps", 0);
        break;
      case "step_started":
        this.stepState(e.step_id, "running", { summary: e.kind === "decision" ? "Evaluating rule…" : `Running ${e.tool}…`, shimmer: true });
        this.shownAt[e.step_id] = performance.now();
        this.fm?.set(e.step_id, "running");
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
        this.fm?.set(e.step_id, "retrying");
        this.count("retries");
        this.count("api");
        break;
      }
      case "step_finished": {
        this.finishStep(e);
        const st = e.status === "ok" ? "done" : e.status === "failed" ? "failed" : "skipped";
        this.fm?.set(e.step_id, st, e.duration_ms || 0);
        if (e.status === "ok" && e.engine === "llm") this.count("llm");
        if (e.status !== "skipped" && this.steps.get(e.step_id)?.def.api) this.count("api");
        this.count("steps");
        break;
      }
      case "decision":
        this.renderDecision(e);
        this.fm?.decision(e.step_id, e.result);
        break;
      case "rewind":
        this.rewind(e.to_step);
        this.fm?.rewind(e.to_step);
        break;
      case "ask":
        this.renderAsk(e);
        break;
      case "resumed":
        this.waiting = false;
        this.bar.classList.add("running");
        break;
      case "result":
        this.renderResult(e);
        break;
      case "run_finished":
        this.done(e.status);
        this.fm?.done(e.status);
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
    this.plan = e;
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
    this.counts.steps = [...this.steps.values()].filter((x) => x.li.classList.contains("done") || x.li.classList.contains("skipped")).length;
    let hit = false;
    for (const [id, s] of this.steps) {
      if (id === toStep) hit = true;
      if (hit) {
        if (s.li.classList.contains("done") || s.li.classList.contains("skipped")) this.counts.steps -= 1;
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
    this.bar.classList.remove("running");
    this.fm?.status("wait", "Waiting for your answer");
    if (e.kind === "workflow") this.stage("route", "wait");
    else if (e.kind === "inputs") this.stage("inputs", "wait");
    else {
      this.stage("exec", "wait");
      const s = this.steps.get(e.step_id);
      if (s) this.stepState(e.step_id, "waiting");
      this.fm?.set(e.step_id, "waiting");
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
    this.result = e;
  }

  done(status) {
    if (this.finished) return;
    this.finished = true;
    this.status = status;
    this.waiting = false;
    clearInterval(this.tick);
    this.clock.textContent = ((performance.now() - this.started) / 1000).toFixed(1) + "s";
    this.bar.style.width = "100%";
    this.bar.classList.remove("wait");
    this.bar.classList.add(status === "failed" ? "fail" : "ok");
    this.bar.classList.remove("running");
    ["route", "inputs", "exec"].forEach((k) => {
      if (this.stageEls[k].classList.contains("active")) this.stage(k, status === "failed" ? "fail" : "done");
    });
    markLive(null);
    this.renderActions();
    setBusy(false);
  }

  renderActions() {
    const a = this.actions;
    a.innerHTML = "";
    const rerun = h("button", { class: "btn", type: "button" }, icon("retry"), "Run again");
    rerun.onclick = () => submit(this.request);
    a.append(rerun);
    if (this.result) {
      const md = h("button", { class: "btn", type: "button" }, icon("md"), "Copy as Markdown");
      md.onclick = () => copyText(toMarkdown(this.request, this.result), "Result copied as Markdown");
      a.append(md);
    }
    if (this.steps.size) {
      const exp = h("button", { class: "btn ghost", type: "button" }, icon("expand"), "Expand all steps");
      exp.onclick = () => {
        const open = exp.dataset.open !== "1";
        this.steps.forEach((s) => s.li.classList.toggle("open", open));
        exp.dataset.open = open ? "1" : "0";
        exp.lastChild.textContent = open ? "Collapse all steps" : "Expand all steps";
      };
      a.append(exp);
      const map = h("button", { class: "btn ghost", type: "button" }, icon("map"), "Show in flow map");
      map.onclick = () => this.replayMap();
      a.append(map);
    }
    a.style.display = "";
  }

  // Re-draw this run's path in the flow map (e.g. after a newer run took it over).
  replayMap() {
    if (!this.plan) return;
    setMap(true);
    flow.attach(this);
    flow.route({ workflow_id: this.plan.workflow_id, workflow_name: this.plan.workflow_name });
    if (flow.planned !== this.plan.workflow_id) flow.plan(this.plan.steps);
    requestAnimationFrame(() => {
      for (const [id, s] of this.steps) {
        const st = ["done", "failed", "skipped", "waiting"].find((c) => s.li.classList.contains(c));
        if (st) flow.set(id, st === "done" || st === "failed" ? "running" : st);
        if (st === "done" || st === "failed") flow.set(id, st);
      }
      flow.stats(this.counts, this.total);
      flow.done(this.status || "completed");
    });
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
  if (!text) return;
  if (state.busy) return toast("A run is still in progress. Answer or wait for it first.", "info");
  $("#intro")?.remove();
  $("#intent").classList.remove("show");
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
    list.append(h("li", { "data-id": w.id }, btn));
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
      sug.append(h("button", { class: "suggestion", type: "button", title: t.check, onclick: () => submit(t.request) },
        h("span", { class: "s-top" }, h("span", { class: "s-id" }, w.id), h("span", { class: "s-wf" }, w.name)),
        h("span", { class: "s-text" }, t.request), t.check ? h("span", { class: "s-meta" }, t.check) : null));
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
    const card = h("div", { class: `wfd ${open.has(w.id) ? "open" : ""}`, "data-id": w.id, "data-text": `${w.id} ${w.name} ${w.trigger} ${w.tools.join(" ")}`.toLowerCase() });
    const head = h("div", { class: "wfd-head", role: "button", tabindex: "0" }, icon("chev", "caret"), h("span", { class: "route-id" }, w.id),
      h("div", { class: "grow" }, h("h3", {}, w.name), h("div", { class: "trig" }, w.trigger)),
      h("span", { class: "wfd-spark", title: "Plan shape: tool steps, LLM steps and decisions" }, w.steps.map((s) => h("i", { class: s.kind === "decision" ? "decision" : s.llm ? "llm" : "tool" }))),
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
  filterWorkflows();
}

function filterWorkflows() {
  const q = ($("#wfFilter")?.value || "").trim().toLowerCase();
  $$(".wfd", $("#wfDetails")).forEach((c) => (c.style.display = !q || c.dataset.text.includes(q) ? "" : "none"));
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

// ------------------------------------------------------------------ markdown export
function toMarkdown(request, r) {
  const out = [`# ${r.title || "Result"}`, "", `**Request:** ${request}`, ""];
  if (r.subtitle) out.push(`_${r.subtitle}_`, "");
  const cell = (v) => (v === null || v === undefined ? "" : Array.isArray(v) ? v.join(", ") : String(v)).replace(/\|/g, "/").replace(/\n/g, " ");
  for (const s of r.sections || []) {
    if (s.title) out.push(`## ${s.title}`);
    if (s.type === "alert" || s.type === "summary") out.push(`> ${s.text}`);
    else if (s.type === "kpis") s.items.forEach((k) => out.push(`- ${k.label}: **${k.value}**`));
    else if (s.type === "table") {
      if (!s.rows.length) out.push(`_${s.empty || "No rows"}_`);
      else {
        const cols = s.columns.map((c) => (typeof c === "string" ? { key: c, label: c } : c));
        out.push(`| ${cols.map((c) => c.label).join(" | ")} |`, `|${cols.map(() => "---").join("|")}|`);
        s.rows.slice(0, 100).forEach((row) => out.push(`| ${cols.map((c) => cell(row[c.key])).join(" | ")} |`));
      }
    } else if (s.type === "content") s.fields.forEach((f) => out.push(`**${f.label}:** ${f.value}`, ""));
    else if (s.type === "record") s.items.forEach((i) => out.push(`- **${i.label}:** ${i.value ?? "—"}`));
    else if (s.type === "list") s.items.forEach((i) => out.push(`- ${i}`));
    else if (s.type === "bars") s.items.forEach((i) => out.push(`- ${i.label}: ${s.format === "pct" ? i.value.toFixed(1) + "%" : i.value}`));
    else if (s.type === "download") s.files.forEach((f) => out.push(`- ${f.label} (${f.rows ?? "?"} rows)`));
    out.push("");
  }
  return out.join("\n");
}

// ------------------------------------------------------------------ live helpers
function markLive(id) {
  $$("#wfList li").forEach((li) => li.classList.toggle("live", !!id && li.dataset.id === id));
}

function setMap(on) {
  const c = $(".console");
  const wide = matchMedia("(min-width: 1241px)").matches;
  c.classList.toggle("map-off", wide && !on);
  c.classList.toggle("map-on", !wide && on);
  $("#mapBtn").setAttribute("aria-pressed", String(on));
  try { localStorage.setItem("flowline-map", on ? "1" : "0"); } catch { /* storage unavailable */ }
}
const mapIsOn = () => $("#mapBtn").getAttribute("aria-pressed") === "true";

// Instant, LLM-free guess of the workflow while typing (the run itself may use the LLM router).
let intentTimer = null, intentSeq = 0;
function previewIntent() {
  clearTimeout(intentTimer);
  const el = $("#intent");
  const q = $("#input").value.trim();
  if (q.length < 4) return el.classList.remove("show");
  intentTimer = setTimeout(async () => {
    const seq = ++intentSeq;
    try {
      const r = await fetch(`${API}/api/route/preview?q=${encodeURIComponent(q)}`).then((x) => x.json());
      if (seq !== intentSeq || $("#input").value.trim() !== q) return;
      el.innerHTML = "";
      if (!r.workflow_id) {
        el.append(icon("info"), h("span", {}, "No workflow matches yet. Keep typing, or press Ctrl K to browse."));
      } else {
        const pct = Math.round(r.confidence * 100);
        const low = pct < Math.round((r.threshold || 0.55) * 100);
        el.classList.toggle("low", low);
        el.append(h("span", {}, "Likely"), h("span", { class: "route-id" }, r.workflow_id), h("b", {}, r.workflow_name),
          h("span", { class: "meter", title: `${pct}% match` }, h("i", { style: { width: `${pct}%` } })), h("span", {}, `${pct}%`),
          low ? h("span", { class: "alt" }, "· low, the agent will ask you to confirm") : r.alternatives?.[0] ? h("span", { class: "alt" }, `· next best ${r.alternatives[0].id}`) : null);
      }
      el.classList.add("show");
    } catch {
      el.classList.remove("show");
    }
  }, 220);
}

// ------------------------------------------------------------------ command palette
const palette = { items: [], sel: 0 };

function paletteCommands() {
  const cmds = [];
  const views = [["console", "Go to Console", "console"], ["insights", "Go to Insights", "chart"], ["workflows", "Go to Workflows", "sheet"], ["tools", "Go to Tool library", "tool"], ["runs", "Go to Run history", "history"]];
  views.forEach(([v, label, ic], i) => cmds.push({ group: "Pages", label, ic, hint: String(i + 1), run: () => showView(v) }));
  state.workflows.forEach((w) => (w.test_requests || []).forEach((t) => cmds.push({ group: "Run a test request", label: t.request, ic: "play", id: w.id, hint: w.name, run: () => (showView("console"), submit(t.request)) })));
  state.workflows.forEach((w) => cmds.push({ group: "Open a workflow", label: w.name, ic: "sheet", id: w.id, hint: w.executable ? `${w.steps.length} steps` : "needs a plan", run: () => openWorkflow(w.id) }));
  cmds.push(
    { group: "Actions", label: $("#faultToggle").checked ? "Turn off simulated API faults" : "Turn on simulated API faults", ic: "bolt", hint: "F", run: toggleFaults },
    { group: "Actions", label: mapIsOn() ? "Hide the flow map" : "Show the flow map", ic: "map", hint: "M", run: () => setMap(!mapIsOn()) },
    { group: "Actions", label: "Toggle light and dark", ic: "moon", hint: "T", run: toggleTheme },
    { group: "Actions", label: "Reload workflows from Excel", ic: "retry", run: reload },
    { group: "Actions", label: "Clear the console", ic: "trash", run: clearConsole },
    { group: "Actions", label: "Keyboard shortcuts", ic: "keys", hint: "?", run: () => openOverlay("#shortcuts") });
  return cmds;
}

function score(q, c) {
  if (!q) return 1;
  const hay = `${c.label} ${c.id || ""} ${c.hint || ""} ${c.group}`.toLowerCase();
  const words = q.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.every((w) => hay.includes(w))) return 0;
  return (c.label.toLowerCase().startsWith(words[0]) ? 3 : 1) + (c.id && c.id.toLowerCase() === words[0] ? 4 : 0);
}

function renderPalette() {
  const q = $("#paletteInput").value.trim();
  const list = $("#paletteList");
  list.innerHTML = "";
  let items = paletteCommands().map((c) => ({ c, s: score(q, c) })).filter((x) => x.s > 0);
  if (q) items.sort((a, b) => b.s - a.s);
  items = items.map((x) => x.c).slice(0, q ? 30 : 60);
  if (q) items.push({ group: "Ask the agent", label: `Run “${q}”`, ic: "play", hint: "Enter", run: () => (showView("console"), submit(q)) });
  palette.items = items;
  palette.sel = Math.min(palette.sel, Math.max(0, items.length - 1));
  let group = null;
  items.forEach((c, i) => {
    if (c.group !== group) {
      group = c.group;
      list.append(h("li", { class: "grp", role: "presentation" }, group));
    }
    const li = h("li", { class: `item ${i === palette.sel ? "sel" : ""}`, role: "option", "aria-selected": String(i === palette.sel) },
      icon(c.ic), c.id ? h("span", { class: "route-id" }, c.id) : null, h("span", { class: "txt" }, c.label), c.hint ? h("span", { class: "hint" }, c.hint) : null);
    li.onmouseenter = () => {
      palette.sel = i;
      $$(".item", list).forEach((x, j) => x.classList.toggle("sel", j === i));
    };
    li.onclick = () => choosePalette(i);
    list.append(li);
  });
  if (!items.length) list.append(h("li", { class: "none" }, "No matches."));
  $(".item.sel", list)?.scrollIntoView({ block: "nearest" });
}

function choosePalette(i) {
  const c = palette.items[i];
  closeOverlays();
  c?.run();
}

function openPalette() {
  palette.sel = 0;
  $("#paletteInput").value = "";
  openOverlay("#palette");
  renderPalette();
  setTimeout(() => $("#paletteInput").focus(), 10);
}

function openOverlay(sel) {
  closeOverlays();
  $(sel).hidden = false;
}
function closeOverlays() {
  if (document.activeElement?.closest(".overlay")) document.activeElement.blur();
  $$(".overlay").forEach((o) => (o.hidden = true));
}

function openWorkflow(id) {
  showView("workflows");
  const f = $("#wfFilter");
  if (f) f.value = "";
  filterWorkflows();
  const card = $(`.wfd[data-id="${id}"]`);
  if (!card) return;
  card.classList.add("open");
  card.scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "start" });
}

function toggleFaults() {
  const t = $("#faultToggle");
  t.checked = !t.checked;
  toast(t.checked ? "Simulated API faults on: the next API call fails first, then retries" : "Simulated API faults off", t.checked ? "bolt" : "ok");
}

function clearConsole() {
  showView("console");
  $$("#thread .turn").forEach((t) => t.remove());
  flow.owner = null;
  flow.empty();
  toast("Console cleared");
}

// ------------------------------------------------------------------ insights
async function renderInsights() {
  const box = $("#insights");
  box.innerHTML = "";
  box.append(h("div", { class: "empty shimmer" }, "Loading run history…"));
  let runs = [];
  try {
    runs = (await fetch(API + "/api/runs?limit=200").then((r) => r.json())).runs;
  } catch (err) {
    box.innerHTML = "";
    box.append(h("div", { class: "alert danger" }, icon("danger"), `Could not load runs: ${err.message}`));
    return;
  }
  box.innerHTML = "";
  if (!runs.length) {
    const go = h("button", { class: "btn primary", type: "button" }, icon("play"), "Run the first test request");
    go.onclick = () => {
      const t = state.workflows.find((w) => w.test_requests?.length)?.test_requests[0];
      showView("console");
      if (t) submit(t.request);
    };
    box.append(h("div", { class: "runs-wrap" }, h("div", { class: "empty" }, h("div", {}, "No runs logged yet. Insights appear after the first run."), go)));
    return;
  }
  const n = runs.length;
  const by = (k) => runs.filter((r) => r.status === k).length;
  const completed = by("completed"), escalated = by("escalated"), failed = by("failed");
  const routed = runs.filter((r) => r.workflow_id);
  const llmRouted = runs.filter((r) => r.route_method === "llm").length;
  const avgMs = Math.round(runs.reduce((a, r) => a + (r.active_ms || 0), 0) / n);
  const conf = routed.length ? routed.reduce((a, r) => a + (r.confidence || 0), 0) / routed.length : 0;
  const success = routed.length ? (completed + escalated) / routed.length : 0;

  const svgDefs = `<defs><linearGradient id="insGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#19C37D"/><stop offset=".5" stop-color="#4C7DFF"/><stop offset="1" stop-color="#9A6BFF"/></linearGradient></defs>`;
  const ring = (frac) => {
    const r = 18, c = 2 * Math.PI * r;
    const el = h("span", { html: `<svg class="ring" viewBox="0 0 44 44">${svgDefs}<circle class="bg" cx="22" cy="22" r="${r}"/><circle class="fg" cx="22" cy="22" r="${r}" stroke-dasharray="${c}" stroke-dashoffset="${c}"/></svg>` });
    const svg = el.firstChild;
    requestAnimationFrame(() => requestAnimationFrame(() => ($(".fg", svg).style.strokeDashoffset = c * (1 - frac))));
    return svg;
  };
  box.append(h("div", { class: "ins-kpis" },
    h("div", { class: "ins-kpi" }, h("div", { class: "v" }, n), h("div", { class: "l" }, "Runs logged")),
    h("div", { class: "ins-kpi" }, ring(success), h("div", { class: "v" }, `${Math.round(success * 100)}%`), h("div", { class: "l" }, "Finished (completed or escalated)")),
    h("div", { class: "ins-kpi" }, h("div", { class: "v" }, ms(avgMs)), h("div", { class: "l" }, "Average active time per run")),
    h("div", { class: "ins-kpi" }, ring(conf), h("div", { class: "v" }, `${Math.round(conf * 100)}%`), h("div", { class: "l" }, "Average routing confidence")),
    h("div", { class: "ins-kpi" }, h("div", { class: "v" }, failed), h("div", { class: "l" }, failed === 1 ? "Failed run" : "Failed runs"))));

  // per-workflow status mix
  const wfs = {};
  runs.forEach((r) => {
    const k = r.workflow_id || "none";
    wfs[k] ??= { id: r.workflow_id, name: r.workflow_name || "No match", completed: 0, escalated: 0, failed: 0, other: 0, n: 0 };
    const b = wfs[k];
    b.n += 1;
    b[["completed", "escalated", "failed"].includes(r.status) ? r.status : "other"] += 1;
  });
  const rowsSorted = Object.values(wfs).sort((a, b) => b.n - a.n);
  const max = Math.max(...rowsSorted.map((r) => r.n));
  const stacks = h("div", { class: "stack-rows" }, rowsSorted.map((r) => {
    const st = h("div", { class: "stack", style: { width: `${(r.n / max) * 100}%` }, title: `${r.completed} completed · ${r.escalated} escalated · ${r.failed} failed · ${r.other} other` },
      ["completed", "escalated", "failed", "other"].map((k) => h("i", { class: k, style: { width: `${(r[k] / r.n) * 100}%` } })));
    return h("div", { class: "stack-row" }, h("span", { class: "lbl", title: r.name }, r.id ? h("code", {}, r.id) : null, r.name), h("div", {}, st), h("span", { class: "n" }, r.n));
  }));
  const legend = h("div", { class: "legend" }, [["Completed", "linear-gradient(90deg,var(--s1),var(--s2))"], ["Escalated", "var(--warn)"], ["Failed", "var(--danger)"], ["No match / other", "var(--faint)"]].map(([l, c]) => h("span", {}, h("i", { style: { background: c } }), l)));

  // active time per run, oldest → newest
  const series = runs.slice(0, 40).reverse();
  const W = 520, H = 150, P = 26;
  const vmax = Math.max(...series.map((r) => r.active_ms || 0), 1);
  const x = (i) => P + (series.length === 1 ? (W - 2 * P) / 2 : (i * (W - 2 * P)) / (series.length - 1));
  const y = (v) => H - 20 - (v / vmax) * (H - 40);
  const pts = series.map((r, i) => [x(i), y(r.active_ms || 0)]);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
  const area = `${line} L${pts[pts.length - 1][0].toFixed(1)} ${H - 20} L${pts[0][0].toFixed(1)} ${H - 20} Z`;
  const spark = h("div", { html: `<svg class="spark-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Active time per run">
    <defs><linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4C7DFF"/><stop offset="1" stop-color="#4C7DFF" stop-opacity="0"/></linearGradient>
    <linearGradient id="sparkLine" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#19C37D"/><stop offset=".5" stop-color="#4C7DFF"/><stop offset="1" stop-color="#9A6BFF"/></linearGradient></defs>
    <line class="grid" x1="${P}" x2="${W - P}" y1="${H - 20}" y2="${H - 20}"/><line class="grid" x1="${P}" x2="${W - P}" y1="20" y2="20" stroke-dasharray="3 4"/>
    <text x="${P}" y="14">${ms(vmax)}</text><text x="${P}" y="${H - 4}">older</text><text x="${W - P}" y="${H - 4}" text-anchor="end">latest</text>
    <path class="area" d="${area}"/><path class="line" d="${line}"/>
    ${pts.map((p, i) => `<circle class="pt ${series[i].status}" cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3.5"><title>${(series[i].request || "").replace(/[<&]/g, "")} · ${ms(series[i].active_ms || 0)} · ${series[i].status}</title></circle>`).join("")}
  </svg>` });

  // routing method split
  const lex = runs.filter((r) => r.route_method === "lexical").length;
  const other = n - llmRouted - lex;
  const split = h("div", { class: "split" },
    h("div", { class: "split-bar" }, h("i", { style: { width: `${(llmRouted / n) * 100}%`, background: "var(--llm)" } }), h("i", { style: { width: `${(lex / n) * 100}%`, background: "var(--s2)" } }), h("i", { style: { width: `${(other / n) * 100}%`, background: "var(--faint)" } })),
    h("div", { class: "legend" }, h("span", {}, h("i", { style: { background: "var(--llm)" } }), `LLM router ${llmRouted}`), h("span", {}, h("i", { style: { background: "var(--s2)" } }), `Lexical (offline) ${lex}`), h("span", {}, h("i", { style: { background: "var(--faint)" } }), `Chosen by you / other ${other}`)));

  const counts = {};
  runs.forEach((r) => (counts[r.request] = (counts[r.request] || 0) + 1));
  const top = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 6);
  const topList = h("ul", { class: "top-list" }, top.map(([q, c]) => {
    const li = h("li", {}, h("span", { class: "q", title: q }, q), h("span", { class: "c" }, `×${c}`));
    const btn = h("button", { class: "link-btn", type: "button" }, "Run");
    btn.onclick = () => (showView("console"), submit(q));
    li.append(btn);
    return li;
  }));

  box.append(h("div", { class: "ins-grid" },
    h("div", { class: "panel" }, h("h3", {}, "Runs by workflow"), h("p", { class: "sub" }, "Bar length is the number of runs; colour shows how they ended."), stacks, legend),
    h("div", { class: "panel" }, h("h3", {}, "Active time per run"), h("p", { class: "sub" }, "The last 40 runs. Hover a point for the request."), spark),
    h("div", { class: "panel" }, h("h3", {}, "How requests were routed"), h("p", { class: "sub" }, "LLM routing needs an API key; the lexical router runs offline."), split),
    h("div", { class: "panel" }, h("h3", {}, "Most frequent requests"), h("p", { class: "sub" }, "Run any of them again in one click."), topList)));
}

// ------------------------------------------------------------------ tool library
let toolCache = null;
async function renderTools() {
  const box = $("#tools");
  if (!toolCache) {
    box.innerHTML = "";
    box.append(h("div", { class: "empty shimmer" }, "Loading the tool library…"));
    try {
      toolCache = (await fetch(API + "/api/tools").then((r) => r.json())).tools;
    } catch (err) {
      box.innerHTML = "";
      box.append(h("div", { class: "alert danger" }, icon("danger"), `Could not load tools: ${err.message}`));
      return;
    }
  }
  const usedBy = {};
  state.workflows.forEach((w) => w.steps.forEach((s) => s.tool && (usedBy[s.tool] ??= new Set()).add(w.id)));
  const nWf = state.workflows.length || 10;
  const shared = toolCache.filter((t) => (usedBy[t.name]?.size || 0) > 1).length;
  $("#toolsSub").textContent = `${toolCache.length} tools, ${shared} of them shared by two or more workflows. Workflows are YAML plans that call these; none of them belongs to a single workflow.`;
  const q = ($("#toolFilter").value || "").trim().toLowerCase();
  const cats = {};
  toolCache.filter((t) => !q || `${t.name} ${t.description} ${t.category}`.toLowerCase().includes(q)).forEach((t) => (cats[t.category] ??= []).push(t));
  box.innerHTML = "";
  const wrap = h("div", { class: "tool-cats" });
  Object.entries(cats).sort((a, b) => b[1].length - a[1].length).forEach(([cat, tools]) => {
    tools.sort((a, b) => (usedBy[b.name]?.size || 0) - (usedBy[a.name]?.size || 0));
    wrap.append(h("div", { class: "tool-cat" }, h("h3", {}, cat, h("span", {}, `${tools.length} tool${tools.length > 1 ? "s" : ""}`)),
      h("div", { class: "tool-grid" }, tools.map((t) => {
        const used = [...(usedBy[t.name] || [])].sort();
        return h("div", { class: "tool-card" },
          h("div", { class: "tc-top" }, h("span", { class: "tc-name" }, t.name), t.llm ? h("span", { class: "chip llm" }, "LLM") : null, t.simulated_api ? h("span", { class: "chip api" }, t.simulated_api) : null,
            h("span", { class: "reuse", title: `Used by ${used.length} of ${nWf} workflows` }, Array.from({ length: nWf }, (_, i) => h("i", { class: i < used.length ? "on" : "" })))),
          h("div", { class: "tc-desc" }, t.description),
          h("div", { class: "tc-args" }, Object.entries(t.args).map(([a, d]) => h("code", { class: d === "required" ? "req" : "", title: d }, a))),
          h("div", { class: "tc-used" }, used.length ? ["Used by", ...used.map((id) => {
            const b = h("button", { class: "route-id", type: "button", style: { border: 0, cursor: "pointer" }, title: "Open workflow" }, id);
            b.onclick = () => openWorkflow(id);
            return b;
          })] : "Not used by any plan yet"));
      }))));
  });
  if (!wrap.children.length) wrap.append(h("div", { class: "empty" }, `No tools match “${q}”.`));
  box.append(wrap);
}

// ------------------------------------------------------------------ navigation & boot
const TITLES = { console: "Console", insights: "Insights", workflows: "Workflows", tools: "Tool library", runs: "Run history" };
function showView(v) {
  $$(".view").forEach((x) => x.classList.toggle("active", x.id === `view-${v}`));
  $$(".nav-item").forEach((x) => x.classList.toggle("active", x.dataset.view === v));
  $("#viewTitle").textContent = TITLES[v];
  if (v === "runs") renderRuns();
  if (v === "insights") renderInsights();
  if (v === "tools") renderTools();
  $("#sidebar").classList.remove("open");
}

function toggleTheme() {
  const dark = document.documentElement.dataset.theme === "dark" || (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
  const next = dark ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("flowline-theme", next); } catch { /* ignore */ }
}

function initTheme() {
  let t = null;
  try { t = localStorage.getItem("flowline-theme"); } catch { /* storage unavailable */ }
  if (t) document.documentElement.dataset.theme = t;
  $("#themeBtn").onclick = toggleTheme;
}

async function attachFile(file) {
  try {
    const meta = await uploadFile(file);
    state.attachments.push(meta);
    renderAttachments();
    toast(`Attached ${meta.name}`, "file");
  } catch (err) {
    toast(err.message, "warn");
  }
}

function initDrop() {
  const zone = $("#dropZone"), ov = $("#dropOverlay");
  let depth = 0;
  zone.addEventListener("dragenter", (e) => {
    if (![...(e.dataTransfer?.types || [])].includes("Files")) return;
    e.preventDefault();
    depth += 1;
    ov.classList.add("show");
  });
  zone.addEventListener("dragover", (e) => e.dataTransfer?.types?.includes("Files") && e.preventDefault());
  zone.addEventListener("dragleave", () => (depth = Math.max(0, depth - 1)) || ov.classList.remove("show"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    depth = 0;
    ov.classList.remove("show");
    [...(e.dataTransfer?.files || [])].forEach(attachFile);
  });
}

function initKeys() {
  document.addEventListener("keydown", (e) => {
    const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName) || document.activeElement?.isContentEditable;
    const pal = !$("#palette").hidden;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      return pal ? closeOverlays() : openPalette();
    }
    if (e.key === "Escape") return closeOverlays();
    if (pal) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        palette.sel = (palette.sel + (e.key === "ArrowDown" ? 1 : -1) + palette.items.length) % Math.max(1, palette.items.length);
        renderPalette();
      } else if (e.key === "Enter") {
        e.preventDefault();
        choosePalette(palette.sel);
      }
      return;
    }
    if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
    const views = ["console", "insights", "workflows", "tools", "runs"];
    if (/^[1-5]$/.test(e.key)) return showView(views[Number(e.key) - 1]);
    if (e.key === "/") {
      e.preventDefault();
      showView("console");
      return $("#input").focus();
    }
    if (e.key === "?") return openOverlay("#shortcuts");
    const k = e.key.toLowerCase();
    if (k === "m") return setMap(!mapIsOn());
    if (k === "f") return toggleFaults();
    if (k === "t") return toggleTheme();
  });
  $$(".overlay").forEach((o) => o.addEventListener("mousedown", (e) => e.target === o && closeOverlays()));
  $$("[data-close]").forEach((b) => (b.onclick = closeOverlays));
  $("#paletteInput").addEventListener("input", () => ((palette.sel = 0), renderPalette()));
}

function boot() {
  initTheme();
  initKeys();
  initDrop();
  let mapPref = "1";
  try { mapPref = localStorage.getItem("flowline-map") ?? "1"; } catch { /* storage unavailable */ }
  setMap(mapPref === "1" && matchMedia("(min-width: 1241px)").matches);
  $$(".nav-item").forEach((b) => (b.onclick = () => showView(b.dataset.view)));
  $("#menuBtn").onclick = () => $("#sidebar").classList.toggle("open");
  $("#mapBtn").onclick = () => setMap(!mapIsOn());
  $("#paletteBtn").onclick = openPalette;
  $("#helpBtn").onclick = () => openOverlay("#shortcuts");
  $("#reloadBtn").onclick = () => {
    $("#reloadBtn").classList.add("spin");
    setTimeout(() => $("#reloadBtn").classList.remove("spin"), 800);
    reload();
  };
  $("#reloadBtn2").onclick = reload;
  $("#refreshRuns").onclick = renderRuns;
  $("#refreshInsights").onclick = renderInsights;
  $("#wfFilter").addEventListener("input", filterWorkflows);
  $("#toolFilter").addEventListener("input", renderTools);
  $("#composer").onsubmit = (e) => (e.preventDefault(), submit());
  $("#input").addEventListener("input", () => (autosize(), previewIntent()));
  $("#input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  });
  $("#fileInput").onchange = async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (file) attachFile(file);
  };
  loadAll().catch((err) => {
    $(".label", $("#modePill")).textContent = "Backend unreachable";
    toast(`Could not reach the backend at ${API}: ${err.message}`, "warn");
  });
}

boot();