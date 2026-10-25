"""The "Channels" dashboard view: the channel profiles under config/channels/ and this studio's own approval setting. Read-only: it changes nothing.
Served at /channels (page) and /api/channels (data) behind the dashboard login."""
import channelconfig
import channelprofile


def _row(p: dict) -> dict:
    if "error" in p:
        return {"id": str(p.get("id", "?"))[:60], "error": str(p["error"])[:300]}
    lim = p["limits"]
    return {"id": p["id"], "audience": p["audience"][:200], "language": p["language"], "made_for_kids": p["made_for_kids"], "human_approval": p["human_approval"],
            "daily_budget_usd": lim["daily_budget_usd"], "videos_per_week": lim["videos_per_week"], "sources": p["sources"], "visuals": p["visuals"], "voice": p["voice"]}


def build() -> dict:
    return {"studio_human_approval": channelprofile.human_approval(), "channels": [_row(p) for p in channelconfig.load_all()]}
