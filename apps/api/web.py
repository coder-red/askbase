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
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    height: 100%;
    overflow: hidden;
    scrollbar-width: none;
    -ms-overflow-style: none;
  }
  html::-webkit-scrollbar, body::-webkit-scrollbar { display: none; }
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
    gap: 12px;
    padding: 12px 20px;
    border-bottom: 1px solid var(--border);
    background: var(--panel);
    flex: 0 0 auto;
  }
  header .brand { font-weight: 700; font-size: 17px; letter-spacing: -0.2px; }
  header .brand .accent { color: var(--accent); }
  .badge {
    font-size: 12px; padding: 3px 8px; border-radius: 999px;
    border: 1px solid var(--border); color: var(--muted); background: var(--panel-2);
  }
  .badge.ok { color: var(--ok); border-color: var(--ok); background: var(--accent-soft); }
  .badge.warn { color: var(--warn); border-color: var(--warn); }
  .badge.err { color: var(--err); border-color: var(--err); }
  main {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    align-items: stretch;
    overflow: hidden;
  }
  #messages {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    scrollbar-width: none;
    -ms-overflow-style: none;
  }
  #messages::-webkit-scrollbar { display: none; }
  .inner {
    max-width: 720px;
    margin: 0 auto;
    padding: 0 24px;
    display: flex;
    flex-direction: column;
    min-height: 100%;
  }
  .msg { margin-bottom: 20px; }
  .role {
    font-size: 12px; color: var(--muted); margin-bottom: 4px; font-weight: 500;
  }
  .bubble {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 14px 18px;
    font-size: 14.5px;
    line-height: 1.65;
    max-width: 600px;
  }
  .bubble p { margin: 0 0 8px; }
  .bubble p:last-child { margin-bottom: 0; }
  .bubble ul, .bubble ol { margin: 4px 0 8px 20px; }
  .bubble li { margin-bottom: 2px; }
  .bubble code {
    background: var(--panel-2); padding: 1px 6px;
    border-radius: 4px; font-size: 13px;
  }
  .bubble strong { font-weight: 600; }
  .msg.user .bubble {
    background: var(--accent-soft);
    border-color: var(--accent);
    margin-left: auto;
    max-width: 600px;
  }
  .cites { margin-top: 10px; font-size: 13px; }
  .cites summary {
    color: var(--accent); cursor: pointer; font-weight: 500; user-select: none;
  }
  .cites ol { margin: 6px 0 0 20px; color: var(--muted); }
  .cites li { margin-bottom: 4px; }
  .cites a { color: var(--accent); text-decoration: none; word-break: break-all; }
  .cites a:hover { text-decoration: underline; }
  .typing {
    color: var(--muted); font-style: italic; padding: 8px 0;
  }
  .typing::after { content: "..."; animation: dots 1.5s steps(4, end) infinite; }
  @keyframes dots {
    0%, 20% { content: ""; }
    40% { content: "."; }
    60% { content: ".."; }
    80%, 100% { content: "..."; }
  }
  .empty {
    flex: 1; display: flex; flex-direction: column; align-items: center;
    justify-content: center; text-align: center; color: var(--muted); padding: 40px 20px;
  }
  .empty h2 { font-size: 22px; color: var(--text); margin-bottom: 8px; font-weight: 600; }
  .empty p { max-width: 440px; margin-bottom: 24px; }
  .examples { display: flex; flex-direction: column; gap: 8px; max-width: 480px; width: 100%; }
  .example {
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 10px 14px; cursor: pointer; text-align: left; font-size: 13.5px;
    color: var(--text); transition: border-color 0.15s, background 0.15s;
  }
  .example:hover { border-color: var(--accent); background: var(--accent-soft); }
  #form-wrap {
    flex: 0 0 auto;
    border-top: 1px solid var(--border);
    background: var(--panel);
    padding: 14px 20px;
  }
  #form-wrap form {
    max-width: 720px;
    margin: 0 auto;
    display: flex;
    gap: 10px;
    align-items: center;
  }
  input[type=text] {
    flex: 1; background: var(--bg); color: var(--text);
    border: 1px solid var(--border-strong); border-radius: 24px;
    padding: 12px 18px; font-size: 15px; outline: none;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  input[type=text]:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 15%, transparent);
  }
  input[type=text]::placeholder { color: var(--muted); }
  button.send {
    background: var(--accent); color: #fff; border: none;
    border-radius: 24px; padding: 10px 22px; font-size: 14px; font-weight: 600;
    cursor: pointer; transition: background 0.15s, transform 0.1s;
    flex-shrink: 0;
  }
  button.send:hover { background: var(--accent-2); }
  button.send:active { transform: scale(0.97); }
  button.send:disabled { opacity: 0.5; cursor: default; }
  @media (max-width: 600px) {
    .inner { padding: 0 16px; }
    #form-wrap { padding: 12px 16px; }
    .bubble { border-radius: 14px; }
    input[type=text] { border-radius: 20px; padding: 10px 14px; }
    button.send { padding: 8px 16px; border-radius: 20px; }
  }
