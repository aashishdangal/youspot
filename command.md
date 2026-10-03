# ytspot — Commands & Testing

Every command below is run from the project root. Prefix with `uv run` unless you
installed it globally with `uv tool install .`, in which case plain `ytspot` works.

---

## Setup commands

| Command | What it does |
| --- | --- |
| `brew install uv ffmpeg` | Installs the two prerequisites. FFmpeg does the MP3 conversion; uv brings its own Python (yt-dlp needs 3.10+, macOS ships 3.9) |
| `uv sync` | Creates `.venv` and installs all dependencies from `uv.lock` |
| `uv sync --upgrade` | Upgrades dependencies — the fix when YouTube changes break yt-dlp |
| `uv tool install .` | Optional: puts a global `ytspot` on your PATH |
| `uv tool uninstall ytspot` | Undoes the above |

---

## Import commands

```
ytspot URL [OPTIONS]
```

`URL` is a YouTube video, playlist, or channel URL. `ytspot URL` is shorthand for
`ytspot get URL`; both work.

| Option | What it does |
| --- | --- |
| `--items TEXT` | Import only part of a playlist: `1-10`, `1,5,8`, `3:12:2` (yt-dlp syntax) |
| `--album TEXT` | Override the album name (default: playlist name, or `YouTube Imports`) |
| `--music-dir PATH` | Save somewhere other than the configured folder, just this once |
| `--quality TEXT` | MP3 bitrate; `320` by default |
| `--no-archive` | Re-download videos even if they were imported before |
| `--dry-run` | Show what would be imported, download nothing |
| `--help` | Show the options |

### Examples

```bash
# single video
uv run ytspot "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# whole playlist
uv run ytspot "https://www.youtube.com/playlist?list=PL..."

# first 10 tracks only
uv run ytspot "https://www.youtube.com/playlist?list=PL..." --items 1-10

# specific positions
uv run ytspot "https://www.youtube.com/playlist?list=PL..." --items 1,5,8

# look before you leap
uv run ytspot "https://www.youtube.com/playlist?list=PL..." --dry-run

# name the album yourself, at a smaller bitrate
uv run ytspot "https://www.youtube.com/playlist?list=PL..." \
  --album "Driving Mix" --quality 192

# force a re-download of something already imported
uv run ytspot "https://www.youtube.com/watch?v=..." --no-archive
```

---

## Config commands

| Command | What it does |
| --- | --- |
| `ytspot config` | Print the current settings and the config file path |
| `ytspot config --show` | Same thing, explicitly |
| `ytspot config --set-music-dir PATH` | Change where MP3s are saved (creates the folder) |

The config lives at `~/.config/ytspot/config.json`; set `$YTSPOT_CONFIG` to use a
different file. The first import prompts for the music folder if none is set.

```bash
uv run ytspot config
uv run ytspot config --set-music-dir ~/Music/ytspot
YTSPOT_CONFIG=/tmp/test.json uv run ytspot config   # use a throwaway config
```

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Everything imported or skipped |
| `1` | The URL could not be read, or at least one video failed |
| `2` | FFmpeg is not on your PATH |

---

## Testing

### Automated tests

45 tests, no network and no downloads — they run in well under a second.

```bash
uv run pytest                       # everything
uv run pytest -q                    # quiet
uv run pytest -v                    # one line per test
uv run pytest tests/test_titles.py  # title cleanup only
uv run pytest tests/test_downloader.py  # plan logic only
uv run pytest -k album_artist       # tests matching a name
uv run pytest -x                    # stop at the first failure
```

What they cover:

| File | Covers |
| --- | --- |
| `tests/test_titles.py` | Stripping `(Official Video)`, `[4K]`, `HD`, `(4K Remaster)` etc; **keeping** real metadata like `(feat. X)` and `(Remix)`; the artist/title split and its guards; filename sanitising |
| `tests/test_downloader.py` | Album-artist choice, album folder naming, yt-dlp option construction, and that one broken video does not stop a run (via a fake yt-dlp, so no network) |

Add a new real-world junk title to `tests/test_titles.py` and fix it in
`src/ytspot/titles.py` — that layer is pure functions, so nothing else is involved.

### Manual end-to-end testing

Use a throwaway config so your real settings and music folder stay untouched:

```bash
export YTSPOT_CONFIG=/tmp/ytspot-test.json
mkdir -p /tmp/ytspot-music
cat > "$YTSPOT_CONFIG" <<'JSON'
{
  "music_dir": "/tmp/ytspot-music",
  "archive_path": "/tmp/ytspot-archive.txt",
  "quality": "320",
  "singles_album": "YouTube Imports"
}
JSON
```

Then work through these — this is the exact sequence used to verify the tool:

```bash
# 1. CLI loads and the options are there
uv run ytspot --help
uv run ytspot get --help

# 2. settings are read correctly
uv run ytspot config

# 3. dry run: no network writes, check the planned filenames
uv run ytspot "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --dry-run

# 4. real import of a short playlist (ytsearch works as a stand-in playlist)
uv run ytspot "ytsearch2:kevin macleod carefree" --album "Test Album"

# 5. nothing but MP3s should exist - no stray .jpg or .part files
find /tmp/ytspot-music -type f

# 6. re-run: both tracks should say "skipped (already imported)"
uv run ytspot "ytsearch2:kevin macleod carefree" --album "Test Album"

# 7. the archive recorded the video IDs
cat /tmp/ytspot-archive.txt

# 8. a bad URL reports the real reason and exits 1
uv run ytspot "https://www.youtube.com/watch?v=aaaaaaaaaaa"; echo "exit=$?"

# 9. partial playlist
uv run ytspot "ytsearch5:lofi" --items 1-3 --dry-run
```

**Checking the tags** of what you imported:

```bash
uv run python - <<'EOF'
from pathlib import Path
from mutagen.id3 import ID3
from mutagen.mp3 import MP3

for f in sorted(Path("/tmp/ytspot-music").rglob("*.mp3")):
    tags, audio = ID3(f), MP3(f)
    art = tags.getall("APIC")
    print(f"\n{f.name}")
    print(f"  ID3v2.{tags.version[1]}  {audio.info.bitrate // 1000}kbps  {audio.info.length:.0f}s")
    for key in ("TIT2", "TPE1", "TALB", "TPE2", "TRCK", "TDRC", "WOAS"):
        if key in tags:
            print(f"  {key:<5} {tags[key]}")
    print(f"  APIC  {len(art[0].data) if art else 0} bytes")
EOF
```

What a correct result looks like:

- `ID3v2.3` — **not** 2.4. Spotify is unreliable at reading v2.4.
- `320kbps` (or whatever `--quality` you passed).
- `APIC` present and non-zero — the embedded cover art.
- `TRCK` like `1/2` for playlists, absent for single videos.
- `TALB` = the playlist name (or your `--album`).
- Filenames `01 - Artist - Title.mp3` for playlists, `Artist - Title.mp3` for singles.

Clean up afterwards:

```bash
rm -rf /tmp/ytspot-music /tmp/ytspot-archive.txt /tmp/ytspot-test.json
unset YTSPOT_CONFIG
```

### Testing in Spotify

The part no script can check for you:

1. Spotify **desktop** → Settings → Local Files → turn on *Show songs from* →
   **Add a source** → select your music folder.
2. Restart Spotify; it only rescans on launch.
3. Your Library → Local Files. Tracks should be grouped under the album name,
   with cover art.

Local files don't work in the web player. To hear them on your phone, add them to
a playlist and download that playlist with both devices on the same Wi-Fi.
