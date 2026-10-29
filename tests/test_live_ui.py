"""The dashboard's live pages (29 Oct 2026): every icon and tab the page names exists, the monitor reads only fields /api/now sends, and the old stand-alone
addresses forward into the app."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import nowview

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "dashboard.html").read_text()
MON = (ROOT / "monitor.html").read_text()


def script() -> str:
    return re.search(r"<script>(.*?)</script>\s*</body>", HTML, re.S).group(1)


def test_every_icon_the_page_uses_exists():
    decl = re.search(r"const NAV=.*?const SET=[^;]*;", script(), re.S).group(0)
    names = set(re.findall(r'ico\("([a-z-]+)"', HTML)) | set(re.findall(r'\["[a-z]+","[A-Za-z ]+","([a-z-]+)"\]', decl))
    names |= set(re.findall(r'empty\("([a-z-]+)"', HTML)) | set(re.findall(r'icon:"([a-z-]+)"', HTML))
    missing = sorted(n for n in names if not (ROOT / "static" / "icons" / f"{n}.svg").exists())
    assert not missing, missing
    assert {"broadcast", "monitor-play", "film-slate", "users-three"} <= {p.stem for p in (ROOT / "static" / "icons").glob("*.svg")}


def test_every_tab_in_the_navigation_has_a_view_and_the_new_ones_are_first_class():
    js = script()
    tabs = re.findall(r'\["([a-z]+)","[A-Za-z ]+","[a-z-]+"\]', re.search(r"const NAV=(.*?);\s*const TOOLS=(.*?);", js, re.S).group(0))
    table = re.search(r"\(\{([a-z,]+)\}\)\[tab\]", js).group(1).split(",")
    assert {"home", "live", "videos", "autopilot", "footage", "channels"} <= set(tabs) and set(tabs) <= set(table) | {"niche"}, (tabs, table)
    nav_order = [t for t in tabs][:4]
    assert nav_order == ["home", "live", "videos", "autopilot"]  # the phone's tab bar shows the first four
    assert "pagelinks" not in HTML.split("<body>")[1]  # no more tiny text links at the foot of the sidebar


def test_the_monitor_reads_only_fields_the_live_api_sends(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "OUT", tmp_path / "out")
    (tmp_path / "out").mkdir()
    sent = set(nowview.build())
    used = set(re.findall(r"\bL\.([a-z_]+)", MON))
    assert used <= sent, used - sent
    st = nowview.stage_now([], None, False)
    assert set(re.findall(r"\bst\.([a-z_]+)", MON)) <= set(st), set(re.findall(r"\bst\.([a-z_]+)", MON)) - set(st)
    block = HTML[HTML.index("/* ---------- Live ---------- */"):HTML.index("/* ---------- Footage ---------- */")]
    live = set(re.findall(r"\bL\.([a-z_]+)", block))
    assert live <= sent, live - sent


def test_old_addresses_forward_to_a_real_tab_and_keep_their_text_for_a_browser_without_scripts():
    for page, tab, text in (("now.html", "live", "Right now"), ("footage.html", "footage", "Footage clips"), ("channels.html", "channels", "Channels")):
        body = (ROOT / page).read_text()
        assert f'location.replace("/#{tab}")' in body and text in body
        assert f'["{tab}",' in HTML


def test_no_dash_flourish_in_the_new_screens_and_the_monitor_is_accessible():
    assert "—" not in MON and "–" not in MON
    assert "prefers-reduced-motion" in MON and "aria-live" in MON and ":focus-visible" in MON and 'name="viewport"' in MON
    live_block = HTML[HTML.index("/* ---------- Live ---------- */"):HTML.index("/* ---------- Home ---------- */")]
    assert "—" not in live_block and "window.addEventListener(\"scroll\"" not in live_block
    assert "document.hidden" in live_block  # no polling for a page nobody is looking at


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_dashboard_script_parses(tmp_path):
    f = tmp_path / "dash.js"
    f.write_text(script())
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ---- shell, notifications, theme (29 Oct 2026) ----
CSS = (ROOT / "static" / "studio.css").read_text()
V3 = CSS[CSS.index("v3 (29 Oct 2026)"):]
NOTES = (ROOT / "notifications.html").read_text()


def test_the_shell_has_a_top_bar_with_the_bell_and_an_accessible_day_night_switch():
    for needle in ('id="topbar"', 'id="bell"', 'aria-haspopup="dialog"', 'id="notes"', 'role="dialog"', 'id="toasts"', 'id="tswitch"', 'role="switch"', 'aria-label="Night mode"',
                   'id="alertsw"', 'id="pill"', 'id="navlist"'):
        assert needle in HTML, needle
    js = script()
    for fn in ("toggleTheme", "toggleNotes", "closeNotes", "notesRead", "toastNote", "pollNotes", "toggleAlerts", "movePill", "countUp"):
        assert re.search(rf"function {fn}\(", js), fn
    assert 'key==="Escape"' in js and "startViewTransition" in js and "reduced()" in js  # keyboard close, the circular reveal, and no motion when the person asked for none
    assert 'localStorage.setItem("theme"' in js


def test_only_transform_and_opacity_move_in_the_new_animations():
    bodies = re.findall(r"@keyframes\s+[\w-]+\s*\{(.*?\})\s*\}", V3, re.S)
    assert bodies
    for b in bodies:
        props = set(re.findall(r"([a-z-]+)\s*:", b)) - {"from", "to"}
        assert props <= {"transform", "opacity"}, props
    assert "prefers-reduced-motion" in V3 and "@media(max-width:900px)" in V3  # reduced motion handled, phone layout handled


def test_the_notifications_window_reads_the_api_and_marks_read(tmp_path):
    for needle in ("/api/notifications", "/api/notifications/read", "prefers-reduced-motion", ":focus-visible", 'aria-live="polite"', 'name="viewport"'):
        assert needle in NOTES, needle
    assert "—" not in NOTES
    import notifyview
    sent = set(notifyview.build(events=[])) | {"counts", "items", "sources"}
    assert set(re.findall(r"\bD\.([a-z]+)", NOTES)) <= sent


def test_the_notification_routes_answer_and_read_marks_the_feed(tmp_path, monkeypatch):
    import agentlog
    import dashboard
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    agentlog.event("error", "A render failed", "ffmpeg exited 1")
    agentlog.event("applied", "Repaired a title")
    d = dashboard.notifications_view()
    assert d["counts"]["unread"] >= 2 and d["counts"]["badge"] >= 2 and any(i["title"] == "A render failed" and i["source"] == "Warnings" for i in d["items"])
    dashboard.agent_read()
    assert dashboard.notifications_view()["counts"]["unread"] == 0


# ---- black and white, Autopilot sections, Android (29 Oct 2026) ----
V4 = CSS[CSS.index("v4 (29 Oct 2026)"):]


def _greys(block: str) -> dict:
    out = {}
    for name, val in re.findall(r"--(bg|surface|surface2|sunken|ink|ink2|line|accent|accent-ink|accent-soft|accent-text|ok|ok-bg|warn|warn-bg|bad|bad-bg|pop):(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})\b", block):
        out.setdefault(name, []).append(val)
    return out


def test_the_palette_is_black_and_white_only_in_both_themes_and_on_every_page():
    def grey(h):
        h = h.lstrip("#")
        h = "".join(c * 2 for c in h) if len(h) == 3 else h
        return len({h[0:2].lower(), h[2:4].lower(), h[4:6].lower()}) == 1
    toks = _greys(V4)
    assert len(toks) >= 15
    assert all(grey(v) for vals in toks.values() for v in vals), {k: v for k, v in toks.items() if not all(grey(x) for x in v)}
    for f in ("monitor.html", "notifications.html"):
        page = (ROOT / f).read_text()
        for v in re.findall(r"--(?:bg|surface|ink|ink2|line|accent|ok|warn|bad)[a-z-]*:(#[0-9a-fA-F]{3,6})", page):
            assert grey(v), (f, v)
    assert "rgba(255,190,0" not in HTML  # the amber policy-hold fill is gone


def test_status_is_carried_by_an_icon_and_a_fill_not_by_colour_alone():
    for needle in (".b-ok::before", ".b-warn::before", ".b-bad::before", "check.svg", "warning.svg", "x-circle.svg"):
        assert needle in V4, needle
    for icon in ("check", "warning", "x-circle"):
        assert (ROOT / "static" / "icons" / f"{icon}.svg").exists()


def test_autopilot_is_four_sections_each_with_content_and_the_choice_is_remembered():
    block = HTML[HTML.index("async function autopilot(m){"):HTML.index("function slotEditor(name){")]
    groups = re.findall(r'data-ap="(overview|schedule|rules|research)"', block)
    assert {g: groups.count(g) for g in ("overview", "schedule", "rules", "research")} == {"overview": 8, "schedule": 1, "rules": 1, "research": 5}
    assert "function apSubSet(" in block and 'role="tablist"' in block and "sessionStorage" in block
    for g in ("overview", "schedule", "rules", "research"):
        assert f'#apwrap[data-sub="{g}"] [data-ap]:not([data-ap="{g}"])' in V4


def test_the_app_installs_on_android_and_its_pages_are_built_for_touch():
    import json
    m = json.loads((ROOT / "static" / "manifest.webmanifest").read_text())
    assert m["display"] == "standalone" and m["start_url"] == "/" and m["name"] and m["short_name"]
    sizes = {(i["sizes"], i["purpose"]) for i in m["icons"]}
    assert ("192x192", "any") in sizes and ("512x512", "any") in sizes and ("512x512", "maskable") in sizes
    for i in m["icons"]:
        assert (ROOT / i["src"].lstrip("/")).is_file()
    for page in (HTML, MON, NOTES, (ROOT / "login.html").read_text()):
        assert 'rel="manifest"' in page and 'name="theme-color"' in page and "viewport" in page
    assert "viewport-fit=cover" in HTML and 'name="color-scheme"' in HTML
    for needle in ("touch-action:manipulation", "-webkit-tap-highlight-color", "min-height:44px", "env(safe-area-inset", "overflow-x:clip", "color-scheme:dark"):
        assert needle in V4, needle
    import dashboard
    assert '".webmanifest": "application/manifest+json"' in (ROOT / "dashboard.py").read_text() and dashboard.H.serve_static


def test_the_deploy_script_never_restarts_the_dashboard_under_a_build_the_owner_started_from_it():
    """29 Oct 2026: it only looked for builds in the worker, so a deploy would have ended a documentary started from the dashboard."""
    sh = (ROOT / "deploy" / "deploy.sh").read_text()
    assert sh.count("docker exec studio-dashboard") >= 2  # looked for in the preview and in the real run
    guard = sh[sh.index("Python files are loaded once"):]
    assert 'dashjobs' in guard and 'FORCE:-0' in guard and "docker compose restart dashboard" in guard
    assert guard.index("dashjobs") < guard.index("docker compose restart dashboard")  # checked before the restart
    assert "(dashboard\\.(py|html)" not in sh  # pages and styles are read from disk: they never needed a restart
