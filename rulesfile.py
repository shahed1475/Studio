"""One versioned rules file for the numbers the content and growth agents judge by: config/rules.json.

A missing, unreadable or invalid file never stops a job: every value falls back to its default (today's behaviour) and the problem is reported on the Risks card.
Agents may only PROPOSE a change (`propose`); it takes effect when the owner approves it (`approve`, `run.py rules approve <id>`). The hard rules below are
constants: no file and no approved patch can change them."""
import copy
import datetime as dt
import json
from pathlib import Path

import config
import filelock

FILE = config.ROOT / "config" / "rules.json"
STALE_DAYS = 30
HARD_RULES = (
    "Never mislead the viewer: the title and thumbnail must be paid off.",
    "Always disclose realistic synthetic or AI media when YouTube requires it.",
    "Never buy views or subscribers, use engagement bots or ask people to loop videos.",
    "Never copy another creator's script, footage or thumbnail.",
)
# (kind, low, high): kind "num" is one number, "pair" two numbers low < high
SPECS = {
    "benchmarks": {
        "ctr_target": ("num", 0.005, 0.5), "ctr_retest_below": ("num", 0.005, 0.5),
        "retention_target_pct": ("num", 5, 100), "retention_at_30s_min_pct": ("num", 5, 100),
        "shorts_stayed_target_pct": ("num", 5, 100), "shorts_min_seconds": ("num", 5, 120), "shorts_max_seconds": ("num", 10, 180),
        "long_min_minutes": ("num", 1, 60), "long_max_minutes": ("num", 2, 120),
        "views_per_unique_flag": ("num", 1, 50), "topic_repeat_block_days": ("num", 1, 365),
        "hook_max_seconds": ("num", 3, 60), "rehook_max_seconds": ("num", 20, 300), "title_hard_max": ("num", 40, 100),
        "min_impressions_for_ctr": ("num", 20, 100000), "min_views_for_diagnosis": ("num", 5, 10000), "retention_drop_pp": ("num", 3, 80),
        "drift_sigma": ("num", 1, 6), "drift_recent_days": ("num", 3, 30), "drift_baseline_days": ("num", 7, 90), "drift_min_videos": ("num", 2, 50),
        "title_chars": ("pair", 10, 100), "pace_wpm": ("pair", 60, 250), "pace_target_wpm": ("pair", 60, 250), "thumb_words": ("pair", 1, 12),
    },
    "limits": {"doc_duration_s": ("pair", 30, 7200), "short_duration_s": ("pair", 5, 600)},
}
DEFAULTS = {
    "rules_version": "1.0.0",
    "last_verified": "2026-10-28",
    "benchmarks": {
        "ctr_target": 0.04, "ctr_retest_below": 0.03, "retention_target_pct": 50, "retention_at_30s_min_pct": 40,
        "shorts_stayed_target_pct": 70, "shorts_min_seconds": 35, "shorts_max_seconds": 58, "long_min_minutes": 8, "long_max_minutes": 14,
        "views_per_unique_flag": 3, "topic_repeat_block_days": 30, "hook_max_seconds": 15, "rehook_max_seconds": 90,
        "min_impressions_for_ctr": 200, "min_views_for_diagnosis": 30, "retention_drop_pp": 15,
        "drift_sigma": 2, "drift_recent_days": 7, "drift_baseline_days": 28, "drift_min_videos": 3,
        "title_chars": [40, 62], "title_hard_max": 70, "pace_wpm": [105, 175], "pace_target_wpm": [140, 155], "thumb_words": [2, 4],
    },
    "limits": {"doc_duration_s": [180, 900], "short_duration_s": [20, 180]},  # what the reviewer blocks on: unchanged until the owner raises the minimum length
    "policy_constraints": [
        {"id": "inauthentic_content", "status": "UNVERIFIED", "source": "owner's content prompt, 'clarified July 2026'; not re-read from YouTube's page",
         "summary": "No generic, template or mass-produced videos with little variation; an original element and two sources beyond Wikipedia."},
        {"id": "synthetic_disclosure", "status": "VERIFIED", "source": "compliance.RULES ai_disclosure, YouTube Help page watched daily",
         "summary": "Disclose realistic altered or synthetic media; every upload sets containsSyntheticMedia."},
        {"id": "distressing_content", "status": "UNVERIFIED", "source": "owner's content prompt, 'July 2026'",
         "summary": "No distressing or shock content made to farm views."},
    ],
    "banned_patterns": ["description starts with 'Sources:'", "encyclopedia-style titles", "title longer than title_hard_max"],
    "insights": {"winning_title_patterns": [], "winning_topics": [], "losing_patterns": []},
    "pending_changes": [],
    "history": [],
    "unverified": [
        "A Short's related video, a pinned comment and Test and Compare can be set through the API (the spec assumes it).",
        "A unique-viewers metric: the Analytics API answered 'Unknown identifier' for uniques on 28 Oct 2026, so views per unique viewer cannot be read from it.",
        "Every channel figure quoted in the owner's prompts (CTR, retention, unique viewers).",
    ],
}
LISTS = ("policy_constraints", "banned_patterns", "pending_changes", "history", "unverified")


