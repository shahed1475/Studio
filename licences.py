"""The studio's one rule for pictures and footage: may this licence be used, and does it need a credit line.

Owner's decision, 10 Nov 2026 (it widens CLAUDE.md section D, which said "public domain, CC0, labelled AI art only"): public domain, CC0, CC BY, CC BY-SA, NASA media (never with NASA logos)
and the Pixabay Content License may be used, as long as every item keeps its address, licence and credit and the credits go in the video's description.
Never: non-commercial, no-derivatives, all rights reserved, fair use, "used with permission", GFDL, Pexels (the owner did not list it), or a licence nobody named.
The text can be a bare licence name ("CC BY-SA 4.0") or a whole credit line that contains one ("Title (Wikimedia Commons, CC BY-SA 4.0), https://..."): a refusal word anywhere wins."""
import re

REFUSED = re.compile(r"\bnc\b|\bnd\b|-nc\b|-nd\b|non-?commercial|no[- ]derivatives?|all rights|fair use|used with permission|pexels|gfdl", re.I)
# first match wins, so CC0 and public domain are tried before the credit-needing licences
KINDS = (
    ("cc0", re.compile(r"\bcc0\b|\bcc[- ]zero\b", re.I)),
    ("public_domain", re.compile(r"public domain|\bpdm\b|\bpd\b|\bpd-", re.I)),
    ("cc_by_sa", re.compile(r"\bcc[- ]by[- ]sa\b", re.I)),
    ("cc_by", re.compile(r"\bcc[- ]by\b", re.I)),
    ("nasa", re.compile(r"\bnasa media\b", re.I)),
    ("pixabay", re.compile(r"\bpixabay (content )?licen[cs]e\b", re.I)),
)
CREDITED = {"cc_by", "cc_by_sa", "nasa", "pixabay"}
PREFERENCE = {"cc0": 0, "public_domain": 0, "cc_by_sa": 1, "cc_by": 1, "nasa": 2, "pixabay": 3}  # lower is preferred when two pictures fit equally


def kind(text) -> str | None:
    """'cc0', 'public_domain', 'cc_by_sa', 'cc_by', 'nasa', 'pixabay', or None when the text names no licence the studio may use (or names one it refuses)."""
    text = str(text or "")
    if REFUSED.search(text):
        return None
    for name, rx in KINDS:
        if rx.search(text):
            return name
    return None


def accepted(text) -> bool:
    return kind(text) is not None


def needs_credit(text) -> bool:
    """True when the licence obliges us to show a credit line (CC BY, CC BY-SA, NASA media, Pixabay). Public domain and CC0 do not, though the studio keeps the record either way."""
    text = str(text or "")
    return accepted(text) and any(rx.search(text) for name, rx in KINDS if name in CREDITED)
