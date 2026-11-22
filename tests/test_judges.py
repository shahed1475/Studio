"""The judge cascade (judges.py, the owner's order of 22 Nov 2026): two judges of different families, the stricter answer, never the writer, OpenRouter
tried once and skipped for an hour when busy, reasoning never read as the verdict, compact source excerpts that keep every checkable term."""
import datetime as dt
import json

import pytest
import requests

import freemodels
import judges
import llm
import reviewer
import sourceslice

NOW = dt.datetime(2026, 11, 22, 3, 0, tzinfo=dt.timezone.utc)
KEY = "freellmapi-SECRET-0123456789abcdef"
FULL_OK = {"invented_facts_risk": 1, "policy_risk": 0, "misleading_title": False, "title_reason": "", "covers": "", "better_titles": [],
           "misleading_thumbnail": False, "thumbnail_reason": "", "issues": []}
COMPACT_OK = {"invented_facts": 1, "policy": 0, "title_accurate": True, "thumb_accurate": True, "strict_note": ""}
ROSTER = ["nvidia/nemotron-3-ultra-550b-a55b:free", "nvidia/nemotron-3.5-lightning:free", "google/gemma-4-31b-it:free", "openrouter/free",
          "particle-ai/particle-1:free"]
FILLER = ("The valley was farmed for many generations and its fields were watered by small canals that the villagers kept clean each spring. " * 6).strip()
DEEP = "Herodotus wrote that Cambyses sent fifty thousand soldiers from Thebes in 524 BC toward the oasis of Siwa, and that a wind buried them in the sand."
SOURCE = "\n\n".join(["The Lost Army of Cambyses is a story told by the Greek historian Herodotus."] + [FILLER] * 30 + [DEEP] + [FILLER] * 30)
META = {"title": "The Lost Army of Cambyses", "description": "A calm retelling of what Herodotus wrote about the army.", "thumb_hook": "LOST ARMY",
        "lines": [{"text": "In 524 BC Cambyses sent fifty thousand soldiers from Thebes toward the oasis of Siwa."},
                  {"text": "Herodotus says a great wind buried them all in the sand."}],
        "script_writers": ["extra:minimaxaiminimax-m3.1-flash"], "script_model": "google/gemma-4-26b-a4b-it:free"}


def http_error(code, msg="", headers=None):
    r = requests.Response()
    r.status_code = code
    r._content = json.dumps({"error": {"message": msg}}).encode()
    r.headers.update(headers or {})
    return requests.HTTPError(f"{code} error", response=r)


class World:
    """Stand-in providers: `replies[model]` is a reply (a dict, a raw text, an exception) or a list of them, one per request."""

    def __init__(self):
        self.sent, self.replies, self.served = [], {}, {}

    def post(self, payload, key):
        mid = payload["model"]
        self.sent.append({"model": mid, "prompt": payload["messages"][0]["content"], "timeout": payload.get("_timeout_s"),
                          "max_tokens": payload["max_tokens"], "reasoning": payload.get("reasoning")})
        if mid not in self.replies:
            raise http_error(404, f"stand-in: {mid} has no reply")
        r = self.replies[mid]
        r = (r.pop(0) if r else http_error(404, "no more replies")) if isinstance(r, list) else r
        if isinstance(r, Exception):
            raise r
        content = r if isinstance(r, str) else json.dumps(r)
        served = self.served.get(mid, mid.split(":", 1)[1] if mid.startswith(("extra:", "gemini:")) else mid)
        return {"model": served, "choices": [{"message": {"content": content}, "finish_reason": "stop"}], "usage": {}}

    def asked(self):
        return [s["model"] for s in self.sent]


