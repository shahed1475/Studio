"""Doctor: the agent that keeps the other agents working.

Every 6 hours: (1) compare each agent's last run with its cadence and read the worker log, (2) for an agent that is stale or keeps failing run the escalation
ladder with SAFE fixes only (run its registered job again, fix file permissions, create missing folders), (3) when that fails write a post-mortem proposal,
(4) draft a skill, in quarantine, for a problem family that keeps coming back, (5) check that the dashboard answers and list missing setup with the exact
commands for the owner. Every attempt is a lesson.
It installs nothing, runs only registered jobs, puts no draft into service (the owner adds a skill with `python extend.py add` after `vetskill.py`), and
never makes anything public or deletes anything. It uses the model roles the worker has (OpenRouter); MCP servers exist only in Claude Code sessions."""
import datetime as dt
import json
import re
import urllib.request
from pathlib import Path

import agentbus
import agentlog
import agents
import config
import escalate
import filelock
import playbook
import scriptreview

REPORT = config.ROOT / "data" / "agent" / "doctor.json"
PROPOSALS = config.ROOT / "data" / "agent" / "proposals"
STALE_FACTOR = 2.5     # an agent is stale when it has not run for this many of its own periods
FAIL_STREAK = 2        # consecutive failed runs that make an agent "failing"
MAX_PER_RUN = 2        # agents the ladder works on in one run
DASHBOARD = "http://127.0.0.1:8913/healthz"
TS = "%Y-%m-%dT%H:%M:%SZ"
MIN_FREE_GB = 20.0  # below this a long film (renders, motion clips and caches) may not fit: the owner is asked to look; nothing is deleted
NEVER_RERUN = {"autopilot"}  # the main loop is not restarted from outside; it has its own lock and its own recovery


def _parse(ts: str) -> dt.datetime:
    return dt.datetime.strptime(ts, TS).replace(tzinfo=dt.timezone.utc)


def log_results(job: str, lines: list[str]) -> list[bool]:
    """True/False for each logged run of the job, oldest first (exit 0 is True; a non-zero exit, a timeout or a start failure is False)."""
    out = []
    for line in lines:
        m = re.match(rf"^\S+ {re.escape(job)} .*? -> exit (\d+)$", line)
        if m:
            out.append(m.group(1) == "0")
        elif re.match(rf"^\S+ {re.escape(job)} .*(timed out after|could not start)", line):
            out.append(False)
    return out


HEALTH = {"ok": "HEALTHY", "stale": "STALE", "failing": "FAILED", "not_yet": "NOT_TESTED"}  # evidence-based names shown with every row (22 Nov 2026)
KEY_URL = "https://openrouter.ai/api/v1/key"  # OpenRouter's key check: free, no model, no tokens


def _last_success(job: str, lines: list[str]) -> str | None:
    """When the job last ended with exit 0 in logs/worker.log (its first field), or None when no successful run is in the lines read."""
    ok = [l.split(" ", 1)[0] for l in lines if re.match(rf"^\S+ {re.escape(job)} .*? -> exit 0$", l)]
    return ok[-1] if ok else None


def probe_openrouter_key(now: dt.datetime, get=None) -> dict:
    """A real check of the saved OpenRouter key (22 Nov 2026: the doctor reported 12/12 free models while every one answered 401, because it only
    checked that a key existed). HEALTHY on 200, FAILED on 401 (and the router is told, so it stops asking OpenRouter), UNKNOWN when the check itself
    cannot run, NOT_CONFIGURED without a key. `get(url)` returns a status code in tests."""
    import llm

    out = {"checked_at": now.strftime(TS), "source": "GET " + KEY_URL}
    key = llm.api_key()
    if not key:
        return {**out, "state": "NOT_CONFIGURED", "evidence": "no OpenRouter key is saved"}
    try:
        if get:
            code, text = get(KEY_URL), ""
        else:
            import requests

            r = requests.get(KEY_URL, headers={"Authorization": f"Bearer {key}"}, timeout=10)
            code, text = r.status_code, llm.scrub(r.text)[:160]
    except Exception as e:
        return {**out, "state": "UNKNOWN", "evidence": f"the check could not run ({type(e).__name__})"}
    if code == 200:
        return {**out, "state": "HEALTHY", "evidence": "OpenRouter accepted the key"}
    if code == 401:
        llm._openrouter_refused_now(now, key, 401, text or "401")
        return {**out, "state": "FAILED", "evidence": f"OpenRouter refused the key (401) {text}".strip()}
    return {**out, "state": "UNKNOWN", "evidence": f"OpenRouter answered {code}"}