def _ok(spec: tuple, value) -> bool:
    kind, lo, hi = spec
    num = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) and lo <= x <= hi
    if kind == "num":
        return num(value)
    return isinstance(value, (list, tuple)) and len(value) == 2 and all(num(x) for x in value) and value[0] < value[1]


def _day(text) -> bool:
    try:
        dt.date.fromisoformat(str(text))
        return True
    except ValueError:
        return False


def load(path: Path | None = None) -> dict:
    """The rules in force: defaults overlaid with every valid value in the file. Never raises; `_problems` lists what was ignored."""
    out, problems = copy.deepcopy(DEFAULTS), []
    try:
        raw = json.loads(Path(path or FILE).read_text())
        if not isinstance(raw, dict):
            raise ValueError("not an object")
    except FileNotFoundError:
        raw = {}
        problems.append("rules file missing: defaults in use")
    except (OSError, ValueError):
        raw = {}
        problems.append("rules file unreadable: defaults in use")
    for section, specs in SPECS.items():
        for key, value in (raw.get(section) or {}).items() if isinstance(raw.get(section), dict) else ():
            if key in specs and _ok(specs[key], value):
                out[section][key] = list(value) if isinstance(value, (list, tuple)) else value
            else:
                problems.append(f"{section}.{key} ignored: not a known name or outside its allowed range")
    if isinstance(raw.get("rules_version"), str) and raw["rules_version"].count(".") == 2:
        out["rules_version"] = raw["rules_version"]
    if raw.get("last_verified") is not None:
        if _day(raw["last_verified"]):
            out["last_verified"] = str(raw["last_verified"])
        else:
            problems.append("last_verified is not a date: the default date is used")
    for key in LISTS:
        if isinstance(raw.get(key), list):
            out[key] = raw[key]
    if isinstance(raw.get("insights"), dict):
        out["insights"].update({k: v for k, v in raw["insights"].items() if isinstance(v, list)})
    out["hard_rules"] = list(HARD_RULES)  # constants: whatever the file says
    out["_problems"] = problems
    return out


def get(section: str, key: str, rules: dict | None = None):
    return (rules or load())[section][key]


def rng(section: str, key: str, rules: dict | None = None) -> tuple:
    lo, hi = get(section, key, rules)
    return lo, hi


def stale_days(rules: dict | None = None, now: dt.datetime | None = None) -> int | None:
    """Days since the rules were last verified when that is more than STALE_DAYS, else None."""
    rules = rules or load()
    now = now or dt.datetime.now(dt.timezone.utc)
    age = (now.date() - dt.date.fromisoformat(rules["last_verified"])).days
    return age if age > STALE_DAYS else None


