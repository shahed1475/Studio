"""Per-film drawing limit (24 Nov 2026): the Seven Sleepers film replayed its scenes 9 to 32 for its last third because drawing stopped at 16."""
import inspect

import aiart
import run


def test_the_standard_limit_holds_without_an_owner_setting():
    assert run._art_limit({}) == aiart.MAX_PER_VIDEO["doc"]
    assert run._art_limit({"art_limit": None}) == aiart.MAX_PER_VIDEO["doc"]
    assert run._art_limit({"art_limit": "many"}) == aiart.MAX_PER_VIDEO["doc"]


def test_an_owner_limit_raises_the_cap_but_never_lowers_it_or_passes_the_ceiling():
    assert run._art_limit({"art_limit": 60}) == 60
    assert run._art_limit({"art_limit": 3}) == aiart.MAX_PER_VIDEO["doc"]
    assert run._art_limit({"art_limit": 10_000}) == run.ART_LIMIT_MAX
    assert run.ART_LIMIT_MAX * 104 < 10_000  # even at the ceiling one film fits inside Cloudflare's free day (104 Neurons a 1024x576 picture)


def test_the_documentary_producer_uses_the_films_own_limit_in_both_passes():
    src = inspect.getsource(run._produce_doc)
    assert "art_limit=_art_limit(data)" in src
    assert "art_limit=max(_art_limit(data), aiart.MAX_PER_VIDEO[\"doc\"] + aiart.EXTRA_FOR_VARIETY)" in src