def scan(now: dt.datetime, state: dict | None = None, lines: list[str] | None = None, jobs=None) -> list[dict]:
    """One row per agent that has a worker job: status ok, stale, failing, or not_yet (no run recorded: a new install is not a fault)."""
    import worker

    state = worker.load_state() if state is None else state
    if lines is None:
        try:
            lines = worker.LOG.read_text().splitlines()[-600:]
        except OSError:
            lines = []
    jd = agents.job_defs(jobs)
    rows = []
    for name, a in agents.AGENTS.items():
        job = a.get("job")
        if not job or job not in jd:
            continue
        last, res = state.get(job), log_results(job, lines)
        row = {"agent": name, "job": job, "last": last, "status": "ok", "evidence": "", "checked_at": now.strftime(TS),
               "source": "worker state (last start) and logs/worker.log (exit codes)", "last_success": _last_success(job, lines)}
        try:
            age = None if last is None else (now - _parse(last)).total_seconds()
        except (ValueError, TypeError):
            age = float("inf")  # a time that cannot be read counts as a run that did not happen
        if last is None:
            row["status"] = "not_yet"
        elif age > STALE_FACTOR * agents.cadence_seconds(jd[job]):
            row["status"], row["evidence"] = "stale", f"last run {str(last)[:30]}, expected every {agents.cadence_seconds(jd[job]) / 3600:.0f} hours"
        if len(res) >= FAIL_STREAK and not any(res[-FAIL_STREAK:]):
            row["status"] = "failing"
            row["evidence"] = "; ".join(l[:160] for l in lines if re.match(rf"^\S+ {re.escape(job)} ", l))[-400:]
        row["health"] = HEALTH[row["status"]]
        row["failure_reason"] = row["evidence"] if row["status"] != "ok" else ""
        rows.append(row)
    return rows


def probe_dashboard(get=None) -> int | None:
    """The HTTP status of the local dashboard's health page, or None when nothing answers."""
    try:
        if get:
            return get(DASHBOARD)
        with urllib.request.urlopen(DASHBOARD, timeout=5) as r:
            return r.status
    except Exception:
        return None


def provider_answers(url: str, get=None) -> bool:
    """True when the owner's model provider at `url` answers at all (any HTTP status, a 401 too): one GET of its model list, no key sent, 3 s."""
    import requests

    try:
        (get or requests.get)(url.rstrip("/") + "/models", timeout=3, allow_redirects=False)
        return True
    except requests.RequestException:
        return False


