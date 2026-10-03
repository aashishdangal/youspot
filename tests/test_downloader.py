"""Tests for the plan-level logic that needs no network."""

from pathlib import Path

from ytspot import downloader
from ytspot.tagging import VARIOUS_ARTISTS


def _plan(*raw_titles: str) -> downloader.Plan:
    targets = [
        downloader.Target(
            index=position,
            video_id=f"id{position}",
            url=f"https://www.youtube.com/watch?v=id{position}",
            raw_title=raw_title,
            ie_key="Youtube",
            track_number=position,
        )
        for position, raw_title in enumerate(raw_titles, start=1)
    ]
    return downloader.Plan(album="Album", is_playlist=True, targets=targets)


def test_album_artist_when_every_title_agrees():
    plan = _plan("Radiohead - Creep", "Radiohead - No Surprises (Official Video)")
    assert downloader._guess_album_artist(plan) == "Radiohead"


def test_album_artist_is_compilation_when_artists_differ():
    plan = _plan("Radiohead - Creep", "Blur - Song 2")
    assert downloader._guess_album_artist(plan) == VARIOUS_ARTISTS


def test_album_artist_is_compilation_when_any_title_is_unreadable():
    # One unsplittable title means we cannot claim the album has a single
    # artist, even though the other title names one.
    plan = _plan("Radiohead - Creep", "Some Untitled Upload")
    assert downloader._guess_album_artist(plan) == VARIOUS_ARTISTS


def test_album_dir_sanitises_the_album_name():
    assert downloader.album_dir(Path("/music"), "AC/DC: Live") == Path(
        "/music/AC_DC_ Live"
    )


def test_album_dir_falls_back_for_an_empty_name():
    assert downloader.album_dir(Path("/music"), "") == Path("/music/YouTube Imports")


def test_download_opts_set_quality_and_archive():
    opts = downloader.build_download_opts(Path("/music/Album"), "320", Path("/a.txt"))
    extract_audio = opts["postprocessors"][0]
    assert extract_audio["key"] == "FFmpegExtractAudio"
    assert extract_audio["preferredcodec"] == "mp3"
    assert extract_audio["preferredquality"] == "320"
    assert opts["download_archive"] == "/a.txt"
    # Off on purpose: the caller downloads one video per call and catches its
    # own errors, and ignoreerrors would hide the reason a video failed.
    assert opts["ignoreerrors"] is False
    # The thumbnail convertor only works registered this early.
    assert opts["postprocessors"][1]["when"] == "before_dl"


def test_download_opts_omit_archive_when_disabled():
    opts = downloader.build_download_opts(Path("/music/Album"), "192", None)
    assert "download_archive" not in opts
    assert opts["postprocessors"][0]["preferredquality"] == "192"


def test_target_archive_probe_has_what_yt_dlp_needs():
    # YoutubeDL._make_archive_id needs an id plus an extractor key.
    probe = _plan("Artist - Song").targets[0].archive_probe
    assert probe == {"id": "id1", "ie_key": "Youtube"}


def test_one_bad_video_does_not_stop_the_run(tmp_path, monkeypatch):
    """The core promise: a broken video is recorded and the rest still import."""
    monkeypatch.setattr(downloader, "write_tags", lambda *a, **k: None)

    class FakeYoutubeDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def in_download_archive(self, info):
            return info["id"] == "id3"

        def extract_info(self, url, download=False):
            if url.endswith("id1"):
                # yt-dlp fetches the thumbnail before the audio, so a failure
                # here is exactly when staging files get orphaned.
                stray = tmp_path / "Album"
                stray.mkdir(parents=True, exist_ok=True)
                (stray / "id1.jpg").write_bytes(b"")
                raise RuntimeError("ERROR: Video unavailable")
            mp3 = tmp_path / "Album" / "id2.mp3"
            mp3.parent.mkdir(parents=True, exist_ok=True)
            mp3.write_bytes(b"")
            return {
                "title": "Artist - Song",
                "upload_date": "20200101",
                "webpage_url": url,
                "requested_downloads": [{"filepath": str(mp3)}],
                "thumbnails": [],
            }

    monkeypatch.setattr(downloader, "YoutubeDL", FakeYoutubeDL)

    class NullReporter:
        def starting(self, *a):
            pass

        def imported(self, *a):
            pass

        def skipped(self, *a):
            pass

        def failed(self, *a):
            pass

    plan = _plan("Bad - Video", "Artist - Song", "Already - Imported")
    result = downloader.import_plan(
        plan,
        music_root=tmp_path,
        quality="320",
        archive=tmp_path / "archive.txt",
        reporter=NullReporter(),
    )

    assert result.imported == 1
    assert result.skipped == 1
    assert result.failed == 1
    # The real reason is kept, not a generic placeholder.
    assert result.failures[0].index == 1
    assert "Video unavailable" in result.failures[0].reason
    assert (tmp_path / "Album" / "02 - Artist - Song.mp3").is_file()
    # The failed video leaves nothing behind in the music folder.
    assert not (tmp_path / "Album" / "id1.jpg").exists()
