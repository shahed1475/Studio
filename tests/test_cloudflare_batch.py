"""tools/cloudflare_batch.py (1 Nov 2026): FLUX.1 schnell on Cloudflare Workers AI, free up to 10,000 Neurons a day. The token travels only in a header, a daily counter stops a run before the free allowance, and a cached picture costs nothing."""
import base64
import json

import pytest

import config
import tools.cloudflare_batch as cb
import tools.flux_batch as fb
import tools.pollinations_batch as pb
import tools.zimage_batch as zb

JOB = {"id": "k1", "prompt": "a river at dusk, photorealistic", "steps": 4, "seed": 7}
JPEG = b"\xff\xd8\xff\xe0" + b"x" * 64


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(cb, "USAGE", tmp_path / "usage.json")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok_secret_456")


def ok_body(img=JPEG):
    return json.dumps({"success": True, "result": {"image": base64.b64encode(img).decode()}}).encode()


def fake(calls, status=200, body=None):
    def fetch(url, headers, payload):
        calls.append((url, dict(headers), payload))
        return status, body if body is not None else ok_body()

    return fetch


def test_the_cache_path_is_its_own_and_stable():
    p = cb.path_for(JOB)
    assert p == cb.path_for(dict(JOB)) and p.name.startswith("c-") and p.suffix == ".jpg" and p != cb.path_for({**JOB, "seed": 8})
    assert p not in (fb.path_for({**JOB, "width": 512, "height": 512}), zb.path_for({**JOB, "width": 512, "height": 512}), pb.path_for({**JOB, "width": 512, "height": 512}))


def test_a_picture_costs_tiles_and_steps_in_neurons_from_cloudflares_price_list():
    assert round(cb.neurons(JOB), 1) == 57.6 and round(cb.neurons({**JOB, "steps": 8}), 1) == 96.0


def test_the_token_goes_in_a_header_the_body_has_the_prompt_and_the_picture_is_saved():
    calls = []
    out = cb.draw(JOB, fetch=fake(calls))
    url, headers, payload = calls[0]
    assert out.read_bytes() == JPEG and "tok_secret_456" not in url and "acc123" in url and url.endswith("/ai/run/@cf/black-forest-labs/flux-1-schnell")
    assert headers["Authorization"] == "Bearer tok_secret_456" and payload == {"prompt": JOB["prompt"], "steps": 4}  # Cloudflare refuses a seed field (400, checked live 1 Nov 2026)


def test_a_cached_picture_is_not_fetched_again():
    calls = []
    cb.draw(JOB, fetch=fake(calls))
    cb.draw(JOB, fetch=fake(calls))
    assert len(calls) == 1


def test_missing_settings_stop_before_any_request_and_name_only_the_variables(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN")
    calls = []
    with pytest.raises(RuntimeError, match="CLOUDFLARE_API_TOKEN"):
        cb.draw(JOB, fetch=fake(calls))
    assert calls == []


def test_an_error_answer_raises_without_the_token_and_leaves_no_file():
    with pytest.raises(RuntimeError) as e:
        cb.draw(JOB, fetch=fake([], status=429, body=b'{"errors":[{"message":"daily limit tok_secret_456"}]}'))
    assert "429" in str(e.value) and "tok_secret_456" not in str(e.value) and not cb.path_for(JOB).exists()


def test_a_run_stops_before_the_free_allowance_counts_per_day_and_cached_pictures_cost_nothing():
    jobs = [{**JOB, "id": f"j{i}", "seed": i} for i in range(5)]
    cb.draw(jobs[0], fetch=fake([]))  # cached: free
    calls = []
    res = cb.run(jobs, cap=120, fetch=fake(calls), today="2026-11-01")  # room for two pictures of 57.6
    assert [r["status"] for r in res] == ["DONE", "DONE", "DONE", "CAP", "CAP"] and len(calls) == 2
    assert round(json.loads(cb.USAGE.read_text())["neurons"], 1) == 115.2
    more = cb.run(jobs[3:], cap=120, fetch=fake([]), today="2026-11-01")
    assert [r["status"] for r in more] == ["CAP", "CAP"]  # the day's counter was kept
    nextday = cb.run(jobs[3:], cap=120, fetch=fake([]), today="2026-11-02")
    assert [r["status"] for r in nextday] == ["DONE", "DONE"]


KLEIN = {"id": "v1", "prompt": "a candlelit study", "model": "klein", "width": 1280, "height": 720}


def test_klein_has_its_own_cache_path_per_size_and_costs_output_tiles_from_cloudflares_price_list():
    assert cb.path_for(KLEIN) != cb.path_for({**KLEIN, "width": 1920, "height": 1080}) and cb.path_for(KLEIN) != cb.path_for({"id": "x", "prompt": "a candlelit study", "steps": 4})
    assert round(cb.neurons(KLEIN), 1) == 156.3  # 3 x 2 tiles of 512 x 26.05 Neurons (counted by whole tiles: the safe side)
    assert round(cb.neurons({**KLEIN, "width": 1920, "height": 1080}), 1) == 312.6


def test_klein_is_sent_as_a_multipart_form_with_the_size_and_no_seed_or_steps():
    calls = []

    def fetch(url, headers, payload, multipart=False):
        calls.append((url, dict(headers), payload, multipart))
        return 200, ok_body()

    out = cb.draw(KLEIN, fetch=fetch)
    url, headers, payload, multipart = calls[0]
    assert out.exists() and url.endswith("/ai/run/@cf/black-forest-labs/flux-2-klein-4b") and multipart is True and "tok_secret_456" not in url
    assert payload == {"prompt": "a candlelit study", "width": 1280, "height": 720} and headers["Authorization"] == "Bearer tok_secret_456"