def needs(dashboard: int | None, now: dt.datetime, reach=None) -> list[dict]:
    """Setup the agents cannot do for themselves: what is missing, why it matters, the exact lines to run."""
    import backup
    import llm
    import titletest

    out = []
    if dashboard != 200:
        out.append({"need": "dashboard", "why": "the dashboard does not answer on this machine; the owner cannot see or approve anything",
                    "commands": ["cd ~/studio && docker compose restart dashboard", "docker logs --tail 50 studio-dashboard"]})
    if not llm.api_key():
        out.append({"need": "model key", "why": "no OpenRouter key is saved, so no agent can use a model",
                    "commands": ["Open Settings in the dashboard and save the OpenRouter key (never paste it in chat)"]})
    elif llm.openrouter_refused(now):
        out.append({"need": "model key refused", "why": "OpenRouter refuses the saved key (HTTP 401), so every OpenRouter model is skipped; only Google (the Gemini key) and the "
                    "owner's own provider can write and judge, and a fact-check needs two judges that answer",
                    "commands": ["Create a new key at https://openrouter.ai/keys and save it in Settings, OpenRouter card (only sk-or- keys are accepted; never paste it in chat)",
                                 "A key from another service (FreeLLMAPI, Gemini) goes into its own card"]})
    own = llm.extra_cfg()
    if own and re.match(r"https?://(127\.0\.0\.1|localhost)[:/]", own["url"]) and not (reach or provider_answers)(own["url"]):
        out.append({"need": "own model provider", "why": "the model provider app on this PC (FreeLLMAPI) does not answer, so the owner's free writers and judges are not "
                    "used; OpenRouter's free models stand in meanwhile. The app does not start by itself after a power cut",
                    "commands": ["Open the FreeLLMAPI app on the PC (21 Nov 2026: ~/Downloads/FreeLLMAPI-0.16.31.AppImage)",
                                 f"curl -s -o /dev/null -w '%{{http_code}}\\n' {own['url']}/models   # any number means it is running"]})
    if titletest.mode() == "apply" and not titletest.can_write():
        out.append({"need": "youtube edit permission", "why": "the title test is in apply mode but the YouTube login cannot edit videos",
                    "commands": ["Open Settings, reconnect YouTube and allow managing your videos"]})
    gb = free_gb()
    if gb is not None and gb < MIN_FREE_GB:
        out.append({"need": "disk space", "why": f"only {gb:.0f} GB free where the studio keeps its videos; a long render can fail part way",
                    "commands": ["du -sh ~/studio/output ~/studio/output_old ~/studio/cache ~/studio/backups", "df -h ~/studio",
                                 "Move old videos you no longer need off this PC yourself: the studio never deletes a video to make room"]})
    if backup.pushed_age_hours(now) is None:
        out.append({"need": "off-server backup", "why": "no backup copy has left the server yet",
                    "commands": ["Create a private GitHub repo for the records", "Set BACKUP_REPO_URL and BACKUP_SSH_KEY_FILE in ~/studio/.env", "Run deploy/backup_push.sh once"]})
    return out


def free_gb(usage=None) -> float | None:
    """Free space where the studio keeps its videos, in GB (None when it cannot be read)."""
    import shutil

    try:
        return (usage or shutil.disk_usage)(config.ROOT).free / 1e9
    except OSError:
        return None


def provider_status(now: dt.datetime) -> dict:
    """How many free text models can be asked right now, read from the studio's own records (no network): the owner's provider and OpenRouter's
    free roster. Free tiers rate-limit and recover on their own, so this is reported in doctor.json, not raised as a task every six hours."""
    import freemodels
    import llm

    try:
        cfg = llm.load_config()
        extras = sorted({m for r in ("script", "review", "cheap") for m in llm.extra_models(r)})
        roster = freemodels.roster_ids()
        try:
            health = json.loads(freemodels.FILE.read_text()).get("health", {})
        except (OSError, ValueError):
            health = {}

        def proven(m):  # available now AND its newest success is newer than its newest failure: a cool-down that ran out proves nothing (22 Nov 2026)
            h = health.get(m) or {}
            if not freemodels.available(m, now) or not h.get("ok"):
                return False
            lo, lf = h.get("last_ok"), h.get("last_fail")
            return not lf or bool(lo and lo > lf)

        refused = llm.openrouter_refused(now) is not None
        ok = lambda ids: sum(1 for m in ids if proven(m))
        return {"free_mode": bool(llm.free_only()), "paid_allowed": bool(llm.paid_allowed(cfg)), "own_provider": {"models": len(extras), "available": ok(extras)},
                "openrouter_free": {"models": len(roster), "available": 0 if refused else ok(roster), **({"note": "the OpenRouter key is refused (401)"} if refused else {})},
                "checked_at": now.strftime(TS), "source": "data/free_models.json (newest success after newest failure) and the OpenRouter key check"}
    except Exception as e:  # a report line, never a reason for the doctor's run to fail
        return {"error": type(e).__name__}