@pytest.fixture
def world(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"extra_llm_on": True, "extra_llm_url": "http://127.0.0.1:31415/v1", "extra_llm_local": True, "extra_llm_key": KEY,
                                    "extra_llm_gap_s": 0, "extra_llm_models": {"script": "gemini-3.5-flash, gemini-3-flash-preview, minimaxaiminimax-m3.1-flash",
                                                                               "review": "gemini-3.6-flash, nemotron-3-ultra-550b"}}))
    monkeypatch.setattr(llm, "SETTINGS_FILE", settings)
    llm._url_cache.clear()
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "usage.json")
    monkeypatch.setattr(freemodels, "FILE", tmp_path / "free_models.json")
    roster = [{"id": m, "context": 262144, "score": 9 - i} for i, m in enumerate(ROSTER)]
    with freemodels._update() as d:
        d.update(fetched_at=NOW.strftime(freemodels.TS), models=roster)
    monkeypatch.setattr(freemodels, "refresh", lambda now, *a, **k: roster)
    monkeypatch.setattr(freemodels, "quota", lambda *a, **k: None)
    jf = tmp_path / "judges.json"
    jf.write_text(json.dumps(judges.DEFAULTS))
    monkeypatch.setattr(judges, "CONFIG_FILE", jf)
    monkeypatch.setattr(llm, "extra_status", lambda mid: "ready")
    monkeypatch.setattr(llm, "api_key", lambda: "or-key-0123456789")
    monkeypatch.setattr(llm, "_now", lambda: NOW)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cfg = {**llm.DEFAULTS, "free": True, "free_review": True}
    monkeypatch.setattr(llm, "load_config", lambda: dict(cfg))
    w = World()
    w.config = jf
    monkeypatch.setattr(llm, "_post", w.post)
    for state in (llm._last_free, llm._served):
        state.clear()
    llm._WRITERS.clear()
    yield w


def review(meta=None, source=SOURCE):
    checks = reviewer.llm_review(dict(meta or META), source)
    return {c["name"]: c for c in checks}, reviewer.verdict_from(checks, "wikipedia")


# ---- 1. OpenRouter busy: one try, no retry, skipped for an hour, FreeLLMAPI answers in the same review ----
def test_openrouter_429_fails_over_to_freellmapi_at_once_and_is_skipped_for_an_hour(world):
    world.replies = {"extra:gemini-2.5-flash": FULL_OK, "nvidia/nemotron-3-ultra-550b-a55b:free": http_error(429, "Rate limit exceeded: free-models-per-day"),
                     "extra:qwen-3.8-27b": [COMPACT_OK, COMPACT_OK], "extra:gemini-3.8-flash": FULL_OK}
    checks, verdict = review()
    assert verdict == "pass" and checks["invented_facts"]["ok"]
    assert world.asked() == ["extra:gemini-2.5-flash", "nvidia/nemotron-3-ultra-550b-a55b:free", "extra:qwen-3.8-27b"]  # one OpenRouter request, no retry
    orq = world.sent[1]
    assert orq["timeout"] <= 25 and "title_accurate" in orq["prompt"] and "excerpts" in orq["prompt"]                 # compact rubric with source excerpts
    cooling = freemodels.provider_cooling("openrouter", NOW + dt.timedelta(minutes=59))
    assert cooling and "quota" in cooling["why"] and not freemodels.provider_cooling("openrouter", NOW + dt.timedelta(minutes=61))
    assert llm.LAST_REVIEW["models"] == ["extra:gemini-2.5-flash", "extra:qwen-3.8-27b"]                              # the 429 is no judge
    assert freemodels._load()["health"]["nvidia/nemotron-3-ultra-550b-a55b:free"]["fails"] == 0                      # and no failure of the model
    assert "different families" in checks["invented_facts"]["detail"] and "google" in checks["invented_facts"]["detail"]
    world.sent.clear()
    world.replies["extra:gemini-2.5-flash"] = FULL_OK
    review()                                                                                                          # within the hour
    assert world.asked() == ["extra:gemini-2.5-flash", "extra:qwen-3.8-27b"]                                          # OpenRouter is not asked at all


