#!/usr/bin/env python3
"""Click every control of the studio dashboard, on a COPY of the studio (never the live one).

    python tools/dashboard_button_audit.py COPY_DIR OUT_DIR [PORT]

COPY_DIR is a copy of the studio folder made WITHOUT secrets (.env, token.json, client_secret.json, settings.json,
data/auth*.json, data/sessions.json) and with run.py replaced by a stand-in that only records what it was asked
to run. The copied dashboard runs with every outside connection pointed at a dead proxy and HOME set inside the
copy, so no button can reach YouTube, OpenRouter, Cloudflare, Telegram or the owner's files, and no job can render
or spend. Without data/auth.json the copied dashboard needs no login, so the owner's password is never used.

For every visible button, switch, checkbox, select and disclosure on every page (and on a few video pages), the
page is opened fresh, the control is clicked with a real mouse event, and the audit records the requests it made
and their answers, dialogs it raised, windows it tried to open, JavaScript errors and server tracebacks.
Writes OUT_DIR/button-audit.json, OUT_DIR/BUTTON_AUDIT.md and screenshots in OUT_DIR/shots/."""
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "tests"))
from browserdrive import Browser  # noqa: E402

COPY = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 8931
BASE = f"http://127.0.0.1:{PORT}"
SHOTS = OUT / "shots"
PY = str(HERE / ".venv" / "bin" / "python")
DEAD = "http://127.0.0.1:9"  # nothing listens here: every outside request of the copied dashboard fails at once
POLLS = ("/api/state", "/api/now", "/api/notifications", "/api/risk")  # background polling, not caused by a click
SECTIONS = ["home", "live", "videos", "autopilot", "desk", "create", "growth", "activity", "youtube", "footage", "channels", "downloads", "reports", "settings"]
SUBTABS = {"autopilot": [f"apSubSet('{k}')" for k in ("overview", "schedule", "rules", "research")],
           "growth": [f"gSubSet('{k}')" for k in ("overview", "videos", "ideas", "research", "controls")]}
PAGES = ["/now", "/competitor", "/notifications", "/monitor", "/footage", "/channels", "/mail"]
SAME_KIND_MAX = 3  # buttons that only differ by the video they act on: the first three of a kind are clicked

INIT = r"""
window.__calls=[];window.__dialogs=[];window.__opens=[];window.__errs=[];
(()=>{const of=window.fetch.bind(window);
window.fetch=async(u,o)=>{o=o||{};const rec={u:String(u),m:o.method||'GET',s:null,b:o.body?String(o.body).slice(0,160):null,r:null};window.__calls.push(rec);
  try{const r=await of(u,o);rec.s=r.status;r.clone().text().then(x=>{rec.r=x.slice(0,240)}).catch(()=>{});return r}catch(e){rec.s='network: '+e;throw e}};
window.confirm=m=>{window.__dialogs.push(['confirm',String(m)]);return true};
window.alert=m=>{window.__dialogs.push(['alert',String(m)])};
window.prompt=(m,d)=>{window.__dialogs.push(['prompt',String(m)]);return null};
window.open=(u,t)=>{window.__opens.push([String(u),String(t||'')]);return null};
addEventListener('error',e=>window.__errs.push('error: '+e.message));
addEventListener('unhandledrejection',e=>window.__errs.push('rejection: '+String(e.reason&&e.reason.message||e.reason)));
const ce=console.error.bind(console);console.error=(...a)=>{window.__errs.push('console: '+a.map(String).join(' ').slice(0,200));ce(...a)};
document.addEventListener('click',e=>{const a=e.target.closest&&e.target.closest('a[target=_blank]');if(a){e.preventDefault();window.__opens.push([a.href,'_blank'])}},true);
})();
"""

LIST = r"""(scope=>{const vis=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
 const root=document.querySelector(scope);if(!root)return [];
 document.querySelectorAll('[data-audit]').forEach(e=>e.removeAttribute('data-audit'));
 const els=[...root.querySelectorAll('button,[role=button],[role=switch],input[type=checkbox],input[type=radio],select,summary')].filter(vis);
 return els.map((e,i)=>({i,tag:e.tagName.toLowerCase(),type:e.type||'',text:(e.getAttribute('aria-label')||e.innerText||e.value||e.title||'').trim().replace(/\s+/g,' ').slice(0,70),
   on:(e.getAttribute('onclick')||e.getAttribute('onchange')||'').slice(0,160),id:e.id||'',disabled:!!e.disabled}))})"""