def production_status(now: dt.datetime, pending: Path | None = None) -> dict:
    """The production parts added on 20 Nov 2026 and the known ways they stop, read from files (no network, no model): Blender for 3D scenes, the music library, a film
    waiting at its checkpoint for the free pictures, and saved scripts set aside. Each problem carries its plain reason and the exact safe step; the doctor never starts
    a production itself (a render is long and belongs to Autopilot's lock), it says when and how the waiting film continues."""
    out = {"blender": None, "music_tracks": 0, "checkpoints": [], "set_aside": [], "problems": []}
    try:
        import ccrender

        out["blender"] = ccrender.BLENDER.exists()
        if not out["blender"]:
            out["problems"].append({"need": "blender", "why": f"Blender is not at {ccrender.BLENDER}: documentaries get no 3D globe or scenes (they are still made with other pictures)",
                                    "commands": ["ls ~/tools/blender/blender", "cd ~/studio && docker compose config | grep -A2 opt/blender",
                                                 "export STUDIO_UID=$(id -u) STUDIO_GID=$(id -g); docker compose up -d worker dashboard   # only when no render is running"]})
    except Exception as e:
        out["problems"].append({"need": "blender", "why": f"the Blender check failed ({type(e).__name__})", "commands": []})
    try:
        import musicbed

        out["music_tracks"] = len(musicbed.tracks())
        if not out["music_tracks"]:
            out["problems"].append({"need": "music", "why": "no usable track in music/ (each needs its LEDGER.json entry, an unchanged file and LICENSE.txt): videos are made without music",
                                    "commands": ["cat ~/studio/music/LICENSE.txt", "python -c \"import musicbed; print(len(musicbed.tracks()))\""]})
    except Exception:
        pass
    pend = pending or config.ROOT / "data" / "pending_doc.json"
    try:
        saved = json.loads(pend.read_text())
        wait = saved.get("waiting_for_pictures")
        if wait:
            import freeart

            back = freeart.quota_left(now=now) >= freeart.MIN_LEFT_TO_START
            out["checkpoints"].append({"film": str(saved.get("data", {}).get("title", ""))[:80], "folder": saved.get("folder", ""), "waiting_for": "free pictures",
                                       "scenes_left": wait.get("short"), "ready_to_continue": back,
                                       "resume": "python run.py autopilot make doc   (continues the same film from data/pending_doc.json; pictures drawn so far cost nothing)"})
    except (OSError, ValueError):
        pass
    out["set_aside"] = sorted(f.name for f in pend.parent.glob("pending_doc.set-aside-*.json"))
    try:  # what a power cut or a killed render left unfinished (recovery.py): read only, the doctor never starts the render itself
        import recovery

        out["interrupted"] = [i for i in recovery.scan(pend.parent / "output" if pending else None, pend) if i["interrupted"]]
    except Exception:
        out["interrupted"] = []
    return out


def can_spend() -> bool:
    import llm

    try:
        return bool(llm.api_key()) and llm.spent_today() < llm.load_config()["daily_budget_usd"] - 0.3
    except Exception:
        return False


def fixes_for(agent: str, job: str, jobs=None, runner=None, busy=None) -> dict:
    """The only things the doctor may do to an unhealthy agent. `runner` runs a registered worker job and returns its exit code; `busy` lists running renders."""
    import risk
    import safety

    jd = agents.job_defs(jobs)

    def rerun():
        if job in NEVER_RERUN or job not in jd:
            return False, "this job is not run again from outside"
        if (busy or risk.running_jobs)():
            return False, "a render is running: not now"
        import worker

        rc = (runner or worker.run_job)(jd[job])
        return rc == 0, f"{job} finished with exit {rc}"

    def perms():
        done = safety.fix_permissions()
        return bool(done), ("fixed permissions on " + ", ".join(done)) if done else "nothing to change"

    def dirs():
        made = [p.name for p in (config.ROOT / "data" / "agent", config.ROOT / "logs", config.OUT) if not p.exists()]
        try:
            for p in (config.ROOT / "data" / "agent", config.ROOT / "logs", config.OUT):
                p.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return False, f"cannot create a folder ({type(e).__name__})"
        return bool(made), ("created " + ", ".join(made)) if made else "nothing missing"

    return {"rerun_job": (f"run the {job} job again now", rerun), "fix_permissions": ("make the secret files private again", perms),
            "create_folders": ("create a missing data, logs or output folder", dirs)}