@pytest.mark.parametrize("failure, cools", [(http_error(503, "no instances available"), True), (http_error(429, "rate limited upstream"), True),
                                            (requests.ReadTimeout("read timed out"), False), (http_error(400, "bad request"), False)])
def test_openrouter_failures_fail_over_and_only_busy_or_down_cool_it(world, failure, cools):
    world.replies = {"extra:gemini-2.5-flash": FULL_OK, "nvidia/nemotron-3-ultra-550b-a55b:free": [failure, failure, failure], "extra:qwen-3.8-27b": COMPACT_OK}
    _, verdict = review()
    assert verdict == "pass" and world.asked()[-1] == "extra:qwen-3.8-27b"
    assert bool(freemodels.provider_cooling("openrouter", NOW)) is cools
    h = freemodels._load()["health"].get("nvidia/nemotron-3-ultra-550b-a55b:free", {})
    if isinstance(failure, requests.Timeout):                      # the cascade's own 25 s ended it: a miss for reviews, never a bench for writing
        assert h["fails"] == 0 and h["roles"]["review"]["late"] == 1 and freemodels.available("nvidia/nemotron-3-ultra-550b-a55b:free", NOW)


def test_every_judge_failing_or_used_up_is_unreviewed_never_pass_and_never_fail(world):
    world.replies = {m: http_error(429, "quota exhausted for today") for m in ["extra:gemini-2.5-flash", "extra:gemini-3.8-flash", "extra:gemini-3.5-flash-lite",
                                                                              "extra:qwen-3.8-27b", "extra:glm-4.7-flash", "extra:nemotron-3-ultra-550b",
                                                                              "nvidia/nemotron-3-ultra-550b-a55b:free", "particle-ai/particle-1:free"]}
    checks, verdict = review()
    assert verdict == "unreviewed" and not checks["llm_review"]["ok"] and "invented_facts" not in checks
    world.replies = {"extra:gemini-2.5-flash": FULL_OK, **{m: http_error(503) for m in ["extra:qwen-3.8-27b", "extra:glm-4.7-flash", "extra:nemotron-3-ultra-550b",
                                                                                         "nvidia/nemotron-3-ultra-550b-a55b:free", "particle-ai/particle-1:free"]}}
    _, verdict = review()
    assert verdict == "unreviewed"                                                                                    # one judge alone never passes


# ---- 2. reasoning blocks and malformed answers ----
@pytest.mark.parametrize("reply, expected", [
    ('<think>{"a": 1} looks right... no</think>{"a": 2}', {"a": 2}),
    ('I weigh it up.\n{"a": 9} was a draft</think>\n{"a": 3}', {"a": 3}),          # the opening tag was in the prompt template
    ('<thinking>{"a": 1}</thinking> <reasoning>{"a": 4}</reasoning> {"a": 5}', {"a": 5}),
    ('{"note": "the word <think> in a value"}', {"note": "the word <think> in a value"}),  # plain JSON is read as it is
])
def test_reasoning_is_stripped_before_the_json_is_read(reply, expected):
    assert llm.parse_json(reply) == expected


def test_a_reply_that_is_all_reasoning_has_no_json():
    with pytest.raises(ValueError):
        llm.parse_json('<think>the answer is {"invented_facts": 0} I think, and then the output stopped')


def test_a_judge_s_reasoning_is_never_its_verdict(world):
    draft = json.dumps(COMPACT_OK)
    final = json.dumps({"invented_facts": 8, "policy": 0, "title_accurate": False, "thumb_accurate": True, "strict_note": "the title promises a name the narration calls lost"})
    world.replies = {"extra:gemini-2.5-flash": FULL_OK, "nvidia/nemotron-3-ultra-550b-a55b:free": f"<think>{draft} hmm, no.</think>{final}"}
    checks, verdict = review()
    assert verdict == "fail" and not checks["invented_facts"]["ok"] and not checks["title_matches"]["ok"]
    assert "calls lost" in checks["title_matches"]["detail"]                                                       # the compact note becomes the reason


