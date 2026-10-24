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
MAX_EDITS = 1                     # one automatic repair of a video's title or description; a second change is the owner's
MAX_TRIES = 3                     # videos tried in one run when the first ones fail
PULL_AFTER = 2                    # consecutive content failures before a scheduled video is taken back to private


def _parse(ts: str) -> dt.datetime:
    return dt.datetime.strptime(ts, TS).replace(tzinfo=dt.timezone.utc)


def _when_dt(meta: dict) -> dt.datetime | None:
    """The video's time as a datetime, None when it is missing or not in the usual form (one odd record must not stop the whole job)."""
    try:
        return _parse(_when(meta))
    except (ValueError, TypeError):
        return None


def heal() -> list[str]:
    """An uploaded video must keep its slot and its approval: YouTube holds it and an upload is only ever sent for an approved video. If an edit lost either
    (reviewer.invalidate used to), restore them from the upload's own read-back. Returns the folders healed."""
    healed = []
    for m in config.OUT.glob("*/meta.json"):
        try:
            meta = json.loads(m.read_text())
        except ValueError:
            continue
        chk = meta.get("upload_check") if isinstance(meta.get("upload_check"), dict) else {}
        if not meta.get("video_id") or not chk.get("ok") or meta.get("taken_back") or meta.get("hold"):
            continue  # a pulled-back or held video is private on purpose: its old slot is not restored
        changes = {}
        if not meta.get("publish_at") and chk.get("publishAt"):
            changes["publish_at"] = chk["publishAt"]
        if not meta.get("approved"):
            changes["approved"] = True
        if changes:
            meta.update(changes)
            meta["healed"] = {"fields": sorted(changes), "why": "uploaded video had lost its slot or approval; restored from the upload read-back"}
            m.write_text(json.dumps(meta, indent=2))
            healed.append(m.parent.name)
    return healed


def sync_titles(yt, now: dt.datetime) -> list[str]:
    """YouTube's title is the truth after an upload: a change made in Studio, by the title test or by hand through the API must not be undone by a later
    repair that pushes the saved record. For every uploaded video whose title on YouTube differs, the saved title is brought up to date (one cheap read for up to
    50 videos). Returns the folders updated."""
    mine = {}
    for m in config.OUT.glob("*/meta.json"):
        try:
            meta = json.loads(m.read_text())
        except ValueError:
            continue
        if meta.get("video_id"):
            mine[meta["video_id"]] = (m.parent, meta)
    changed, ids = [], list(mine)
    for k in range(0, len(ids), 50):
        for item in yt.videos().list(part="snippet", id=",".join(ids[k:k + 50])).execute().get("items", []):
            folder, meta = mine[item["id"]]
            title = item["snippet"]["title"]
            if title and title != meta.get("title"):
                _merge(folder, {"title": title})
                agentlog.event("info", "The saved title now matches YouTube", f"{meta.get('title', '')[:60]} -> {title[:60]}", now=now)
                changed.append(folder.name)
    return changed


def enforce_holds(yt, now: dt.datetime) -> list[str]:
    """A video on hold must not go public by itself. The hold used to stop only Autopilot: a video already scheduled on YouTube would still publish. For every
    uploaded video on hold whose time has not come, make sure YouTube shows it private with no time; YouTube's read-back can lag, so a second look follows
    next hour. Returns the folders it had to change."""
    changed = []
    for m in config.OUT.glob("*/meta.json"):
        try:
            meta = json.loads(m.read_text())
        except ValueError:
            continue
        at = _when_dt(meta)
        if not (meta.get("video_id") and meta.get("hold") and meta.get("publish_at")) or at is None or at <= now:
            continue
        try:
            items = yt.videos().list(part="status", id=meta["video_id"]).execute().get("items", [])
            if not items:  # deleted in Studio: nothing to hold
                continue
            st = items[0]["status"]
            if st.get("publishAt") or st.get("privacyStatus") != "private":
                take_back(yt, meta["video_id"])
                _merge(m.parent, {"taken_back": now.strftime(TS)})
                agentlog.event("applied", f"A video on hold was still scheduled on YouTube: made private ({meta.get('title', '')[:50]})", "A hold now stops the upload's own schedule too.", notify=True, now=now)
                changed.append(m.parent.name)
        except Exception as e:  # one video must not stop the others
            agentlog.event("found", f"Could not check the hold on {meta.get('title', m.parent.name)[:50]}", f"{type(e).__name__}", now=now)
    return changed


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
        if not meta.get("video_id") or meta.get("hold") or meta.get("approved_by") == "you":
            continue  # a video the owner approved himself or herself was judged by a human: it is not second-guessed
        at = _when_dt(meta)
        if at is None:
            continue
        try:
            last = _parse((meta.get("recheck") or {}).get("at") or "")
        except ValueError:
            last = None
        if not (now - AFTER <= at <= now + AHEAD) or (last and last > now - EVERY):
            continue
        out.append((at, m.parent, meta))
    return sorted(out, key=lambda x: x[0])


