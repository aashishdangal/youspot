"""yt-dlp orchestration: resolve a URL to a list of videos, then import each one.

Resolving up front (a flat playlist extraction) and downloading one video at a
time is what makes an exact "12/48" counter, per-video error isolation and an
accurate skip count possible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from yt_dlp import YoutubeDL

from . import titles
from .tagging import VARIOUS_ARTISTS, write_tags

_COVER_EXTS = (".jpg", ".jpeg", ".png", ".webp")


class ResolveError(RuntimeError):
    """Raised when a URL yields nothing importable."""


class _CollectingLogger:
    """Keeps yt-dlp off the console while remembering its error messages.

    yt-dlp reports some failures by logging rather than raising, so without
    this the summary can only say "something went wrong".
    """

    def __init__(self) -> None:
        self.errors: list[str] = []

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        cleaned = " ".join(str(msg).split())
        for prefix in ("ERROR: ", "ERROR:"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        if cleaned:
            self.errors.append(cleaned)

    @property
    def last_error(self) -> str | None:
        return self.errors[-1] if self.errors else None


@dataclass
class Target:
    """One video to import."""

    index: int  # position in this run, 1-based
    video_id: str
    url: str
    raw_title: str
    ie_key: str
    track_number: int | None = None

    @property
    def archive_probe(self) -> dict[str, str]:
        """The minimal info dict YoutubeDL.in_download_archive needs."""
        return {"id": self.video_id, "ie_key": self.ie_key}


@dataclass
class Plan:
    album: str
    is_playlist: bool
    targets: list[Target]
    album_artist: str | None = None

    @property
    def total(self) -> int:
        return len(self.targets)


@dataclass
class Failure:
    index: int
    label: str
    reason: str


@dataclass
class Result:
    imported: int = 0
    skipped: int = 0
    failures: list[Failure] = field(default_factory=list)

    @property
    def failed(self) -> int:
        return len(self.failures)


def resolve(url: str, items: str | None, singles_album: str) -> Plan:
    """Flat-extract `url` into a Plan without downloading anything."""
    logger = _CollectingLogger()
    opts = {
        "extract_flat": "in_playlist",
        "quiet": True,
        "no_warnings": True,
        # Tolerated here so a playlist still resolves when some entries are
        # unavailable; the per-video download pass does not use it.
        "ignoreerrors": True,
        "noprogress": True,
        "logger": logger,
    }
    if items:
        opts["playlist_items"] = items

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        detail = logger.last_error or "nothing importable was found"
        raise ResolveError(f"Could not read {url}: {detail}")

    if info.get("_type") == "playlist":
        entries = [e for e in (info.get("entries") or []) if e]
        if not entries:
            raise ResolveError(
                "The playlist resolved to no playable videos"
                + (f" for --items {items}" if items else "")
            )
        targets = [
            Target(
                index=position,
                video_id=entry.get("id") or "",
                url=entry.get("url") or _watch_url(entry.get("id")),
                raw_title=entry.get("title") or entry.get("id") or "",
                ie_key=entry.get("ie_key") or entry.get("extractor_key") or "Youtube",
                track_number=position,
            )
            for position, entry in enumerate(entries, start=1)
        ]
        plan = Plan(
            album=info.get("title") or singles_album,
            is_playlist=True,
            targets=targets,
        )
        plan.album_artist = _guess_album_artist(plan)
        return plan

    target = Target(
        index=1,
        video_id=info.get("id") or "",
        url=info.get("webpage_url") or url,
        raw_title=info.get("title") or "",
        ie_key=info.get("extractor_key") or info.get("ie_key") or "Youtube",
    )
    return Plan(album=singles_album, is_playlist=False, targets=[target])


def _watch_url(video_id: str | None) -> str:
    return f"https://www.youtube.com/watch?v={video_id}" if video_id else ""


def _guess_album_artist(plan: Plan) -> str:
    """A single-artist playlist keeps that artist; anything else is a compilation.

    Guessed from the flat titles before any download, so every track in the run
    gets the same album artist and Spotify shows one album, not several. Every
    title has to name the same artist - if even one is unreadable we cannot
    claim the album belongs to one artist, so it becomes a compilation.
    """
    guesses = [titles.guess_artist(target.raw_title) for target in plan.targets]
    if not guesses or not all(guesses):
        return VARIOUS_ARTISTS
    if len({guess.casefold() for guess in guesses}) == 1:
        return guesses[0]
    return VARIOUS_ARTISTS


def album_dir(music_root: Path, album: str) -> Path:
    return music_root / titles.safe_filename(album, fallback="YouTube Imports")


def build_download_opts(
    destination: Path, quality: str, archive: Path | None, logger=None
) -> dict:
    opts = {
        "format": "bestaudio/best",
        "outtmpl": {"default": str(destination / "%(id)s.%(ext)s")},
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(quality),
            },
            # 'before_dl' is how yt-dlp's own CLI registers this; YouTube serves
            # .webp thumbnails, which Spotify will not render as embedded art.
            {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"},
        ],
        "writethumbnail": True,
        # Deliberately NOT ignoreerrors: this pass downloads one video per
        # call, so the loop below already isolates failures, and letting the
        # error surface is what makes the failure summary say anything useful.
        "ignoreerrors": False,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 5,
        "fragment_retries": 5,
    }
    if archive is not None:
        opts["download_archive"] = str(archive)
    if logger is not None:
        opts["logger"] = logger
    return opts


def _cover_bytes(info: dict, audio_path: Path) -> bytes | None:
    """Find the thumbnail the convertor left next to the audio file."""
    candidates: list[Path] = []
    for thumb in reversed(info.get("thumbnails") or []):
        filepath = thumb.get("filepath")
        if filepath:
            candidates.append(Path(filepath))
    candidates.extend(
        audio_path.with_suffix(ext) for ext in _COVER_EXTS
    )
    for candidate in candidates:
        if candidate.is_file() and candidate.suffix.lower() in (".jpg", ".jpeg"):
            try:
                return candidate.read_bytes()
            except OSError:
                continue
    return None


def _cleanup_thumbnails(info: dict, audio_path: Path) -> None:
    leftovers = {
        Path(thumb["filepath"])
        for thumb in (info.get("thumbnails") or [])
        if thumb.get("filepath")
    }
    leftovers.update(audio_path.with_suffix(ext) for ext in _COVER_EXTS)
    for path in leftovers:
        if path.is_file() and path.suffix.lower() in _COVER_EXTS:
            path.unlink(missing_ok=True)


def _cleanup_staging(destination: Path, video_id: str) -> None:
    """Remove half-finished files left by a video that failed mid-import.

    Everything is downloaded as "<video id>.<ext>" and only renamed once it is
    tagged, so a failure can leave a thumbnail or partial download behind in
    what is meant to be a tidy music folder.
    """
    if not video_id:
        return
    for path in destination.glob(f"{video_id}.*"):
        if path.is_file():
            path.unlink(missing_ok=True)


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for n in range(2, 100):
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if not candidate.exists():
            return candidate
    return path


def _reason(exc: BaseException) -> str:
    text = " ".join(str(exc).split())
    text = text.replace("ERROR: ", "")
    return text[:200] or exc.__class__.__name__


def import_plan(
    plan: Plan,
    *,
    music_root: Path,
    quality: str,
    archive: Path | None,
    reporter,
) -> Result:
    """Download, tag and file every target in `plan`."""
    result = Result()
    destination = album_dir(music_root, plan.album)
    destination.mkdir(parents=True, exist_ok=True)
    if archive is not None:
        archive.parent.mkdir(parents=True, exist_ok=True)

    logger = _CollectingLogger()
    opts = build_download_opts(destination, quality, archive, logger)

    with YoutubeDL(opts) as ydl:
        for target in plan.targets:
            label = titles.clean_title(target.raw_title) or target.video_id
            errors_before = len(logger.errors)
            try:
                if archive is not None and ydl.in_download_archive(target.archive_probe):
                    result.skipped += 1
                    reporter.skipped(target, plan.total, label)
                    continue

                reporter.starting(target, plan.total, label)
                info = ydl.extract_info(target.url, download=True)
                if not info:
                    raise RuntimeError("yt-dlp could not download this video")

                final_path = _finish_one(info, plan, target, destination)
                result.imported += 1
                reporter.imported(target, plan.total, final_path)
            except Exception as exc:  # one bad video must not stop the run
                _cleanup_staging(destination, target.video_id)
                # yt-dlp's own message is more specific than ours when it has one.
                logged = logger.errors[errors_before:]
                reason = logged[-1] if logged else _reason(exc)
                result.failures.append(Failure(target.index, label, reason))
                reporter.failed(target, plan.total, label, reason)

    return result


def _finish_one(info: dict, plan: Plan, target: Target, destination: Path) -> Path:
    downloads = info.get("requested_downloads") or []
    if not downloads or not downloads[0].get("filepath"):
        raise RuntimeError("yt-dlp reported no output file")

    # FFmpegExtractAudioPP rewrites 'filepath' to the converted .mp3.
    audio_path = Path(downloads[0]["filepath"])
    if not audio_path.is_file():
        raise RuntimeError(f"expected {audio_path.name} on disk")

    artist, title = titles.split_artist_title(info.get("title") or target.raw_title, info)
    upload_date = info.get("upload_date") or ""

    write_tags(
        audio_path,
        title=title,
        artist=artist,
        album=plan.album,
        album_artist=plan.album_artist,
        track_number=target.track_number,
        track_total=plan.total if plan.is_playlist else None,
        cover_bytes=_cover_bytes(info, audio_path),
        year=upload_date[:4] if len(upload_date) >= 4 else None,
        source_url=info.get("webpage_url") or target.url,
    )
    _cleanup_thumbnails(info, audio_path)

    final_path = _unique_path(
        destination / titles.track_filename(artist, title, target.track_number)
    )
    audio_path.replace(final_path)
    return final_path
