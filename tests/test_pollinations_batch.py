"""tools/pollinations_batch.py (1 Nov 2026): realistic pictures from Pollinations with the owner's own key. The key travels only in a header, a spending cap stops a run, and a model whose price cannot be read is refused."""
import pytest

import config
import tools.flux_batch as fb
import tools.pollinations_batch as pb
import tools.zimage_batch as zb

JOB = {"id": "k1", "prompt": "a quiet river at dusk, photorealistic", "width": 1280, "height": 720, "seed": 7}
JPEG = b"\xff\xd8\xff\xe0" + b"x" * 64
PRICES = {"tongyi-mai/z-image-turbo": 0.004, "black-forest-labs/flux.1.1-pro": 0.03}


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    monkeypatch.setenv("POLLINATIONS_API_KEY", "sk_testkey123")


def fake(calls, status=200, body=JPEG):
    def fetch(url, headers):
        calls.append((url, dict(headers)))
        return status, body

    return fetch


def test_the_cache_path_names_the_model_and_never_collides_with_the_local_pictures():
    p = pb.path_for(JOB)
    assert p == pb.path_for(dict(JOB)) and p.name.startswith("p-") and p.suffix == ".jpg"
    assert p != pb.path_for({**JOB, "model": "black-forest-labs/flux.1.1-pro"}) and p != pb.path_for({**JOB, "seed": 8})
    assert p not in (fb.path_for(JOB), zb.path_for(JOB))


def test_a_size_is_rounded_up_to_a_multiple_of_32():
    assert pb.fit_size(1280, 720) == (1280, 736) and pb.fit_size(768, 448) == (768, 448) and pb.fit_size(1000, 33) == (1024, 64)


def test_the_key_is_sent_in_a_header_and_never_in_the_address():
    calls = []
    out = pb.draw(JOB, fetch=fake(calls))
    url, headers = calls[0]
    assert out.exists() and out.read_bytes() == JPEG and "sk_testkey123" not in url and "key=" not in url
    assert headers["Authorization"] == "Bearer sk_testkey123" and "model=tongyi-mai%2Fz-image-turbo" in url and "width=1280&height=736" in url


def test_a_picture_that_exists_is_not_fetched_again():
    calls = []
    pb.draw(JOB, fetch=fake(calls))
    pb.draw(JOB, fetch=fake(calls))
    assert len(calls) == 1


def test_without_a_key_it_stops_before_any_request_and_names_only_the_variable(monkeypatch):
    monkeypatch.delenv("POLLINATIONS_API_KEY")
    calls = []
    with pytest.raises(RuntimeError, match="POLLINATIONS_API_KEY"):
        pb.draw(JOB, fetch=fake(calls))
    assert calls == []


def test_an_error_answer_raises_without_the_key_and_leaves_no_file():
    with pytest.raises(RuntimeError) as e:
        pb.draw(JOB, fetch=fake([], status=402, body=b'{"error":{"message":"payment required sk_testkey123"}}'))
    assert "402" in str(e.value) and "sk_testkey123" not in str(e.value) and not pb.path_for(JOB).exists()


def test_a_run_stops_before_the_request_that_would_pass_the_cap_and_cached_pictures_cost_nothing():
    calls = []
    jobs = [{**JOB, "id": f"j{i}", "seed": i} for i in range(5)]
    pb.draw(jobs[0], fetch=fake([]))  # already drawn: free
    done = pb.run(jobs, cap=0.009, prices=PRICES, fetch=fake(calls))
    assert [d["id"] for d in done if d["status"] == "DONE"] == ["j0", "j1", "j2"] and len(calls) == 2
    assert [d["status"] for d in done][3:] == ["CAP", "CAP"] and round(sum(d.get("cost", 0) for d in done), 3) == 0.008


def test_a_model_without_a_flat_per_picture_price_is_refused():
    with pytest.raises(ValueError, match="price"):
        pb.run([{**JOB, "model": "google/gemini-nano-banana-2.1"}], cap=1, prices=PRICES, fetch=fake([]))