@pytest.mark.parametrize("bad", [{"invented_facts": "low", "policy": 0, "title_accurate": True, "thumb_accurate": True, "strict_note": ""},
                                 {"invented_facts": 11, "policy": 0, "title_accurate": True, "thumb_accurate": True, "strict_note": ""},
                                 {"policy": 0, "title_accurate": True, "thumb_accurate": True},
                                 {"invented_facts": 0, "policy": 0, "title_accurate": "yes", "thumb_accurate": True, "strict_note": ""},
                                 {"invented_facts": 0, "policy": 0, "title_accurate": True, "strict_note": ""},              # thumbnail text exists: its flag is required
                                 "no json here at all"])
def test_a_malformed_answer_is_no_judge_and_the_next_one_is_asked(world, bad):
    world.replies = {"extra:gemini-2.5-flash": FULL_OK, "nvidia/nemotron-3-ultra-550b-a55b:free": bad, "extra:qwen-3.8-27b": COMPACT_OK}
    _, verdict = review()
    assert verdict == "pass" and llm.LAST_REVIEW["models"][1] == "extra:qwen-3.8-27b"


def test_compact_scores_round_up_and_the_note_is_cut_to_twelve_words():
    got = judges.parse_compact({"invented_facts": "3.2", "policy": 0.5, "title_accurate": "false", "strict_note": " ".join(["word"] * 20)}, thumb=False)
    assert got["invented_facts"] == 4 and got["policy"] == 1 and got["title_accurate"] is False and len(got["strict_note"].split()) == 12
    full = judges.to_full(got)
    assert full["misleading_title"] is True and full["issues"] == [got["strict_note"]] and full["title_reason"] == got["strict_note"]
    assert judges.to_full(judges.parse_compact(COMPACT_OK | {"strict_note": "fine"}, thumb=True))["issues"] == []    # nothing flagged: no issue invented


def test_the_stricter_answer_wins_field_by_field(world):
    world.replies = {"extra:gemini-2.5-flash": FULL_OK | {"invented_facts_risk": 5, "issues": ["line 2 date unclear"]},
                     "nvidia/nemotron-3-ultra-550b-a55b:free": COMPACT_OK | {"policy": 6, "title_accurate": False, "strict_note": "overpromises"}}
    checks, _ = review()
    assert checks["invented_facts"]["detail"].startswith("risk 5/10") and not checks["policy_risk"]["ok"] and not checks["title_matches"]["ok"]
    assert "invented_facts_watch" in checks                                                                         # 5 from slot A still starts the polish


# ---- 3. the writer never judges, under any provider's name; two different families ----
def test_identity_and_family_across_providers():
    same = [("nvidia/nemotron-3-ultra-550b-a55b:free", "extra:nemotron-3-ultra-550b"), ("extra:nvidianemotron-3-ultra-550b-a55b", "nemotron-3-ultra-550b"),
            ("extra:minimaxaiminimax-m3.1-flash", "minimax/minimax-m3.1-flash"), ("extra:deepseek-aideepseek-v4.1-flash", "deepseek/deepseek-v4.1-flash"),
            ("google/gemma-4-31b-it:free", "extra:googlegemma-4-31b-it"), ("extra:z-aiglm-5.3-flash", "glm-5.3-flash"), ("qwen3.8-27b", "extra:qwen-3.8-27b"),
            ("gemini:gemini-2.5-flash", "extra:gemini-2.5-flash"), ("gemini-3.1-flash-lite-preview", "gemini-3.1-flash-lite"),
            ("deepseek/deepseek-chat-v3-0324:free", "deepseek-chat-v3")]
    for a, b in same:
        assert llm.model_identity(a) == llm.model_identity(b), (a, b)
    assert llm.model_identity("gemini-3.5-flash-lite") != llm.model_identity("gemini-3.5-flash")                     # a different model, not a variant label
    assert llm.model_identity("extra:gemini-3.6-flash") == "gemini-3.6-flash"
    assert llm.model_family("extra:gemini-2.5-flash") == llm.model_family("google/gemma-4-31b-it:free") == {"google"}
    assert llm.model_family("extra:deepseek-r1-distill-qwen-32b") == {"deepseek", "qwen"}
    assert llm.same_family("extra:deepseek-r1-distill-qwen-32b", "extra:qwen-3.8-27b") and not llm.same_family("extra:glm-4.7-flash", "extra:qwen-3.8-27b")
    assert llm.model_family("nvidia/nemotron-3.5-lightning:free") == {"nvidia"} and llm.model_family("particle-ai/particle-1:free") == {"particle"}


