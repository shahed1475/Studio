import { api, h, icon, rise, themeToggle } from "./site.js";
import { mountSky } from "./constellation.js";

document.getElementById("theme-slot").replaceWith(themeToggle());
const sky = mountSky(document.getElementById("sky"));
rise();

// the example room plays its four lines once, as it comes into view
const log = document.getElementById("room-log");
new IntersectionObserver(([e], io) => { if (e.isIntersecting) { log.classList.add("play"); io.disconnect(); } }, { threshold: 0.3 }).observe(log);

const form = document.getElementById("match"), out = document.getElementById("match-out"), btn = document.getElementById("match-btn"), input = document.getElementById("niche-text");
form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const text = input.value.trim();
  if (text.split(/\s+/).length < 3) { out.replaceChildren(h("span", { class: "err" }, icon("warn"), "Write a few words about the videos you want to make.")); return; }
  btn.disabled = true; out.textContent = "Asking the concierge...";
  sky.ping("concierge");
  try {
    const r = await api("/api/demo/niche", { text });
    if (r.status === 429) throw new Error("That was a lot of questions. Wait a minute and try again.");
    if (!r.ok) throw new Error("The concierge could not answer. Try again.");
    const d = r.data, kids = [h("span", {}, d.text)];
    if (d.state === "completed") {
      kids.push(h("div", { class: "go" }, h("a", { class: "btn primary", href: "signin.html", id: "continue" }, "Continue with this niche", icon("arrow"))));
      try { sessionStorage.setItem("hub_niche_text", text); } catch (e) { /* not carried to sign-in */ }
    }
    out.replaceChildren(...kids);
  } catch (e) {
    out.replaceChildren(h("span", { class: "err" }, icon("warn"), e.message));
  } finally { btn.disabled = false; }
});
