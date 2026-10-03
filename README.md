# ytspot

Import YouTube audio into Spotify's **Local Files** as properly tagged MP3s.

Give it a video or playlist URL and it downloads the audio, converts it to MP3,
cleans the junk out of the title (`[4K]`, `(Official Video)`, …), splits it into
artist and title, embeds the thumbnail as cover art, and sets an album so the
tracks group together in Spotify. Re-running is cheap: anything already imported
is skipped, and one broken video never stops a playlist.

```
$ ytspot "https://www.youtube.com/playlist?list=PL..."
Reading URL ...
48 track(s) from playlist "Late Night Drive"
Saving to /Users/you/Music/ytspot/Late Night Drive

[ 1/48] Tame Impala - Borderline ... ok
[ 2/48] Khruangbin - Time (You and I) ... skipped (already imported)
[ 3/48] Men I Trust - Show Me How ... ok
...

Imported 45, skipped 2, failed 1
Folder: /Users/you/Music/ytspot/Late Night Drive

Failures:
  #31  Some Deleted Track - Video unavailable
```

## Setup

### 1. Install the prerequisites

```bash
brew install uv ffmpeg
```

- **FFmpeg** does the MP3 conversion. ytspot refuses to run without it.
- **uv** manages Python and the dependencies. It brings its own Python, which
  matters here: yt-dlp needs Python 3.10+, and macOS still ships 3.9.

No Homebrew? Get it from [brew.sh](https://brew.sh), or install uv via
`curl -LsSf https://astral.sh/uv/install.sh | sh` and FFmpeg from
[ffmpeg.org/download.html](https://ffmpeg.org/download.html).

### 2. Install ytspot

```bash
git clone <this repo> ytspot && cd ytspot
uv sync
```

Run it with `uv run ytspot ...`. To get a plain `ytspot` command on your PATH:

```bash
uv tool install .
```

### 3. First run

The first import asks where to save files and remembers the answer:

```
$ uv run ytspot "https://www.youtube.com/watch?v=..."
First run: ytspot needs a folder to save imported MP3s.
Use the folder you have added (or will add) to
Spotify > Settings > Local Files > Add a source.
Music folder [/Users/you/Music/ytspot]:
```

### 4. Point Spotify at the folder

In the **desktop** app: **Settings → Local Files →** turn on *Show songs from* →
**Add a source** → choose the folder from step 3. Your imports appear under
*Your Library → Local Files*, grouped by album.

Two things worth knowing: local files only work in the desktop and mobile apps,
not the web player, and to hear them on your phone you add them to a playlist,
then download that playlist with both devices on the same Wi-Fi.

## Usage

```bash
ytspot URL [OPTIONS]
```

| Option | What it does |
| --- | --- |
| `--items TEXT` | Import only part of a playlist: `1-10`, `1,5,8`, `3:12:2` |
| `--album TEXT` | Override the album name (defaults to the playlist name) |
| `--music-dir PATH` | Save somewhere other than the configured folder |
| `--quality TEXT` | MP3 bitrate; `320` by default |
| `--no-archive` | Re-download videos even if they were imported before |
| `--dry-run` | Show what would be imported, download nothing |

```bash
# a single video
ytspot "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# first 10 of a playlist
ytspot "https://www.youtube.com/playlist?list=PL..." --items 1-10

# look before you leap
ytspot "https://www.youtube.com/playlist?list=PL..." --dry-run
```

Check or change settings:

```bash
ytspot config                                  # show current settings
ytspot config --set-music-dir ~/Music/ytspot   # change the destination
```

## How it tags files

| Tag | Value |
| --- | --- |
| Title / Artist | From YouTube Music's own `artist`/`track` metadata when present, otherwise split from `Artist - Title`, otherwise the channel name |
| Album | The playlist name, or `YouTube Imports` for a single video |
| Album artist | The playlist's artist if they all match, otherwise `Various Artists` |
| Track number | Playlist position, e.g. `7/48` (playlists only) |
| Year | The video's upload year |
| Cover art | The video thumbnail, converted to JPEG and embedded |
| Comment / URL | The source YouTube URL, so you can trace a file later |

Tags are written as **ID3v2.3** — Spotify is unreliable at reading the newer
v2.4 that most taggers default to.

Files land in `<music folder>/<album>/`, named `07 - Artist - Title.mp3`
(playlists) or `Artist - Title.mp3` (single videos).

YouTube Music links (`music.youtube.com`) give noticeably better tags than
`youtube.com` ones, because they carry real artist and track fields.

## Skipping what you already have

Every imported video ID is recorded in `~/.config/ytspot/archive.txt`
(yt-dlp's download-archive format). Re-running the same playlist only fetches
what's new, which makes `ytspot <playlist url>` a reasonable thing to run
occasionally on a playlist you follow. Use `--no-archive` to force a
re-download, or delete lines from that file to forget specific videos.

## Configuration

`~/.config/ytspot/config.json` (override the location with `$YTSPOT_CONFIG`):

```json
{
  "music_dir": "/Users/you/Music/ytspot",
  "archive_path": "/Users/you/.config/ytspot/archive.txt",
  "quality": "320",
  "singles_album": "YouTube Imports"
}
```

## Troubleshooting

**"FFmpeg was not found on your PATH"** — `brew install ffmpeg`, then open a new
terminal.

**Tracks don't show up in Spotify** — confirm the folder is listed under
Settings → Local Files, then restart Spotify; it only rescans on launch. Check
the files are where you expect with `ytspot config`.

**Cover art missing** — a few videos have no usable thumbnail. The rest of the
tags are still written.

**A video failed** — the summary prints the reason per video. Private,
deleted and region-blocked videos are the usual causes, and the rest of the
playlist still imports. If *everything* fails, `uv sync --upgrade` usually
fixes it: YouTube changes break older yt-dlp versions regularly.

## Development

```bash
uv run pytest        # title-parsing tests (no network)
```

The title cleanup in `src/ytspot/titles.py` is pure functions, so new
real-world junk patterns can be added to `tests/test_titles.py` and fixed
without touching the download path.
