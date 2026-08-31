"""Browser UI for BaseChatt.

A dependency-free single-page interface layered on top of the JSON API. Served
at ``GET /`` so opening the local URL in a browser lands on a usable chat
console instead of raw JSON.
"""

# ruff: noqa: E501  (embedded HTML/CSS/JS lines may exceed 100 chars)

from __future__ import annotations

from fastapi.responses import HTMLResponse

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BaseChatt — Financial Research Agent</title>
<style>
  :root {
    --bg: #0d1117;
    --panel: #161b22;
    --panel-2: #1c2330;
    --border: #2d3645;
    --text: #e6edf3;
    --muted: #8b98a9;
    --accent: #4f8cff;
    --accent-2: #7bb3ff;
    --ok: #3fb950;
    --warn: #d29922;
    --err: #f85149;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }
  body {
    font-family: "Segoe UI", system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    display: flex;
    flex-direction: column;
  }
  header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 18px;
    border-bottom: 1px solid var(--border);
    background: var(--panel);
    flex: 0 0 auto;
  }
  header .brand { font-weight: 700; font-size: 16px; letter-spacing: .3px; }
  header .brand span { color: var(--accent-2); }
  .badge {
    font-size: 12px;
    padding: 3px 10px;
    border-radius: 999px;
    border: 1px solid var(--border);
    color: var(--muted);
  }
  .badge.ok { color: var(--ok); border-color: var(--ok); }
  .badge.warn { color: var(--warn); border-color: var(--warn); }
  .spacer { flex: 1; }
  .provider { font-size: 12px; color: var(--muted); }
  main { flex: 1 1 auto; display: flex; min-height: 0; }
  aside {
    width: 260px;
    flex: 0 0 auto;
    border-right: 1px solid var(--border);
    background: var(--panel);
    overflow-y: auto;
    padding: 12px;
  }
  aside h3 {
    font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
    color: var(--muted); margin: 10px 0 6px;
  }
  aside p.count { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
  .chip {
    display: block; width: 100%; text-align: left;
    background: var(--panel-2); color: var(--text);
    border: 1px solid var(--border); border-radius: 8px;
    padding: 6px 8px; margin-bottom: 4px; font-size: 12.5px;
    cursor: pointer;
  }
  .chip:hover { border-color: var(--accent); }
  .chip .t { font-weight: 600; }
  .chip .s { color: var(--muted); font-size: 11px; }
  .chip.active { border-color: var(--accent); background: #17263f; }
  section.chat { flex: 1 1 auto; display: flex; flex-direction: column; min-width: 0; }
  #context {
    flex: 0 0 auto; padding: 6px 18px; font-size: 12.5px;
    color: var(--muted); border-bottom: 1px solid var(--border);
    background: var(--panel);
    display: none;
  }
  #context button {
    margin-left: 8px; background: none; border: 1px solid var(--border);
    color: var(--muted); border-radius: 6px; padding: 1px 8px; cursor: pointer;
  }
  #context button:hover { color: var(--err); border-color: var(--err); }
  #messages { flex: 1 1 auto; overflow-y: auto; padding: 18px; }
  .msg { margin-bottom: 14px; max-width: 760px; }
  .msg.user { margin-left: auto; }
  .bubble {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 12px 14px;
    white-space: pre-wrap;
    word-wrap: break-word;
    font-size: 14px;
    line-height: 1.55;
  }
  .msg.user .bubble { background: #12325e; border-color: #1f4a86; }
  .meta { margin-top: 6px; font-size: 12px; color: var(--muted); display: flex; gap: 12px; flex-wrap: wrap; }
  .meta b { color: var(--text); }
  .cites { margin-top: 8px; font-size: 12.5px; }
  .cites summary { color: var(--accent-2); cursor: pointer; }
  .cites ol { margin: 6px 0 0 18px; color: var(--muted); }
  .cites a { color: var(--accent-2); text-decoration: none; }
  .cites a:hover { text-decoration: underline; }
  .error { color: var(--err); }
  .typing { color: var(--muted); font-style: italic; }
  form {
    flex: 0 0 auto; display: flex; gap: 10px; padding: 12px 18px;
    border-top: 1px solid var(--border); background: var(--panel);
  }
  input[type=text] {
    flex: 1; background: var(--panel-2); color: var(--text);
    border: 1px solid var(--border); border-radius: 10px;
    padding: 11px 14px; font-size: 14px; outline: none;
  }
  input[type=text]:focus { border-color: var(--accent); }
  button.send {
    background: var(--accent); color: #fff; border: none;
    border-radius: 10px; padding: 0 20px; font-size: 14px; font-weight: 600;
    cursor: pointer;
  }
  button.send:hover { background: var(--accent-2); color: #0d1117; }
  button.send:disabled { opacity: .55; cursor: default; }
</style>
</head>
<body>
<header>
  <div class="brand">Base<span>Chatt</span></div>
  <span id="health" class="badge">connecting…</span>
  <div class="spacer"></div>
  <span id="provider" class="provider"></span>
  <a class="badge" href="/docs" style="text-decoration:none">API docs</a>
</header>
<main>
  <aside>
    <h3>Companies</h3>
    <p class="count" id="companies-count">loading…</p>
    <div id="companies"></div>
    <h3>Sources</h3>
    <p class="count" id="sources-count">loading…</p>
    <div id="sources"></div>
  </aside>
  <section class="chat">
    <div id="context"></div>
    <div id="messages"></div>
    <form id="form" autocomplete="off">
      <input id="input" type="text" placeholder="Ask about Nigerian companies, e.g. &#39;compare GTCO and Zenith&#39;" required>
      <button class="send" type="submit">Ask</button>
    </form>
  </section>
</main>
<script>
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  let context = { company: null, source: null };

  const esc = (s) => s.replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function addBubble(role, text, meta) {
    const wrap = document.createElement("div");
    wrap.className = "msg " + (role === "user" ? "user" : "assistant");
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;
    wrap.appendChild(bubble);
    if (meta) {
      const m = document.createElement("div");
      m.className = "meta";
      m.innerHTML = meta;
      wrap.appendChild(m);
    }
    $("messages").appendChild(wrap);
  }

  async function fetchJSON(url, opts) {
    const resp = await fetch(url, opts);
    let body = null;
    try { body = await resp.json(); } catch (e) { /* ignore */ }
    if (!resp.ok) throw new Error(body && body.detail ? body.detail : ("HTTP " + resp.status));
    return body;
  }

  async function loadHealth() {
    try {
      const h = await fetchJSON("/api/v1/health");
      const el = $("health");
      el.textContent = h.database === "ok" ? "online" : "degraded (" + h.database + ")";
      el.className = "badge " + (h.database === "ok" ? "ok" : "warn");
      $("provider").textContent = h.provider.toUpperCase();
    } catch (e) {
      const el = $("health");
      el.textContent = "offline";
      el.className = "badge warn";
    }
  }

  async function loadCompanies() {
    try {
      const data = await fetchJSON("/api/v1/companies");
      $("companies-count").textContent = data.count + " companies";
      const box = $("companies");
      box.textContent = "";
      for (const c of data.companies) {
        const b = document.createElement("button");
        b.className = "chip";
        b.innerHTML = '<div class="t">' + esc(c.ticker) + '</div><div class="s">' + esc(c.name) + "</div>";
        b.onclick = () => selectCompany(c, b);
        box.appendChild(b);
      }
    } catch (e) {
      $("companies-count").textContent = "unavailable";
    }
  }

  async function loadSources() {
    try {
      const data = await fetchJSON("/api/v1/sources");
      $("sources-count").textContent = data.count + " sources";
      const box = $("sources");
      box.textContent = "";
      for (const s of data.sources) {
        const b = document.createElement("button");
        b.className = "chip";
        b.innerHTML = '<div class="t">' + esc(s.code) + '</div><div class="s">' +
          esc(s.name) + " · " + esc(s.authority_level) + "</div>";
        b.onclick = () => selectSource(s, b);
        box.appendChild(b);
      }
    } catch (e) {
      $("sources-count").textContent = "unavailable";
    }
  }

  function renderContext() {
    const box = $("context");
    if (!context.company && !context.source) { box.style.display = "none"; box.textContent = ""; return; }
    const parts = [];
    if (context.company) parts.push("company: <b>" + esc(context.company.ticker) + "</b>");
    if (context.source) parts.push("source: <b>" + esc(context.source.code) + "</b>");
    box.innerHTML =
      parts.join(" · ") +
      '<button id="clear-context">clear</button>';
    box.style.display = "block";
    $("clear-context").onclick = () => { context = { company: null, source: null }; renderContext(); document.querySelectorAll(".chip.active").forEach((c) => c.classList.remove("active")); };
  }

  function selectCompany(c, el) {
    document.querySelectorAll("#companies .chip").forEach((x) => x.classList.remove("active"));
    el.classList.add("active");
    context.company = c;
    renderContext();
  }

  function selectSource(s, el) {
    document.querySelectorAll("#sources .chip").forEach((x) => x.classList.remove("active"));
    el.classList.add("active");
    context.source = s;
    renderContext();
  }

  function citationsHtml(payload) {
    const cites = payload.citations || [];
    if (!cites.length) return "";
    let list = "<ol>";
    for (const c of cites) {
      list += "<li>" + (c.title ? esc(c.title) : "citation") +
        (c.source_url ? ' — <a href="' + esc(c.source_url) + '" target="_blank" rel="noopener">source</a>' : "") +
        "</li>";
    }
    list += "</ol>";
    return '<details class="cites"><summary>' + cites.length + ' citation(s)</summary>' + list + "</details>";
  }

  function followUpsHtml(list) {
    if (!list || !list.length) return "";
    return 'follow-ups: <i>' + esc(list.join(" · ")) + "</i>";
  }

  const form = $("form");
  const input = $("input");
  const sendBtn = form.querySelector(".send");

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const q = input.value.trim();
    if (!q || sendBtn.disabled) return;
    input.value = "";
    addBubble("user", q);

    const typing = document.createElement("div");
    typing.className = "msg typing";
    typing.textContent = "researching…";
    $("messages").appendChild(typing);

    sendBtn.disabled = true;
    try {
      const body = { query: q };
      if (context.company) body.company_ticker = context.company.ticker;
      if (context.source) body.source_code = context.source.code;
      const data = await fetchJSON("/api/v1/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const meta =
        'confidence <b>' + esc(String(data.confidence)) + "</b> · " +
        "uncertainty <b>" + esc(String(data.uncertainty)) + "</b> · " +
        '<b>' + esc(String(data.elapsed_ms)) + "</b> ms" +
        (data.verdict ? " · verdict <b>" + esc(String(data.verdict.verified)) + "</b>" : "") +
        citationsHtml(data) +
        followUpsHtml(data.follow_up_queries);
      addBubble("assistant", data.answer, meta);
    } catch (e) {
      addBubble("assistant", "Error: " + e.message, "");
    } finally {
      sendBtn.disabled = false;
      typing.remove();
      input.focus();
    }
  });

  loadHealth();
  loadCompanies();
  loadSources();
})();
</script>
</body>
</html>
"""


def chat_page() -> HTMLResponse:
    """Return the rendered BaseChatt chat console."""
    return HTMLResponse(content=_PAGE)
