"""Re-check videos that are already on YouTube and repair what can be repaired there.

Autopilot repairs a video before it uploads and then leaves it alone. A review that changes its mind later (the AI review is not perfectly steady), a
policy page that changes, or a title that no longer matches the narration was never looked at again. This job looks again, one video an hour:

- a metadata problem (title, description, tags) is repaired and pushed to YouTube (needs the edit permission and titletest mode "apply");
- a content problem (invented facts, a wrong picture, the narration) cannot be repaired on YouTube: the owner is told, and a video that is still
  scheduled and fails twice in a row is taken back to private so it does not go public while it is wrong. A public video is never touched that way.
Nothing is deleted and nothing is made public here."""
import datetime as dt
import fcntl
import json

import agentlog
import config

TS = "%Y-%m-%dT%H:%M:%SZ"
META_ONLY = {"title_matches", "duplicate_title", "title", "description", "tags", "hashtags", "metadata_valid", "title_style"}
AFTER = dt.timedelta(hours=48)    # a public video is looked at for two days after its time
AHEAD = dt.timedelta(days=3)      # a scheduled one for its last three days
EVERY = dt.timedelta(hours=12)    # the same video is not reviewed again within twelve hours (each review costs a few cents)
KEEP_FREE = 0.6                   # dollars of the day's cap left alone for making videos: no re-check when less than this remains
PULL_AFTER = 2                    # consecutive content failures before a scheduled video is taken back to private


def _parse(ts: str) -> dt.datetime:
    return dt.datetime.strptime(ts, TS).replace(tzinfo=dt.timezone.utc)


def _when(meta: dict) -> str:
    """When the video is (or became) public: its scheduled time, or for one uploaded straight to public the upload time."""
    return meta.get("publish_at") or meta.get("uploaded_at") or ""


def candidates(now: dt.datetime) -> list:
    """(publish time, folder, meta) of uploaded videos worth a second look, the soonest first."""
    out = []
    for m in config.OUT.glob("*/meta.json"):
        try:
            meta = json.loads(m.read_text())
        except ValueError:
            continue
        if not meta.get("video_id") or not _when(meta) or meta.get("hold"):
            continue
        at = _parse(_when(meta))
        last = (meta.get("recheck") or {}).get("at")
        if not (now - AFTER <= at <= now + AHEAD) or (last and _parse(last) > now - EVERY):
            continue
        out.append((at, m.parent, meta))
    return sorted(out, key=lambda x: x[0])


def failing(result: dict) -> list[str]:
    return [c["name"] for c in result.get("checks", []) if not c["ok"] and c["severity"] in ("block", "human")]


def push_metadata(yt, meta: dict) -> None:
    """videos.update replaces the whole snippet: send back everything that was there with only the title, description and tags changed."""
    import compliance

    sn = yt.videos().list(part="snippet", id=meta["video_id"]).execute()["items"][0]["snippet"]
    sn["title"], sn["description"], sn["tags"] = meta["title"], compliance.final_description(meta), meta.get("tags", sn.get("tags", []))
    yt.videos().update(part="snippet", body={"id": meta["video_id"], "snippet": {k: sn[k] for k in ("title", "description", "categoryId", "tags", "defaultLanguage") if k in sn}}).execute()


def take_back(yt, video_id: str) -> None:
    """A scheduled video becomes plain private (no time): it cannot go public by itself."""
    st = yt.videos().list(part="status", id=video_id).execute()["items"][0]["status"]
    st.pop("publishAt", None)
    st["privacyStatus"] = "private"
    yt.videos().update(part="status", body={"id": video_id, "status": st}).execute()


def repair_metadata(folder, meta: dict, bad: list[str], chat=None) -> list[str]:
    """The same repairs the fixer makes before an upload, for metadata only. Returns what was done."""
    import compliance
    import fixer

    done = []
    failing_checks = {c["name"]: c for c in (meta.get("_recheck_checks") or [])}
    if "title_matches" in bad:
        tm = failing_checks.get("title_matches", {})
        if fixer.realign_description(meta, tm.get("covers", ""), chat):
            done.append("rewrote the description to match what the video covers")
    if {"title_matches", "duplicate_title", "title"} & set(bad):
        tm = failing_checks.get("title_matches", {})
        t = fixer.pick_title(meta, fixer.other_titles(folder), chat, tm.get("detail", ""), tm.get("covers", ""), None, tm.get("better_titles"))
        if t:
            meta["title"] = t
            done.append(f"new title: {t}")
    tags = fixer.clean_tags(meta)
    if tags != meta.get("tags"):
        meta["tags"] = tags
        done.append("cleaned the tags")
    if {"description", "metadata_valid", "hashtags"} & set(bad):
        done += compliance.sanitize(meta)
    return done


