"""What an account chose during onboarding: the niche, and the platforms it wants packages for. One row per account, read and written only with the account id from the session."""
import json
import time

from . import db

TIERS = ("", "A", "B")


def get(account_id: str) -> dict:
    with db.read() as con:
        r = con.execute("select * from profiles where account_id=?", (account_id,)).fetchone()
    if not r:
        return {"niche_id": "", "niche_text": "", "tier": "", "platforms": []}
    return {"niche_id": r["niche_id"], "niche_text": r["niche_text"], "tier": r["tier"], "platforms": json.loads(r["platforms"])}


def save(account_id: str, niche_id: str, niche_text: str, tier: str, platforms, preset_ids, known_platforms) -> dict:
    """Validates, then stores. A niche id must be one of the studio's ready-made niches (or empty for a custom idea); platforms must be known names."""
    niche_id, tier = str(niche_id or ""), str(tier or "")
    if niche_id and niche_id not in preset_ids:
        raise ValueError("unknown niche")
    if tier not in TIERS:
        raise ValueError("unknown tier")
    if not isinstance(platforms, list) or any(p not in known_platforms for p in platforms):
        raise ValueError("unknown platform")
    text = " ".join(str(niche_text or "").split())[:500]
    with db.tx() as con:
        con.execute("insert into profiles(account_id,niche_id,niche_text,tier,platforms,updated_at) values(?,?,?,?,?,?) "
                    "on conflict(account_id) do update set niche_id=excluded.niche_id, niche_text=excluded.niche_text, tier=excluded.tier, platforms=excluded.platforms, updated_at=excluded.updated_at",
                    (account_id, niche_id, text, tier, json.dumps(sorted(set(platforms))), time.time()))
    return get(account_id)
