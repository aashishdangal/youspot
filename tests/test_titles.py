"""Tests for the title-cleaning logic - no network, no filesystem."""

import pytest

from ytspot import titles


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Artist - Song (Official Video) [4K]", "Artist - Song"),
        ("Artist - Song [Official Music Video]", "Artist - Song"),
        ("Artist - Song | Official Video", "Artist - Song"),
        ("Artist - Song (Official Audio)", "Artist - Song"),
        ("Artist - Song (Lyrics)", "Artist - Song"),
        ("Artist - Song Official Video", "Artist - Song"),
        ("Artist - Song [HD] [1080p]", "Artist - Song"),
        ("Artist - Song (Remastered 2011)", "Artist - Song"),
        ("Artist - Song [Visualizer] (Explicit)", "Artist - Song"),
        ("Artist - Song (OFFICIAL VIDEO - 4K)", "Artist - Song"),
        ("Artist - Song (4K Remaster)", "Artist - Song"),
        ("Artist - Song [Official Video HD]", "Artist - Song"),
        ("Artist - Song (Official Video) (1080p 60)", "Artist - Song"),
        ("  Artist  -  Song   ", "Artist - Song"),
    ],
)
def test_clean_title_strips_noise(raw, expected):
    assert titles.clean_title(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Song (feat. Someone) [Official Video]", "Song (feat. Someone)"),
        ("Song (Remix) [Official Audio]", "Song (Remix)"),
        ("Song (Live at Wembley) [4K]", "Song (Live at Wembley)"),
        ("Song (Acoustic Version) (Official Video)", "Song (Acoustic Version)"),
        ("Song (Radio Edit) [HQ]", "Song (Radio Edit)"),
        ("Song (Pt. 2) [Official Video]", "Song (Pt. 2)"),
    ],
)
def test_clean_title_keeps_real_metadata(raw, expected):
    assert titles.clean_title(raw) == expected


def test_clean_title_leaves_plain_titles_alone():
    raw = "A Long Sentence That Happens To Be The Name Of This Song"
    assert titles.clean_title(raw) == raw


def test_split_prefers_yt_dlp_metadata_fields():
    info = {"artist": "Aphex Twin", "track": "Avril 14th", "uploader": "WARP"}
    assert titles.split_artist_title("whatever (Official Video)", info) == (
        "Aphex Twin",
        "Avril 14th",
    )


def test_split_takes_first_of_several_artists():
    info = {"artist": "A, B", "track": "Song"}
    assert titles.split_artist_title("ignored", info) == ("A", "Song")


def test_split_uses_dash_when_no_metadata():
    assert titles.split_artist_title("Tame Impala - Borderline [Official Video]", {}) == (
        "Tame Impala",
        "Borderline",
    )


def test_split_handles_en_dash():
    assert titles.split_artist_title("Artist – Song", {}) == ("Artist", "Song")


def test_split_falls_back_to_uploader_without_a_dash():
    info = {"uploader": "Some Band - Topic"}
    assert titles.split_artist_title("Just A Song Title", info) == (
        "Some Band",
        "Just A Song Title",
    )


def test_split_does_not_break_up_sentence_titles():
    raw = "I Went To The Shop And Then Something Happened - A Story"
    artist, title = titles.split_artist_title(raw, {"uploader": "Channel"})
    assert artist == "Channel"
    assert title == raw


def test_split_without_any_metadata_is_still_usable():
    assert titles.split_artist_title("Mystery Track", {}) == (
        "Unknown Artist",
        "Mystery Track",
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Band - Topic", "Band"),
        ("BandVEVO", "Band"),
        ("Band Official", "Band"),
    ],
)
def test_clean_artist_strips_channel_suffixes(raw, expected):
    assert titles.clean_artist(raw) == expected


def test_safe_filename_removes_path_characters():
    assert titles.safe_filename("AC/DC: Back\\In Black?") == "AC_DC_ Back_In Black_"


def test_safe_filename_falls_back_when_empty():
    assert titles.safe_filename("///") == "___"
    assert titles.safe_filename("") == "untitled"


def test_safe_filename_is_length_capped():
    assert len(titles.safe_filename("x" * 400)) == titles._MAX_FILENAME_LEN


@pytest.mark.parametrize(
    "raw",
    ["CON", "con", "nul", "PRN.mp3", "aux", "COM1", "lpt9"],
)
def test_safe_filename_escapes_windows_reserved_names(raw):
    # Windows refuses these outright, extension or not.
    assert titles.safe_filename(raw).startswith("_")


def test_safe_filename_keeps_names_that_merely_contain_a_reserved_word():
    assert titles.safe_filename("Console") == "Console"
    assert titles.safe_filename("Aux Cable") == "Aux Cable"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("name.", "name"),
        ("name ", "name"),
        ("name . ", "name"),
        ("name...  ", "name"),
        (".hidden", "hidden"),
    ],
)
def test_safe_filename_removes_trailing_dots_and_spaces(raw, expected):
    # Windows rejects both, and stripping one can expose the other.
    assert titles.safe_filename(raw) == expected


def test_track_filename_stays_within_the_length_cap():
    name = titles.track_filename("A" * 300, "B" * 300, 7)
    assert len(name) <= titles._MAX_FILENAME_LEN + len("07 - ") + len(".mp3")


def test_track_filename_shapes():
    assert titles.track_filename("Artist", "Song", 7) == "07 - Artist - Song.mp3"
    assert titles.track_filename("Artist", "Song", None) == "Artist - Song.mp3"


def test_guess_artist():
    assert titles.guess_artist("Artist - Song (Official Video)") == "Artist"
    assert titles.guess_artist("No Dash Here") is None
