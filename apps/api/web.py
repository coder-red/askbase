"""Browser UI for BaseChatt."""

# ruff: noqa: E501

from __future__ import annotations

from fastapi.responses import HTMLResponse

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BaseChatt</title>
<style>
  :root {
    --bg: #f7f7f5;
    --panel: #ffffff;
    --panel-2: #f3f3ef;
    --border: #e5e5e0;
    --border-strong: #d4d4ce;
    --text: #1a1a1a;
    --muted: #6b6b6b;
    --accent: #00875a;
    --accent-soft: #e6f4ed;
    --accent-2: #00684a;
    --ok: #00875a;
    --warn: #b54708;
    --err: #b42318;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0f0f0e;
      --panel: #1a1a1a;
      --panel-2: #232323;
      --border: #2e2e2e;
      --border-strong: #3a3a3a;
      --text: #ececec;
      --muted: #9a9a9a;
      --accent: #4ade80;
      --accent-soft: #0e2e1f;
      --accent-2: #86efac;
      --ok: #4ade80;
      --warn: #fbbf24;
      --err: #f87171;
    }
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    display: flex;
    flex-direction: column;
    font-size: 15px;
    line-height: 1.5;
  }
  header {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px 24px;
    border-bottom: 1px solid var(--border);
    background: var(--panel);
    flex: 0 0 auto;
  }
  header .brand {
    font-weight: 700;
    font-size: 17px;
    letter-spacing: -0.2px;
  }
  header .brand .accent { color: var(--accent); }
  header .tag {
    font-size: 12px;
    color: var(--muted);
    border-left: 1px solid var(--border);
    padding-left: 14px;
  }
  .badge {
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 999px;
    border: 1px solid var(--border);
    color: var(--muted);
    background: var(--panel-2);
  }
  .badge.ok { color: var(--ok); border-color: var(--ok); background: var(--accent-soft); }
  .badge.warn { color: var(--warn); border-color: var(--warn); }
  .badge.err { color: var(--err); border-color: var(--err); }
  .spacer { flex: 1; }
  .provider { font-size: 12px; color: var(--muted); }
  a.link { color: var(--muted); text-decoration: none; font-size: 13px; }
  a.link:hover { color: var(--text); }
  main { flex: 1 1 auto; display: flex; min-height: 0; }
  aside {
    width: 280px;
    flex: 0 0 auto;
    border-right: 1px solid var(--border);
    background: var(--panel);
    overflow-y: auto;
    padding: 16px;
  }
  aside h3 {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--muted);
    margin: 14px 0 8px;
    font-weight: 600;
  }
  aside h3:first-child { margin-top: 0; }
  aside p.count { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
  .chip {
    display: block; width: 100%; text-align: left;
    background: var(--panel-2); color: var(--text);
    border: 1px solid transparent; border-radius: 8px;
    padding: 8px 10px; margin-bottom: 4px; font-size: 13px;
    cursor: pointer;
    transition: border-color 0.1s, background 0.1s;
  }
  .chip:hover { border-color: var(--border-strong); }
  .chip .t { font-weight: 600; }
  .chip .s { color: var(--muted); font-size: 11.5px; margin-top: 1px; }
  .chip.active { border-color: var(--accent); background: var(--accent-soft); }
  section.chat { flex: 1 1 auto; display: flex; flex-direction: column; min-width: 0; }
  #context {
    flex: 0 0 auto; padding: 10px 24px; font-size: 13px;
    color: var(--muted); border-bottom: 1px solid var(--border);
    background: var(--panel);
    display: none;
    align-items: center;
    gap: 8px;
  }
  #context button {
    margin-left: auto; background: none; border: 1px solid var(--border);
    color: var(--muted); border-radius: 6px; padding: 2px 10px; cursor: pointer;
    font-size: 12px;
  }
  #context button:hover { color: var(--err); border-color: var(--err); }
  #messages { flex: 1 1 auto; overflow-y: auto; padding: 24px; }
  .msg { margin-bottom: 18px; max-width: 760px; }
  .msg.user { margin-left: auto; }
  .role {
    font-size: 12px;
    color: var(--muted);
    margin-bottom: 4px;
    font-weight: 500;
  }
  .msg.user .role { text-align: right; }
  .bubble {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 12px 16px;
    font-size: 14.5px;
    line-height: 1.6;
  }
  .bubble p { margin: 0 0 8px; }
  .bubble p:last-child { margin-bottom: 0; }
  .bubble ul, .bubble ol { margin: 4px 0 8px 20px; }
  .bubble li { margin-bottom: 2px; }
  .bubble code {
    background: var(--panel-2);
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 13px;
  }
  .bubble strong { font-weight: 600; }
  .msg.user .bubble {
    background: var(--accent-soft);
    border-color: var(--accent);
  }
  .meta {
    margin-top: 8px; font-size: 12px; color: var(--muted);
    display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
  }
  .meta .pill {
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--panel-2);
    border: 1px solid var(--border);
  }
  .meta .pill.ok { color: var(--ok); border-color: var(--ok); background: var(--accent-soft); }
  .meta .pill.warn { color: var(--warn); border-color: var(--warn); }
  .meta b { color: var(--text); font-weight: 600; }
  .cites { margin-top: 10px; font-size: 13px; }
  .cites summary {
    color: var(--accent);
    cursor: pointer;
    font-weight: 500;
    user-select: none;
  }
  .cites ol { margin: 6px 0 0 20px; color: var(--muted); }
  .cites li { margin-bottom: 4px; }
  .cites a { color: var(--accent); text-decoration: none; word-break: break-all; }
  .cites a:hover { text-decoration: underline; }
  .error { color: var(--err); }
  .typing {
    color: var(--muted);
    font-style: italic;
    padding: 8px 0;
  }
  .typing::after {
    content: "...";
    animation: dots 1.5s steps(4, end) infinite;
  }
  @keyframes dots {
    0%, 20% { content: ""; }
    40% { content: "."; }
    60% { content: ".."; }
    80%, 100% { content: "..."; }
  }
  .empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    color: var(--muted);
    padding: 40px 20px;
  }
  .empty h2 {
    font-size: 22px;
    color: var(--text);
    margin-bottom: 8px;
    font-weight: 600;
  }
  .empty p { max-width: 440px; margin-bottom: 24px; }
  .examples { display: flex; flex-direction: column; gap: 8px; max-width: 480px; width: 100%; }
  .example {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px 14px;
    cursor: pointer;
    text-align: left;
    font-size: 13.5px;
    color: var(--text);
    transition: border-color 0.1s, background 0.1s;
  }
  .example:hover { border-color: var(--accent); background: var(--accent-soft); }
  form {
    flex: 0 0 auto; display: flex; gap: 10px; padding: 14px 24px;
    border-top: 1px solid var(--border); background: var(--panel);
  }
  input[type=text] {
    flex: 1; background: var(--bg); color: var(--text);
    border: 1px solid var(--border-strong); border-radius: 12px;
    padding: 12px 16px; font-size: 15px; outline: none;
    transition: border-color 0.1s;
  }
  input[type=text]:focus { border-color: var(--accent); }
  button.send {
    background: var(--accent); color: #fff; border: none;
    border-radius: 12px; padding: 0 22px; font-size: 14px; font-weight: 600;
    cursor: pointer;
    transition: background 0.1s;
  }
  button.send:hover { background: var(--accent-2); }
  button.send:disabled { opacity: 0.5; cursor: default; }
  @media (max-width: 720px) {
    aside { display: none; }
    header { padding: 12px 16px; }
    #messages, form, #context { padding-left: 16px; padding-right: 16px; }
  }
