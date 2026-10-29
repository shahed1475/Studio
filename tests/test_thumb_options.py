"""The dashboard's thumbnail options (30 Oct 2026). The preview route showed `thumb-<n>.jpg` whatever the list said and the choose route picked `thumb-<n>.jpg` too, so the drawn
thumbnails (art-a, v2-...) could not be seen or chosen: the owner only ever saw the template frames and said every thumbnail looked the same. Option n is now the n-th entry of the
video's own `thumbnails` list, and only a file inside its thumbs folder."""
import pytest

import dashboard


META = {"thumbnails": ["thumbs/art-a.jpg", "thumbs/art-b.jpg", "thumbs/thumb-1.jpg"], "thumbnail": "thumbs/art-a.jpg"}


def folder(tmp_path):
    f = tmp_path / "v"
    (f / "thumbs").mkdir(parents=True)
    for n in ("art-a.jpg", "art-b.jpg", "thumb-1.jpg"):
        (f / "thumbs" / n).write_bytes(b"x")
    return f


def test_option_n_is_the_nth_entry_of_the_list_not_thumb_n(tmp_path):
    f = folder(tmp_path)
    assert dashboard.thumb_option(f, META, 1) == "thumbs/art-a.jpg"
    assert dashboard.thumb_option(f, META, 2) == "thumbs/art-b.jpg"
    assert dashboard.thumb_option(f, META, 3) == "thumbs/thumb-1.jpg"


@pytest.mark.parametrize("n", [0, 4, -1, "x", None])
def test_a_number_outside_the_list_is_no_option(tmp_path, n):
    assert dashboard.thumb_option(folder(tmp_path), META, n) is None


def test_an_entry_that_leaves_the_thumbs_folder_or_is_missing_is_never_served(tmp_path):
    f = folder(tmp_path)
    (tmp_path / "secret.jpg").write_bytes(b"s")
    bad = {"thumbnails": ["../secret.jpg", "thumbs/../../secret.jpg", "thumbs/gone.jpg", "/etc/passwd"]}
    for n in range(1, 5):
        assert dashboard.thumb_option(f, bad, n) is None
