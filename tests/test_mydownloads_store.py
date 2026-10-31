"""My Downloads: where things live, the list of the owner's channels, the saved queue and the log."""
import json

import pytest

from mydownloads import store

CID = "UCYeOLFYx2orIghktFlQrV7A"


@pytest.fixture(autouse=True)
def private_home(tmp_path, monkeypatch):
    """No test may read or write the owner's real settings or Desktop."""
    monkeypatch.setenv("MYDL_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("MYDL_FOLDER", str(tmp_path / "Desktop" / "My YouTube Downloads"))
    return tmp_path


def test_home_and_folder_follow_the_environment(private_home):
    assert store.home() == private_home / "cfg"
    assert store.folder() == private_home / "Desktop" / "My YouTube Downloads"


def test_default_folder_is_on_the_desktop(tmp_path, monkeypatch):
    monkeypatch.delenv("MYDL_FOLDER")
    monkeypatch.delenv("MYDL_HOME")
    xdg = tmp_path / "xdg"
    xdg.mkdir()
    (xdg / "user-dirs.dirs").write_text('XDG_DESKTOP_DIR="$HOME/Schreibtisch"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    monkeypatch.setenv("HOME", str(tmp_path / "me"))
    assert store.desktop() == tmp_path / "me" / "Schreibtisch"
    assert store.folder() == tmp_path / "me" / "Schreibtisch" / "My YouTube Downloads"
    assert store.home() == xdg / "studio-mydownloads"


def test_desktop_falls_back_to_a_desktop_folder_then_to_home(tmp_path, monkeypatch):
    monkeypatch.delenv("MYDL_FOLDER")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "none"))
    monkeypatch.setenv("HOME", str(tmp_path / "me"))
    (tmp_path / "me").mkdir()
    assert store.desktop() == tmp_path / "me"
    (tmp_path / "me" / "Desktop").mkdir()
    assert store.desktop() == tmp_path / "me" / "Desktop"


def test_no_channels_until_one_is_added():
    assert store.channels() == [] and store.channel_ids() == set()


def test_add_channel_is_saved_and_repeatable():
    c = store.add_channel(CID, "The Sleeping Library", "@thesleepinglib", "studio upload record")
    assert c["id"] == CID and c["how"] == "studio upload record" and c["added"]
    store.add_channel(CID, "The Sleeping Library", "@thesleepinglib", "typed again")
    assert [x["id"] for x in store.channels()] == [CID]  # one entry, not two
    assert store.channels()[0]["how"] == "studio upload record"  # the first statement stays
    assert store.channel_ids() == {CID}
    assert json.loads((store.home() / "channels.json").read_text())[0]["handle"] == "@thesleepinglib"


@pytest.mark.parametrize("bad", ["", "abc", "UC123", "XX" + "a" * 22, CID + "x", "../../etc/passwd"])
def test_a_bad_channel_id_is_refused(bad):
    with pytest.raises(ValueError):
        store.add_channel(bad, "x", "", "test")
    assert store.channels() == []


def test_remove_channel():
    store.add_channel(CID, "T", "@t", "test")
    assert store.remove_channel(CID) is True
    assert store.channel_ids() == set()
    assert store.remove_channel(CID) is False


def test_a_damaged_channel_file_means_no_channels_not_a_crash():
    store.home().mkdir(parents=True)
    (store.home() / "channels.json").write_text("{not json")
    assert store.channels() == []


def test_job_file_round_trip_leaves_no_temporary_file():
    assert store.load_job() is None
    store.save_job({"id": "j1", "items": [{"id": "a", "status": "queued"}]})
    assert store.load_job()["items"][0]["status"] == "queued"
    assert [p.name for p in store.home().iterdir() if p.name.endswith(".tmp")] == []


def test_a_damaged_job_file_is_ignored():
    store.home().mkdir(parents=True)
    (store.home() / "job.json").write_text("{oops")
    assert store.load_job() is None


def test_audit_log_appends_one_json_line_per_event():
    store.audit({"id": "a", "status": "done"})
    store.audit({"id": "b", "status": "refused"})
    lines = (store.home() / "downloads.log").read_text().splitlines()
    assert [json.loads(l)["id"] for l in lines] == ["a", "b"]
    assert "at" in json.loads(lines[0])


def test_saved_path_finds_a_finished_video_by_its_id(private_home):
    d = store.folder() / "The Sleeping Library"
    d.mkdir(parents=True)
    (d / "A title [w5crV5QVfvo].mp4").write_bytes(b"x")
    (d / "Half [-abc_DEF123].mp4.part").write_bytes(b"x")
    (d / "Meta [zzzzzzzzzzz].info.json").write_text("{}")
    assert store.saved_path("w5crV5QVfvo") == d / "A title [w5crV5QVfvo].mp4"
    assert store.saved_path("-abc_DEF123") is None  # a half-finished file is not a saved video
    assert store.saved_path("zzzzzzzzzzz") is None
    assert store.saved_path("nope") is None
    assert store.saved_path("") is None


def test_saved_path_with_no_folder_yet():
    assert store.saved_path("w5crV5QVfvo") is None