</style>
</head>
<body>
<header>
  <div class="brand">Base<span class="accent">Chatt</span></div>
  <span class="tag">Nigerian financial research</span>
  <span id="health" class="badge">connecting</span>
  <div class="spacer"></div>
  <span id="provider" class="provider"></span>
  <a class="link" href="/docs">API</a>
</header>
<main>
  <aside>
    <h3>Companies</h3>
    <p class="count" id="companies-count">loading</p>
    <div id="companies"></div>
    <h3>Sources</h3>
    <p class="count" id="sources-count">loading</p>
    <div id="sources"></div>
  </aside>
  <section class="chat">
    <div id="context"></div>
    <div id="messages">
      <div class="empty" id="empty">
        <h2>Ask about Nigerian finance</h2>
        <p>Macro data, listed companies, SEC rules, NGX, FMDQ, CBN policy. Pick a ticker or source from the sidebar, or try one of these:</p>
        <div class="examples">
          <button class="example" data-q="What was Nigeria's headline inflation rate in December 2024?">What was Nigeria's headline inflation rate in December 2024?</button>
          <button class="example" data-q="What did the MPC decide about the MPR at the last meeting?">What did the MPC decide about the MPR at the last meeting?</button>
          <button class="example" data-q="How did GTCO's profit after tax move in Q3 2024?">How did GTCO's profit after tax move in Q3 2024?</button>
          <button class="example" data-q="What is the minimum holding period under SEC's 2024 amended rules?">What is the minimum holding period under SEC's 2024 amended rules?</button>
        </div>
      </div>
    </div>
    <form id="form" autocomplete="off">
      <input id="input" type="text" placeholder="Ask a question" required>
      <button class="send" type="submit">Ask</button>
    </form>
  </section>
