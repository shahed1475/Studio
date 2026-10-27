"""The studio's agents on one page: who they are, which worker job runs them, and who they hand work to.

Used by the doctor (which agents should have run lately), by the evaluation (every agent has a playbook, every hand-over target exists, nobody is
unreachable) and by `playbook.acting_as` (which playbook a command or Autopilot action works under). Cadences come from the worker's own job list."""
AGENTS = {
    "autopilot": {"job": "autopilot", "cmds": ["autopilot"], "hands_to": ["research", "creator", "fixer", "publisher", "reviewer"]},
    "research": {"job": "trendwatch", "cmds": ["ideas", "research", "trends", "channels", "trend-import"], "hands_to": ["creator"]},
    "growth": {"job": "agent", "cmds": ["agent"], "hands_to": ["research"]},
    "collector": {"job": "growthdata", "cmds": ["growthdata"], "hands_to": ["diagnoser"]},
    "diagnoser": {"job": "diagnose", "cmds": ["diagnose"], "hands_to": ["fixer", "research"]},
    "news": {"job": "policywatch", "cmds": ["newswatch", "policywatch"], "hands_to": ["creator", "guardian"]},
    "creator": {"job": None, "cmds": ["doc", "make", "redo", "remake", "batch"], "hands_to": ["scriptreview", "seo", "reviewer"]},
    "scriptreview": {"job": None, "cmds": ["script-review"], "hands_to": ["creator", "doctor"]},
    "clipper": {"job": None, "cmds": ["clip", "remake-short"], "hands_to": ["reviewer"]},
    "seo": {"job": None, "cmds": ["seo", "seo-fix"], "hands_to": ["reviewer"]},
    "qa": {"job": None, "cmds": ["inspect", "analyze-video", "score-thumbnails"], "hands_to": []},
    "compliance": {"job": None, "cmds": [], "hands_to": []},
    "reviewer": {"job": None, "cmds": ["review"], "hands_to": ["compliance", "qa", "fixer", "publisher"]},
    "fixer": {"job": "unstick", "cmds": ["repair", "unstick"], "hands_to": ["reviewer"]},
    "publisher": {"job": None, "cmds": ["upload", "schedule"], "hands_to": ["recheck", "health"]},
    "recheck": {"job": "recheck", "cmds": ["recheck"], "hands_to": ["guardian"]},
    "titletest": {"job": "titletest", "cmds": ["titletest"], "hands_to": ["reporter"]},
    "guardian": {"job": "guardian", "cmds": ["guardian"], "hands_to": ["autopilot"]},
    "health": {"job": "health", "cmds": ["health"], "hands_to": ["guardian", "reporter"]},
    "reporter": {"job": "report", "cmds": ["report"], "hands_to": []},
    "monetization": {"job": None, "cmds": [], "ondemand": True, "hands_to": ["reporter"]},
    "backup": {"job": "backup", "cmds": ["backup"], "hands_to": []},
    "triage": {"job": None, "cmds": [], "hands_to": ["trainer"]},
    "trainer": {"job": None, "cmds": ["trainset"], "hands_to": ["evaluator"]},
    "evaluator": {"job": "agent-review", "cmds": ["agent-review", "agents"], "hands_to": ["triage", "doctor"]},
    "doctor": {"job": "doctor", "cmds": ["doctor"], "hands_to": ["scriptreview"]},
}
# What Autopilot's actions are, in agent terms (an action not listed works under the autopilot playbook).
ACTIONS = {"review": "reviewer", "fix": "fixer", "polish": "fixer", "prelaunch": "publisher", "schedule": "publisher", "upload": "publisher",
           "ideas": "research", "make": "creator", "make_short": "creator", "make_clip": "clipper", "make_news": "news"}


def for_command(cmd: str) -> str | None:
    return next((n for n, a in AGENTS.items() if cmd in a["cmds"]), None)


def for_action(action: str) -> str:
    return ACTIONS.get(action, "autopilot")


def job_defs(jobs=None) -> dict:
    if jobs is None:
        import worker

        jobs = worker.JOBS
    return {j["name"]: j for j in jobs}


def cadence_seconds(job: dict) -> float:
    return float(job["every"]) if "every" in job else (7 * 86400.0 if "weekday" in job else 86400.0)


def problems(playbook_dir=None, jobs=None) -> list[str]:
    """Registry mistakes: no playbook, a hand-over to nobody, a job the worker does not have, an agent nothing can start."""
    import playbook

    out, jd = [], job_defs(jobs)
    reachable = {t for a in AGENTS.values() for t in a["hands_to"]} | set(ACTIONS.values())
    for name, a in AGENTS.items():
        out += playbook.problems(name, playbook_dir)
        out += [f"{name} hands work to {t}, which is not an agent" for t in a["hands_to"] if t not in AGENTS]
        if a["job"] and a["job"] not in jd:
            out.append(f"{name} names the job {a['job']}, which the worker does not have")
        if not a["job"] and not a["cmds"] and not a.get("ondemand") and name not in reachable:
            out.append(f"{name} has no job, no command and nobody hands it work")
    return out
