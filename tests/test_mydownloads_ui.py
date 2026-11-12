"""My Downloads page in a real Chrome (skipped where Chrome is missing): typing, a stand-in microphone, the list, the download, a hostile title, a phone screen."""
import json
import threading

import pytest

import browserdrive
from mydownloads import jobs, server, store

pytestmark = pytest.mark.skipif(not browserdrive.CHROME, reason="needs Chrome")

CID = "UCYeOLFYx2orIghktFlQrV7A"
EVIL = '<img src=x onerror="window.__pwn=1">Bad title'


def vid(n):
    return "v" + f"{n:010d}"


class FakeEngine:
    def __init__(self):
        self.asked = []

    def _item(self, n, title, kind="long", **kw):
        return dict({"id": vid(n), "title": title, "kind": kind, "url": "u", "duration": 518 if kind == "long" else None, "channel": "The Sleeping Library", "channel_id": CID,
                     "saved": False, "owned": True, "refused": "", "error": "", "partial": False}, **kw)

    def plan(self, it, only_channel=None):
        self.asked.append((it.count, it.kind, only_channel))
        if it.kind == "short":
            return {"items": [self._item(2, "A Short", "short")], "notes": []}
        return {"items": [self._item(1, EVIL), self._item(3, "Saved already", saved=True), self._item(4, "Elsewhere", owned=False, refused="This video is on “Other”, which is not one of your channels, so I will not download it.")],
                "notes": list(it.notes)}

    def resolve_channel(self, text):
        return {"id": CID, "title": "The Sleeping Library", "handle": "@thesleepinglib"}

    def download(self, video_id, folder, on_progress, stop):
        on_progress({"percent": 50.0, "speed": 2e6, "eta": 4, "bytes": 5e5, "stage": "downloading"})
        out = folder / "The Sleeping Library" / f"T [{video_id}].mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x" * 2048)
        return out


FAKE_MIC = """
window.__violations = [];
addEventListener('securitypolicyviolation', e => window.__violations.push(e.violatedDirective + ' ' + e.blockedURI));
class FakeMic {
  start() { setTimeout(() => { this.onstart && this.onstart();
    setTimeout(() => { this.onresult && this.onresult({results: [[{transcript: 'my last 3 shorts'}]]}); this.onend && this.onend(); }, 60); }, 20); }
  stop() { this.onend && this.onend(); }
}
window.SpeechRecognition = FakeMic;        // newer Chrome has the unprefixed name and the page prefers it
window.webkitSpeechRecognition = FakeMic;
"""


@pytest.fixture
def page(tmp_path, monkeypatch):
    monkeypatch.setenv("MYDL_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("MYDL_FOLDER", str(tmp_path / "Downloads"))
    eng = FakeEngine()
    runner = jobs.Runner(eng, threaded=True, sleep=lambda s: None, free_bytes=lambda p: 50 << 30)
    httpd = server.make_server(server.App(eng, runner, open_folder=lambda p: None), port=0)
    threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.02), daemon=True).start()
    b = browserdrive.Browser(1100, 900)
    b.send("Page.enable")  # Chrome runs a before-load script only after Page.enable
    b.send("Page.addScriptToEvaluateOnNewDocument", source=FAKE_MIC)
    url = f"http://127.0.0.1:{httpd.server_port}/"
    b.open(url, wait_for="document.documentElement.getAttribute('data-ready') === '1'")
    yield b, eng, tmp_path, url
    b.close()
    httpd.shutdown()
    httpd.server_close()


def type_into(b, selector, text):
    b.click(f"document.querySelector('{selector}')")
    b.send("Input.insertText", text=text)


def add_my_channel(b):
    type_into(b, "#chaninput", "@thesleepinglib")
    b.click("document.getElementById('chantick')")
    b.click("[...document.querySelectorAll('.addform button')].find(x => x.textContent === 'Add this channel')")
    b.until("document.querySelector('#channels strong')?.textContent === 'The Sleeping Library'")


def test_a_new_page_asks_for_my_channel_first(page):
    b, *_ = page
    assert b.js("document.getElementById('find').disabled") is True
    assert "which channel is yours" in b.js("document.querySelector('.addform strong').textContent")
    b.click("[...document.querySelectorAll('.addform button')].find(x => x.textContent === 'Add this channel')")  # without the tick
    b.until("document.querySelector('.addform .say')?.textContent.includes('Tick the box')")
    assert store.channels() == []
    add_my_channel(b)
    assert b.js("document.getElementById('find').disabled") is False
    assert [c["handle"] for c in store.channels()] == ["@thesleepinglib"]