def failing(result: dict) -> list[str]:
    """Blocking problems only. A check that needs a human's eyes (`human` severity) is the owner's call, never a reason to pull a video, and when the AI
    review itself failed (`llm_review`) there is no finding at all."""
    return [c["name"] for c in result.get("checks", []) if not c["ok"] and c["severity"] == "block" and c["name"] != "llm_review"]


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


def _merge(folder, changes: dict) -> None:
    """Write only these keys into the video's current record: the review took minutes, and the title test, the dashboard or a hold may have written the file meanwhile."""
    p = folder / "meta.json"
    fresh = json.loads(p.read_text())
    fresh.update(changes)
    p.write_text(json.dumps(fresh, indent=2))


def _changed(before: dict, after: dict) -> dict:
    return {k: v for k, v in after.items() if before.get(k) != v and not k.startswith("_")}


def check_one(now: dt.datetime, folder, meta: dict, yt, review, chat=None, may_edit: bool = False) -> dict:
    """Review one uploaded video and act on the result. Returns {"slug", "verdict", "actions"}."""
    before = json.loads(json.dumps(meta))
    # the stamp goes in first: a crash below must not make the same video the next pick again, hour after hour
    _merge(folder, {"recheck": {**(meta.get("recheck") or {}), "at": now.strftime(TS), "verdict": "started"}})
    result = review(folder)
    rec = dict(before.get("recheck") or {})
    out = {"slug": folder.name, "verdict": result["verdict"], "actions": []}
    rec["at"] = now.strftime(TS)
    if result["verdict"] == "unreviewed" or any(c["name"] == "llm_review" and not c["ok"] for c in result.get("checks", [])):  # a model failure is not a finding
        out["actions"].append("the AI review could not run; nothing changed")
        _merge(folder, {"recheck": {**rec, "verdict": "unreviewed"}})
        return out
    bad = failing(result)
    if not bad:
        _merge(folder, {"recheck": {"at": rec["at"], "verdict": "pass", "content_fails": 0, "edits": rec.get("edits", 0)}})
        return out
    public = (_when_dt(meta) or now) <= now
    title = meta.get("title", folder.name)[:50]
    if set(bad) <= META_ONLY:
        edits = rec.get("edits", 0)
        if not may_edit:
            agentlog.event("found", f"Re-check: {title} has a metadata problem ({', '.join(bad)})", "Not changed: editing titles on YouTube is switched off.", now=now)
            out["actions"].append("metadata problem, no permission to edit")
        elif edits >= MAX_EDITS:
            agentlog.event("found", f"Re-check: {title} still has a metadata problem ({', '.join(bad)})",
                           "It was already repaired once by Autopilot; a second change is yours to make in YouTube Studio.", now=now)
            out["actions"].append("metadata problem again after one repair: owner told")
        else:
            work = json.loads(json.dumps(meta))
            work["_recheck_checks"] = result["checks"]
            done = repair_metadata(folder, work, bad, chat)
            work.pop("_recheck_checks", None)
            if work.get("title") != meta.get("title"):
                import reviewer

                ok, why = reviewer.title_ok(work, work["title"])  # the new title must pass the same question the reviewer asks of every title
                if not ok:
                    work["title"] = meta["title"]
                    done = [d for d in done if not d.startswith("new title")] + [f"kept the old title: the new one was not accepted ({why[:80]})"]
            if work.get("title") != meta.get("title") or work.get("description") != meta.get("description") or work.get("tags") != meta.get("tags"):
                push_metadata(yt, work)
                _merge(folder, _changed(before, work))
                rec["edits"] = edits + 1
                agentlog.event("applied", f"Re-check: repaired the metadata of an uploaded video ({title})", "; ".join(done), now=now)
            out["actions"] += done
        _merge(folder, {"recheck": {"at": rec["at"], "verdict": "metadata", "content_fails": 0, "problems": bad, "edits": rec.get("edits", 0)}})
        return out
    fails = rec.get("content_fails", 0) + 1
    names = ", ".join(bad)
    changes = {"recheck": {"at": rec["at"], "verdict": "content", "content_fails": fails, "problems": bad, "edits": rec.get("edits", 0)}}
    if public:
        agentlog.event("found", f"Re-check: a public video has a problem ({title})", f"{names}. It is public, so nothing was changed: look at it.", notify=True, now=now)
        out["actions"].append("public video with a content problem: owner told")
    elif fails >= PULL_AFTER and may_edit:
        try:
            take_back(yt, meta["video_id"])
        except Exception as e:  # YouTube refused: the owner must act, and must be told loudly
            agentlog.event("found", f"Re-check: could NOT take a failing scheduled video back to private ({title})",
                           f"{names}; YouTube said {type(e).__name__}. Open YouTube Studio and make it private yourself.", notify=True, now=now)
            out["actions"].append("could not take it back to private: owner told")
        else:
            changes.update(hold=True, taken_back=now.strftime(TS))
            agentlog.event("applied", f"Re-check: took a scheduled video back to private ({title})",
                           f"{names}, found in {fails} checks in a row. It will not go public by itself; repair or release it.", notify=True, now=now)
            out["actions"].append("scheduled video taken back to private and put on hold")
    else:
        agentlog.event("found", f"Re-check: a scheduled video has a problem ({title})",
                       f"{names}. The next check decides: if it fails again the video is taken back to private.", notify=True, now=now)
        out["actions"].append(f"content problem {fails} of {PULL_AFTER}: owner told")
    _merge(folder, changes)
    return out


