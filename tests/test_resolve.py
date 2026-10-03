"""How a URL turns into a Plan: playlists are opt-in, one song is the default."""

import pytest

from ytspot import downloader

SINGLES = "YouTube Imports"
RADIO = "https://www.youtube.com/watch?v=vid2&list=RDvid2&start_radio=1"
PLAYLIST_ONLY = "https://www.youtube.com/playlist?list=PLabc"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=abc123", "abc123"),
        ("https://www.youtube.com/watch?v=abc123&list=RDabc123&start_radio=1", "abc123"),
        ("https://music.youtube.com/watch?v=abc123&list=PLxyz", "abc123"),
        ("https://youtu.be/abc123", "abc123"),
        ("https://www.youtube.com/shorts/abc123", "abc123"),
        ("https://www.youtube.com/playlist?list=PLxyz", None),
        ("https://example.com/watch?v=abc123", None),
        ("not a url at all", None),
    ],
)
def test_video_id_from_url(url, expected):
    assert downloader.video_id_from_url(url) == expected


@pytest.fixture
def fake_ydl(monkeypatch):
    """Stands in for yt-dlp: honours noplaylist, otherwise returns 3 entries."""

    class FakeYoutubeDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download=False):
            if self.opts.get("noplaylist"):
                return {
                    "_type": "video",
                    "id": downloader.video_id_from_url(url),
                    "title": "Second Song",
                    "webpage_url": url,
                    "extractor_key": "Youtube",
                }
            return {
                "_type": "playlist",
                "title": "Some Mix",
                "entries": [
                    {"id": f"vid{n}", "title": f"Artist {n} - Song {n}", "ie_key": "Youtube"}
                    for n in (1, 2, 3)
                ],
            }

    monkeypatch.setattr(downloader, "YoutubeDL", FakeYoutubeDL)


def test_playlist_link_imports_one_song_by_default(fake_ydl):
    plan = downloader.resolve(PLAYLIST_ONLY, None, SINGLES)
    assert len(plan.targets) == 1
    assert plan.is_playlist is False
    assert plan.album == SINGLES
    assert plan.targets[0].track_number is None
    # It reports what it skipped, so the CLI can say so.
    assert plan.available == 3


def test_playlist_flag_imports_everything(fake_ydl):
    plan = downloader.resolve(PLAYLIST_ONLY, None, SINGLES, playlist=True)
    assert len(plan.targets) == 3
    assert plan.is_playlist is True
    assert plan.album == "Some Mix"
    assert [t.track_number for t in plan.targets] == [1, 2, 3]


def test_items_implies_the_whole_playlist_machinery(fake_ydl):
    # --items is itself a playlist request, so no --playlist is needed.
    plan = downloader.resolve(PLAYLIST_ONLY, "1-3", SINGLES)
    assert len(plan.targets) == 3
    assert plan.is_playlist is True
    assert plan.album == "Some Mix"


def test_radio_mix_link_imports_the_linked_video(fake_ydl):
    # watch?v=...&list=RD... names a video and an endless radio mix. Default
    # to the video, and never resolve the mix at all.
    plan = downloader.resolve(RADIO, None, SINGLES)
    assert len(plan.targets) == 1
    assert plan.is_playlist is False
    assert plan.targets[0].video_id == "vid2"
    assert plan.targets[0].raw_title == "Second Song"
    assert plan.available is None  # the mix was never expanded


def test_radio_mix_link_with_playlist_flag_takes_the_mix(fake_ydl):
    plan = downloader.resolve(RADIO, None, SINGLES, playlist=True)
    assert len(plan.targets) == 3
    assert plan.is_playlist is True


def test_default_picks_the_linked_entry_not_the_first(monkeypatch):
    """A link with &index=3 should not silently import track 1."""

    class FakeYoutubeDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download=False):
            # Pretend yt-dlp ignored noplaylist and handed back the playlist,
            # so resolve has to choose the right entry itself.
            return {
                "_type": "playlist",
                "title": "Some Mix",
                "entries": [
                    {"id": f"vid{n}", "title": f"Song {n}", "ie_key": "Youtube"}
                    for n in (1, 2, 3)
                ],
            }

    monkeypatch.setattr(downloader, "YoutubeDL", FakeYoutubeDL)
    plan = downloader.resolve(
        "https://www.youtube.com/watch?v=vid3&list=PLabc&index=3", None, SINGLES
    )
    assert plan.targets[0].video_id == "vid3"


def test_empty_playlist_still_raises(monkeypatch):
    class FakeYoutubeDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download=False):
            return {"_type": "playlist", "title": "Empty", "entries": []}

    monkeypatch.setattr(downloader, "YoutubeDL", FakeYoutubeDL)
    with pytest.raises(downloader.ResolveError):
        downloader.resolve(PLAYLIST_ONLY, None, SINGLES)
