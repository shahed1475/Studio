"""The final check on a scheduled video, a day before it posts: the real file and the written rules again, nothing from memory.

It runs when the 24-hour review window opens (27 hours before the slot), so a problem still has time to be repaired, and it uses no AI model and writes
nothing to the video's review. A video the reviewer approved that fails goes back to being a draft (no approval, no slot, a failing check the fixer can
act on); a video you approved yourself is never pulled back, you are told instead.
"""
import datetime as dt

import reviewer
import studiochecks

WINDOW_EXTRA_HOURS = 3  # the check starts this long before the review window closes on the slot, so it is not left to the last hour


def check(slug: str, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    folder, meta = studiochecks.load(slug)
    source = reviewer.source_text(meta)
    rows = []
    for name, fn in (("script", lambda: studiochecks.check_script(meta, source)), ("sources", lambda: studiochecks.check_sources(meta, folder, source)),
                     ("licenses", lambda: studiochecks.check_licenses(meta)), ("video", lambda: studiochecks.check_video(folder, meta, False)),
                     ("publish", lambda: studiochecks.check_publish_ready(meta, now))):
        try:
            rows += [{**r, "name": f"{name}: {r['name']}"} for r in fn()]
        except Exception as e:  # a check that cannot run is a failed check, never a skipped one
            rows.append(studiochecks.row(f"{name}: could not run", False, f"{type(e).__name__}: {e}"))
    blocking = [r for r in rows if not r["ok"] and r["severity"] in ("block", "human")]
    return {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "ok": not blocking, "problems": [f"{r['name']}: {r['detail']}"[:200] for r in blocking]}
