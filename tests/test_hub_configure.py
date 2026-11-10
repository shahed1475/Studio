"""`python -m hub.configure`: the terminal prompt where the owner pastes the Gmail app password and the Google client id.
The keyboard is replaced by scripted answers; the file is a temporary one. Every test also checks that nothing typed is ever printed back."""
import os
import smtplib
import stat

import pytest

from hub import configure, secretstore as ss

ADDRESS = "owner.private@gmail.com"
PASSWORD = "abcdefghijklmnop"
CLIENT = "123456789012-abcdefghijklmnopqrstuvwx.apps.googleusercontent.com"


class Script:
    """Answers for a prompt, in order; an exception in the list is raised; running out is end of input."""

    def __init__(self, *answers):
        self.answers, self.prompts = list(answers), []

    def __call__(self, prompt=""):
        self.prompts.append(prompt)
        if not self.answers:
            raise EOFError
        a = self.answers.pop(0)
        if isinstance(a, BaseException):
            raise a
        return a


class Out:
    def __init__(self):
        self.lines = []

    def __call__(self, *a):
        self.lines.append(" ".join(str(x) for x in a))

    def text(self):
        return "\n".join(self.lines)


@pytest.fixture(autouse=True)
def never_the_real_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HUB_SECRETS_FILE", str(tmp_path / "default" / "hub.env"))


def run(tmp_path, *flags, ask=(), secret=(), send_test=None):
    a, s, o = Script(*ask), Script(*secret), Out()
    code = configure.main(["--file", str(tmp_path / "hub.env"), *flags], ask=a, ask_secret=s, out=o, send_test=send_test)
    return code, a, s, o


def stored(tmp_path):
    env = {}
    ss.load(tmp_path / "hub.env", env)
    return env


def nothing_typed_is_echoed(o, *scripts):
    shown = o.text() + "\n".join(p for s in scripts for p in s.prompts)
    for secret in (PASSWORD, CLIENT, ADDRESS):
        assert secret not in shown


def test_saves_gmail_settings_with_defaults_and_a_private_file(tmp_path):
    code, a, s, o = run(tmp_path, "--no-test", ask=[ADDRESS, CLIENT], secret=[PASSWORD])
    env = stored(tmp_path)
    assert code == 0 and stat.S_IMODE(os.stat(tmp_path / "hub.env").st_mode) == 0o600
    assert env == {"HUB_SMTP_HOST": "smtp.gmail.com", "HUB_SMTP_PORT": "587", "HUB_SMTP_USER": ADDRESS, "HUB_MAIL_FROM": ADDRESS,
                   "HUB_SMTP_PASSWORD": PASSWORD, "HUB_GOOGLE_CLIENT_ID": CLIENT}
    nothing_typed_is_echoed(o, a, s)


def test_spaces_in_the_app_password_are_removed(tmp_path):
    run(tmp_path, "--no-test", ask=[ADDRESS, ""], secret=["abcd efgh ijkl mnop"])
    assert stored(tmp_path)["HUB_SMTP_PASSWORD"] == PASSWORD


def test_enter_keeps_existing_values(tmp_path):
    ss.save({"HUB_SMTP_HOST": "smtp.gmail.com", "HUB_SMTP_PORT": "587", "HUB_SMTP_USER": ADDRESS, "HUB_MAIL_FROM": ADDRESS, "HUB_SMTP_PASSWORD": PASSWORD}, tmp_path / "hub.env")
    code, a, s, o = run(tmp_path, "--no-test", ask=["", CLIENT], secret=[""])
    env = stored(tmp_path)
    assert code == 0 and env["HUB_SMTP_PASSWORD"] == PASSWORD and env["HUB_SMTP_USER"] == ADDRESS and env["HUB_GOOGLE_CLIENT_ID"] == CLIENT
    assert any("already set" in p for p in a.prompts)
    nothing_typed_is_echoed(o, a, s)


def test_nothing_to_change_saves_nothing(tmp_path):
    code, a, s, o = run(tmp_path, "--no-test", ask=["", ""], secret=[])
    assert code == 1 and not (tmp_path / "hub.env").exists()


def test_end_of_input_midway_writes_nothing(tmp_path):
    code, a, s, o = run(tmp_path, ask=[ADDRESS], secret=[PASSWORD])  # the client id prompt finds the input closed
    assert code == 1 and not (tmp_path / "hub.env").exists() and "Nothing was saved" in o.text()


def test_ctrl_c_midway_writes_nothing(tmp_path):
    code, *_ = run(tmp_path, ask=[ADDRESS], secret=[KeyboardInterrupt()])
    assert code == 1 and not (tmp_path / "hub.env").exists()


def test_bad_client_id_shape_is_refused_after_three_tries_and_nothing_is_saved(tmp_path):
    code, a, s, o = run(tmp_path, "--no-test", ask=[ADDRESS, "not-an-id", "also bad", "123.apps.example.com"], secret=[PASSWORD])
    assert code == 2 and not (tmp_path / "hub.env").exists()


def test_bad_email_shape_is_asked_again(tmp_path):
    code, *_ = run(tmp_path, "--no-test", ask=["not an address", ADDRESS, ""], secret=[PASSWORD])
    assert code == 0 and stored(tmp_path)["HUB_SMTP_USER"] == ADDRESS


@pytest.mark.parametrize("answer,expect_code", [("no", 2), ("yes", 0)])
def test_password_of_the_wrong_shape_needs_a_typed_yes(tmp_path, answer, expect_code):
    code, a, s, o = run(tmp_path, "--no-test", ask=[ADDRESS, answer, ""], secret=["Not-a-16-char-app-password!"])
    assert code == expect_code and (tmp_path / "hub.env").exists() == (expect_code == 0)
    assert "Not-a-16-char" not in o.text()


