"""Pure helpers for turning YouTube titles into artist/title/filename strings.

Nothing here touches the network or the filesystem, so it is all directly
unit-testable (see tests/test_titles.py).
"""

from __future__ import annotations

import os
import re
import unicodedata

# Parenthetical content worth keeping: it is real metadata, not YouTube noise.
_KEEP = re.compile(
    r"\b(?:feat\.?|ft\.?|featuring|with|remix|remixed|rmx|bootleg|edit|vip|mix|"
    r"live|acoustic|unplugged|instrumental|karaoke|cover|demo|reprise|remake|"
    r"version|ver\.?|extended|radio\s*edit|club\s*mix|slowed|reverb|sped\s*up|"
    r"interlude|intro|outro|part\s*\d+|pt\.?\s*\d+|prod\.?)\b",
    re.I,
)

# Junk phrases YouTube uploaders decorate titles with.
_NOISE_PHRASES = [
    r"official\s*music\s*video",
    r"official\s*lyrics?\s*video",
    r"official\s*visuali[sz]er",
    r"official\s*video",
    r"official\s*audio",
    r"official",
    r"lyrics?\s*video",
    r"lyrics?",
    r"with\s*lyrics",
    r"visuali[sz]er",
    r"m/?v",
    r"audio\s*only",
    r"audio",
    r"video",
    r"full\s*album",
    r"full\s*song",
    r"free\s*download",
    r"download",
    r"out\s*now",
    r"new\s*song",
    r"explicit",
    r"uhd",
    r"hd",
    r"hq",
    r"[48]\s*k",
    r"\d{3,4}p(?:\s*60)?",
    r"(?:19|20)\d{2}\s*remaster(?:ed)?",
    r"remaster(?:ed)?(?:\s*(?:19|20)\d{2})?",
    r"high\s*quality",
    r"copyright\s*free",
    r"no\s*copyright",
]

# The subset confident enough to strip when it trails a title unbracketed,
# e.g. "Song Title Official Video" or "Song Title | 4K".
_STRONG_NOISE = [
    r"official\s*music\s*video",
    r"official\s*lyrics?\s*video",
    r"official\s*visuali[sz]er",
    r"official\s*video",
    r"official\s*audio",
    r"lyrics?\s*video",
    r"lyrics?",
    r"with\s*lyrics",
    r"visuali[sz]er",
    r"full\s*album",
    r"free\s*download",
    r"out\s*now",
    r"uhd",
    r"hd",
    r"hq",
    r"[48]\s*k",
    r"\d{3,4}p(?:\s*60)?",
]

_SEPS = r"|/\\\-–—,&+•·:;"

_ANY_NOISE = "|".join(_NOISE_PHRASES)
_STRONG = "|".join(_STRONG_NOISE)

# A bracketed group whose entire content is noise (possibly several joined
# with separators, e.g. "[Official Video - 4K]").
# Noise phrases may be joined by punctuation or just a space, so that
# "[Official Video - 4K]" and "(4K Remaster)" both match as pure noise.
_JOIN = rf"(?:\s*[{_SEPS}]+\s*|\s+)"
_NOISE_ONLY = re.compile(
    rf"^\s*(?:{_ANY_NOISE})(?:{_JOIN}(?:{_ANY_NOISE}))*\s*$", re.I
)
_BRACKETED = re.compile(r"\s*[(\[\{]([^(){}\[\]]*)[)\]\}]")
_EMPTY_BRACKETS = re.compile(r"\s*[(\[\{]\s*[)\]\}]")

# Trailing noise introduced by a separator: "Song | Official Video".
_TRAILING_SEP_NOISE = re.compile(
    rf"\s*[{_SEPS}]+\s*(?:{_ANY_NOISE})(?:{_JOIN}(?:{_ANY_NOISE}))*\s*$", re.I
)
# Trailing noise with no separator at all: "Song Official Video".
_TRAILING_BARE_NOISE = re.compile(rf"\s+(?:{_STRONG})\s*$", re.I)