def test_type_find_pick_and_download(page):
    b, eng, tmp, _ = page
    add_my_channel(b)
    type_into(b, "#ask", "download my last 5 videos")
    b.click("document.getElementById('find')")
    b.until("document.querySelector('#result h2')?.textContent === 'The 5 newest of your videos'")
    rows = b.js("[...document.querySelectorAll('#result .row')].map(r => [r.querySelector('input').checked, r.querySelector('input').disabled])")
    assert rows == [[True, False], [False, False], [False, True]]  # a new one is picked, a saved one is not, someone else's cannot be
    assert "not one of your channels" in b.js("document.querySelectorAll('#result .row')[2].textContent")
    assert b.js("document.getElementById('gotext').textContent") == "Download 1 video"
    b.click("document.getElementById('go')")
    b.until("document.querySelector('#job h2')?.textContent === 'Finished'")
    assert (tmp / "Downloads" / "The Sleeping Library" / f"T [{vid(1)}].mp4").is_file()
    assert "Saved" in b.js("document.querySelector('#job .jrow .meta').textContent")
    assert b.js("document.getElementById('result').hidden") is True


def test_a_video_title_is_shown_as_text_and_never_runs(page):
    b, *_ = page
    add_my_channel(b)
    type_into(b, "#ask", "my last 5 videos")
    b.click("document.getElementById('find')")
    b.until("!!document.querySelector('#result .title')")
    assert b.js("document.querySelector('#result .title').textContent") == EVIL
    assert b.js("document.querySelectorAll('#result img').length") == 0 and b.js("window.__pwn === undefined") is True


def test_speaking_fills_the_box_and_finds(page):
    b, eng, *_ = page
    add_my_channel(b)
    b.click("document.getElementById('mic')")
    b.until("document.querySelector('#result h2')?.textContent === 'The 3 newest of your Shorts'")
    assert b.js("document.getElementById('ask').value") == "my last 3 shorts"
    assert eng.asked[-1][:2] == (3, "short")
    assert b.js("document.getElementById('mic').getAttribute('aria-pressed')") == "false"


def test_a_chip_fills_the_box(page):
    b, *_ = page
    b.click("[...document.querySelectorAll('.chip')].find(x => x.textContent === 'all my videos')")
    assert b.js("document.getElementById('ask').value") == "all my videos"


def test_nothing_typed_is_a_plain_message(page):
    b, *_ = page
    add_my_channel(b)
    b.click("document.getElementById('find')")
    b.until("document.getElementById('heard').getAttribute('data-kind') === 'error'")
    assert "Tell me what to download" in b.js("document.getElementById('heard').textContent")


def test_the_page_has_no_script_errors_and_breaks_no_security_rule(page):
    b, *_ = page
    add_my_channel(b)
    type_into(b, "#ask", "my last 5 videos")
    b.click("document.getElementById('find')")
    b.until("!!document.querySelector('#result .row')")
    assert json.loads(b.errors()) == [] and b.js("window.__violations.length") == 0


def test_a_phone_screen_has_no_sideways_scroll(page):
    b, *_ = page
    add_my_channel(b)
    type_into(b, "#ask", "my last 5 videos")
    b.click("document.getElementById('find')")
    b.until("!!document.querySelector('#result .row')")
    b.size(360, 740, mobile=True)
    assert b.js("document.documentElement.scrollWidth <= window.innerWidth") is True
    small = b.js("[...document.querySelectorAll('button, input[type=checkbox], select')].filter(e => e.offsetParent && Math.min(e.getBoundingClientRect().width, e.getBoundingClientRect().height) < 22).length")
    assert small == 0


def test_without_speech_support_the_microphone_is_hidden(tmp_path, monkeypatch):
    monkeypatch.setenv("MYDL_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("MYDL_FOLDER", str(tmp_path / "Downloads"))
    eng = FakeEngine()
    httpd = server.make_server(server.App(eng, jobs.Runner(eng, threaded=False, free_bytes=lambda p: 50 << 30), open_folder=lambda p: None), port=0)
    threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.02), daemon=True).start()
    b = browserdrive.Browser(1100, 900)
    try:
        b.send("Page.enable")
        b.send("Page.addScriptToEvaluateOnNewDocument", source="delete window.SpeechRecognition; delete window.webkitSpeechRecognition;")
        b.open(f"http://127.0.0.1:{httpd.server_port}/", wait_for="document.documentElement.getAttribute('data-ready') === '1'")
        assert b.js("document.getElementById('mic').hidden") is True and "Typing works" in b.js("document.getElementById('micnote').textContent")
    finally:
        b.close()
        httpd.shutdown()
        httpd.server_close()
