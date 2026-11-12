import datetime as dt
import json
import smtplib
import stat

import alerts
import pytest

TOKEN = "123456789:" + "A" * 35
PW = "abcdefghijklmnop"
NOW = dt.datetime(2026, 11, 13, 10, 0, tzinfo=dt.timezone.utc)


def test_gmail_is_saved_privately_mirrored_for_the_hub_and_never_reported_back():
    alerts.save_gmail("Me@Gmail.com", "abcd efgh ijkl mnop")
    assert alerts.status()["gmail"] == {"saved": True, "address": "me@gmail.com"}
    assert PW not in json.dumps(alerts.status())
    assert json.loads(alerts.BRIDGE.read_text()) == {"address": "me@gmail.com", "app_password": PW}
    assert stat.S_IMODE(alerts.BRIDGE.stat().st_mode) == 0o600 and stat.S_IMODE(alerts.SETTINGS.stat().st_mode) == 0o600
    alerts.remove_gmail()
    assert alerts.status()["gmail"]["saved"] is False and not alerts.BRIDGE.exists()


@pytest.mark.parametrize("address,pw", [("me@yahoo.com", PW), ("me@gmail.com", "My-normal-Password1!"), ("me@gmail.com", "short"), ("not an email", PW), ("me@gmail.com.evil.com", PW)])
def test_a_bad_address_or_a_password_that_is_not_an_app_password_is_refused_and_nothing_is_saved(address, pw):
    with pytest.raises(ValueError):
        alerts.save_gmail(address, pw)
    assert not alerts.BRIDGE.exists() and alerts.status()["gmail"]["saved"] is False


def test_the_gmail_test_sends_one_message_to_the_owner_and_explains_a_refusal_without_the_password():
    alerts.save_gmail("me@gmail.com", PW)
    sent = []
    assert "me@gmail.com" in alerts.test_gmail(lambda a, p, m: sent.append((a, p, m["To"])))
    assert sent == [("me@gmail.com", PW, "me@gmail.com")]

    def refuse(a, p, m):
        raise smtplib.SMTPAuthenticationError(535, b"bad " + PW.encode())

    with pytest.raises(ValueError) as e:
        alerts.test_gmail(refuse)
    assert PW not in str(e.value) and "refused" in str(e.value)


def tg(replies):
    seen = []

    def fetch(url, payload):
        seen.append((url, payload))
        return replies[url.rsplit("/", 1)[1]]
    return fetch, seen


def test_a_telegram_token_is_checked_with_telegram_before_it_is_kept_and_the_chat_is_found_from_a_message():
    fetch, seen = tg({"getMe": {"ok": True, "result": {"username": "my_bot"}}})
    assert alerts.save_telegram(TOKEN, fetch) == "my_bot" and alerts.status()["telegram"] == {"saved": True, "chat": False, "bot": "my_bot"}
    assert TOKEN not in json.dumps(alerts.status())
    with pytest.raises(ValueError):
        alerts.find_chat(tg({"getUpdates": {"ok": True, "result": []}})[0])
    ups = {"getUpdates": {"ok": True, "result": [{"message": {"chat": {"id": -100, "type": "group"}}}, {"message": {"chat": {"id": 4242, "type": "private"}}}]}}
    alerts.find_chat(tg(ups)[0])
    assert alerts.status()["telegram"]["chat"] is True and alerts._settings()["telegram_chat_id"] == "4242"


def test_a_token_that_telegram_refuses_or_that_has_the_wrong_shape_is_never_saved():
    with pytest.raises(ValueError):
        alerts.save_telegram("not a token")
    with pytest.raises(ValueError):
        alerts.save_telegram(TOKEN, tg({"getMe": {"ok": False}})[0])
    assert alerts.status()["telegram"]["saved"] is False


def test_pushed_events_are_limited_to_notify_and_error_deduped_and_capped():
    alerts._save({"telegram_bot_token": TOKEN, "telegram_chat_id": "1"})
    sent = []
    fetch = lambda url, payload: sent.append(payload["text"]) or {"ok": True}
    assert alerts.push("info", "Daily briefing", "x", False, NOW, fetch) is False
    assert alerts.push("error", "Money low", "$0.40 left", False, NOW, fetch) is True
    assert alerts.push("error", "Money low", "again", False, NOW + dt.timedelta(hours=1), fetch) is False  # same title within 6 hours
    assert alerts.push("error", "Money low", "later", False, NOW + dt.timedelta(hours=7), fetch) is True
    assert alerts.push("info", "A video needs you", "", True, NOW, fetch) is True
    for i in range(30):
        alerts.push("error", f"E{i}", "", False, NOW, fetch)
    assert len(sent) <= alerts.DAILY_CAP and sent[0].startswith("Money low")


def test_without_a_linked_chat_nothing_is_sent_and_nothing_raises():
    fetch = lambda url, payload: pytest.fail("must not call Telegram")
    assert alerts.push("error", "x", "", True, NOW, fetch) is False


def test_errors_never_carry_a_secret():
    alerts._save({"telegram_bot_token": TOKEN})
    assert TOKEN not in alerts.clean(f"failed https://api.telegram.org/bot{TOKEN}/getMe") and "bot***" in alerts.clean(f"https://api.telegram.org/bot{TOKEN}/x")