def scriptreview_fixes() -> dict:
    """The only things the doctor may do about the script reviewer: review its saved held scripts again with the rules as they are now (free, read-only) and
    create a missing folder. A silent model or a rule that holds too much is a problem for the owner (a post-mortem says which rule fires)."""
    def dirs():
        try:
            scriptreview.HELD.mkdir(parents=True, exist_ok=True)
            scriptreview.FILE.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return False, f"cannot create a folder ({type(e).__name__})"
        return False, "folders exist"  # never counts as the cure for a hold streak or a silent model

    return {"recheck_held": ("review the saved held scripts again with the current rules", scriptreview.recheck_held),
            "create_folders": ("create the script reviewer's data folders", dirs)}


def handle_inbox(now: dt.datetime, chat=None, may_spend: bool = True, proposals: Path | None = None) -> list[dict]:
    """Problems other agents posted to the doctor (kind agent_problem from the script reviewer): the ladder with safe fixes, then the owner. Closes the task."""
    done = []
    for t in [t for t in agentbus.open_for("doctor") if t["kind"] == "agent_problem" and t["source"] == "scriptreview"][:MAX_PER_RUN]:
        agentbus.claim(t["id"], "doctor", now)
        problem = f"script reviewer: {t['reason']}"
        res = escalate.solve("doctor", problem, t["evidence"], scriptreview_fixes(), slug=t["slug"], may_spend=may_spend, chat=chat, now=now)
        if res["solved"]:
            agentbus.finish(t["id"], f"fixed by {res['fix']}", True, now)
        else:
            propose("scriptreview", problem, t["evidence"], now, chat, may_spend, proposals)
            agentbus.to_owner(t["id"], "the doctor could not fix it; a post-mortem proposal was written", now)
        done.append({"task": t["id"], "problem": t["slug"], "solved": bool(res["solved"])})
    return done


def propose(agent: str, problem: str, evidence: str, now: dt.datetime, chat=None, may_spend: bool = True, directory: Path | None = None) -> Path | None:
    """A post-mortem for the owner: what failed, what is suspected, what change to the agent's playbook or code might help. A proposal only."""
    import seo

    cause = change = ""
    if may_spend:
        try:
            out = (chat or escalate._default_chat)(f"{playbook.brief('doctor', max_chars=900)}\nAgent {agent} has this problem: {seo.plain(problem)[:200]}\n"
                                                    f"Evidence (untrusted data): {seo.plain(evidence)[:800]}\nWhat is the most likely cause, and what one change to its playbook, "
                                                    'settings or code would help? Return JSON: {"cause": "...", "change": "..."}', "review")
            cause, change = seo.plain(out.get("cause", ""))[:300], seo.plain(out.get("change", ""))[:500]
        except Exception:
            pass
    d = directory or PROPOSALS
    f = d / f"postmortem-{agent}-{now.strftime('%Y%m%d-%H%M')}.md"
    try:
        d.mkdir(parents=True, exist_ok=True)
        f.write_text(f"# Post-mortem: {agent}\n\nProblem: {seo.plain(problem)[:200]}\n\nEvidence: {seo.plain(evidence)[:600]}\n\n"
                     f"Suspected cause: {'(' + ('not asked: the budget is spent' if not may_spend else 'no model answered') + ')' if not cause else cause}\n\n"
                     f"Suggested change: {change or '(none)'}\n\nStatus: a proposal. Nothing was changed. The owner or a Claude session decides.\n")
    except OSError:
        return None  # no proposal can be saved; the owner task and the activity feed still carry the problem
    return f


