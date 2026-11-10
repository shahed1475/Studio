// Shared helpers for every page. No inline scripts exist anywhere (the security policy forbids them) and no text from a person, an agent or the web is ever written as markup (everything goes in as text nodes).
const BRAND = "Nightloom"; // working name: the owner chooses the real one. Changing this string and the <title> tags is all it takes.
const root = document.documentElement;

export function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") el.className = v; else if (k.startsWith("on")) el.addEventListener(k.slice(2), v); else if (v !== false && v != null) el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return el;
}
export const icon = (name) => h("span", { class: `i i-${name}`, "aria-hidden": "true" });

export async function api(path, body) {
  const opt = { headers: { "X-Hub": "1" }, credentials: "same-origin" };
  if (body !== undefined) { opt.method = "POST"; opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  const r = await fetch(path, opt);
  let data = {};
  try { data = await r.json(); } catch (e) { /* not json */ }
  return { status: r.status, ok: r.ok, data };
}

export async function a2a(agent, method, params) {
  const r = await fetch(`/a2a/${agent}`, { method: "POST", credentials: "same-origin", headers: { "X-Hub": "1", "Content-Type": "application/json", "A2A-Version": "1.0" },
    body: JSON.stringify({ jsonrpc: "2.0", id: crypto.randomUUID(), method, params }) });
  const j = await r.json();
  if (j.error) throw new Error(j.error.message);
  return j.result;
}

export function toast(text) {
  let t = document.getElementById("toast");
  if (!t) { t = h("div", { id: "toast", class: "toast", role: "status", hidden: true }); document.body.append(t); }
  t.textContent = text; t.hidden = false;
  clearTimeout(t._timer); t._timer = setTimeout(() => { t.hidden = true; }, 3600);
}

function themeNow() { return root.dataset.theme || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"); }
function paintToggle(btn) {
  const dark = themeNow() === "dark";
  btn.replaceChildren(icon(dark ? "sun" : "moon"), h("span", { class: "sr" }, dark ? "Switch to light theme" : "Switch to dark theme"));
}
export function themeToggle() {
  const btn = h("button", { class: "btn icon", type: "button", "aria-label": "Change theme" });
  paintToggle(btn);
  btn.addEventListener("click", () => {
    const next = themeNow() === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem("hub_theme", next); } catch (e) { /* not remembered */ }
    paintToggle(btn); window.dispatchEvent(new Event("themechange"));
  });
  matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => { paintToggle(btn); window.dispatchEvent(new Event("themechange")); });
  return btn;
}

// A soft rise for things that tell a sequence; each element rises once, as it comes into view.
export function rise() {
  const els = [...document.querySelectorAll("[data-rise]")];
  if (!("IntersectionObserver" in window)) return els.forEach((e) => e.classList.add("in"));
  const io = new IntersectionObserver((entries) => entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: 0.18 });
  els.forEach((e) => io.observe(e));
}
export const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
export { BRAND };
