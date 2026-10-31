"use strict";
/* My Downloads page. Everything on screen is built with textContent, never HTML strings, so a video title cannot inject markup. */
(function () {
  const $ = (id) => document.getElementById(id);
  const NS = "http://www.w3.org/2000/svg";
  const S = { state: null, plan: null, picked: new Set(), timer: null, rec: null, listening: false, busy: false, refreshing: false, lastJob: "", addOpen: false };
  const EXAMPLES = ["my last 5 videos", "my last 3 Shorts", "all my videos", "my 3 oldest videos", "my videos about "];

  function el(tag, props, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else if (v === true) n.setAttribute(k, "");
      else if (v !== false && v != null) n.setAttribute(k, v);
    }
    for (const c of kids.flat()) if (c != null && c !== false) n.append(c);
    return n;
  }
  function icon(name) {
    const s = document.createElementNS(NS, "svg");
    s.setAttribute("class", "icon");
    s.setAttribute("aria-hidden", "true");
    const u = document.createElementNS(NS, "use");
    u.setAttribute("href", "#i-" + name);
    s.append(u);
    return s;
  }

  async function api(path, body) {
    const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json", "X-MyDownloads": "1" }, body: JSON.stringify(body) };
    let r;
    try { r = await fetch(path, opt); } catch (e) { throw new Error("I cannot reach the downloader. Is it still running on this computer?"); }
    let d = {};
    try { d = await r.json(); } catch (e) { /* the body was not JSON */ }
    if (!r.ok) throw new Error(d.error || "Something went wrong (" + r.status + ").");
    return d;
  }

  const dur = (s) => (s ? Math.floor(s / 60) + ":" + String(Math.round(s % 60)).padStart(2, "0") : "");
  const mb = (b) => (b >= 1e9 ? (b / 1e9).toFixed(2) + " GB" : (b / 1e6).toFixed(1) + " MB");
  const eta = (s) => (s == null ? "" : s >= 90 ? Math.round(s / 60) + " min left" : Math.round(s) + " s left");
  function say(text, kind) {
    const p = $("heard");
    p.textContent = text || "";
    if (kind) p.setAttribute("data-kind", kind); else p.removeAttribute("data-kind");
  }
  function busy(on, text) {
    S.busy = on;
    $("find").disabled = on;
    if (text) say(text);
  }

  // ---------- my channels
  function chanId() { const s = $("chan"); return s && s.value ? s.value : null; }

  function addForm() {
    const first = !S.state.channels.length;
    const input = el("input", { type: "text", id: "chaninput", placeholder: "@yourname or a channel link", autocomplete: "off", "aria-label": "Your channel" });
    const tick = el("input", { type: "checkbox", id: "chantick" });
    const msg = el("p", { class: "say", role: "status" });
    const go = el("button", { type: "button", class: "primary small", text: "Add this channel", onclick: async () => {
      go.disabled = true; msg.removeAttribute("data-kind"); msg.textContent = "Checking the channel…";
      try {
        const d = await api("/api/channels", { text: input.value, confirm: tick.checked });
        S.state.channels = d.channels; S.addOpen = false; renderChannels(); say("Channel added.");
      } catch (e) { msg.textContent = e.message; msg.setAttribute("data-kind", "error"); go.disabled = false; }
    } });
    return el("div", { class: "addform" },
      el("strong", { text: first ? "First, tell me which channel is yours" : "Add another channel of yours" }),
      input,
      el("label", { class: "tick", for: "chantick" }, tick, el("span", { text: "This is my own channel, and I made these videos." })),
      el("p", { class: "why", text: "I only download from channels you list here. Your tick is your word that they are yours; I cannot check it." }),
      el("div", { class: "bar" }, go, first ? null : el("button", { type: "button", class: "link", text: "Cancel", onclick: () => { S.addOpen = false; renderChannels(); } }), msg));
  }

  function renderChannels() {
    const box = $("channels"), ch = S.state.channels;
    box.replaceChildren();
    if (ch.length) {
      box.append("Looking in");
      if (ch.length === 1) box.append(el("strong", { text: ch[0].title || ch[0].handle || ch[0].id }), ch[0].handle ? el("span", { text: ch[0].handle }) : null);
      else box.append(el("select", { id: "chan", "aria-label": "Which channel" }, el("option", { value: "", text: "All my channels" }), ch.map((c) => el("option", { value: c.id, text: c.title || c.handle || c.id }))));
      box.append(el("button", { type: "button", class: "link", text: "Add another channel", onclick: () => { S.addOpen = true; renderChannels(); $("chaninput").focus(); } }));
      box.append(el("button", { type: "button", class: "link", text: "Remove", "aria-label": "Remove a channel from my list", onclick: () => removeChannel(ch) }));
    }
    if (!ch.length || S.addOpen) box.append(addForm());
    $("find").disabled = S.busy || !ch.length;
  }

  async function removeChannel(ch) {
    const pick = ch.length === 1 ? ch[0] : ch.find((c) => c.id === chanId());
    if (!pick) { say("Choose the channel to remove in the list first.", "error"); return; }
    if (!window.confirm("Remove " + (pick.title || pick.id) + " from my list? Nothing on YouTube changes, and files already saved stay.")) return;
    try { const d = await api("/api/channels/remove", { id: pick.id }); S.state.channels = d.channels; renderChannels(); say("Removed."); } catch (e) { say(e.message, "error"); }
  }

  // ---------- speaking
  function micError(code) {
    return ({ "not-allowed": "The microphone is blocked. Click the lock beside the address, allow the microphone for this page, and try again.",
      "service-not-allowed": "The microphone is blocked. Click the lock beside the address, allow the microphone for this page, and try again.",
      "no-speech": "I did not hear anything. Press the microphone and try again.", "audio-capture": "I cannot find a microphone on this computer.",
      "network": "Voice typing needs an internet connection." })[code] || "Voice typing stopped (" + code + "). You can type instead.";
  }
  function paintMic() {
    const m = $("mic");
    m.setAttribute("aria-pressed", S.listening ? "true" : "false");
    m.setAttribute("aria-label", S.listening ? "Stop listening" : "Speak what you need");
  }
  function startMic() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SR();
    rec.lang = "en-US"; rec.interimResults = true; rec.continuous = false; rec.maxAlternatives = 1;
    let heard = "";
    rec.onstart = () => { S.listening = true; paintMic(); say("Listening… say what you need, for example “my last 5 videos”."); };
    rec.onresult = (e) => { let t = ""; for (let i = 0; i < e.results.length; i++) t += e.results[i][0].transcript; heard = t.trim(); $("ask").value = heard; };
    rec.onerror = (e) => { heard = ""; say(micError(e.error), "error"); };
    rec.onend = () => { S.listening = false; S.rec = null; paintMic(); if (heard) { say("Heard: “" + heard + "”"); find(); } };
    S.rec = rec;
    try { rec.start(); } catch (e) { say("The microphone could not start. Try again.", "error"); }
  }
  function setupMic() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      $("mic").hidden = true;
      const n = $("micnote"); n.hidden = false; n.textContent = "Voice typing needs Chrome or Edge. Typing works in any browser.";
      return;
    }
    $("mic").addEventListener("click", () => { if (S.listening && S.rec) S.rec.stop(); else startMic(); });
    const n = $("micnote"); n.hidden = false; n.textContent = "Voice typing uses your browser's speech service, which may send what you say to its maker (Google, in Chrome).";
  }

  // ---------- finding
  async function find() {
    const text = $("ask").value.trim();
    if (!text) { say("Tell me what to download, for example “my last 5 videos”.", "error"); $("ask").focus(); return; }
    if (!S.state.channels.length) { say("Add your channel first.", "error"); return; }
    busy(true, "Looking through your channel…");
    try {
      const p = await api("/api/plan", { text, channel: chanId() });
      say("");
      renderPlan(p);
    } catch (e) { say(e.message, "error"); }
    finally { busy(false); $("find").disabled = !S.state.channels.length; }
  }

  function renderPlan(p) {
    S.plan = p;
    S.picked = new Set(p.items.filter((i) => i.owned && !i.error && !i.saved).map((i) => i.id));
    const box = $("result");
    box.replaceChildren();
    box.hidden = false;
    box.append(el("h2", { text: p.summary }));
    if (p.notes.length) box.append(el("ul", { class: "notes" }, p.notes.map((n) => el("li", { text: n }))));
    if (!p.items.length) { box.append(el("p", { class: "empty", text: "Nothing to download. Try other words, or say a number, for example “my last 5 videos”." })); return; }
    const go = el("button", { type: "button", class: "primary", id: "go" }, icon("download"), el("span", { id: "gotext" }));
    go.addEventListener("click", startDownload);
    const sync = () => {
      const n = S.picked.size;
      $("gotext").textContent = n ? "Download " + n + (n === 1 ? " video" : " videos") : "Choose a video";
      go.disabled = !n;
    };
    const list = el("ul", { class: "list" });
    for (const i of p.items) {
      const can = i.owned && !i.error;
      const cb = el("input", { type: "checkbox", id: "p-" + i.id, checked: S.picked.has(i.id), disabled: !can });
      cb.addEventListener("change", () => { if (cb.checked) S.picked.add(i.id); else S.picked.delete(i.id); sync(); });
      const meta = [i.kind === "short" ? "Short" : "Long video", dur(i.duration), i.channel, i.partial ? "matches only some of your words" : "", i.saved ? "already saved" : ""].filter(Boolean).join(" · ");
      list.append(el("li", {}, el("label", { class: "row" + (can ? "" : " off"), for: "p-" + i.id }, cb,
        el("span", { class: "rt" }, el("span", { class: "title", text: i.title }), el("span", { class: "meta", text: i.refused || i.error || meta })))));
    }
    box.append(list, el("div", { class: "bar" }, go));
    sync();
  }

  // ---------- downloading
  async function startDownload() {
    const items = S.plan.items.filter((i) => S.picked.has(i.id)).map((i) => ({ id: i.id, title: i.title, kind: i.kind }));
    if (!items.length) return;
    $("go").disabled = true;
    try {
      S.state.job = await api("/api/download", { items });
      $("result").hidden = true; S.plan = null; S.lastJob = "";
      renderJob(); schedule();
    } catch (e) { say(e.message, "error"); $("go").disabled = false; }
  }

  function jobLine(i) {
    const parts = { queued: "Waiting", done: "Saved", skipped: "Already saved", downloading: "Downloading" };
    if (i.status === "downloading") {
      if (i.stage === "joining") return "Joining picture and sound…";
      const bits = [Math.round(i.percent || 0) + "%", i.speed ? mb(i.speed) + "/s" : "", eta(i.eta)].filter(Boolean);
      return "Downloading · " + bits.join(" · ");
    }
    if (i.status === "done") return "Saved · " + mb(i.bytes || 0);
    if (i.status === "failed") return "Could not download · " + (i.error || "");
    if (i.status === "refused") return "Not downloaded · " + (i.error || "");
    return parts[i.status] || i.status;
  }

  function renderJob() {
    const j = S.state.job, box = $("job");
    const sig = JSON.stringify(j);
    if (sig === S.lastJob) return;
    S.lastJob = sig;
    box.hidden = !j;
    if (!j) return;
    box.replaceChildren();
    const finished = j.items.filter((i) => ["done", "skipped", "failed", "refused"].includes(i.status)).length;
    const head = j.state === "running" ? "Downloading · " + finished + " of " + j.items.length : j.state === "done" ? "Finished" : "Paused";
    box.append(el("h2", { text: head }));
    if (j.message) box.append(el("p", { class: "meta", text: j.message }));
    const list = el("ul", { class: "list" });
    for (const i of j.items) {
      const ic = { done: "check", skipped: "check", failed: "x", refused: "warn", queued: "wait", downloading: "download" }[i.status] || "wait";
      list.append(el("li", { class: "jrow" }, el("span", { class: "st st-" + i.status }, icon(ic)),
        el("span", { class: "rt" }, el("span", { class: "title", text: i.title }), el("span", { class: "meta", text: jobLine(i) }),
          i.status === "downloading" ? el("progress", { max: "100", value: String(Math.round(i.percent || 0)), "aria-label": "Progress" }) : null)));
    }
    const bar = el("div", { class: "bar" });
    if (j.state === "running") bar.append(el("button", { type: "button", class: "quiet", onclick: stopJob }, icon("stop"), el("span", { text: "Stop" })));
    if (j.resumable) bar.append(el("button", { type: "button", class: "primary", onclick: resumeJob }, icon("download"), el("span", { text: "Continue" })));
    bar.append(el("button", { type: "button", class: "quiet", onclick: openFolder }, icon("folder"), el("span", { text: "Open folder" })));
    box.append(list, bar);
  }
  async function stopJob() { try { await api("/api/stop", {}); say("Stopping after this moment…"); } catch (e) { say(e.message, "error"); } }
  async function resumeJob() { try { S.state.job = await api("/api/resume", {}); S.lastJob = ""; renderJob(); schedule(); } catch (e) { say(e.message, "error"); } }
  async function openFolder() { try { await api("/api/open-folder", {}); } catch (e) { say(e.message, "error"); } }

  function schedule() {
    clearInterval(S.timer); S.timer = null;
    if (S.state.job && S.state.job.state === "running") S.timer = setInterval(refresh, 1000);
  }
  async function refresh() {
    if (S.refreshing) return;
    S.refreshing = true;
    try { S.state = Object.assign(S.state, await api("/api/state")); renderJob(); renderFoot(); schedule(); }
    catch (e) { say(e.message, "error"); }
    finally { S.refreshing = false; }
  }

  function renderFoot() {
    const s = S.state, f = $("foot");
    f.replaceChildren(el("span", {}, "Saved in ", el("span", { class: "path", text: s.folder })),
      el("button", { type: "button", class: "link", text: "Open folder", onclick: openFolder }),
      el("span", { text: s.free_gb + " GB free" }), s.yt_dlp ? el("span", { text: "Downloader " + s.yt_dlp }) : null);
  }

  // ---------- start
  async function boot() {
    const chips = $("chips");
    for (const t of EXAMPLES) chips.append(el("button", { type: "button", class: "chip", text: t.trim() + (t.endsWith(" ") ? "…" : ""), onclick: () => { const a = $("ask"); a.value = t; a.focus(); a.setSelectionRange(t.length, t.length); } }));
    $("find").addEventListener("click", find);
    $("ask").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); find(); } });
    setupMic();
    try { S.state = await api("/api/state"); } catch (e) { say(e.message, "error"); S.state = { channels: [], job: null, folder: "", free_gb: 0 }; }
    renderChannels(); renderJob(); renderFoot(); schedule();
    document.documentElement.setAttribute("data-ready", "1");
  }
  boot();
})();