def validate_patch(patch) -> tuple[bool, str]:
    """A patch may set known benchmark or limit values inside their range and add policy constraints or banned patterns. Nothing else, never a hard rule."""
    if not isinstance(patch, dict) or not patch:
        return False, "empty patch"
    for section, body in patch.items():
        if section in SPECS:
            if not isinstance(body, dict) or not body:
                return False, f"{section}: expected values"
            for key, value in body.items():
                if key not in SPECS[section] or not _ok(SPECS[section][key], value):
                    return False, f"{section}.{key}: unknown name or value outside its range"
        elif section == "banned_patterns_add":
            if not (isinstance(body, list) and body and all(isinstance(x, str) and 3 <= len(x) <= 160 for x in body)):
                return False, "banned_patterns_add: expected short strings"
        elif section == "policy_constraints_add":
            if not (isinstance(body, list) and body and all(isinstance(x, dict) and {"id", "summary", "source"} <= set(x) for x in body)):
                return False, "policy_constraints_add: expected id, summary and source"
        else:
            return False, f"{section}: not something a patch may change"
    return True, ""


def _raw(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text())
        return raw if isinstance(raw, dict) else copy.deepcopy(DEFAULTS)
    except (OSError, ValueError):
        return copy.deepcopy(DEFAULTS)


def _save(path: Path, raw: dict) -> None:
    filelock.write_atomic(path, json.dumps(raw, indent=2, ensure_ascii=False) + "\n")


def propose(patch: dict, why: str, source: str, now: dt.datetime | None = None, path: Path | None = None) -> str | None:
    """Queue a change for the owner. Returns its id, or None when the patch is not allowed. Nothing changes until `approve`."""
    ok, _ = validate_patch(patch)
    if not ok:
        return None
    path = Path(path or FILE)
    raw, now = _raw(path), now or dt.datetime.now(dt.timezone.utc)
    pend = [p for p in raw.get("pending_changes", []) if isinstance(p, dict)]
    if any(p.get("patch") == patch for p in pend):
        return next(p["id"] for p in pend if p.get("patch") == patch)
    pid = f"p-{now:%Y%m%d}-{len(pend) + len(raw.get('history', [])) + 1:02d}"
    pend.append({"id": pid, "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "why": str(why)[:400], "source": str(source)[:200], "patch": patch})
    raw["pending_changes"] = pend
    _save(path, raw)
    return pid


def _bump(version: str) -> str:
    a, b, c = (version.split(".") + ["0", "0"])[:3]
    return f"{a}.{b}.{int(c) + 1 if c.isdigit() else 1}"


def resolve(pid: str, approve: bool, now: dt.datetime | None = None, path: Path | None = None) -> str:
    """The owner's decision on a pending change. Approve applies it, bumps the version and sets last_verified; reject only records it."""
    path, now = Path(path or FILE), now or dt.datetime.now(dt.timezone.utc)
    raw = _raw(path)
    hit = next((p for p in raw.get("pending_changes", []) if isinstance(p, dict) and p.get("id") == pid), None)
    if not hit:
        return f"no pending change {pid}"
    if approve:
        ok, why = validate_patch(hit["patch"])
        if not ok:
            return f"{pid} not applied: {why}"
        for section, body in hit["patch"].items():
            if section in SPECS:
                raw.setdefault(section, {}).update(body)
            elif section == "banned_patterns_add":
                raw["banned_patterns"] = list(dict.fromkeys([*raw.get("banned_patterns", DEFAULTS["banned_patterns"]), *body]))
            elif section == "policy_constraints_add":
                raw["policy_constraints"] = [*raw.get("policy_constraints", DEFAULTS["policy_constraints"]), *body]
        raw["rules_version"] = _bump(raw.get("rules_version", DEFAULTS["rules_version"]))
        raw["last_verified"] = now.date().isoformat()
    raw["pending_changes"] = [p for p in raw["pending_changes"] if p is not hit]
    raw["history"] = (raw.get("history", []) + [{"id": pid, "decision": "approved" if approve else "rejected", "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                   "patch": hit["patch"], "why": hit.get("why", "")}])[-50:]
    _save(path, raw)
    return f"{pid} {'approved: rules ' + raw['rules_version'] if approve else 'rejected'}"


def mark_verified(now: dt.datetime | None = None, path: Path | None = None) -> str:
    """The owner (or a verified policy check) confirms the rules still hold today."""
    path, now = Path(path or FILE), now or dt.datetime.now(dt.timezone.utc)
    raw = _raw(path)
    raw["last_verified"] = now.date().isoformat()
    _save(path, raw)
    return f"rules marked verified on {raw['last_verified']}"