MARK = r"""((scope,i,text)=>{const vis=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
 const root=document.querySelector(scope);if(!root)return false;
 const els=[...root.querySelectorAll('button,[role=button],[role=switch],input[type=checkbox],input[type=radio],select,summary')].filter(vis);
 const t=e=>(e.getAttribute('aria-label')||e.innerText||e.value||e.title||'').trim().replace(/\s+/g,' ').slice(0,70);
 let e=els[i];if(!e||t(e)!==text)e=els.find(x=>t(x)===text);if(!e)return false;e.setAttribute('data-audit','1');return true})"""

SNAP = r"""({n:__calls.length,d:__dialogs.length,o:__opens.length,e:__errs.length,url:location.href,
  h:(()=>{const m=document.getElementById('main')||document.body;return m.innerHTML.length+':'+[...m.innerHTML].reduce((a,c)=>(a*31+c.charCodeAt(0))|0,0)})()})"""


def kind(c: dict) -> str:
    return c["tag"] + ":" + re.sub(r"'[^']*'|\"[^\"]*\"|\d+", "_", c["on"] or ("text:" + c["text"]))


def start_dashboard():
    home = COPY / "_home"
    home.mkdir(exist_ok=True)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(home), "DASH_PORT": str(PORT), "PYTHONDONTWRITEBYTECODE": "1", "NO_PROXY": "", "no_proxy": ""}
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env[k] = DEAD
    log = (OUT / "dashboard-copy.log").open("w")
    p = subprocess.Popen([PY, "-u", "dashboard.py"], cwd=COPY, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(100):
        try:
            if opener.open(BASE + "/healthz", timeout=2).read() == b"ok":
                return p
        except Exception:
            time.sleep(0.2)
    p.terminate()
    raise SystemExit("the copied dashboard did not start; see " + str(OUT / "dashboard-copy.log"))


def log_size() -> int:
    return (OUT / "dashboard-copy.log").stat().st_size


def log_since(pos: int) -> str:
    with (OUT / "dashboard-copy.log").open(errors="replace") as f:
        f.seek(pos)
        return f.read()


class Audit:
    def __init__(self):
        self.b = Browser(1440, 900)
        self.b.send("Page.enable")
        self.b.send("Page.addScriptToEvaluateOnNewDocument", source=INIT)
        self.rows = []

    def home(self):
        self.b.open(BASE + "/", timeout=30)

    def settle(self, timeout=8):
        end = time.time() + timeout
        time.sleep(0.35)
        while time.time() < end:
            try:
                if self.b.js("__calls.every(c=>c.s!==null)"):
                    break
            except RuntimeError:
                pass
            time.sleep(0.2)
        time.sleep(0.5)

    def prepare(self, where: dict):
        """Open the place the control lives in, fresh."""
        if where["kind"] == "page":
            self.b.open(BASE + where["path"], wait_for="document.body && document.body.innerText.length > 20", timeout=20)
        else:
            if not self.b.js("typeof go === 'function'") or not self.b.js("location.pathname === '/'"):
                self.home()
            self.b.js(f"go('{where['tab']}',{{slug:{json.dumps(where.get('slug'))}}})")
            self.b.until(Browser.READY, 20)
            if where.get("sub"):
                self.settle(5)  # the page loads its own data first (Growth draws its sections only then)
                self.b.js(where["sub"])
        self.settle(6)

    def controls(self, where: dict) -> list[dict]:
        self.prepare(where)
        return self.b.js(f"{LIST}({json.dumps(where['scope'])})") or []

    def click(self, where: dict, c: dict) -> dict:
        row = {"where": where["label"], "control": c["text"] or c["id"] or c["tag"], "tag": c["tag"], "onclick": c["on"], "disabled": c["disabled"]}
        try:
            self.prepare(where)
            if not self.b.js(f"{MARK}({json.dumps(where['scope'])},{c['i']},{json.dumps(c['text'])})"):
                row["result"] = "not found after reopening the page (it depends on earlier state)"
                return row
            s0, pos = self.b.js(SNAP), log_size()
            sel = "document.querySelector('[data-audit=\"1\"]')"
            if c["tag"] == "select":
                row["action"] = "changed to the next option"
                self.b.js(f"(()=>{{const e={sel};e.selectedIndex=(e.selectedIndex+1)%e.options.length;e.dispatchEvent(new Event('change',{{bubbles:true}}))}})()")
            elif c["disabled"]:
                row["result"] = "disabled (not clicked)"
                return row
            else:
                self.b.click(sel)
            self.settle()
            try:
                s1 = self.b.js(SNAP)
                fresh = self.b.js(f"({{calls:__calls.slice({s0['n']}),dialogs:__dialogs.slice({s0['d']}),opens:__opens.slice({s0['o']}),errs:__errs.slice({s0['e']}),"
                                  "toast:(document.querySelector('#toast.show')||{}).textContent||''})")
                navigated = s1["url"] != s0["url"]
            except RuntimeError:  # the click loaded another document
                fresh, navigated, s1 = {"calls": [], "dialogs": [], "opens": [], "errs": [], "toast": ""}, True, {"url": self.b.js("location.href"), "h": ""}
            srv = log_since(pos)
            calls = [x for x in fresh["calls"] if not (x["m"] == "GET" and x["u"].split("?")[0] in POLLS)]
            row.update(calls=[f"{x['m']} {x['u']} -> {x['s']}" + (f" {x['r'][:140]}" if x.get("r") and (not isinstance(x['s'], int) or x['s'] >= 400) else "") for x in calls],
                       dialogs=fresh["dialogs"], opens=fresh["opens"], errors=fresh["errs"], toast=fresh["toast"].strip()[:160],
                       navigated_to=s1["url"] if navigated else None, changed=s1["h"] != s0["h"])
            tb = "Traceback" in srv
            bad_calls = [x for x in calls if not isinstance(x["s"], int) or x["s"] >= 500]
            refused = [x for x in calls if isinstance(x["s"], int) and 400 <= x["s"] < 500]
            handled = [e for e in fresh["errs"] if e.startswith("rejection: ") and fresh["toast"] and e[len("rejection: "):].strip() in fresh["toast"]]
            js_bad = [e for e in fresh["errs"] if e not in handled]
            if tb:
                row["server"] = srv[srv.find("Traceback"):][:900]
            if tb or bad_calls or js_bad:
                row["result"] = "ERROR"
            elif refused:
                row["result"] = "refused with a message" if fresh["toast"] or any(x.get("r") for x in refused) else "refused silently"
            elif calls or navigated or fresh["dialogs"] or fresh["opens"] or row["changed"] or fresh["toast"]:
                row["result"] = "works"
            else:
                row["result"] = "no visible effect"
        except Exception as e:  # one control must never stop the audit
            row["result"] = f"audit could not click it: {type(e).__name__}: {str(e)[:200]}"
            try:
                self.home()
            except Exception:
                pass
        return row

    def run_place(self, where: dict):
        try:
            cs = self.controls(where)
        except Exception as e:
            self.rows.append({"where": where["label"], "control": "(page)", "result": f"page did not open: {type(e).__name__}: {e}"})
            return
        seen: dict[str, int] = {}
        todo = []
        for c in cs:
            k = kind(c)
            seen[k] = seen.get(k, 0) + 1
            if seen[k] <= SAME_KIND_MAX:
                todo.append(c)
        skipped = len(cs) - len(todo)
        print(f"{where['label']}: {len(cs)} controls, {len(todo)} clicked, {skipped} repeats of the same kind skipped", flush=True)
        for c in todo:
            r = self.click(where, c)
            self.rows.append(r)
            if r["result"] not in ("works", "refused with a message", "disabled (not clicked)"):
                print(f"   {r['result']}: {r['control']!r} {r.get('errors') or ''} {r.get('calls') or ''}", flush=True)
        if skipped:
            self.rows.append({"where": where["label"], "control": f"({skipped} more of a kind already clicked)", "result": "skipped (same handler, another item)"})

    def nav_and_chrome(self):
        """The side menu, the tools, settings, the bell and the day and night switch."""
        self.home()
        items = self.b.js("[...document.querySelectorAll('#navlist button,#nav3 button,#nav2 button')].map(b=>b.textContent.trim())")
        for t in items:
            if t == "Sign out":
                continue
            self.home()
            self.b.click(f"[...document.querySelectorAll('#navlist button,#nav3 button,#nav2 button')].find(b=>b.textContent.trim()==={json.dumps(t)})")
            try:
                self.b.until(Browser.READY, 20)
                self.settle(6)
                h1 = self.b.js("(document.querySelector('#main h1')||{}).textContent||''")
                errs = self.b.js("__errs")
                self.rows.append({"where": "menu", "control": t, "result": "works" if h1 and not errs else "ERROR", "opened": h1, "errors": errs})
            except Exception as e:
                self.rows.append({"where": "menu", "control": t, "result": f"ERROR: {type(e).__name__}: {e}"})
        self.home()
        th0 = self.b.js("document.documentElement.dataset.theme")
        self.b.js("toggleTheme()")
        time.sleep(1.4)
        th1 = self.b.js("document.documentElement.dataset.theme")
        self.rows.append({"where": "top bar", "control": "day and night switch", "result": "works" if th0 != th1 else "no visible effect", "before": th0, "after": th1})
        self.b.js(f"setTheme('{th0}')")
        time.sleep(1.4)
        try:
            self.b.js("document.getElementById('bell').click()")
            self.b.until("((document.getElementById('notes')||{}).innerText||'').trim().length > 20", 15)
            n = self.b.js("(document.getElementById('notes').innerText||'').trim().split('\\n').length")
            self.rows.append({"where": "top bar", "control": "bell (notification panel)", "result": "works", "lines": n, "errors": self.b.js("__errs")})
            self.b.js("document.getElementById('bell').click()")
        except Exception as e:
            self.rows.append({"where": "top bar", "control": "bell (notification panel)", "result": f"ERROR: {type(e).__name__}: {e}"})

    def shots_and_phone(self):
        SHOTS.mkdir(parents=True, exist_ok=True)
        over = {}
        self.home()
        for k in SECTIONS:
            self.b.js(f"go('{k}',{{slug:null}})")
            self.b.until(Browser.READY, 20)
            self.settle(5)
            self.b.shot(str(SHOTS / f"desktop-{k}.png"))
        for w, h in ((360, 800), (412, 844)):
            self.b.size(w, h, mobile=True)
            self.home()
            bad = []
            for k in SECTIONS:
                self.b.js(f"go('{k}',{{slug:null}})")
                self.b.until(Browser.READY, 20)
                self.settle(4)
                if self.b.js("document.documentElement.scrollWidth > window.innerWidth + 1"):
                    bad.append(k)
            over[str(w)] = bad
            self.b.shot(str(SHOTS / f"phone-{w}-reports.png"))
            # the phone's More sheet
            try:
                self.b.click("[...document.querySelectorAll('#tabbar button')].find(b=>b.textContent.includes('More'))")
                time.sleep(0.6)
                self.rows.append({"where": f"phone {w}px", "control": "More (menu sheet)", "result": "works" if self.b.js("(document.getElementById('sheetcard').innerText||'').length > 40") else "no visible effect"})
                self.b.key("Escape", vk=27)
            except Exception as e:
                self.rows.append({"where": f"phone {w}px", "control": "More (menu sheet)", "result": f"ERROR: {type(e).__name__}: {e}"})
        self.b.size(1440, 900)
        return over


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.time()
    p = start_dashboard()
    a = None
    try:
        a = Audit()
        a.home()
        slugs = a.b.js("(S.videos||[]).map(v=>[v.slug,v.state||v.status||''])") or []
        picked, states = [], set()
        for slug, st in slugs:  # one video of each state, at most five
            if st not in states and len(picked) < 5:
                states.add(st)
                picked.append(slug)
        a.nav_and_chrome()
        places = []
        for k in SECTIONS:
            for sub in SUBTABS.get(k, [None]):
                places.append({"kind": "tab", "tab": k, "sub": sub, "scope": "#main", "label": k + (" / " + sub.split("'")[1] if sub else "")})
        for s in picked:
            places.append({"kind": "tab", "tab": "videos", "slug": s, "scope": "#main", "label": f"video page: {s}"})
        for path in PAGES:
            places.append({"kind": "page", "path": path, "scope": "body", "label": "page " + path})
        for w in places:
            a.run_place(w)
        over = a.shots_and_phone()
    finally:
        if a:
            a.b.close()
        p.terminate()
        try:
            p.wait(timeout=10)
        except Exception:
            p.kill()
    jobs = (COPY / "audit_jobs.jsonl").read_text().splitlines() if (COPY / "audit_jobs.jsonl").exists() else []
    tb = log_since(0).count("Traceback")
    res = {"started": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(started)) + " UTC", "minutes": round((time.time() - started) / 60, 1),
           "videos_opened": picked, "rows": a.rows if a else [], "phone_sideways_scroll": over, "jobs_requested": [json.loads(j) for j in jobs],
           "server_tracebacks": tb}
    (OUT / "button-audit.json").write_text(json.dumps(res, indent=1))
    count: dict[str, int] = {}
    for r in res["rows"]:
        key = r["result"] if not r["result"].startswith(("ERROR", "audit could not", "page did not")) else "ERROR"
        count[key] = count.get(key, 0) + 1
    print("\nresults:", json.dumps(count), "| server tracebacks:", tb, "| phone sideways scroll:", over, "| jobs asked for:", len(jobs))
    print(f"{res['minutes']} minutes")


if __name__ == "__main__":
    main()
