"""Rules the hub's website keeps, checked on the files themselves (the live behaviour was exercised in a real browser; see the commit message).
The security policy forbids inline scripts, so a page that needs one would silently break: these tests catch that before a visitor does."""
import re
from pathlib import Path

import pytest

WEB = Path(__file__).parent.parent / "hub" / "web"
PAGES = sorted(WEB.glob("*.html"))
TEXT = sorted([*WEB.glob("*.html"), *WEB.glob("*.js"), *WEB.glob("*.css")])


def test_there_are_pages_and_files_to_check():
    assert {p.name for p in PAGES} == {"index.html", "signin.html", "app.html", "privacy.html"} and len(TEXT) >= 8


@pytest.mark.parametrize("f", TEXT, ids=lambda f: f.name)
def test_no_em_or_en_dash_in_anything_a_visitor_can_see(f):
    assert "—" not in f.read_text() and "–" not in f.read_text()


@pytest.mark.parametrize("f", PAGES, ids=lambda f: f.name)
def test_pages_have_no_inline_script_or_handler_and_one_h1_and_a_language(f):
    t = f.read_text()
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", t), "inline script"
    assert not re.search(r"\son[a-z]+\s*=", t), "inline event handler"
    assert t.count("<h1") == 1 and '<html lang="en">' in t and "<title>" in t and 'name="viewport"' in t


@pytest.mark.parametrize("f", [f for f in WEB.glob("*.js")], ids=lambda f: f.name)
def test_scripts_never_write_html_from_strings(f):
    t = f.read_text()
    assert "innerHTML" not in t and "insertAdjacentHTML" not in t and "document.write" not in t and "eval(" not in t


def test_every_local_file_a_page_style_or_script_points_at_exists():
    missing = []
    for f in TEXT:
        t = f.read_text()
        refs = re.findall(r'(?:href|src)="([^"#:]+?)"', t) if f.suffix == ".html" else []
        refs += re.findall(r"url\(([^)]+)\)", t) if f.suffix == ".css" else []
        refs += re.findall(r'from "\./([^"]+)"', t) if f.suffix == ".js" else []
        for r in refs:
            r = r.strip("'\" ")
            if r.startswith(("data:", "http", "var(")) or "${" in r:
                continue
            if not (WEB / r.split("?")[0]).exists():
                missing.append(f"{f.name} -> {r}")
    assert not missing, missing


def test_only_transform_and_opacity_are_animated_and_reduced_motion_is_respected():
    css = (WEB / "site.css").read_text()
    for decl in re.findall(r"transition:\s*([^;]+);", css):
        props = {part.strip().split()[0] for part in decl.split(",")}
        assert props <= {"transform", "opacity", "none"}, decl
    assert "prefers-reduced-motion: reduce" in css
    assert "reduce" in (WEB / "constellation.js").read_text() and "prefers-reduced-motion" in (WEB / "constellation.js").read_text()


def test_both_themes_and_the_control_border_token_exist_with_enough_contrast():
    css = (WEB / "site.css").read_text()
    assert 'data-theme="light"' in css and "prefers-color-scheme: light" in css and css.count("--line:") == 3

    def lum(h):
        h = h.lstrip("#")
        c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    def ratio(a, b):
        hi, lo = sorted([lum(a), lum(b)], reverse=True)
        return (hi + 0.05) / (lo + 0.05)
    dark = dict(re.findall(r"--(line|ink|deep|raise): (#[0-9a-f]{6})", css.split(":root[data-theme=\"light\"]")[0]))
    light = dict(re.findall(r"--(line|ink|deep|raise): (#[0-9a-f]{6})", css.split(":root[data-theme=\"light\"]")[1].split("@media")[0]))
    for theme in (dark, light):
        for surface in ("ink", "deep", "raise"):
            assert ratio(theme["line"], theme[surface]) >= 3.0, (theme["line"], surface)


def test_licences_for_the_fonts_and_icons_are_kept_with_them():
    assert (WEB / "fonts" / "bricolage-LICENSE.txt").exists() and (WEB / "fonts" / "geist-LICENSE.txt").exists() and (WEB / "icons" / "phosphor-LICENSE.txt").exists()
    assert "SIL Open Font License" in (WEB / "fonts" / "geist-LICENSE.txt").read_text()
