import reviewer
import rulesfile

PLAIN = "The merchant carried the ledgers across the old stone bridge at dawn."
TURN = "But that is not the strangest part of the story."


def doc(lines, desc="Did people sleep twice a night? A look at the records."):
    return {"format": "doc", "lines": [{"text": t} for t in lines], "description": desc}


def by_name(checks):
    return {c["name"]: c for c in checks}


def test_a_flat_script_with_no_question_or_turn_warns_about_the_re_hook_gap_and_a_turning_one_does_not():
    flat = by_name(reviewer.generator_checks(doc([PLAIN] * 40), {"duration": 400}))
    assert not flat["rehook_gap"]["ok"] and "proxy" in flat["rehook_gap"]["detail"]
    turning = by_name(reviewer.generator_checks(doc(([PLAIN] * 5 + [TURN]) * 7), {"duration": 400}))
    assert turning["rehook_gap"]["ok"]


def test_a_greeting_or_a_very_long_first_sentence_warns_and_a_cold_open_does_not():
    for opening in ("Welcome back to the channel, today we look at a strange old book.", "In this video we explore the story of the sleeping giant.",
                    "Long ago in a valley far from any road there lived a family who kept bees and goats and told stories about the ridge above them every single night of the year, and nobody who lived there could say when the first of them had settled in that place."):
        assert not by_name(reviewer.generator_checks(doc([opening, PLAIN]), {"duration": 60}))["hook_opening"]["ok"], opening
    assert by_name(reviewer.generator_checks(doc(["No one has read this book in 600 years.", PLAIN]), {"duration": 60}))["hook_opening"]["ok"]


def test_an_outro_in_the_last_lines_warns():
    assert not by_name(reviewer.generator_checks(doc([PLAIN, "Thanks for watching, and don't forget to subscribe."]), {"duration": 60}))["no_outro"]["ok"]
    assert by_name(reviewer.generator_checks(doc([PLAIN, "And the question stays open."]), {"duration": 60}))["no_outro"]["ok"]


def test_a_short_outside_its_length_and_a_description_that_opens_with_sources_warn():
    short = {"format": "short", "lines": [{"text": PLAIN}], "description": "Sources: Wikipedia and a book."}
    c = by_name(reviewer.generator_checks(short, {"duration": 75}))
    assert not c["short_target_length"]["ok"] and not c["description_hook"]["ok"]
    assert by_name(reviewer.generator_checks({**short, "description": "A hook first."}, {"duration": 50}))["short_target_length"]["ok"]


def test_every_one_of_these_rules_is_only_a_warning_so_a_good_video_is_never_failed_for_style():
    bad = doc(["Welcome to the channel!"] + [PLAIN] * 40 + ["Thanks for watching, subscribe."], desc="Sources: x")
    checks = reviewer.generator_checks(bad, {"duration": 400})
    assert len(checks) >= 4 and not all(c["ok"] for c in checks) and {c["severity"] for c in checks} == {"warn"}


def test_the_limits_come_from_the_rules_file(tmp_path):
    r = rulesfile.load()
    r["benchmarks"]["rehook_max_seconds"] = 20
    loose = by_name(reviewer.generator_checks(doc(([PLAIN] * 5 + [TURN]) * 7), {"duration": 400}, r))
    assert not loose["rehook_gap"]["ok"] and "20" in loose["rehook_gap"]["detail"]


# ---- a Short's hook and payoff (29 Oct 2026) ----
HOOK = "No one has ever found the army that vanished."
PAYOFF = "Only the desert knows, and it has never said."
INVITE = "Follow for the next story."


def short(lines):
    return {"format": "short", "lines": [{"text": t} for t in lines], "description": "A hook first."}


def test_a_short_whose_first_line_is_a_question_or_turn_in_few_words_passes_and_a_flat_long_one_warns():
    good = by_name(reviewer.generator_checks(short([HOOK, PLAIN, PAYOFF, INVITE]), {"duration": 50}))["short_hook"]
    assert good["ok"] and good["severity"] == "warn"
    flat = by_name(reviewer.generator_checks(short([PLAIN, PAYOFF, INVITE]), {"duration": 50}))["short_hook"]
    assert not flat["ok"] and "proxy" in flat["detail"]
    long = "No one can say why the whole army walked into the great sand sea that day and never walked back out of it again."
    assert not by_name(reviewer.generator_checks(short([long, PAYOFF, INVITE]), {"duration": 50}))["short_hook"]["ok"]


def test_the_line_before_the_follow_invitation_must_pay_off_not_ask_a_new_question():
    ok = by_name(reviewer.generator_checks(short([HOOK, PLAIN, PAYOFF, INVITE]), {"duration": 50}))["short_payoff"]
    assert ok["ok"]
    hanging = by_name(reviewer.generator_checks(short([HOOK, PLAIN, "But what if it is still out there?", INVITE]), {"duration": 50}))["short_payoff"]
    assert not hanging["ok"]
    no_invite = by_name(reviewer.generator_checks(short([HOOK, PLAIN, "Who gave the order?"]), {"duration": 50}))["short_payoff"]
    assert not no_invite["ok"]  # without an invitation the last line itself is the payoff line


def test_the_short_hook_limit_comes_from_the_rules_file():
    r = rulesfile.load()
    r["benchmarks"]["short_hook_max_words"] = 5
    tight = by_name(reviewer.generator_checks(short([HOOK, PAYOFF, INVITE]), {"duration": 50}, r))["short_hook"]
    assert not tight["ok"] and "5" in tight["detail"]


def test_a_documentary_gets_no_short_checks():
    names = set(by_name(reviewer.generator_checks(doc([PLAIN] * 5), {"duration": 400})))
    assert "short_hook" not in names and "short_payoff" not in names


def test_the_short_prompt_asks_for_a_payoff_before_the_invitation_and_never_for_loops():
    import scriptgen
    prompt = scriptgen.short_prompt("The Lost Army of Cambyses")
    low = prompt.lower()
    assert "payoff" in low and "answers" in low  # the hook's question is answered, or the sources' disagreement is said plainly
    assert low.index("payoff") < low.index("invitation")  # the payoff comes first, the invitation is the last line
    assert "never end on a new question" in low
    assert "loop" not in low  # a hard rule: never ask people to loop videos
    assert "under 12 words" in low
