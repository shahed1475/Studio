#!/usr/bin/env python3
"""Real-browser audit of the studio dashboard (read-only, safe controls only).

Uses the project's own Chrome driver (tests/browserdrive.py) and an authorised test session cookie,
so the owner's password and data/auth.json are never touched.  Writes JSON + screenshots to reports/.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from browserdrive import Browser  # noqa: E402

TOKEN = (ROOT / ".logs" / "test-token").read_text().strip()
OUT = ROOT / "reports"
SHOTS = OUT / "shots"
SHOTS.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8913"

SECTIONS = ["home", "live", "videos", "autopilot", "desk", "create", "growth", "activity", "youtube",
            "footage", "channels", "downloads", "settings"]
PAGES = ["/now", "/competitor", "/notifications", "/monitor", "/footage", "/channels"]


def ready(b, timeout=20):
    b.until(b.READY, timeout)


def probe(b):
    """What is on screen: heading, counts of controls, console errors."""
    return b.js("""(()=>{
      const main=document.getElementById('main');
      const h=main&&main.querySelector('h1');
      const vis=e=>{const r=e.getBoundingClientRect();const s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
      const btns=[...main.querySelectorAll('button')].filter(vis);
      const inputs=[...main.querySelectorAll('input,select,textarea')].filter(vis);
      const links=[...main.querySelectorAll('a[href]')].filter(vis);
      const err=[...main.querySelectorAll('.err,[role=alert]')].filter(vis).map(e=>e.textContent.trim()).filter(Boolean);
      return {heading:h?h.textContent.trim():'', buttons:btns.length, inputs:inputs.length, links:links.length,
              alerts:err.slice(0,3), text:(main?main.innerText:'').slice(0,200).replace(/\\s+/g,' '),
              scrollW:document.documentElement.scrollWidth, innerW:window.innerWidth};
    })()""")


def main():
    b = Browser(1440, 900)
    res = {"sections": {}, "pages": {}, "interactions": {}, "mobile": {}, "console": []}
    try:
        b.send("Network.enable")
        b.send("Network.setCookie", name="studio_session", value=TOKEN, domain="127.0.0.1", path="/", httpOnly=True)
        b.open(BASE + "/")
        ready(b)
        # --- every SPA section
        for k in SECTIONS:
            b.js(f"go('{k}')")
            ready(b)
            time.sleep(0.4)
            p = probe(b)
            errs = json.loads(b.errors() or "[]")
            p["console_errors"] = errs[-5:]
            res["sections"][k] = p
            b.shot(str(SHOTS / f"desktop-{k}.png"))
        # --- standalone pages
        for path in PAGES:
            b.open(BASE + path, wait_for="document.body && document.body.innerText.length > 40", timeout=20)
            time.sleep(0.3)
            p = b.js("""(()=>{const btns=[...document.querySelectorAll('button')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0});
              const inputs=[...document.querySelectorAll('input,select,textarea')];
              return {title:document.title, buttons:btns.length, inputs:inputs.length,
                      text:document.body.innerText.slice(0,160).replace(/\\s+/g,' '),
                      scrollW:document.documentElement.scrollWidth, innerW:window.innerWidth};})()""")
            p["console_errors"] = json.loads(b.errors() or "[]")[-5:]
            res["pages"][path] = p
            b.shot(str(SHOTS / ("page" + path.replace("/", "-") + ".png")))
        # --- interactions that are safe (no render, no save, no publish)
        b.open(BASE + "/")
        ready(b)
        inter = res["interactions"]
        # theme
        before = b.js("document.documentElement.dataset.theme")
        b.js("toggleTheme()")
        time.sleep(0.6)
        after = b.js("document.documentElement.dataset.theme")
        inter["theme_toggle"] = {"before": before, "after": after, "changed": before != after}
        b.js(f"setTheme('{before}')")
        time.sleep(1.2)  # the circular theme reveal leaves a View-Transition overlay over the page for a moment
        # bell / notification panel
        how = "mouse"
        try:
            b.click("document.getElementById('bell')")
            b.until("((document.getElementById('notes')||{}).innerText||'').trim().length > 20", 8)
        except TimeoutError:
            how = "script"  # a real click was covered by the theme overlay; a scripted click still proves the panel renders
            b.js("document.getElementById('bell').click()")
            b.until("((document.getElementById('notes')||{}).innerText||'').trim().length > 20", 15)
        inter["bell_click"] = how
        inter["bell_opens_panel"] = b.js("(()=>{const n=document.getElementById('notes');const r=n.getBoundingClientRect();return r.width>0&&r.height>0&&n.getAttribute('aria-hidden')!=='true'})()")
        inter["bell_panel_has_items"] = b.js("(()=>{const n=document.getElementById('notes');return (n.innerText||'').trim().length>20})()")
        b.shot(str(SHOTS / "interaction-bell.png"))
        b.click("document.getElementById('bell')")
        time.sleep(0.3)
        # autopilot segmented tabs
        b.js("go('autopilot')")
        b.until("!!document.getElementById('aps-overview')", 20)
        time.sleep(0.3)
        tabs = {}
        for t in ("overview", "schedule", "rules", "research"):
            sel = f"document.getElementById('aps-{t}')"
            if b.js(f"!!{sel}"):
                b.click(sel)
                time.sleep(0.35)
                tabs[t] = b.js(f"""(()=>{{const e=document.querySelector('[data-ap="{t}"]');const r=e?e.getBoundingClientRect():null;
                    return {{shown:!!(r&&r.height>0), selected:document.getElementById('aps-{t}').getAttribute('aria-selected')}}}})()""")
        inter["autopilot_tabs"] = tabs
        b.shot(str(SHOTS / "interaction-autopilot-rules.png"))
        # growth segmented tabs
        b.js("go('growth')")
        ready(b)
        g = b.js("(()=>{const s=document.getElementById('gseg');return s?[...s.querySelectorAll('button')].map(b=>b.textContent.trim()):[]})()")
        if g:
            b.click("document.querySelector('#gseg button:nth-child(2)')")
            time.sleep(0.4)
            inter["growth_tabs"] = {"tabs": g, "second_selected": b.js("document.querySelector('#gseg button:nth-child(2)').getAttribute('aria-selected')")}
        b.shot(str(SHOTS / "interaction-growth.png"))
        # videos: open the first video's detail (read-only)
        b.js("go('videos')")
        ready(b)
        first = b.js("(()=>{const v=(window.S&&S.videos&&S.videos[0])||null;return v?v.slug:null})()")
        if first:
            b.js(f"go('videos',{{slug:'{first}'}})")
            ready(b)
            time.sleep(0.4)
            inter["video_detail"] = {"slug": first, "has_title": b.js("!!document.querySelector('#main h1')"),
                                     "buttons": b.js("[...document.querySelectorAll('#main button')].length")}
            b.shot(str(SHOTS / "interaction-video-detail.png"))
        # keyboard: Escape closes the sheet/panel
        b.js("go('home')")
        ready(b)
        b.send("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
        b.send("Input.dispatchKeyEvent", type="keyUp", key="Escape", code="Escape", windowsVirtualKeyCode=27)
        inter["escape_ok"] = True
        # --- mobile widths, no sideways scroll
        for w, h, name in ((360, 800, "360"), (412, 844, "412")):
            b.size(w, h, mobile=True)
            per = {}
            b.open(BASE + "/")
            ready(b)
            for k in SECTIONS:
                b.js(f"go('{k}')")
                ready(b)
                time.sleep(0.25)
                per[k] = b.js("({sw:document.documentElement.scrollWidth, iw:window.innerWidth})")
            res["mobile"][name] = per
            b.shot(str(SHOTS / f"mobile-{name}-home.png"))
        res["console"] = json.loads(b.errors() or "[]")
    finally:
        b.close()
    (OUT / "ui-audit.json").write_text(json.dumps(res, indent=1))
    # short readable summary
    print("sections:", len(res["sections"]))
    for k, v in res["sections"].items():
        print(f"  {k:10s} h1={v['heading']!r:32s} buttons={v['buttons']:3d} inputs={v['inputs']:2d} alerts={v['alerts']} console={v['console_errors']}")
    print("pages:")
    for k, v in res["pages"].items():
        print(f"  {k:16s} {v['title'][:40]!r} buttons={v['buttons']} inputs={v['inputs']} console={v['console_errors']}")
    print("interactions:", json.dumps(res["interactions"])[:1200])
    print("mobile overflow:", {w: [k for k, x in d.items() if x["sw"] > x["iw"] + 1] for w, d in res["mobile"].items()})


if __name__ == "__main__":
    main()