</style>
</head>
<body>
<header>
  <div class="brand">Base<span class="accent">Chatt</span></div>
  <span id="health" class="badge"></span>
</header>
<main>
  <div id="messages">
    <div class="inner">
      <div class="empty" id="empty">
        <h2>Ask about Nigerian finance</h2>
        <p>Macro data, listed companies, SEC rules, NGX, FMDQ, CBN policy.</p>
        <div class="examples">
          <button class="example" data-q="What was Nigeria's headline inflation rate in December 2024?">What was Nigeria's headline inflation rate in December 2024?</button>
          <button class="example" data-q="What did the MPC decide about the MPR at the last meeting?">What did the MPC decide about the MPR at the last meeting?</button>
          <button class="example" data-q="How did GTCO's profit after tax move in Q3 2024?">How did GTCO's profit after tax move in Q3 2024?</button>
          <button class="example" data-q="What is the minimum holding period under SEC's 2024 amended rules?">What is the minimum holding period under SEC's 2024 amended rules?</button>
        </div>
      </div>
    </div>
  </div>
  <div id="form-wrap">
    <form id="form" autocomplete="off">
      <input id="input" type="text" placeholder="Ask a question" required>
      <button class="send" type="submit">Ask</button>
    </form>
  </div>
</main>
<script>
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  let history = JSON.parse(localStorage.getItem("basechatt_history") || "[]");

  const esc = (s) => String(s).replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function renderMarkdown(text) {
    if (!text) return "";
    let html = esc(text);
    html = html.replace(/```([\\s\\S]*?)```/g, (_, code) => "<pre><code>" + code + "</code></pre>");
    html = html.replace(/`([^`]+)`/g, (_, code) => "<code>" + code + "</code>");
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, "$1<em>$2</em>");
    html = html.replace(/\[(\d{1,3})\]/g, '<sup><a href="#cite-$1" class="cite-ref">[$1]</a></sup>');
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
    bubble.innerHTML = renderMarkdown(text) + (meta || "");
    wrap.appendChild(roleLbl);
    wrap.appendChild(bubble);
    const inner = document.querySelector("#messages .inner") || $("messages");
    inner.appendChild(wrap);
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

  async function loadHealth(retries = 3) {
    for (let i = 0; i < retries; i++) {
      try {
        const h = await fetchJSON("/api/v1/health");
        const el = $("health");
        el.textContent = "online";
        el.className = "badge ok";
        return;
      } catch (e) {
        if (i === retries - 1) {
          $("health").textContent = "offline";
          $("health").className = "badge err";
        } else {
          await new Promise((r) => setTimeout(r, 1500));
        }
      }
    }
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

  const form = $("form");
  const input = $("input");
  const sendBtn = form.querySelector(".send");

  async function sendQuery(q) {
    if (!q || sendBtn.disabled) return;
    input.value = "";
    addBubble("user", q);
    history.push({ role: "user", text: q });

    let typing = null;
    let typingTimeout = null;
    const showTyping = () => {
      typing = document.createElement("div");
      typing.className = "msg typing";
      typing.textContent = "researching";
      (document.querySelector("#messages .inner") || $("messages")).appendChild(typing);
      $("messages").scrollTop = $("messages").scrollHeight;
    };
    typingTimeout = setTimeout(showTyping, 500);

    sendBtn.disabled = true;
    try {
      const data = await fetchJSON("/api/v1/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q }),
      });
      if (typingTimeout) clearTimeout(typingTimeout);
      if (typing) typing.remove();
      const meta = citationsHtml(data);
      addBubble("assistant", data.answer, meta);
      history.push({ role: "assistant", text: data.answer, meta: meta });
      saveHistory();
    } catch (e) {
      if (typingTimeout) clearTimeout(typingTimeout);
      if (typing) typing.remove();
      addBubble("assistant", "Error: " + e.message, "");
    } finally {
      if (typingTimeout) clearTimeout(typingTimeout);
      if (typing) typing.remove();
      sendBtn.disabled = false;
      input.focus();
    }
  }

  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const q = input.value.trim();
    if (q) input.value = "";
    sendQuery(q).catch((e) => {
      sendBtn.disabled = false;
      console.error("sendQuery failed:", e);
    });
  });

  document.querySelectorAll(".example").forEach((b) => {
    b.addEventListener("click", () => sendQuery(b.dataset.q));
  });

  rehydrateHistory();
  loadHealth();
})();
</script>
</body>
</html>
"""


def chat_page() -> HTMLResponse:
    """Return the rendered BaseChatt chat console."""
    return HTMLResponse(content=_PAGE)
