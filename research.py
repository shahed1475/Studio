"""Daily research: what story themes are popular in different countries, then original topic ideas.

Reads only public metadata (titles, view counts). It never downloads or copies anyone's video.
Needs YT_API_KEY (free YouTube Data API key) for live trends; without it the model suggests
country folklore from its own knowledge.
"""
import datetime as dt
import os

import config
import scriptgen

COUNTRIES = {
    "US": "United States", "GB": "United Kingdom", "IN": "India", "JP": "Japan", "BR": "Brazil",
    "DE": "Germany", "MX": "Mexico", "EG": "Egypt", "TR": "Turkey", "GR": "Greece",
    "NG": "Nigeria", "KR": "South Korea", "ID": "Indonesia", "IE": "Ireland", "NO": "Norway",
}


def todays_countries(n: int = 3) -> list[str]:
    codes = sorted(COUNTRIES)
    start = (dt.date.today().toordinal() * n) % len(codes)
    return [codes[(start + i) % len(codes)] for i in range(n)]


def popular_titles(region: str) -> list[str]:
    key = os.getenv("YT_API_KEY")
    if not key:
        return []
    from googleapiclient.discovery import build

    yt = build("youtube", "v3", developerKey=key)
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    res = yt.search().list(
        q="legend mystery history", part="snippet", type="video", regionCode=region,
        order="viewCount", publishedAfter=since, maxResults=10,
    ).execute()
    return [i["snippet"]["title"] for i in res.get("items", [])]


def run(n_countries: int = 3) -> list[str]:
    found = []
    for code in todays_countries(n_countries):
        name = COUNTRIES[code]
        signals = popular_titles(code)
        print(f"{name}: {len(signals)} trend signals")
        found += scriptgen.country_ideas(name, signals)
    return found