_DASH_SPLIT = re.compile(r"\s+[-–—]\s+|\s*[–—]\s*")
_WS = re.compile(r"\s+")
_ARTIST_SUFFIX = re.compile(r"\s*(?:[-–—]\s*Topic|\s*VEVO|\s*Official)\s*$", re.I)
_QUOTE_PAIRS = [('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’")]

_MAX_ARTIST_LEN = 60
_MAX_ARTIST_WORDS = 6
# Windows caps a full path at 260 characters by default, so components are
# kept shorter there to leave room for the music folder and album folder.
_MAX_FILENAME_LEN = 120 if os.name == "nt" else 180
_ILLEGAL_FILENAME = re.compile(r'[/\\:*?"<>|\x00-\x1f]')

# Names Windows refuses outright, with or without an extension.
_RESERVED_NAMES = frozenset(
    ["con", "prn", "aux", "nul"]
    + [f"com{n}" for n in range(1, 10)]
    + [f"lpt{n}" for n in range(1, 10)]
)


def _strip_brackets(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        inner = match.group(1)
        if _KEEP.search(inner):
            return match.group(0)
        if _NOISE_ONLY.match(inner):
            return ""
        return match.group(0)

    return _BRACKETED.sub(repl, text)


def _strip_edges(text: str) -> str:
    text = text.strip().strip("".join(c for c in "|/-–—,&+•·:;")).strip()
    for left, right in _QUOTE_PAIRS:
        if len(text) > 1 and text.startswith(left) and text.endswith(right):
            text = text[1:-1].strip()
    return text


def clean_title(raw: str) -> str:
    """Strip YouTube decoration from a video title.

    Keeps meaningful parentheticals such as "(feat. X)" or "(Remix)".
    """
    if not raw:
        return ""
    text = unicodedata.normalize("NFC", raw).replace("​", "")

    # Each pass can expose more junk, so repeat until it settles.
    for _ in range(6):
        before = text
        text = _strip_brackets(text)
        text = _EMPTY_BRACKETS.sub("", text)
        text = _TRAILING_SEP_NOISE.sub("", text)
        text = _TRAILING_BARE_NOISE.sub("", text)
        text = _strip_edges(text)
        if text == before:
            break

    return _WS.sub(" ", text).strip()


def clean_artist(raw: str) -> str:
    """Normalise a channel/uploader name into an artist name."""
    if not raw:
        return ""
    text = unicodedata.normalize("NFC", raw).strip()
    for _ in range(3):
        stripped = _ARTIST_SUFFIX.sub("", text).strip()
        if stripped == text:
            break
        text = stripped
    return _WS.sub(" ", text).strip()


def _dash_split(text: str) -> tuple[str, str] | tuple[None, None]:
    """Split "Artist - Title" when the left side plausibly names an artist."""
    match = _DASH_SPLIT.search(text)
    if not match:
        return None, None
    left = text[: match.start()].strip()
    right = text[match.end() :].strip()
    if not left or not right:
        return None, None
    if len(left) > _MAX_ARTIST_LEN or len(left.split()) > _MAX_ARTIST_WORDS:
        return None, None
    return _strip_edges(left), _strip_edges(right)


def guess_artist(raw_title: str) -> str | None:
    """Best guess at the artist from a title alone, or None.

    Used to decide an album artist for a whole playlist before downloading.
    """
    artist, _ = _dash_split(clean_title(raw_title))
    return artist or None


def split_artist_title(raw_title: str, info: dict | None = None) -> tuple[str, str]:
    """Resolve (artist, title) for a video.

    Precedence: yt-dlp's own ``artist``/``track`` fields (YouTube Music supplies
    these and they are authoritative), then an "Artist - Title" dash split, then
    the uploader name with the cleaned title.
    """
    info = info or {}
    track = (info.get("track") or "").strip()
    artist = (info.get("artist") or info.get("creator") or "").strip()
    if track and artist:
        # Several artists arrive comma-separated; the first is the primary.
        primary = artist.split(",")[0].strip() if "," in artist else artist
        return clean_artist(primary) or primary, clean_title(track) or track

    cleaned = clean_title(raw_title)
    left, right = _dash_split(cleaned)
    if left and right:
        return left, right

    uploader = clean_artist(info.get("uploader") or info.get("channel") or "")
    return (uploader or "Unknown Artist"), (cleaned or (raw_title or "").strip())


def safe_filename(name: str, fallback: str = "untitled") -> str:
    """Make a string safe to use as a single path component.

    Satisfies the stricter of the platforms' rules, so a library created on a
    Mac still copies to a Windows machine: no reserved device names, no
    trailing dots or spaces, and no characters either OS rejects.
    """
    text = unicodedata.normalize("NFC", name or "")
    text = _ILLEGAL_FILENAME.sub("_", text)
    text = _WS.sub(" ", text).strip()
    # Windows rejects trailing dots and spaces, and stripping one can expose
    # the other ("name . " -> "name ."  -> "name ").
    while text and text[-1] in " .":
        text = text[:-1]
    text = text.lstrip(".")
    if len(text) > _MAX_FILENAME_LEN:
        text = text[:_MAX_FILENAME_LEN].rstrip(" .")
    if text.split(".")[0].lower() in _RESERVED_NAMES:
        text = f"_{text}"
    return text or fallback


def track_filename(artist: str, title: str, track_number: int | None = None) -> str:
    """Build the on-disk basename, e.g. "01 - Artist - Title.mp3"."""
    stem = safe_filename(f"{artist} - {title}" if artist else title)
    if track_number is not None:
        return f"{track_number:02d} - {stem}.mp3"
    return f"{stem}.mp3"
