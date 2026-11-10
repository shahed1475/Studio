import { api, h, icon, themeToggle } from "./site.js";
import { mountSky } from "./constellation.js";

document.getElementById("theme-slot").replaceWith(themeToggle());
if (matchMedia("(min-width: 961px)").matches) mountSky(document.getElementById("sky"), { labels: false });
else document.getElementById("mobile-brand").style.display = "inline-flex";

const $ = (id) => document.getElementById(id);
const emailForm = $("email-form"), codeForm = $("code-form");
let email = "", timer = 0;
const MESSAGES = {
  bad_email: "Enter a full email address, like name@example.com.",
  too_many: "Too many tries. Wait a little while, then try again.",
  mail_unavailable: "We could not send the email right now. Try again in a few minutes.",
  invalid_or_expired: "That code did not work. It may have expired or been used already. Send a new one.",
  google_refused: "Google sign-in did not work. Use the emailed code instead.",
  not_invited: "Sign-up is by invitation for now. Ask the owner to add your address.",
  mail_busy: "Sign-in emails are paused for today. Please try again tomorrow.",
};
const say = (el, text) => el.replaceChildren(...(text ? [icon("warn"), text] : []));
const go = () => { location.href = "app.html"; };

function step(which) {
  emailForm.hidden = which !== "email"; codeForm.hidden = which !== "code";
  $("title").textContent = which === "email" ? "Sign in" : "Check your email";
  $("lede").textContent = which === "email" ? "We email you a code. No password to remember." : `We sent an 8-digit code to ${email}. It works once, for 10 minutes.`;
  (which === "email" ? $("email") : $("code")).focus();
}
function countdown() {
  clearInterval(timer); let n = 45; const b = $("resend"); b.disabled = true;
  const tick = () => { b.textContent = n > 0 ? `Send a new code in ${n}s` : "Send a new code"; if (n-- <= 0) { clearInterval(timer); b.disabled = false; } };
  tick(); timer = setInterval(tick, 1000);
}
async function sendCode() {
  const r = await api("/api/auth/request", { email });
  if (!r.ok) throw new Error(MESSAGES[r.data.error] || "Something went wrong. Try again.");
}

emailForm.addEventListener("submit", async (ev) => {
  ev.preventDefault(); say($("email-err"), ""); email = $("email").value.trim().toLowerCase();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return say($("email-err"), MESSAGES.bad_email);
  $("send-btn").disabled = true;
  try { await sendCode(); step("code"); countdown(); } catch (e) { say($("email-err"), e.message); } finally { $("send-btn").disabled = false; }
});
codeForm.addEventListener("submit", async (ev) => {
  ev.preventDefault(); say($("code-err"), "");
  const code = $("code").value.replace(/\s/g, "");
  if (!/^\d{8}$/.test(code)) return say($("code-err"), "Enter the 8 digits from the email.");
  $("verify-btn").disabled = true;
  const r = await api("/api/auth/verify", { email, code });
  if (r.ok) return go();
  say($("code-err"), MESSAGES[r.data.error] || "Something went wrong. Try again."); $("verify-btn").disabled = false;
});
$("code").addEventListener("input", (e) => { e.target.value = e.target.value.replace(/\D/g, "").slice(0, 8); });
$("resend").addEventListener("click", async () => { say($("code-err"), ""); try { await sendCode(); countdown(); $("code-help").textContent = "A new code is on its way."; } catch (e) { say($("code-err"), e.message); } });
$("back").addEventListener("click", () => { clearInterval(timer); $("code").value = ""; step("email"); });

// Google: shown only when the server says it is configured; the page never decides trust, the server verifies the token
(async () => {
  const c = await api("/api/config");
  if (!c.data.google_enabled) { $("g-off").hidden = false; return; }
  const s = h("script", { src: "https://accounts.google.com/gsi/client", async: true, defer: true });
  s.onload = () => {
    google.accounts.id.initialize({ client_id: c.data.google_client_id, ux_mode: "popup", callback: async (resp) => {
      const r = await api("/api/auth/google", { credential: resp.credential, csrf: c.data.csrf });
      if (r.ok) go(); else say($("email-err"), MESSAGES[r.data.error] || "Google sign-in did not work.");
    } });
    // Google draws the button 200 to 400 px wide; take the slot's real width so it lines up with the field and the button above it (it was a fixed 320 px, narrower than both)
    const width = Math.max(200, Math.min(400, Math.round($("g-slot").clientWidth) || 320));
    google.accounts.id.renderButton($("g-slot"), { theme: "filled_black", size: "large", shape: "pill", text: "continue_with", width });
  };
  s.onerror = () => { $("g-off").hidden = false; };
  document.head.append(s);
})();
step("email");