def test_the_writer_is_never_asked_under_another_providers_name(world):
    meta = dict(META, script_writers=["extra:nvidianemotron-3-ultra-550b-a55b", "extra:minimaxaiminimax-m3.1-flash"])
    world.replies = {"extra:gemini-2.5-flash": FULL_OK, "nvidia/nemotron-3.5-lightning:free": COMPACT_OK}
    _, verdict = review(meta)
    assert verdict == "pass"
    assert "nvidia/nemotron-3-ultra-550b-a55b:free" not in world.asked() and "extra:nemotron-3-ultra-550b" not in world.asked()
    assert not any("minimax" in m for m in world.asked())


def test_the_label_alone_is_avoided_when_the_real_writers_were_not_recorded(world):
    meta = {k: v for k, v in META.items() if k != "script_writers"} | {"script_model": "extra:gemini-2.5-flash"}       # an older video: only its label
    world.replies = {"extra:gemini-3.8-flash": FULL_OK, "nvidia/nemotron-3-ultra-550b-a55b:free": COMPACT_OK}
    review(meta)
    assert world.asked()[0] == "extra:gemini-3.8-flash"


def test_an_answer_served_by_a_writer_is_thrown_away_and_another_judge_is_asked(world):
    world.served = {"extra:gemini-2.5-flash": "minimax-m3.1-flash"}                                                   # the proxy answered with the writer
    world.replies = {"extra:gemini-2.5-flash": FULL_OK, "extra:gemini-3.8-flash": FULL_OK, "nvidia/nemotron-3-ultra-550b-a55b:free": COMPACT_OK}
    _, verdict = review()
    assert verdict == "pass" and llm.LAST_REVIEW["models"][0] == "extra:gemini-3.8-flash"
    assert any("not used" in t["result"] for t in llm.LAST_REVIEW["tried"])


def test_the_second_judge_is_always_of_another_family(world):
    world.replies = {"extra:gemini-2.5-flash": http_error(429, "quota exhausted"), "extra:gemini-3.8-flash": http_error(429, "quota exhausted"),
                     "extra:gemini-3.5-flash-lite": http_error(429, "quota exhausted"), "extra:qwen-3.8-27b": FULL_OK,
                     "nvidia/nemotron-3-ultra-550b-a55b:free": http_error(503), "extra:glm-4.7-flash": COMPACT_OK}
    _, verdict = review()
    assert verdict == "pass" and llm.LAST_REVIEW["models"] == ["extra:qwen-3.8-27b", "extra:glm-4.7-flash"]
    assert world.asked().count("extra:qwen-3.8-27b") == 1                                                             # qwen judged once, never as slot B
    assert llm.LAST_REVIEW["families"] == [["qwen"], ["zhipu"]]


def test_a_second_answer_served_by_the_first_judges_family_is_not_used(world):
    world.served = {"extra:qwen-3.8-27b": "gemini-3.7-flash"}                                                         # the proxy quietly used a Gemini
    world.replies = {"extra:gemini-2.5-flash": FULL_OK, "nvidia/nemotron-3-ultra-550b-a55b:free": http_error(503), "extra:qwen-3.8-27b": COMPACT_OK,
                     "extra:glm-4.7-flash": COMPACT_OK}
    review()
    assert llm.LAST_REVIEW["models"][1] == "extra:glm-4.7-flash"


