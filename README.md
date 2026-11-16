# L4D2 Mod Manager

A desktop mod manager for **Left 4 Dead 2** on Linux (AppImage) and Windows.
It reads your installed workshop/loose VPK mods, shows their metadata with
thumbnails, detects file conflicts, lets you organize mods with categories
and groups, and can randomize sets of mods when you start the game.

## Features

- **Mod library** — card grid with thumbnails, titles, authors and sizes.
  Toggle mods on/off (written to the game's `addonlist.txt` with automatic
  backups); a details sidebar shows the full description, workshop page link
  and the files inside each VPK.
- **Metadata rescue** — parses `addoninfo.txt` (including common authoring
  mistakes like `addontittle` typos, misnamed or non-UTF-8 files) and fills
  any missing title/description/tags from the Steam Workshop API, cached
  locally so the API is only called for mods never seen before.
- **Conflict detection** — two mods conflict when they replace the same game
  file. Conflicts are detected from the actual VPK contents, the winner is
  resolved from load order (`addonlist.txt` position), and the Conflicts tab
  lets you disable a mod or re-prioritize the winner with one click.
- **Categories** — a sidebar in the Mods tab filters the grid by a curated
  two-level taxonomy built from Steam workshop tags (Weapons → SMG, Special
  Infected → Tank, Survivors → Rochelle, ...), plus your own **custom
  categories** for anything the authors got wrong.
- **Groups** — organize mods into named groups, assign from the mod details
  panel, enable/disable a whole group at once.
- **Random groups + Start L4D2** — a random group is a set of mods *and/or*
  groups; on launch each one picks exactly one member to enable (and
  disables the rest). The **▶ Start L4D2** button rolls everything, applies
  it, shows launch feedback, and starts the game via Steam.

## How it works

- **Scan** — VPKs are discovered in `left4dead2/addons/` (loose) and
  `addons/workshop/`. Each archive is opened with the
  [vpk](https://pypi.org/project/vpk/) library to read `addoninfo.txt`,
  internal file paths (for conflicts) and the preview thumbnail.
- **Steam enrichment** — mods whose `addoninfo.txt` is missing or unusable
  get their title/description/tags from
  `ISteamRemoteStorage/GetPublishedFileDetails` (no API key needed). Results
  are cached in the store, so normal startups make zero network calls; only
  newly subscribed mods trigger one small batch request.
- **Enabling mods** — the game reads `left4dead2/addonlist.txt` (1 = enabled,
  0 = disabled). The manager treats its own store as the source of truth and
  rewrites that file (with a `.bak` backup) on every change. The file's entry
  order is the load priority: **the mod listed higher wins a conflict**.
  Toggling never reorders entries, so priorities are preserved.
- **Conflicts** — an inverted index over every replaced file path finds mods
  that overlap; "active" conflicts are pairs where both mods are enabled.
  "Make winner" moves a mod just above the group's top entry in
  `addonlist.txt`.
- **Randomization** — each random group rolls one member (uniformly). A
  group member contributes all of its mods. A mod in multiple groups stays
  enabled if any roll picked it. Mods outside random groups are never
  touched. The game is launched through `steam://run/550` and a popup
  confirms the process actually started.

## Data locations

| Path | Contents |
|---|---|
| `~/.config/l4d2-mod-manager/settings.json` | game directory |
| `~/.config/l4d2-mod-manager/store.json` | enabled state, tags, groups, random groups, workshop cache |
| `~/.cache/l4d2-mod-manager/thumbs/` | extracted thumbnails for loose VPKs |

Nothing is written inside the game folder except `addonlist.txt` (+ `.bak`).

## Install

### AppImage (Linux)

Download `l4d2-mod-manager-<version>-x86_64.AppImage` from the
[releases page](../../releases), make it executable and run it:

```bash
chmod +x l4d2-mod-manager-*-x86_64.AppImage
./l4d2-mod-manager-*-x86_64.AppImage
```

On systems without FUSE: `./l4d2-mod-manager-*-x86_64.AppImage --appimage-extract-and-run`

The AppImage is built on Ubuntu 22.04 and runs on any x86_64 distro with
glibc 2.35+ (Debian 12+, Ubuntu 22.04+, Fedora, Arch, ...).

### Windows

Download `l4d2-mod-manager-<version>-windows-x64.zip` from the releases
page, extract it anywhere and run `l4d2-mod-manager.exe`.

### From source

Requires Python 3.14+ and [poetry](https://python-poetry.org):

```bash
poetry install
poetry run mod-manager
```

On first start the app auto-detects your Steam installation (or asks you to
point it at the game folder, e.g.
`.../steamapps/common/Left 4 Dead 2`).

## Usage

- **Mods tab** — the main grid. Click a card for details; use its checkbox
  to enable/disable. Selecting a mod highlights its *active* conflict
  partners in red. The categories sidebar on the left filters the grid
  (second level refines, e.g. Weapons › SMG).
- **Add Category / Add to Group / Add to Random** — buttons in the details
  sidebar assign the selected mod to custom categories, groups, or random
  groups. Custom categories and groups can also be managed from the
  *Categories* menu and the *Groups* tab.
- **Groups tab** — create/rename/delete groups, add/remove mods, enable or
  disable an entire group.
- **Randomize tab** — build random groups (members can be mods or whole
  groups), then use **Randomize** (dry run) or **▶ Start L4D2**. The same
  Start button also lives on the menu bar.
- **Conflicts tab** — active conflict groups with winners, one-click
  resolve (disable) or re-prioritize (make winner). The tab enables itself
  only when there is something to review.

## Building from source

```bash
# Linux AppImage (output in dist/)
poetry run bash scripts/build_appimage.sh

# Windows zip (run on Windows, output in dist/)
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

Both scripts bundle the app with
[PyInstaller](https://pyinstaller.org), package it, and run a headless
self-test. Continuous integration (`.github/workflows/build.yml`) runs the
same builds on every push and publishes GitHub Releases for `v*` tags.

## Development

```bash
poetry run pytest                    # unit tests
poetry run python scripts/smoke.py   # headless UI smoke test (offscreen)
```

Project layout: `src/mod_manager/` (app code: scanning, conflicts,
categories, groups, randomizer, store, PySide6 UI), `tests/` (pytest),
`scripts/` (build + icon + smoke), `packaging/` (desktop file, icons,
AppRun).

## License

GPL-3.0 — see [LICENSE.txt](LICENSE.txt).