</main>
<script>
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  let context = { company: null, source: null };
  let history = JSON.parse(localStorage.getItem("basechatt_history") || "[]");

  const esc = (s) => String(s).replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // Tiny markdown renderer: paragraphs, **bold**, *italic*, lists, code.
  function renderMarkdown(text) {
    if (!text) return "";
    let html = esc(text);
    html = html.replace(/```([\\s\\S]*?)```/g, (_, code) => "<pre><code>" + code + "</code></pre>");
    html = html.replace(/`([^`]+)`/g, (_, code) => "<code>" + code + "</code>");
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, "$1<em>$2</em>");
    html = html.replace(/\[(\d{1,3})\]/g, '<sup><a href="#cite-$1" class="cite-ref">[$1]</a></sup>');
    // Lists
    const lines = html.split(/\\n/);
    const out = [];
    let inList = null;
    for (const line of lines) {
      const ol = line.match(/^\\s*\\d+\\.\\s+(.*)$/);
      const ul = line.match(/^\\s*[-*]\\s+(.*)$/);
      if (ol) {
        if (inList !== "ol") { if (inList) out.push(`</${inList}>`); out.push("<ol>"); inList = "ol"; }
        out.push("<li>" + ol[1] + "</li>");
      } else if (ul) {
        if (inList !== "ul") { if (inList) out.push(`</${inList}>`); out.push("<ul>"); inList = "ul"; }
        out.push("<li>" + ul[1] + "</li>");
      } else if (line.trim() === "") {
        if (inList) { out.push(`</${inList}>`); inList = null; }
      } else {
        if (inList) { out.push(`</${inList}>`); inList = null; }
        out.push("<p>" + line + "</p>");
      }
    }
    if (inList) out.push(`</${inList}>`);
    return out.join("").replace(/<p><\\/p>/g, "");
  }

  function saveHistory() {
    try { localStorage.setItem("basechatt_history", JSON.stringify(history.slice(-50))); } catch (e) {}
  }

  function addBubble(role, text, meta) {
    const empty = $("empty");
    if (empty) empty.remove();
    const wrap = document.createElement("div");
    wrap.className = "msg " + role;
    const roleLbl = document.createElement("div");
    roleLbl.className = "role";
    roleLbl.textContent = role === "user" ? "You" : "BaseChatt";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    if (role === "user") {
      bubble.textContent = text;
    } else {
      bubble.innerHTML = renderMarkdown(text);
    }
    wrap.appendChild(roleLbl);
    wrap.appendChild(bubble);
    if (meta) {
      const m = document.createElement("div");
      m.className = "meta";
      m.innerHTML = meta;
      wrap.appendChild(m);
    }
    $("messages").appendChild(wrap);
    $("messages").scrollTop = $("messages").scrollHeight;
  }

  function rehydrateHistory() {
    if (!history.length) return;
    const empty = $("empty");
    if (empty) empty.remove();
    for (const turn of history) {
      addBubble(turn.role, turn.text, turn.meta || "");
    }
  }

  async function fetchJSON(url, opts) {
    const resp = await fetch(url, opts);
    let body = null;
    try { body = await resp.json(); } catch (e) {}
    if (!resp.ok) throw new Error((body && body.detail) ? body.detail : ("HTTP " + resp.status));
    return body;
  }

  async function loadHealth() {
    try {
      const h = await fetchJSON("/api/v1/health");
      const el = $("health");
      el.textContent = h.database === "ok" ? "online" : "degraded";
      el.className = "badge " + (h.database === "ok" ? "ok" : "warn");
      $("provider").textContent = h.provider;
    } catch (e) {
      $("health").textContent = "offline";
      $("health").className = "badge err";
    }
  }

  async function loadCompanies() {
    try {
      const data = await fetchJSON("/api/v1/companies");
      $("companies-count").textContent = data.count + " listed";
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
        b.innerHTML = '<div class="t">' + esc(s.code) + '</div><div class="s">' + esc(s.name) + "</div>";
        b.onclick = () => selectSource(s, b);
        box.appendChild(b);
      }
    } catch (e) {
      $("sources-count").textContent = "unavailable";
    }
  }

  function renderContext() {
    const box = $("context");
    if (!context.company && !context.source) {
      box.style.display = "none";
      box.innerHTML = "";
      return;
    }
    const parts = [];
    if (context.company) parts.push('<b>' + esc(context.company.ticker) + '</b> ' + esc(context.company.name));
    if (context.source) parts.push('<b>' + esc(context.source.code) + '</b> ' + esc(context.source.name));
    box.innerHTML = parts.join(" &middot; ") + '<button id="clear-context">clear</button>';
    box.style.display = "flex";
    $("clear-context").onclick = () => {
      context = { company: null, source: null };
      document.querySelectorAll(".chip.active").forEach((c) => c.classList.remove("active"));
      renderContext();
    };
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
    for (let i = 0; i < cites.length; i++) {
      const c = cites[i];
      list += '<li id="cite-' + (i + 1) + '">' + esc(c.title || "citation") +
        (c.source_url ? ' &mdash; <a href="' + esc(c.source_url) + '" target="_blank" rel="noopener">link</a>' : "") +
        "</li>";
    }
    list += "</ol>";
    return '<details class="cites"><summary>' + cites.length + ' source' + (cites.length === 1 ? '' : 's') + '</summary>' + list + "</details>";
  }

  function verdictPill(v) {
    if (!v) return "";
    const verdict = v.verified || v.verdict || "unverified";
    let cls = "pill";
    if (verdict === "supported" || verdict === "partial") cls += " ok";
    else if (verdict === "unsupported" || verdict === "unverifiable") cls += " warn";
    return '<span class="' + cls + '">' + esc(verdict) + '</span>';
  }

  const form = $("form");
  const input = $("input");
  const sendBtn = form.querySelector(".send");

  async function sendQuery(q) {
    if (!q || sendBtn.disabled) return;
    input.value = "";
    addBubble("user", q);
    history.push({ role: "user", text: q });

    const typing = document.createElement("div");
    typing.className = "msg typing";
    typing.textContent = "researching";
    $("messages").appendChild(typing);
    $("messages").scrollTop = $("messages").scrollHeight;

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
      typing.remove();
      const meta =
        '<span class="pill">confidence <b>' + esc(String(data.confidence)) + "</b></span>" +
        '<span class="pill">' + esc(String(data.elapsed_ms)) + " ms</span>" +
        verdictPill(data.verdict) +
        citationsHtml(data);
      addBubble("assistant", data.answer, meta);
      history.push({ role: "assistant", text: data.answer, meta: meta });
      saveHistory();
    } catch (e) {
      typing.remove();
      addBubble("assistant", "Error: " + e.message, '<span class="pill err">failed</span>');
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  }

  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    sendQuery(input.value.trim());
  });

  document.querySelectorAll(".example").forEach((b) => {
    b.addEventListener("click", () => sendQuery(b.dataset.q));
  });

  rehydrateHistory();
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