def test_routers_and_writer_list_models_are_never_judges(world):
    jc = judges.load()
    banned = {llm.model_identity(m) for m in judges.writers_of(META)}
    skipped = dict(judges.candidates("A", jc | {"slot_a": jc["slot_a"] | {"models": ["extra:auto", "extra:gemini-3.5-flash", "extra:gemini-2.5-flash"]}}, banned, frozenset(), NOW))
    assert "router" in skipped["extra:auto"] and "writer" in skipped["extra:gemini-3.5-flash"] and skipped["extra:gemini-2.5-flash"] == ""
    assert judges.is_router("openrouter/free") and judges.is_router("extra:kilo-auto") and not judges.is_router("extra:glm-4.7-flash")


# ---- 4. the compact source excerpts ----
def test_excerpts_keep_every_checkable_term_inside_the_cap():
    narration = " ".join(l["text"] for l in META["lines"])
    cut = sourceslice.slice_source(SOURCE, narration)
    assert len(SOURCE) > 20000 and cut["chars"] <= sourceslice.CAP
    assert cut["lossless"] and DEEP in cut["text"] and cut["text"].startswith("The Lost Army of Cambyses")             # the deep passage and the lead
    assert {"524", "cambyses", "thebes", "siwa", "herodotus"} <= sourceslice.checkable_terms(narration)
    assert "[...]" in cut["text"]                                                                                  # the judge is told these are excerpts


def test_a_short_source_is_whole_and_a_cap_too_small_says_it_is_lossy():
    narration = "In 1489 Ana Brandt met Oskar Veil in Lübeck and then in Danzig."
    assert {"lübeck", "danzig", "1489", "brandt"} <= sourceslice.checkable_terms(narration)                          # names in any alphabet count
    short = "Ana Brandt met Oskar Veil in 1489 in Lübeck and later in Danzig."
    assert sourceslice.slice_source(short, narration)["text"] == short
    parts = [f"In 1489 {name} lived in a quiet town and kept a careful ledger of every visitor. " * 4 for name in ("Ana Brandt", "Oskar Veil", "Lübeck", "Danzig")]
    big = "\n\n".join(p + "\n\n" + FILLER for p in parts)
    cut = sourceslice.slice_source(big, narration, cap=700, max_cap=700, lead=0, fill=0)
    assert not cut["lossless"] and "danzig" in cut["missing"] and cut["chars"] <= 700
    assert sourceslice.slice_source(big, narration, cap=700, max_cap=3000, lead=0, fill=0)["lossless"]              # the wider cap is tried once


def _three_far_apart_facts():
    """A source whose three needed passages are each about 900 characters: lead + all three cannot fit in 2,000."""
    def big(fact):
        return fact + " " + FILLER + " " + FILLER
    paras = (["The Lost Army of Cambyses is a story told by the Greek historian Herodotus."] + [FILLER] * 8 + [big(DEEP)] + [FILLER] * 8
             + [big("Darius later ruled Egypt from Memphis, where the temples stayed open.")] + [FILLER] * 8
             + [big("Psamtik III lost the battle of Pelusium to the Persians.")] + [FILLER] * 8)
    meta = dict(META, lines=META["lines"] + [{"text": "Darius later ruled Egypt, and Memphis kept its temples."},
                                             {"text": "Before that, Psamtik III had lost at Pelusium."}])
    return meta, "\n\n".join(paras)