def run(now: dt.datetime | None = None, yt=None, review=None, chat=None, may_edit: bool | None = None) -> dict:
    """One video per call (the next one if a video fails). Takes the Autopilot lock so it never edits a video Autopilot is working on."""
    import autopilot
    import titletest

    now = now or dt.datetime.now(dt.timezone.utc)
    lock = open(autopilot.LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return {"skipped": "locked"}
    try:
        for slug in heal():
            agentlog.event("applied", f"Restored the schedule and approval of an uploaded video ({slug[:40]})", "An edit had cleared them; YouTube still held the video.", now=now)
        if may_edit is None:
            may_edit = titletest.mode() == "apply" and titletest.can_write()
        yt = yt or titletest._service()
        try:
            sync_titles(yt, now)
        except Exception as e:  # a read that fails is not worth stopping the job
            agentlog.event("found", "Could not compare saved titles with YouTube", type(e).__name__, now=now)
        if may_edit:
            enforce_holds(yt, now)
        import llm

        if llm.spent_today(now) > llm.load_config()["daily_budget_usd"] - KEEP_FREE:
            return {"skipped": "the day's spending cap is nearly used"}
        todo = candidates(now)
        if not todo:
            return {"checked": 0}
        if review is None:
            import reviewer

            def review(f):
                return reviewer.review(f, use_llm=True, persist=False)
        errors = []
        for _, folder, meta in todo[:MAX_TRIES]:
            try:
                with llm.cost_scope(folder.name):
                    r = check_one(now, folder, meta, yt, review, chat, may_edit)
                return {"checked": 1, **r, **({"errors": errors} if errors else {})}
            except Exception as e:  # the video is stamped as looked at, so the next run goes to the next one; the owner is told
                errors.append(f"{folder.name}: {type(e).__name__}")
                agentlog.event("found", f"Re-check could not finish for {meta.get('title', folder.name)[:50]}", f"{type(e).__name__}: {str(e)[:120]}", now=now)
        return {"checked": 0, "errors": errors}
    finally:
        lock.close()
