"""Save a Wikipedia article as plain text for a spec's `src/` folder (free, no key). The passages of a spec must be word for word in these files.
Usage: python tools/fetchsrc.py "Cheonmachong" --out specs/inbox/my-film/src   -> src/Cheonmachong.txt; prints the address, title and the date read for the source entry."""
import datetime as dt
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://en.wikipedia.org/w/api.php"


def fetch(title: str, get=None) -> tuple[str, str, str]:
    """(page title, plain text, https address) of the article; raises ValueError when there is none."""
    q = urllib.parse.urlencode({"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1, "format": "json", "titles": title})
    get = get or (lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "story-studio-fetchsrc"}), timeout=30).read())
    pages = json.loads(get(f"{API}?{q}"))["query"]["pages"]
    page = next(iter(pages.values()))
    if "missing" in page or not page.get("extract"):
        raise ValueError(f"no Wikipedia article called '{title}'")
    return page["title"], page["extract"], "https://en.wikipedia.org/wiki/" + urllib.parse.quote(page["title"].replace(" ", "_"))


def save(title: str, out: Path, get=None) -> Path:
    name, text, url = fetch(title, get)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / (re.sub(r"[^A-Za-z0-9_.-]+", "_", name)[:70] + ".txt")
    dest.write_text(text)
    print(f'file: src/{dest.name}\ntitle: {name} - Wikipedia\nurl: {url}\nread: {dt.date.today().isoformat()}')
    return dest


if __name__ == "__main__":
    if len(sys.argv) < 4 or sys.argv[2] != "--out":
        print(__doc__)
        sys.exit(2)
    save(sys.argv[1], Path(sys.argv[3]))
