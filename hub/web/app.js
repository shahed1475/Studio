import { a2a, api, h, icon, themeToggle, toast } from "./site.js";

document.getElementById("theme-slot").replaceWith(themeToggle());
const $ = (id) => document.getElementById(id);
const say = (el, text) => el.replaceChildren(...(text ? [icon("warn"), text] : []));
const PLATFORMS = { youtube: ["YouTube", "i-youtube"], tiktok: ["TikTok", "i-tiktok"], instagram: ["Instagram", "i-instagram"], facebook: ["Facebook", "i-facebook"] };
const MODE = { studio_upload: "Studio upload, after you connect your channel", manual_export: "Export package, you post it" };
const state = { niche_id: "", niche_text: "", tier: "", platforms: [], presets: [], best: null };

const me = await api("/api/me");
if (!me.ok) { location.replace("signin.html"); throw new Error("signed out"); }
$("who").textContent = me.data.account.email || "Signed in with Google";
$("out").addEventListener("click", async () => { await api("/api/logout", {}); location.replace("./"); });

const [prof, niches, list] = await Promise.all([api("/api/profile"), fetch("/api/niches").then((r) => r.json()), fetch("/a2a/").then((r) => r.json())]);
Object.assign(state, prof.data.profile); state.presets = niches.niches;
if (!state.niche_text) { try { state.niche_text = sessionStorage.getItem("hub_niche_text") || ""; } catch (e) { /* none */ } }
$("desc").value = state.niche_text;
$("status").textContent = state.niche_id || state.niche_text ? "Your saved choices are loaded." : "Start by describing your channel.";

function drawPicks() {
  const rows = state.presets.map((p) => pick(p.id, p.name, p.audience, p.id === state.best));
  rows.push(pick("", "My own idea", "The team can research and draft it. Full fact-checked video needs a fit check first.", false));
  $("picks").replaceChildren(...rows);
}
function pick(id, name, text, best) {
  const input = h("input", { type: "radio", name: "niche", value: id });
  input.checked = id === state.niche_id && (id !== "" || state.niche_text !== "" || state.tier === "B");
  input.addEventListener("change", () => { state.niche_id = id; state.tier = id ? "A" : "B"; });
  return h("li", {}, h("label", { class: "pick" }, input, h("span", {}, h("b", {}, name, best ? "  (closest match)" : ""), text)));
}
drawPicks();

$("match").addEventListener("click", async () => {
  say($("match-err"), ""); const text = $("desc").value.trim();
  if (text.split(/\s+/).length < 3) return say($("match-err"), "Write a few words about the videos you want to make.");
  $("match").disabled = true;
  try {
    const t = (await a2a("concierge", "SendMessage", { message: { messageId: crypto.randomUUID(), role: "ROLE_USER", parts: [{ text }] } })).task;
    const reply = t.status.message?.parts?.[0]?.text || "";
    state.niche_text = text;
    if (t.status.state === "TASK_STATE_REJECTED") { say($("match-err"), reply); return; }
    const data = t.artifacts?.[0]?.parts?.find((p) => p.data)?.data;
    state.best = data?.matches?.[0]?.id || null; state.tier = data?.tier || "B";
    if (state.tier === "A" && state.best) state.niche_id = state.best;
    drawPicks(); toast(reply);
  } catch (e) { say($("match-err"), e.message); } finally { $("match").disabled = false; }
});

function drawPlatforms() {
  $("plats").replaceChildren(...Object.entries(PLATFORMS).map(([id, [name, cls]]) => {
    const box = h("input", { type: "checkbox", value: id }); box.checked = state.platforms.includes(id);
    box.addEventListener("change", () => { state.platforms = [...document.querySelectorAll("#plats input:checked")].map((i) => i.value); });
    return h("label", { class: "platform-row" }, box, h("span", { class: `i ${cls}`, "aria-hidden": "true" }), h("span", { class: "grow" }, h("b", {}, name), h("br"), h("span", { class: "mute" }, MODE[prof.data.platforms[id]] || ""))); }));
  $("p-platform").replaceChildren(...Object.entries(PLATFORMS).map(([id, [name]]) => h("option", { value: id }, name)));
}
drawPlatforms();
$("plat-form").addEventListener("submit", async (ev) => {
  ev.preventDefault(); say($("save-err"), ""); $("saved").textContent = "";
  const r = await api("/api/profile", { niche_id: state.niche_id, niche_text: state.niche_text || $("desc").value, tier: state.tier, platforms: state.platforms });
  if (r.ok) { $("saved").textContent = "Saved."; $("status").textContent = "Your saved choices are loaded."; } else say($("save-err"), "Could not save: " + (r.data.error || "try again"));
});

const cards = await Promise.all(list.agents.map((a) => fetch(a.card).then((r) => r.json())));
$("team").replaceChildren(...cards.map((c) => {
  const needs = c.skills.some((s) => s.tags.includes("needs-ai-key"));
  return h("li", {}, h("span", {}, h("b", {}, c.name), h("small", {}, c.description)),
    needs ? h("span", { class: "chip next" }, icon("lock"), "Needs an AI key") : h("span", { class: "chip good" }, icon("check"), "Ready"));
}));

$("pkg-form").addEventListener("submit", async (ev) => {
  ev.preventDefault(); say($("p-err"), ""); $("p-out").replaceChildren();
  const tags = $("p-tags").value.split(",").map((t) => t.trim()).filter(Boolean);
  const data = { platform: $("p-platform").value, title: $("p-title").value, caption: $("p-caption").value, hashtags: tags, approved_by_creator: $("p-ok").checked };
  $("p-go").disabled = true;
  try {
    const t = (await a2a("publisher", "SendMessage", { message: { messageId: crypto.randomUUID(), role: "ROLE_USER", parts: [{ data }] } })).task;
    const reply = t.status.message?.parts?.[0]?.text || "";
    const pkg = t.artifacts?.[0]?.parts?.find((p) => p.data)?.data;
    if (t.status.state !== "TASK_STATE_COMPLETED" || !pkg) return say($("p-err"), reply);
    const dl = h("dl", { class: "pkg" }, ...[["Platform", PLATFORMS[pkg.platform][0]], ["Title", pkg.title || "(none)"], ["Caption", pkg.caption || "(none)"], ["Hashtags", pkg.hashtags.join(" ") || "(none)"],
      ["Checklist", pkg.checklist.join(". ")], ["Platform note", pkg.platform_note], ["How sure we are", pkg.platform_note_label], ["Posted", pkg.posted ? "yes" : "No. Nothing was posted."]].flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)]));
    const blob = URL.createObjectURL(new Blob([JSON.stringify(pkg, null, 2)], { type: "application/json" }));
    $("p-out").replaceChildren(h("p", { class: "mute", style: "margin-top:14px" }, reply), dl, h("a", { class: "btn", style: "margin-top:12px", href: blob, download: `package-${pkg.platform}.json` }, icon("down"), "Download as JSON"));
  } catch (e) { say($("p-err"), e.message); } finally { $("p-go").disabled = false; }
});
