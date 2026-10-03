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

ytspot needs **FFmpeg** (does the MP3 conversion; ytspot refuses to run without
it) and **uv** (manages Python and the dependencies — it brings its own Python,
which matters because yt-dlp needs 3.10+ and macOS still ships 3.9).

**macOS:**

```bash
brew install uv ffmpeg
```

**Windows** (PowerShell):

```powershell
winget install astral-sh.uv
winget install Gyan.FFmpeg
```

Then **close and reopen PowerShell** so the new PATH takes effect. Prefer
Chocolatey? `choco install uv ffmpeg`. Scoop? `scoop install uv ffmpeg`.

**Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
sudo apt install ffmpeg          # or your distro's equivalent
```

No package manager at all? uv has installers at
[docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/) and
FFmpeg builds at [ffmpeg.org/download.html](https://ffmpeg.org/download.html) —
on Windows, make sure the folder holding `ffmpeg.exe` is on your PATH.

### 2. Install ytspot

```bash
git clone <this repo> ytspot
cd ytspot
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
Spotify > Settings > Library > Show Local Files > Add a source.
Music folder [/Users/you/Music/ytspot]:
```

### 4. Point Spotify at the folder

This is a few steps and easy to get half-done, so in full.

**On desktop** (Windows or Mac — the web player cannot play local files at all):

1. Click your **profile picture** (top right) → **Settings**
2. Scroll to the **Library** section
3. Turn on **Show Local Files**
4. Under **Show songs from**, click **Add a source**
5. Pick the folder from step 3 — the folder itself, *not* the album subfolder
   inside it. ytspot creates one subfolder per playlist and Spotify scans
   recursively, so adding the parent once covers every future import.
6. **Quit Spotify completely and reopen it** (Cmd+Q on Mac, not just closing
   the window). It only scans on launch.
7. **Your Library** → **Local Files**

Your imports appear grouped by album — the playlist name, or `YouTube Imports`
for single videos.

**To actually live with them**, add the tracks to a real playlist: right-click →
*Add to playlist*. Local files can't be shuffled into your normal listening or
reached by search until they're in one.

**On your phone** (iOS and Android are the same now):

1. Tap your **profile picture** → **Settings and privacy**
2. Tap **Apps and devices**
3. Turn on **Local audio files**
4. **Your Library** → **Local Files**

The catch: the files have to be **physically on the phone**. Spotify no longer
syncs local files from your desktop over Wi-Fi, so you transfer the MP3s
yourself — AirDrop or a USB cable to the Files app on iOS, USB file transfer on
Android — and may have to grant Spotify storage access in your device settings.
If you only ever listen on desktop, ignore this section.

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

Every imported video ID is recorded in an archive file — `~/.config/ytspot/archive.txt`,
or `%APPDATA%\ytspot\archive.txt` on Windows (yt-dlp's download-archive format). Re-running the same playlist only fetches
what's new, which makes `ytspot <playlist url>` a reasonable thing to run
occasionally on a playlist you follow. Use `--no-archive` to force a
re-download, or delete lines from that file to forget specific videos.

## Configuration

The config file lives at:

| Platform | Path |
| --- | --- |
| macOS / Linux | `~/.config/ytspot/config.json` |
| Windows | `%APPDATA%\ytspot\config.json` |

Set the `YTSPOT_CONFIG` environment variable to use a different file. Run
`ytspot config` to print the path in use along with the current settings.

```json
{
  "music_dir": "/Users/you/Music/ytspot",
  "archive_path": "/Users/you/.config/ytspot/archive.txt",
  "quality": "320",
  "singles_album": "YouTube Imports"
}
```

On Windows the paths use backslashes, which must be escaped in JSON
(`"C:\\Users\\you\\Music\\ytspot"`) — easier to let
`ytspot config --set-music-dir` write it for you.

## Troubleshooting

**"FFmpeg was not found on your PATH"** — install it (step 1 above), then open
a **new** terminal so it picks up the changed PATH. On Windows, check it with
`ffmpeg -version`; if that fails after installing, the install folder isn't on
your PATH.

**Tracks don't show up in Spotify** — work down this list:

1. Did you **fully quit** Spotify and reopen it? Cmd+Q on Mac, or right-click
   the tray icon and Quit on Windows. It only scans on launch, and closing the
   window isn't quitting.
2. Is **Show Local Files** still on, and is your folder still listed under
   *Show songs from*? Spotify drops sources after some updates.
3. Are the files where you think they are? `ytspot config` prints the folder.
4. Are you on the **web player**? It can't play local files at all.
5. Still nothing — remove the source, re-add it, and restart again. That
   rebuilds the index.

**Tracks play but look wrong** (no artist, odd titles) — Spotify caches its
index. Removing and re-adding the source picks up re-tagged files.

**Cover art missing** — a few videos have no usable thumbnail. The rest of the
tags are still written.

**A video failed** — the summary prints the reason per video. Private,
deleted and region-blocked videos are the usual causes, and the rest of the
playlist still imports. If *everything* fails, `uv sync --upgrade` usually
fixes it: YouTube changes break older yt-dlp versions regularly.

## Development

```bash
uv run pytest                           # unit tests, no network, instant
uv run python scripts/smoke_test.py     # real end-to-end checks, a few minutes
```

Both work on macOS, Linux and Windows. The smoke test downloads a few tracks
into a temp folder with its own config and checks the output, so your real
library and config are untouched.

The title cleanup in `src/ytspot/titles.py` is pure functions, so new
real-world junk patterns can be added to `tests/test_titles.py` and fixed
without touching the download path.