def check_one(now: dt.datetime, folder, meta: dict, yt, review, chat=None, may_edit: bool = False) -> dict:
    """Review one uploaded video and act on the result. Returns {"slug", "verdict", "actions"}."""
    result = review(folder)
    rec = dict(meta.get("recheck") or {})
    out = {"slug": folder.name, "verdict": result["verdict"], "actions": []}
    rec["at"] = now.strftime(TS)
    if result["verdict"] == "unreviewed":  # a model failure is not a finding
        out["actions"].append("the AI review could not run; nothing changed")
        meta["recheck"] = {**rec, "verdict": "unreviewed"}
        _save(folder, meta)
        return out
    bad = failing(result)
    if not bad:
        meta["recheck"] = {"at": rec["at"], "verdict": "pass", "content_fails": 0}
        _save(folder, meta)
        return out
    public = _parse(_when(meta)) <= now
    if set(bad) <= META_ONLY:
        if not may_edit:
            agentlog.event("found", f"Re-check: {meta['title'][:50]} has a metadata problem ({', '.join(bad)})",
                           "Not changed: editing titles on YouTube is switched off.", now=now)
            out["actions"].append("metadata problem, no permission to edit")
        else:
            meta["_recheck_checks"] = result["checks"]
            done = repair_metadata(folder, meta, bad, chat)
            meta.pop("_recheck_checks", None)
            if done:
                push_metadata(yt, meta)
                out["actions"] += done
                agentlog.event("applied", f"Re-check: repaired the metadata of an uploaded video ({meta['title'][:50]})", "; ".join(done), now=now)
        meta["recheck"] = {"at": rec["at"], "verdict": "metadata", "content_fails": 0, "problems": bad}
        _save(folder, meta)
        return out
    fails = rec.get("content_fails", 0) + 1
    meta["recheck"] = {"at": rec["at"], "verdict": "content", "content_fails": fails, "problems": bad}
    names = ", ".join(bad)
    if public:
        agentlog.event("found", f"Re-check: a public video has a problem ({meta['title'][:50]})", f"{names}. It is public, so nothing was changed: look at it.", notify=True, now=now)
        out["actions"].append("public video with a content problem: owner told")
    elif fails >= PULL_AFTER and may_edit:
        try:
            take_back(yt, meta["video_id"])
        except Exception as e:  # YouTube refused: the owner must act, and must be told loudly
            agentlog.event("found", f"Re-check: could NOT take a failing scheduled video back to private ({meta['title'][:50]})",
                           f"{names}; YouTube said {type(e).__name__}. Open YouTube Studio and make it private yourself.", notify=True, now=now)
            out["actions"].append("could not take it back to private: owner told")
        else:
            meta["hold"] = True
            agentlog.event("applied", f"Re-check: took a scheduled video back to private ({meta['title'][:50]})",
                           f"{names}, found in {fails} checks in a row. It will not go public by itself; repair or release it.", notify=True, now=now)
            out["actions"].append("scheduled video taken back to private and put on hold")
    else:
        agentlog.event("found", f"Re-check: a scheduled video has a problem ({meta['title'][:50]})",
                       f"{names}. The next check decides: if it fails again the video is taken back to private.", notify=True, now=now)
        out["actions"].append(f"content problem {fails} of {PULL_AFTER}: owner told")
    _save(folder, meta)
    return out


def _save(folder, meta: dict) -> None:
    (folder / "meta.json").write_text(json.dumps(meta, indent=2))


def run(now: dt.datetime | None = None, yt=None, review=None, chat=None, may_edit: bool | None = None) -> dict:
    """One video per call. Takes the Autopilot lock so it never edits a video Autopilot is working on."""
    import autopilot
    import titletest

    now = now or dt.datetime.now(dt.timezone.utc)
    lock = open(autopilot.LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return {"skipped": "locked"}
    try:
        import llm

        if llm.spent_today(now) > llm.load_config()["daily_budget_usd"] - KEEP_FREE:
            return {"skipped": "the day's spending cap is nearly used"}
        todo = candidates(now)
        if not todo:
            return {"checked": 0}
        _, folder, meta = todo[0]
        if review is None:
            import reviewer

            def review(f):
                return reviewer.review(f, use_llm=True, persist=False)
        if may_edit is None:
            may_edit = titletest.mode() == "apply" and titletest.can_write()
        yt = yt or titletest._service()
        with llm.cost_scope(folder.name):
            r = check_one(now, folder, meta, yt, review, chat, may_edit)
        return {"checked": 1, **r}
    finally:
        lock.close()
