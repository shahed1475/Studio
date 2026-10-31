"""My Downloads: listing the owner's videos, the own-channel rule, and downloading. A fake yt-dlp stands in for YouTube: no network, no real files outside tmp."""
import re
import threading
from pathlib import Path

import pytest

from mydownloads import engine, intent, store

MINE = "UCYeOLFYx2orIghktFlQrV7A"
OTHER = "UCaaaaaaaaaaaaaaaaaaaaaa"
UPLOADS = f"https://www.youtube.com/playlist?list=UU{MINE[2:]}"
SHORTS = f"https://www.youtube.com/channel/{MINE}/shorts"


def vid(n):
    return "v" + f"{n:010d}"  # an 11-character video id, like YouTube's


class World:
    """What 'YouTube' knows: pages (playlist listings), infos (full video records) and what was asked of it."""

    def __init__(self):
        self.pages, self.infos, self.asked, self.downloaded, self.fail = {}, {}, [], [], {}
        self.streams = []  # (file name, bytes): fetched one after the other, as yt-dlp does for the picture and then the sound

    def cls(self):
        world = self

        class Y:
            def __init__(self, opts):
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def extract_info(self, url, download=False):
                world.asked.append((url, dict(self.opts)))
                m = re.search(r"watch\?v=([\w-]{11})", url)
                if m:
                    v = world.infos[m.group(1)]
                    if isinstance(v, Exception):
                        raise v
                    return dict(v)
                p = world.pages[url]
                if isinstance(p, Exception):
                    raise p
                p = dict(p)
                p["entries"] = list(p.get("entries", []))[: self.opts.get("playlistend") or None]
                return p

            def process_ie_result(self, info, download=True):
                assert download
                if info["id"] in world.fail:
                    raise world.fail[info["id"]]
                out = Path(self.opts["paths"]["home"]) / info["channel"] / f"{info['title']} [{info['id']}].mp4"
                def emit(event):
                    for h in self.opts["progress_hooks"]:
                        h(event)

                if world.streams:
                    for name, total in world.streams:
                        for frac in (0.25, 0.5, 1.0):
                            emit({"status": "downloading", "filename": name, "downloaded_bytes": int(total * frac), "total_bytes": total, "speed": 500.0, "eta": 3})
                        emit({"status": "finished", "filename": name, "downloaded_bytes": total, "total_bytes": total})
                else:
                    for pct in (10, 50, 100):
                        emit({"status": "downloading", "downloaded_bytes": pct * 10, "total_bytes": 1000, "speed": 500.0, "eta": 3})
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"video-bytes")
                world.downloaded.append(info["id"])
                return dict(info, requested_downloads=[{"filepath": str(out)}])

        return Y


def entry(n, title, duration=300, short=False):
    i = vid(n)
    return {"id": i, "title": title, "duration": None if short else duration, "url": f"https://www.youtube.com/{'shorts/' if short else 'watch?v='}{i}"}


