# ytspot

Put YouTube music into Spotify.

You give it a YouTube link. It downloads the audio, turns it into an MP3, names
it properly, adds the cover art, and saves it where Spotify can find it.

```
$ ytspot "https://www.youtube.com/playlist?list=PL..."
48 track(s) from playlist "Late Night Drive"

[ 1/48] Tame Impala - Borderline ... ok
[ 2/48] Khruangbin - Time (You and I) ... skipped (already imported)
[ 3/48] Men I Trust - Show Me How ... ok

Imported 45, skipped 2, failed 1
```

Works with single videos and whole playlists. Run it again on the same link and
it only grabs the new stuff. If one video is broken, the rest still download.

## 1. Install two things first

**Mac:**

```bash
brew install uv ffmpeg
```

**Windows** (in PowerShell):

```powershell
winget install astral-sh.uv
winget install Gyan.FFmpeg
```

Then close PowerShell and open it again.

**Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
sudo apt install ffmpeg
```

What they're for: **ffmpeg** makes the MP3 files, **uv** runs the program.
You don't need to install Python yourself.

## 2. Install ytspot

```bash
git clone https://github.com/aashishdangal/youspot.git ytspot
cd ytspot
uv sync
uv tool install .
```

That's it. You can now type `ytspot` from any folder.

If your terminal says `ytspot: command not found`, run `uv tool update-shell`
and open a new terminal window.

## 3. Run it once

```bash
ytspot "https://www.youtube.com/watch?v=..."
```

The first time, it asks where to save your music. Press Enter to use the
suggested folder (`~/Music/ytspot`), or type your own. It remembers your answer.

## 4. Tell Spotify where to look

Do this once, in the Spotify desktop app:

1. Click your **profile picture** (top right) → **Settings**
2. Scroll down to **Library**
3. Turn on **Show Local Files**
4. Click **Add a source**
5. Pick the folder from step 3 (the main folder, not a folder inside it)
6. **Quit Spotify completely and open it again.** It only looks for new music
   when it starts.
7. Go to **Your Library** → **Local Files**

Your songs are there, grouped into albums.

**Tip:** right-click the songs and add them to a playlist. Spotify won't let you
search for local files or shuffle them until they're in a playlist.

The Spotify website can't play local files, only the app can.

## How to use it

```bash
# one video
ytspot "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# a whole playlist
ytspot "https://www.youtube.com/playlist?list=PL..."

# just the first 10 songs of a playlist
ytspot "https://www.youtube.com/playlist?list=PL..." --items 1-10

# see what it would do, without downloading anything
ytspot "https://www.youtube.com/playlist?list=PL..." --dry-run
```

| Add this | To do this |
| --- | --- |
| `--items 1-10` | Only part of a playlist. Also works like `1,5,8` |
| `--album "My Mix"` | Name the album yourself |
| `--dry-run` | Show what would happen, download nothing |
| `--quality 192` | Smaller files (320 is the default) |
| `--no-archive` | Download something again, even if you already have it |

To see or change where music is saved:

```bash
ytspot config
ytspot config --set-music-dir ~/Music/ytspot
```

## What you end up with

A playlist becomes a folder of numbered songs:

```
~/Music/ytspot/
├── Late Night Drive/
│   ├── 01 - Tame Impala - Borderline.mp3
│   └── 02 - Men I Trust - Show Me How.mp3
└── YouTube Imports/
    └── Aphex Twin - Avril 14th.mp3
```

Single videos go in a folder called **YouTube Imports**. Playlists get their own
folder, named after the playlist.

Each song gets a title, an artist, the playlist name as its album, a track
number, and the video thumbnail as cover art.

**For the best results, use links from `music.youtube.com`.** Those pages tell
us the real artist and song name. Normal YouTube links only have the video
title, so ytspot has to guess by splitting it at the dash
("Artist - Song"). It usually gets it right.

## If something goes wrong

**"FFmpeg was not found"**
Go back to step 1, then open a new terminal window.

**My songs aren't in Spotify**
1. Did you *fully* quit Spotify and reopen it? Closing the window isn't enough.
   Use Cmd+Q on Mac, or the tray icon on Windows.
2. Check Settings → Library. Is **Show Local Files** still on, and is your
   folder still listed? Spotify sometimes forgets it after an update.
3. Type `ytspot config` to double-check where the files are being saved.

**One video failed**
Normal. Private, deleted, and country-blocked videos can't be downloaded.
ytspot tells you which ones failed and carries on with the rest.

**Everything failed**
YouTube changed something. Updating usually fixes it:

```bash
cd ytspot
uv sync --upgrade
uv tool install . --force
```

**No cover art on a song**
That video didn't have a usable thumbnail. Everything else still works.

## Notes

- Your settings live in `~/.config/ytspot/config.json`
  (`%APPDATA%\ytspot\config.json` on Windows).
- ytspot keeps a list of what you've already downloaded, which is why running
  it twice doesn't give you duplicates.
- Songs are saved at 320kbps with ID3v2.3 tags, which is the format Spotify
  reads most reliably.

**Want more detail?** [`command.md`](command.md) lists every command and option,
and explains how to test everything.

## For developers

```bash
uv run pytest                           # quick tests
uv run python scripts/smoke_test.py     # full test, downloads real files
```
