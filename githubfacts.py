"""Dated facts about a GitHub repository for the tech channel. Every fact carries the date it was read; README text is returned as untrusted data and never as instructions.
`get(url)` is injected, so tests use a mock and nothing here calls GitHub unless a real fetcher is passed in. Rate limit: 60 requests an hour without a token, 5,000 with one."""
import datetime as dt
import re

REPO = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
README_CHARS = 1500


def facts(repo: str, get, now: dt.datetime | None = None) -> dict:
    if not REPO.fullmatch(repo):
        raise ValueError("a repository is written owner/name")
    now = now or dt.datetime.now(dt.timezone.utc)
    info = get(f"https://api.github.com/repos/{repo}")
    rel = None
    try:
        rel = get(f"https://api.github.com/repos/{repo}/releases/latest")
    except LookupError:  # no release published: not an error
        pass
    lic = (info.get("license") or {}).get("spdx_id")
    as_of = now.strftime("%Y-%m-%d")
    return {"repo": repo, "as_of": as_of, "source": f"https://github.com/{repo}",
            "stars": {"value": info.get("stargazers_count"), "as_of": as_of},
            "license": lic or "none declared: all rights reserved, describe it, never copy it",
            "licensed": bool(lic) and lic != "NOASSERTION",
            "latest_release": {"tag": rel.get("tag_name"), "published": rel.get("published_at")} if rel else None,
            "description": (info.get("description") or "")[:300],
            "readme_untrusted": (info.get("readme") or "")[:README_CHARS]}