def info_for(n, title, channel_id=MINE, channel="The Sleeping Library"):
    return {"id": vid(n), "title": title, "channel_id": channel_id, "channel": channel, "duration": 300, "uploader_id": "@thesleepinglib"}


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("MYDL_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("MYDL_FOLDER", str(tmp_path / "Downloads"))
    store.add_channel(MINE, "The Sleeping Library", "@thesleepinglib", "test")
    w = World()
    # newest first, as YouTube's uploads list is: 1 and 3 and 5 are long films, 2 and 4 and 6 are Shorts
    names = {1: "Lost Army of Cambyses", 2: "Cambyses Short", 3: "La Llorona Origins", 4: "Mami Wata Comb", 5: "Bell Witch Haunting", 6: "Thunderbird Spirit"}
    ups = [entry(n, names[n], short=n % 2 == 0) for n in range(1, 7)]
    w.pages[UPLOADS] = {"channel_id": MINE, "entries": ups}
    w.pages[SHORTS] = {"channel_id": MINE, "entries": [e for e in ups if e["duration"] is None]}
    for n, t in names.items():
        w.infos[vid(n)] = info_for(n, t)
    return w


def eng(world):
    return engine.Engine(ydl_cls=world.cls(), sleep=lambda s: None)


def ids(plan):
    return [i["id"] for i in plan["items"]]


# ---- finding videos
def test_last_three_videos_come_newest_first_from_the_uploads_list(world):
    plan = eng(world).plan(intent.parse("download my last 3 videos"))
    assert ids(plan) == [vid(1), vid(2), vid(3)]
    assert [i["kind"] for i in plan["items"]] == ["long", "short", "long"]
    assert plan["items"][0]["url"].endswith("watch?v=" + vid(1)) and plan["items"][1]["url"].endswith("shorts/" + vid(2))
    assert all(i["owned"] and i["channel"] == "The Sleeping Library" for i in plan["items"])


def test_a_plain_newest_request_asks_youtube_for_no_more_than_it_needs(world):
    eng(world).plan(intent.parse("download my last 3 videos"))
    limits = [o.get("playlistend") for url, o in world.asked if url == UPLOADS]
    assert limits and limits[0] is not None and limits[0] <= 3


def test_shorts_only_uses_the_shorts_list(world):
    plan = eng(world).plan(intent.parse("get my last 2 shorts"))
    assert ids(plan) == [vid(2), vid(4)] and all(i["kind"] == "short" for i in plan["items"])
    assert UPLOADS not in [u for u, _ in world.asked]


def test_long_only_leaves_the_shorts_out(world):
    plan = eng(world).plan(intent.parse("download 5 documentaries"))
    assert ids(plan) == [vid(1), vid(3), vid(5)]


def test_oldest_first_reverses_the_whole_list(world):
    plan = eng(world).plan(intent.parse("download my oldest 2 videos"))
    assert ids(plan) == [vid(6), vid(5)]


def test_all_returns_everything(world):
    assert len(eng(world).plan(intent.parse("download all my videos"))["items"]) == 6


def test_topic_words_must_all_be_in_the_title(world):
    plan = eng(world).plan(intent.parse("download videos about cambyses"))
    assert ids(plan) == [vid(1), vid(2)] and not any(i["partial"] for i in plan["items"])
    plan = eng(world).plan(intent.parse("download videos about bell witch"))
    assert ids(plan) == [vid(5)]


def test_when_no_title_has_every_word_the_partial_matches_are_listed_and_marked(world):
    plan = eng(world).plan(intent.parse("download videos about witch cambyses"))
    assert set(ids(plan)) == {vid(1), vid(2), vid(5)} and all(i["partial"] for i in plan["items"])
    assert any("only some" in n for n in plan["notes"])


def test_nothing_matching_says_so(world):
    plan = eng(world).plan(intent.parse("download videos about thermodynamics"))
    assert plan["items"] == [] and any("thermodynamics" in n for n in plan["notes"])


def test_already_saved_videos_are_marked(world, tmp_path):
    d = tmp_path / "Downloads" / "The Sleeping Library"
    d.mkdir(parents=True)
    (d / f"Lost Army of Cambyses [{vid(1)}].mp4").write_bytes(b"x")
    plan = eng(world).plan(intent.parse("download my last 2 videos"))
    assert [(i["id"], i["saved"]) for i in plan["items"]] == [(vid(1), True), (vid(2), False)]


def test_without_a_registered_channel_nothing_is_listed(world):
    store.remove_channel(MINE)
    plan = eng(world).plan(intent.parse("download my last 3 videos"))
    assert plan["items"] == [] and any("channel" in n for n in plan["notes"])
    assert world.asked == []  # and YouTube was not asked anything


def test_a_failing_listing_is_a_readable_note_not_a_crash(world):
    world.pages[UPLOADS] = Exception("ERROR: Unable to download webpage: getaddrinfo failed")
    plan = eng(world).plan(intent.parse("download my last 3 videos"))
    assert plan["items"] == [] and any("internet" in n for n in plan["notes"])


# ---- links
def test_my_own_video_link_is_accepted(world):
    plan = eng(world).plan(intent.parse(f"download https://youtu.be/{vid(3)}"))
    assert ids(plan) == [vid(3)] and plan["items"][0]["owned"] and not plan["items"][0]["refused"]


def test_someone_elses_video_link_is_refused_with_the_reason(world):
    world.infos[vid(9)] = info_for(9, "A stranger's lecture", channel_id=OTHER, channel="Other Channel")
    plan = eng(world).plan(intent.parse(f"download https://www.youtube.com/watch?v={vid(9)}"))
    it = plan["items"][0]
    assert not it["owned"] and "not one of your channels" in it["refused"] and it["channel"] == "Other Channel"


def test_a_private_video_link_is_listed_with_the_studio_hint(world):
    world.infos[vid(8)] = Exception("ERROR: [youtube] x: Private video. If the owner of this video has granted you access, please sign in.")
    plan = eng(world).plan(intent.parse(f"download https://youtu.be/{vid(8)}"))
    it = plan["items"][0]
    assert not it["owned"] and "YouTube Studio" in it["error"]


def test_playlist_and_other_links_are_noted_not_followed(world):
    plan = eng(world).plan(intent.parse("download https://www.youtube.com/playlist?list=PLabc"))
    assert plan["items"] == [] and any("playlist" in n.lower() for n in plan["notes"])


def test_my_channel_link_lists_that_channel(world):
    plan = eng(world).plan(intent.parse(f"download 2 videos from https://www.youtube.com/channel/{MINE}"))
    assert ids(plan) == [vid(1), vid(2)]


def test_another_channel_link_is_refused(world):
    plan = eng(world).plan(intent.parse(f"download https://www.youtube.com/channel/{OTHER}"))
    assert plan["items"] == [] and any("not one of your channels" in n for n in plan["notes"])


# ---- adding a channel
def test_resolve_channel_from_a_handle(world):
    world.pages["https://www.youtube.com/@thesleepinglib/videos"] = {"channel_id": MINE, "channel": "The Sleeping Library", "uploader_id": "@thesleepinglib", "entries": []}
    assert eng(world).resolve_channel("@thesleepinglib") == {"id": MINE, "title": "The Sleeping Library", "handle": "@thesleepinglib"}


def test_resolve_channel_refuses_a_video_link(world):
    with pytest.raises(ValueError, match="channel"):
        eng(world).resolve_channel("https://www.youtube.com/watch?v=" + vid(1))


def test_resolve_channel_refuses_a_page_that_is_not_a_channel(world):
    world.pages["https://www.youtube.com/@nobody/videos"] = {"entries": []}
    with pytest.raises(ValueError, match="channel"):
        eng(world).resolve_channel("@nobody")


# ---- downloading
def test_download_saves_under_channel_and_title_and_reports_progress(world, tmp_path):
    seen = []
    path = eng(world).download(vid(1), tmp_path / "Downloads", seen.append, threading.Event())
    assert path == tmp_path / "Downloads" / "The Sleeping Library" / f"Lost Army of Cambyses [{vid(1)}].mp4"
    assert path.read_bytes() == b"video-bytes"
    assert [round(s["percent"]) for s in seen] == [10, 50, 99] and seen[0]["speed"] == 500.0  # never 100 while downloading: the job says 100 when the file is saved


def test_progress_never_goes_backwards_when_picture_and_sound_arrive_separately(world, tmp_path):
    """The first live run showed 88% then 3% again: the picture and the sound are two downloads, each with its own percentage."""
    world.infos[vid(1)]["requested_formats"] = [{"filesize": 900}, {"filesize": 100}]
    world.streams = [("v.f137.mp4", 900), ("v.f140.m4a", 100)]
    seen = []
    eng(world).download(vid(1), tmp_path / "Downloads", seen.append, threading.Event())
    pcts = [s["percent"] for s in seen]
    assert pcts == sorted(pcts), pcts
    assert round(pcts[2]) == 90  # the picture is 90% of the bytes and is done
    assert [s["stage"] for s in seen][:-1] == ["downloading"] * (len(seen) - 1) and seen[-1]["stage"] == "joining" and pcts[-1] == 99.0


def test_progress_still_never_goes_backwards_when_the_sizes_are_unknown(world, tmp_path):
    world.infos[vid(1)]["requested_formats"] = [{}, {}]
    world.streams = [("v.f137.mp4", 900), ("v.f140.m4a", 100)]
    seen = []
    eng(world).download(vid(1), tmp_path / "Downloads", seen.append, threading.Event())
    pcts = [s["percent"] for s in seen]
    assert pcts == sorted(pcts), pcts
    assert round(pcts[2]) == 50 and seen[-1]["stage"] == "joining"  # two equal halves when nothing is known about their size


def test_download_refuses_a_video_that_is_not_on_my_channels_even_if_the_id_was_planned(world, tmp_path):
    world.infos[vid(1)] = info_for(1, "Changed hands", channel_id=OTHER, channel="Other Channel")
    with pytest.raises(engine.NotMine):
        eng(world).download(vid(1), tmp_path / "Downloads", lambda s: None, threading.Event())
    assert world.downloaded == [] and not (tmp_path / "Downloads").exists()


def test_download_refuses_when_no_channel_is_registered(world, tmp_path):
    store.remove_channel(MINE)
    with pytest.raises(engine.NotMine, match="No channel of yours"):
        eng(world).download(vid(1), tmp_path / "Downloads", lambda s: None, threading.Event())
    assert world.asked == []  # YouTube was not even asked


def test_download_rejects_an_id_that_is_not_a_video_id(world, tmp_path):
    with pytest.raises(ValueError):
        eng(world).download("../../etc/passwd", tmp_path / "Downloads", lambda s: None, threading.Event())


def test_stop_ends_the_download_without_a_saved_file(world, tmp_path):
    stop = threading.Event()
    stop.set()
    with pytest.raises(engine.Cancelled):
        eng(world).download(vid(1), tmp_path / "Downloads", lambda s: None, stop)
    assert world.downloaded == []


def test_the_format_prefers_h264_so_the_file_plays_on_old_phones_and_players(world, tmp_path):
    """The first real download came down as AV1, which many older devices cannot play. H.264 is offered at the same size; other formats stay as fallbacks."""
    eng(world).download(vid(1), tmp_path / "Downloads", lambda s: None, threading.Event())
    assert engine.FORMAT.startswith("bv*[vcodec^=avc1]+ba[ext=m4a]")
    assert engine.FORMAT.endswith("/bv*+ba/b")  # and when no H.264 exists the best available is still taken


def test_download_options_are_the_safe_ones(world, tmp_path):
    eng(world).download(vid(1), tmp_path / "Downloads", lambda s: None, threading.Event())
    opts = [o for u, o in world.asked if "watch?v=" in u][0]
    assert opts["noplaylist"] is True and opts.get("cookiesfrombrowser") is None and "cookiefile" not in opts


# ---- plain-words errors
@pytest.mark.parametrize("raw,needle", [
    ("ERROR: [youtube] x: Private video. If the owner of this video has granted you access, please sign in.", "YouTube Studio"),
    ("ERROR: [youtube] x: Sign in to confirm you're not a bot. Use --cookies-from-browser", "VPN"),
    ("ERROR: Unable to download webpage: <urlopen error [Errno -3] Temporary failure in name resolution>", "internet"),
    ("OSError: [Errno 28] No space left on device", "disk space"),
    ("ERROR: ffmpeg not found. Please install or provide the path using --ffmpeg-location", "ffmpeg"),
    ("ERROR: unable to download video data: HTTP Error 403: Forbidden", "update"),
    ("ERROR: [youtube] x: Video unavailable", "unavailable"),
])
def test_friendly_errors(raw, needle):
    assert needle.lower() in engine.friendly(Exception(raw)).lower()


def test_unknown_errors_are_shortened_and_cleaned():
    msg = engine.friendly(Exception("ERROR: \x1b[0;31mSomething odd\x1b[0m " + "x" * 500))
    assert "\x1b" not in msg and not msg.startswith("ERROR") and len(msg) <= 220