def test_a_lossy_slice_never_goes_to_openrouter_and_the_fallback_reads_the_full_source(world):
    cfg = json.loads(world.config.read_text())
    cfg["slice"] = {"cap_chars": 2000, "max_cap_chars": 2000, "fill_chars": 0, "lead_chars": 0}
    world.config.write_text(json.dumps(cfg))
    meta, source = _three_far_apart_facts()
    world.replies = {"extra:gemini-2.5-flash": FULL_OK, "extra:qwen-3.8-27b": COMPACT_OK}
    _, verdict = review(meta, source)
    assert verdict == "pass" and "nvidia/nemotron-3-ultra-550b-a55b:free" not in world.asked()
    qwen = next(s for s in world.sent if s["model"] == "extra:qwen-3.8-27b")
    assert DEEP in qwen["prompt"] and "Darius later ruled Egypt" in qwen["prompt"] and "Pelusium to the Persians" in qwen["prompt"] and "excerpts" not in qwen["prompt"]
    assert any("would drop" in t["result"] for t in llm.LAST_REVIEW["tried"]) and llm.LAST_REVIEW["second_source"] == "full"


def test_measured_savings_on_a_long_source(world):
    paras = [f"In the year {1000 + i} a chronicle about Cambyses, Herodotus and the soldiers in the sand records a wind near the oasis, entry {i}. " * 3
             for i in range(80)]
    source = "\n\n".join(["The Lost Army of Cambyses is a story told by the Greek historian Herodotus."] + paras)
    world.replies = {"extra:gemini-2.5-flash": FULL_OK, "nvidia/nemotron-3-ultra-550b-a55b:free": COMPACT_OK}
    review(META, source)
    full, compact = world.sent[0]["prompt"], world.sent[1]["prompt"]
    assert len(compact) < 0.5 * len(full) and llm.LAST_REVIEW["second_source"] == "excerpts"
    assert "better_titles" in full and "better_titles" not in compact                                               # the compact schema asks for less


# ---- 5. where the cascade applies, and its settings ----
def test_only_the_videos_ai_review_uses_the_cascade(world, monkeypatch):
    used = []
    monkeypatch.setattr(llm, "_free_review", lambda *a, **k: used.append("old") or FULL_OK)
    llm.chat("a fact-check prompt", "review", strict=True)                                                         # the fact-check, the title check
    assert used == ["old"] and world.sent == []
    world.replies = {"extra:gemini-2.5-flash": FULL_OK, "nvidia/nemotron-3-ultra-550b-a55b:free": COMPACT_OK}
    review()
    assert used == ["old"] and len(world.sent) == 2


def test_the_cascade_is_off_in_a_user_studio_when_switched_off_or_without_free_review(world, monkeypatch):
    assert judges.active({"free": True, "free_review": True})
    assert not judges.active({"free": True, "free_review": False})
    monkeypatch.setenv("STUDIO_MODE", "tenant")
    assert not judges.active({"free": True, "free_review": True})
    monkeypatch.delenv("STUDIO_MODE")
    world.config.write_text('{"enabled": false}')
    assert not judges.active({"free": True, "free_review": True})


def test_a_broken_config_gives_the_defaults_and_bad_values_are_dropped(world):
    world.config.write_text("{not json")
    jc = judges.load()
    assert jc["problem"] and jc["slot_a"]["models"] == judges.DEFAULTS["slot_a"]["models"]
    world.config.write_text(json.dumps({"slot_a": {"models": ["extra:ok-model", "bad model id!", 7]}, "slot_b": {"openrouter": {"timeout_s": 9999, "attempts": 2}}}))
    jc = judges.load()
    assert jc["slot_a"]["models"] == ["extra:ok-model"] and jc["slot_b"]["openrouter"]["timeout_s"] == 25 and jc["slot_b"]["openrouter"]["attempts"] == 2
    shipped = json.loads((judges.config.ROOT / "config" / "judges.json").read_text())
    assert shipped["enabled"] is True and shipped["slot_b"]["openrouter"]["timeout_s"] == 25 and shipped["slot_b"]["openrouter"]["cooldown_minutes"] == 60


