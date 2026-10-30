"""The owner (30 Oct 2026): titles should be questions. Autopilot's scorer had no preference, so its Short came out as "The Lost Army of Cambyses: Record, Legend and Dispute". A real question (it opens
with a question word or auxiliary and ends in a question mark) gets a modest bonus; the search phrase still has to be near the front and a vague question is still penalised. No study of ours or of
the sources read on 30 Oct shows that question titles get more views: this is the owner's choice, and the studio's Test & Compare (owner's tool) is where it can be measured."""
import packaging

CORE = "lost army of cambyses"


def test_a_real_question_beats_a_statement_of_the_same_packaging():
    q = packaging.title_score("Lost Army of Cambyses: Where Did 50,000 Men Go?", CORE)
    s = packaging.title_score("Lost Army of Cambyses: Record, Legend and Dispute", CORE)
    assert q > s


def test_the_bonus_is_modest_a_question_without_the_phrase_does_not_beat_a_phrase_first_statement():
    q = packaging.title_score("Where Did All Those Soldiers Go?", CORE)
    s = packaging.title_score("Lost Army of Cambyses: Record, Legend and Dispute", CORE)
    assert s > q


def test_a_vague_question_is_still_penalised_and_a_question_mark_alone_is_not_a_question():
    assert packaging.title_score("What do historians actually think about the lost army of cambyses?", CORE) < packaging.title_score("Lost Army of Cambyses: Where Did 50,000 Men Go?", CORE)
    assert packaging.title_score("Lost Army of Cambyses Found?", CORE) <= packaging.title_score("Lost Army of Cambyses: Where Did 50,000 Men Go?", CORE)


def test_ranking_puts_the_question_first_among_otherwise_equal_titles():
    got = packaging.rank_titles(["Lost Army of Cambyses: Record, Legend and Dispute", "Lost Army of Cambyses: Where Did 50,000 Men Go?"], CORE)
    assert got[0].endswith("Go?")


def test_the_title_prompt_asks_for_at_least_three_questions():
    import inspect

    import seo

    assert "at least three of the five a real question" in inspect.getsource(seo._make)