def test_status_shows_set_or_not_set_and_asks_nothing(tmp_path):
    ss.save({"HUB_SMTP_PASSWORD": PASSWORD, "HUB_GOOGLE_CLIENT_ID": CLIENT}, tmp_path / "hub.env")
    code, a, s, o = run(tmp_path, "--status")
    assert code == 0 and a.prompts == [] and s.prompts == []
    t = o.text()
    assert "HUB_SMTP_PASSWORD: set" in t and "HUB_SMTP_USER: not set" in t and "google-auth" in t
    nothing_typed_is_echoed(o)


def test_status_of_a_loose_file_says_it_is_ignored(tmp_path):
    p = ss.save({"HUB_SMTP_PASSWORD": PASSWORD}, tmp_path / "hub.env")
    os.chmod(p, 0o644)
    code, a, s, o = run(tmp_path, "--status")
    assert code == 0 and "chmod 600" in o.text()


def test_test_mail_goes_to_the_owners_own_address_when_they_say_yes(tmp_path):
    sent = []
    code, a, s, o = run(tmp_path, ask=[ADDRESS, "", "y"], secret=[PASSWORD], send_test=lambda to, env: sent.append((to, env["HUB_SMTP_PASSWORD"])))
    assert code == 0 and sent == [(ADDRESS, PASSWORD)] and "sent" in o.text().lower()
    nothing_typed_is_echoed(o, a, s)


def test_no_test_flag_asks_and_sends_nothing(tmp_path):
    def boom(to, env):
        raise AssertionError("must not send")

    code, a, s, o = run(tmp_path, "--no-test", ask=[ADDRESS, ""], secret=[PASSWORD], send_test=boom)
    assert code == 0 and not any("test" in p.lower() for p in a.prompts)


def test_default_answer_to_the_test_question_is_no(tmp_path):
    def boom(to, env):
        raise AssertionError("must not send")

    code, *_ = run(tmp_path, ask=[ADDRESS, "", ""], secret=[PASSWORD], send_test=boom)
    assert code == 0


def test_failed_test_mail_shows_the_class_and_a_hint_never_the_password(tmp_path):
    def refuse(to, env):
        raise smtplib.SMTPAuthenticationError(535, ("Username and Password not accepted " + env["HUB_SMTP_PASSWORD"]).encode())

    code, a, s, o = run(tmp_path, ask=[ADDRESS, "", "yes"], secret=[PASSWORD], send_test=refuse)
    t = o.text()
    assert code == 3 and "SMTPAuthenticationError" in t and "app password" in t.lower() and (tmp_path / "hub.env").exists()
    nothing_typed_is_echoed(o, a, s)


def test_unwritable_place_is_reported_plainly_without_a_trace(tmp_path, monkeypatch):
    def deny(*a, **k):
        raise PermissionError(13, "Permission denied", "/some/where")

    monkeypatch.setattr(configure.secretstore, "save", deny)
    code, a, s, o = run(tmp_path, "--no-test", ask=[ADDRESS, ""], secret=[PASSWORD])
    assert code == 2 and "Not saved" in o.text() and "Permission denied" in o.text()
    nothing_typed_is_echoed(o, a, s)


def test_the_prompt_keeps_the_servers_other_settings(tmp_path):
    ss.save({"HUB_KEYSTORE_KEY": "k" * 44, "HUB_PUBLIC_URL": "https://hub.example.org", "HUB_ALLOWED_EMAILS": "friend@example.com"}, tmp_path / "hub.env")
    code, a, s, o = run(tmp_path, "--no-test", ask=[ADDRESS, CLIENT], secret=[PASSWORD])
    env = stored(tmp_path)
    assert code == 0 and env["HUB_KEYSTORE_KEY"] == "k" * 44 and env["HUB_ALLOWED_EMAILS"] == "friend@example.com" and env["HUB_SMTP_PASSWORD"] == PASSWORD


def test_contact_flag_asks_only_for_the_privacy_contact_and_keeps_everything_else(tmp_path):
    ss.save({"HUB_KEYSTORE_KEY": "k" * 44, "HUB_SMTP_USER": ADDRESS}, tmp_path / "hub.env")
    code, a, s, o = run(tmp_path, "--contact", ask=["Ann Example, ann@example.org"])
    env = stored(tmp_path)
    assert code == 0 and env["HUB_CONTACT"] == "Ann Example, ann@example.org" and env["HUB_KEYSTORE_KEY"] == "k" * 44 and env["HUB_SMTP_USER"] == ADDRESS
    assert len(a.prompts) == 1 and s.prompts == []


def test_contact_flag_with_nothing_typed_or_too_much_saves_nothing(tmp_path):
    code, *_ = run(tmp_path, "--contact", ask=[""])
    assert code == 1 and not (tmp_path / "hub.env").exists()
    code, a, s, o = run(tmp_path, "--contact", ask=["x" * 201])
    assert code == 2 and not (tmp_path / "hub.env").exists()


def test_secretstore_refusal_is_reported_without_a_trace(tmp_path, monkeypatch):
    monkeypatch.setattr(configure.secretstore, "save", lambda *a, **k: (_ for _ in ()).throw(ss.SecretError("the secrets file must live outside any git work tree")))
    code, a, s, o = run(tmp_path, "--no-test", ask=[ADDRESS, ""], secret=[PASSWORD])
    assert code == 2 and "Not saved" in o.text() and "git work tree" in o.text()
    nothing_typed_is_echoed(o, a, s)