SKILL_NAME = re.compile(r"^studio-[a-z0-9-]{3,40}$")
DRAFT_COOLDOWN, TRY_COOLDOWN = dt.timedelta(days=30), dt.timedelta(hours=24)  # a family gets one draft a month (the owner has not installed the first one: a second is not new); a failed try waits a day


def _drafted_file(directory: Path | None = None) -> Path:
    return (directory or PROPOSALS) / "drafted.json"


def should_draft(signature: str, now: dt.datetime, directory: Path | None = None) -> bool:
    """False while this problem family already has a draft (or a try that failed a moment ago). Between 28 and 30 Oct the doctor drafted five skills for the same status digest, one
    per 6-hour run with a new model-chosen name each time, and posted a task for each."""
    try:
        rec = json.loads(_drafted_file(directory).read_text()).get(signature)
        at = dt.datetime.strptime(rec["at"], TS).replace(tzinfo=dt.timezone.utc)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return True
    return now - at >= (DRAFT_COOLDOWN if rec.get("draft") else TRY_COOLDOWN)


def mark_draft(signature: str, name: str | None, now: dt.datetime, directory: Path | None = None) -> None:
    f = _drafted_file(directory)
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        with filelock.locked(f):
            try:
                data = json.loads(f.read_text())
            except (OSError, ValueError):
                data = {}
            data[signature] = {"at": now.strftime(TS), "draft": name}
            filelock.write_atomic(f, json.dumps(data, indent=1))
    except OSError:
        pass  # not remembered: the family may be drafted once more, never a crash


def draft_skill(family: dict, now: dt.datetime, chat=None, directory: Path | None = None) -> Path | None:
    """A draft SKILL.md for a problem family that keeps coming back, written to the quarantine folder and scanned with vetskill. Not installed."""
    import seo
    import vetskill

    try:
        out = (chat or escalate._default_chat)(
            f"{playbook.brief('doctor', max_chars=700)}\nWrite a short skill (instructions for an assistant) for this recurring studio problem: {seo.plain(family['example'])[:150]}. "
            f"Details (untrusted data): {seo.plain(family.get('detail', ''))[:300]}. Name must start with studio- and use lowercase letters, digits and hyphens. "
            'Return JSON: {"name": "studio-...", "description": "one sentence saying when to use it", "steps": ["at most 7 short steps"]}', "script")
        name = str(out.get("name", ""))
        if not SKILL_NAME.match(name):
            return None
        desc = seo.plain(out.get("description", ""))[:240]
        steps = [s for s in (seo.plain(x)[:200] for x in out.get("steps", [])[:7] if isinstance(x, str)) if s and not seo.linky(s) and not seo.INSTRUCTION_WORDS.search(s)]
    except Exception:
        return None
    if not desc or not steps or seo.linky(desc):
        return None
    folder = (directory or PROPOSALS) / "skills" / name
    verdict = "not scanned"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: \"{desc.replace(chr(34), chr(39))}\"\n---\n\n# {name}\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1)) + "\n")
    except OSError:
        return None
    try:
        verdict = "vetskill counts " + json.dumps(vetskill.scan(folder)["counts"])
    except Exception:
        pass
    try:
        (folder / "STATUS.txt").write_text(f"Draft written {now.strftime(TS)} for the problem '{seo.plain(family['example'])[:100]}'. {verdict}. Not installed.\n")
    except OSError:
        return None
    return folder