def test_google_ai_studio_is_used_only_with_its_key_and_gets_no_openrouter_fields(world, monkeypatch):
    sent = []

    class R:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"model": "gemini-2.5-flash", "choices": [{"message": {"content": json.dumps(FULL_OK)}}], "usage": {}}

    monkeypatch.setattr(llm, "_bounded_post", lambda url, **kw: sent.append((url, kw)) or R())
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        llm._post_gemini({"model": "gemini:gemini-2.5-flash", "messages": []}, 10)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test-key-0123456789")
    llm._post_gemini({"model": "gemini:gemini-2.5-flash", "messages": [], "usage": {"include": True}, "reasoning": {"max_tokens": 9}, "_timeout_s": 1}, 10)
    url, kw = sent[0]
    assert url == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions" and kw["headers"]["Authorization"] == "Bearer AIza-test-key-0123456789"
    assert kw["json"] == {"model": "gemini-2.5-flash", "messages": []} and kw["allow_redirects"] is False
    assert llm.scrub("failed with AIza-test-key-0123456789") == "failed with ***"
    world.replies = {"gemini:gemini-2.5-flash": FULL_OK, "nvidia/nemotron-3-ultra-550b-a55b:free": COMPACT_OK}
    review()
    assert world.asked()[0] == "gemini:gemini-2.5-flash"                                                            # with the key, Google directly first
    assert freemodels.requests_today(NOW) == 1                                                                      # only the OpenRouter request counted


# ---- 6. the agent evaluation cases, and mutation checks: each must fail when its rule is broken ----
def test_agenteval_cascade_case_passes_and_fails_when_a_rule_is_broken(monkeypatch):
    import agenteval

    case = agenteval.case_two_judges_of_different_families_never_the_writer_and_a_busy_openrouter_is_tried_once_then_skipped
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    mutations = [
        (llm, "model_identity", lambda m: str(m), "writer_avoided=False"),                             # names compared as typed: the writer judges under OpenRouter's name
        (llm, "model_family", lambda m: frozenset({str(m)}), "families=False"),                         # every model its own family: a Gemma may follow a Gemini
        (judges, "_cool_openrouter", lambda *a, **k: None, "once=False"),                               # a busy OpenRouter is asked again in the next review
        (llm, "_fail_kind", lambda *a, **k: "error", "cooled=False"),                                   # a 429 not seen as busy
    ]
    for module, name, broken, flag in mutations:
        monkeypatch.setattr(module, name, broken)
        ok, detail = case()
        assert not ok and flag in detail, (name, detail)
        monkeypatch.undo()
    real = judges.review
    monkeypatch.setattr(judges, "review", lambda *a, **k: real(*a, **k) or {"invented_facts_risk": 0, "policy_risk": 0, "misleading_title": False})  # silence passes
    ok, detail = case()
    assert not ok and "unreviewed=False" in detail


def test_agenteval_reasoning_and_excerpts_case_passes_and_fails_when_a_rule_is_broken(monkeypatch):
    import agenteval

    case = agenteval.case_a_judges_reasoning_is_never_its_verdict_and_excerpts_keep_every_checkable_fact
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    monkeypatch.setattr(llm, "strip_think", lambda t: t)                                                # the reasoning's draft is read as the verdict
    ok, detail = case()
    assert not ok and "reasoning_skipped=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(judges, "parse_compact", lambda ans, thumb: ans)                                # any answer counts as a judge
    ok, detail = case()
    assert not ok and "malformed_refused=False" in detail
    monkeypatch.undo()

    def first_chars(source, narration, cap=sourceslice.CAP, *a, **k):                                 # the naive cut: the first 9,000 characters
        return {"text": source[:cap], "chars": min(len(source), cap), "full_chars": len(source), "terms": 0, "covered": 0, "missing": [], "lossless": True, "cap": cap}

    monkeypatch.setattr(sourceslice, "slice_source", first_chars)
    ok, detail = case()
    assert not ok and "excerpts_ok=False" in detail and "lossy_reported=False" in detail
