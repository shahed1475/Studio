"""What our best Short did (30 Oct 2026, owner: check which Shorts get high views and use that for the last Short of the week).

Reads the collector's own numbers (YouTube Analytics through growthdata: views in 90 days, average percent viewed, share still watching at 30 s) and names the winner: the Short with the most
views weighted by how much of it was watched. A Short with fewer than MIN_VIEWS views is not a pattern, and a film is not a Short. The winner's KIND (mystery, case, person, legend...) is what the
sixth Short of the week asks the topic picker for (weekplan.winner_due, topicrank.pop_best). The ranking is ours and small-sample: 10 Shorts at 859 views in all on 30 Oct 2026."""
import json

import kinds

MIN_VIEWS = 50


def _rows(videos) -> list[dict]:
    if videos is None:
        import growthdata

        try:
            videos = json.loads(growthdata.FILE.read_text()).get("videos")
        except (OSError, ValueError, AttributeError):
            return []
    if isinstance(videos, dict):
        return [r for r in videos.values() if isinstance(r, dict)]
    return [r for r in (videos or []) if isinstance(r, dict)]


def winner(videos=None) -> dict | None:
    best = None
    for r in _rows(videos):
        views = int(r.get("views_90d") or 0)
        if not str(r.get("kind") or "").startswith("short") or views < MIN_VIEWS:
            continue
        score = views * float(r.get("avg_pct_viewed") or 50.0) / 100
        if best is None or score > best[0]:
            best = (score, r, views)
    if not best:
        return None
    _, r, views = best
    title = str(r.get("title") or "")
    return {"title": title, "kind": kinds.classify({"title": title, "topic": title}), "views": views, "avg_pct_viewed": r.get("avg_pct_viewed"), "retention_at_30s": r.get("retention_at_30s"), "seconds": r.get("seconds")}