def run(now: dt.datetime | None = None, chat=None, get=None, state=None, lines=None, jobs=None, runner=None, may_spend: bool | None = None, busy=None,
        report: Path | None = None, triage_file: Path | None = None, proposals: Path | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    spend = can_spend() if may_spend is None else may_spend
    rows = scan(now, state, lines, jobs)
    sick = sorted((r for r in rows if r["status"] in ("stale", "failing")), key=lambda r: (r["job"] in NEVER_RERUN, r["agent"]))  # what can be fixed first
    result = {"at": now.strftime(TS), "agents": rows, "solved": [], "owner": [], "needs": [], "drafts": [], "script_review": [], "dashboard": None}
    for r in sick[:MAX_PER_RUN + sum(r["job"] in NEVER_RERUN for r in sick)]:
        problem = f"agent {r['agent']} is {r['status']}"
        fixable = r["job"] not in NEVER_RERUN  # the main loop cannot be restarted from outside: no model is asked about it, the owner is told
        res = escalate.solve("doctor", problem, r["evidence"], fixes_for(r["agent"], r["job"], jobs, runner, busy), slug=r["agent"], may_spend=spend and fixable, chat=chat, now=now)
        if res["solved"]:
            result["solved"].append({"agent": r["agent"], "fix": res["fix"]})
        else:
            propose(r["agent"], problem, r["evidence"], now, chat, spend, proposals)
            result["owner"].append(r["agent"])
    result["script_review"] = handle_inbox(now, chat, spend, proposals)
    result["dashboard"] = probe_dashboard(get)
    result["openrouter_key"] = probe_openrouter_key(now, get)
    result["providers"] = provider_status(now)
    result["free_gb"] = round(free_gb() or 0, 1)
    result["production"] = production_status(now)
    for c in result["production"]["checkpoints"]:
        if c["ready_to_continue"]:  # today's free pictures are back: one task, not one every six hours
            agentbus.post_to_owner_once("resume_film", "doctor", c["folder"] or c["film"], f"The film '{c['film']}' waited for free pictures; today's allowance is back, so it can continue.",
                                        now=now, commands=[c["resume"]])
    for i in result["production"].get("interrupted", []):  # one task per interrupted film, never a render started from here (renders belong to Autopilot's lock)
        agentbus.post_to_owner_once("resume_interrupted", "doctor", i["folder"],
                                    f"A render of {i['folder']} was cut off (power cut, restart or kill). Kept: {i['voice_lines_kept']} voice lines, {i['scenes_kept']} of "
                                    f"{i['scenes_total'] or '?'} checked scenes. Autopilot continues it from there; nothing finished is made again.", now=now, commands=[i["resume"], "python run.py recover"])
    extra = result["production"]["problems"]
    for n in needs(result["dashboard"], now) + extra:
        agentbus.post("setup_request", "doctor", "owner", n["need"], reason=n["why"], now=now, commands=n["commands"])
        result["needs"].append(n["need"])
    for r in agentbus.tasks():  # a setup item that is there again is no longer a request: close what the doctor itself posted
        if r["kind"] == "setup_request" and r["source"] == "doctor" and r["state"] in agentbus.LIVE and r["slug"] not in result["needs"]:
            agentbus.close_for(r["slug"], "no longer missing", True, "setup_request", now)
    try:
        fam = [f for f in json.loads((triage_file or config.ROOT / "data" / "agent" / "triage.json").read_text())["families"] if f["state"] != "known" and f["count"] >= 3]
    except (OSError, ValueError, KeyError):
        fam = []
    fam = [f for f in fam if should_draft(f.get("signature", f.get("example", "")), now, proposals)]
    if fam and spend:
        f = draft_skill(fam[0], now, chat, proposals)
        mark_draft(fam[0].get("signature", fam[0].get("example", "")), f.name if f else None, now, proposals)
        if f:
            result["drafts"].append(f.name)
            agentbus.post("skill_draft", "doctor", "owner", f.name, reason=f"A skill draft for a problem seen {fam[0]['count']} times: {fam[0]['example'][:100]}", now=now,
                          commands=[f"python vetskill.py {f}", f"python extend.py add {f}"])
    rf = report or REPORT
    try:
        rf.parent.mkdir(parents=True, exist_ok=True)
        with filelock.locked(rf):
            filelock.write_atomic(rf, json.dumps(result, indent=1))
    except OSError:
        result["saved"] = False  # the result is still returned and the feed still hears of it
    if sick or result["needs"]:
        agentlog.event("found", f"Doctor: {len(sick)} agent(s) unhealthy, {len(result['needs'])} setup item(s) missing",
                       "; ".join([f"{r['agent']} {r['status']}" for r in sick] + result["needs"])[:300], now=now)
    return result
