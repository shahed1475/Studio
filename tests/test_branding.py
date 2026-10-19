import branding

NAME = "The Sleeping Library"
TAG = "Calm stories for quiet nights"


def test_avatar_is_square_and_big_enough():
    im = branding.avatar(NAME)
    assert im.size == (800, 800)


def test_banner_size_and_text_inside_the_safe_area():
    assert branding.banner(NAME, TAG).size == (2560, 1440)
    x0, y0, x1, y1 = branding.SAFE
    boxes = branding.layout_banner(NAME, TAG)
    assert boxes and all(x0 <= a and y0 <= b and c <= x1 and d <= y1 for a, b, c, d in boxes.values())


def test_long_name_still_fits_safe_area():
    boxes = branding.layout_banner("The Extremely Long Name of a Channel About Old Legends", "A tagline that is also rather long for a banner")
    x0, y0, x1, y1 = branding.SAFE
    assert all(x0 <= a and y0 <= b and c <= x1 and d <= y1 for a, b, c, d in boxes.values())


def test_description_has_ai_disclosure_and_no_schedule_promise():
    d = branding.channel_description(NAME, TAG)
    assert TAG in d and "AI-generated" in d and "every day" not in d.lower()


def test_write_kit_files_and_limits(tmp_path):
    out = branding.write_kit(tmp_path, NAME, TAG)
    assert {p.name for p in out.values()} == {"avatar.png", "banner.png", "description.txt"}
    assert out["avatar"].stat().st_size <= 4_000_000 and out["banner"].stat().st_size <= 6_000_000
