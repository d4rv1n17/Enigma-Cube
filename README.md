# Enigma Cube Timer 3.2.1

A speedcubing timer for Windows, built with Python and PyQt5. It works fully offline.

Enigma Cube generates WCA-style scrambles and shows a preview of each one. It times solves like a Stackmat and tracks your averages and personal bests.

## Features

### Smart cube workspace

- **Launch intro:** a 3.6-second animated logo on a cold start, with its caption in the selected interface language. It plays to completion; clicks and keys do not skip it. Disable it in **Settings → Interface**. Reduced motion uses a brief fade; restoring a window or opening the running app again does not replay the intro.
- **Workspace controls:** **Ctrl+K** searches pages and tools; detached windows remember their size and position. Settings are grouped into Timer, Smart cube, Interface and Shortcuts tabs, with staged defaults and a reduced-motion option.
- **Language:** English is the default, independent of the Windows language. Select Russian in **Settings → Interface**; the selection is saved for the next launch, including the launch intro.
- **Updates:** packaged Windows builds check GitHub Releases in the background and download verified newer installers. **Settings → Interface → Updates** provides the automatic-update switch and a manual check. Restart and install when ready; active solves are not interrupted. Downloads require the release asset's SHA-256, and installation stages files with rollback. See [update notes](docs/UPDATES.md).
- **Giiker-style model:** rounded center caps and curved inner sticker corners, with the Enigma logo printed on the white center; small native window icons remain readable at title-bar sizes.
- **Motion:** eased layer turns with a bounded queue, smooth zoom and camera reset, brief orbit inertia and a restrained solved-state accent. The white-center logo keeps its rotation. Pages crossfade, progress bars settle smoothly and notifications fade in and out; reduced motion disables these effects.

- **Live 3D window:** open from **Cube** or **Windows**, orbit with a drag, zoom with the wheel, reset with a double click. **F11** enters full screen; **Escape** exits. Individual layer turns animate from verified state changes.
- **Solve my cube:** an offline 3x3 assistant reads the connected Giiker, calculates a solution in a separate process and checks each physical step. A wrong turn offers recalculation from the current state. The first calculation prepares cached tables. This is guided solving: the user turns the cube.
- **Physical synchronization:** before automatic timing, training checks or solving guidance, use **Cube → Sync physical state**. Match the real stickers to the net, or fill solved faces only when the physical cube is fully solved. A correction is saved per device and decoder and applied to complete packets, so dropped move notifications do not accumulate errors.
- **Solve replay:** new smart-cube solves store their moves and timings. Open a solve to replay it and inspect turns, tempo and pauses. Recordings that do not match the cube's final state are labeled incomplete.
- **Interactive notation studio:** orbitable 3D models for every puzzle: 2x2–7x7, Pyraminx (including tips), Skewb, Megaminx, shape-changing Square-1 and two-sided Clock with linked hands and pins. Choose a move and direction, then play it or open a separate window with step controls, playback speed and full screen. Cube examples use white on top and green towards you.
- **Shared interface:** typography, spacing, cards, focus states, dialog layouts and button roles come from one theme across Timer, Training, Reference, Achievements, settings and detached tools. See [interface and model notes](docs/INTERFACE_AND_MODELS.md).
- **Daily practice:** a configurable review goal, weak-case suggestions and plain instructions in the trainer. Achievements show the nearest pending milestone.
- **Data recovery:** saves are atomic, retain a previous valid snapshot and restore it if the primary JSON file is damaged.

### Training
- **Courses for all 14 events, from beginner to advanced.** Levels are marked *beginner*, *intermediate* and *advanced*:

  | Event | Methods |
  |---|---|
  | 3x3 | Beginner method, Fridrich/CFOP (2-look OLL/PLL, F2L 41, OLL 57, PLL 21), Roux CMLL 42 |
  | 2x2 | Beginner method, Ortega (OLL 7, PBL 6), CLL 40 |
  | 4x4–7x7 | Reduction, 4x4 parity algorithms, 5x5+ edge pairing |
  | Pyraminx | Beginner method, L4E 36 |
  | Skewb | Layer method (2 corner + 16 centre cases) |
  | Megaminx | Beginner method, 4-look last layer |
  | Square-1 | Beginner method |
  | Clock | Beginner method |
  | 3BLD / OH / FMC | Old Pochmann, one-handed tips, FMC basics |

- **342 algorithm cases.** Algorithms come from speedcubedb.com, cubingcheatsheet.com, ruwix.com and ranzha.cubing.net. Every set that has a simulator in the app (all except Megaminx and Clock) is checked by the tests:
  - each algorithm keeps the solved part of the puzzle intact;
  - all cases in a set are different.
- **Case pictures** are generated from the algorithms themselves:
  - 3x3: OLL, PLL with arrows, F2L in 3D, CMLL corners;
  - 2x2 views and 4x4 views;
  - Pyraminx, Skewb and Square-1 diagrams.
- **Course overview:** a progress bar for the whole course, the next step to take and how many cases are due for review.
- **Detailed case pages:** move count, what the algorithm does (e.g. "cycles 3 edges"), how the case looks before the algorithm, and verified alternative algorithms for 78 popular cases.
- **Recognition quiz:** see a case and pick its name from four options (keys 1–4).
- **Spaced-repetition trainer:**
  - Recognise the case, solve it on your cube, reveal the algorithm and rate yourself (1–3).
  - Cases move through Leitner boxes: review now, then after 1 day, 3, 7, 16 and 35 days.
  - New cases are introduced 4 at a time.
- **Notation reference** for every puzzle, with pictures of each move drawn by the built-in simulators.
- **41 achievements** for solving (counts, sub-X singles and averages), learning (lessons and algorithm sets), guided solving and regular practice (day streaks).
- **Multi-window mode:** the **Windows** menu opens any section in its own window: a compact mini timer (**Ctrl+T**), Training, Reference or Achievements (**Ctrl+Shift+1/2/3**). Pin any window on top of the others. Solves from the mini timer go into your current session.

### Timer and statistics

- **14 WCA events:** 2x2–7x7, Pyraminx, Skewb, Megaminx, Clock, Square-1, OH, 3BLD and FMC.
- **Scramble preview:** cube nets for 2x2–7x7 and orbitable 3D states for Pyraminx, Skewb, Megaminx, Square-1 and Clock. The previews are rendered offline.
- **Scramble navigation:** back/forward buttons and **Shift+N / N** browse up to 100 scrambles per session in the current app run. Returning to a scramble restores its preview and smart-cube target; navigation is blocked during a solve.
- **Stackmat-style timer:**
  - Hold Space until the time turns green, then release to start.
  - Optional 15-second WCA inspection with beeps at 8 and 12 s.
  - Automatic +2 and DNF penalties.
- **WCA statistics:**
  - Current and best single, mo3, ao5, ao12, ao50 and ao100.
  - Session mean and standard deviation.
  - A breakdown of any average, with trimmed times in brackets.
- **Charts:** progress (singles, ao5, ao12) and the distribution of your times.
- **PB notifications** for new best singles and averages.
- **Sessions:** unlimited sessions per event, csTimer import and CSV export.
- **Minimal dark UI:**
  - Focus mode hides everything but the time while you solve.
  - Minimal mode (**M**) shows only the scramble and the timer.
  - English and Russian interface.

## Requirements

- Windows 10 or 11 (64-bit)
- About 100 MB of disk space
- A screen of 1280×720 or larger
- No internet connection needed

## Install

1. Download `EnigmaCube-Setup-3.2.1.exe` from the [latest release](https://github.com/d4rv1n17/Enigma-Cube/releases/latest) and run it.
2. If Windows shows **"Windows protected your PC"**, click **More info → Run anyway**. Windows shows this for new apps that don't have a paid code-signing certificate.
3. Choose the folder and shortcuts, then click **Install**. If an older version is installed, the button says **Update**.

The installer has these properties:
- It starts in English; you can select Russian at the top right.
- It doesn't need administrator rights.
- It updates an existing installation in place, including 2.2 installs made with the old Inno Setup installer.
- You can uninstall the app from **Settings → Apps**. You can also delete your solves when you uninstall.
- Your solves are stored in `%APPDATA%\EnigmaTimer` and are kept when you update.

## Keyboard shortcuts

| Key | Action |
|---|---|
| Space | Hold until the time turns green, then release to start |
| Any key / click | Stop the timer |
| Esc | Cancel inspection |
| Ctrl+1 / Ctrl+2 / Ctrl+3 | Mark the last solve OK / +2 / DNF |
| Ctrl+Z | Delete the last solve |
| N | Next scramble (generates one at the end of history) |
| Shift+N | Previous scramble |
| M | Minimal mode |
| Ctrl+E | Enter a time manually (`12.34`, `1:05.20`, `1234`, `DNF`, `14.00+`) |
| Ctrl+, | Settings |

In the trainer: **Space** reveals the algorithm, **1 / 2 / 3** rates it (forgot / hard / knew it), **Esc** goes back.

You can also start the timer with the mouse: press and release on the time.

## Building from source

**Run it during development:**

```
pip install -r requirements.txt
python main.py
```

**Build the installer on Windows:**

1. Install Python 3.8+ from [python.org](https://www.python.org/downloads/). Tick **"Add python.exe to PATH"** during setup.
2. Double-click **`build_installer.bat`**. It installs PyQt5 and PyInstaller and runs `installer/build.py`, which:
   - builds the app;
   - builds the uninstaller;
   - packs the app;
   - creates the setup.
3. When it finishes, the `Output` folder opens with `EnigmaCube-Setup-3.2.1.exe` inside.

**Build on GitHub Actions:** every push and pull request builds the installer automatically. Download it from **Actions → Build Windows installer → EnigmaCube-Setup**. When a new version reaches `main`, the workflow also publishes a GitHub Release with the installer attached.

**Run the tests:**

```
python -m unittest discover -s tests
```

**Release a new version:** change `VERSION` in `enigma_timer/__init__.py`. The build script uses this number everywhere.

## Project structure

```
main.py                  entry point
enigma_timer/
  scramble.py            scramble generators
  cube.py                NxN cube simulator for previews
  fast3.py               fast 3x3 simulator for the training section
  algs.py                algorithm database (beginner, F2L, OLL, PLL)
  learn.py               learning path and spaced repetition
  lessons.py             lesson texts (EN/RU)
  caseview.py            case pictures (OLL, PLL arrows, F2L 3D)
  training.py            Training section and separate Training windows
  puzzles.py             Pyraminx, Skewb and Square-1 simulators for previews
  stats.py               solves, WCA averages, formatting
  storage.py             persistence, csTimer import, CSV export
  window.py              main window and timer state machine
  widgets.py             timer display, preview, charts
  dialogs.py             settings, solve details, about
  theme.py, i18n.py      styling and translations
assets/                  logo and icons (app.ico for the exe)
installer/               custom setup: setup_app.py (window), setup_core.py (logic), build.py
build_installer.bat      one-click installer build
.github/workflows/       automatic installer build on GitHub
tests/                   unit tests (scrambles, stats, every algorithm, setup logic)
```

## Changelog

### 3.2.1: detect updates in existing app folders

- The installer recognises a selected folder containing `EnigmaCube.exe` even when its Windows uninstall registration is missing.
- Selecting or typing another folder immediately updates the Install/Update button, heading and data-preservation note.
- Registry metadata and legacy uninstall commands are used only for the selected installation, preventing an unrelated copy from being removed.
- Update tests cover unregistered app folders and changing the target folder in both interface languages.

### 3.2: smart cubes, interactive 3D and a unified workspace

- Giiker discovery, reconnection and protocol detection; only smart cubes appear in discovery. Physical-state verification, scramble checking and optional automatic timing prevent unverified turns from starting a solve.
- An offline solve assistant with checked steps, recorded-move replay and a Giiker-style model with the Enigma logo on its white center.
- Interactive 3D notation for 2x2–7x7, Pyraminx, Skewb, Megaminx, Square-1 and Clock; separate windows with playback, zoom and fullscreen controls. White-up, green-front cube examples.
- A shared black/yellow interface, responsive toolbars, larger achievement cards and accessible case details in compact training windows.
- A clearer results sidebar: clickable latest/best solves, available averages, explanations, single-click solve details and improved progress/distribution charts.
- Per-session scramble history with back/forward controls and Shift+N / N shortcuts.
- A short optional launch animation, first-run tour, English by default and a saved Russian-language choice. First launch maximizes the workspace; subsequent launches restore the chosen window size and state.
- Background update checks and verified downloads with user-controlled installation, staged replacement and rollback. Atomic data saves and backup recovery.

**Upgrading from 3.1:** download and run the 3.2 installer once. Automatic updates are available starting with 3.2; existing solves and training data are retained.

### 3.1: clearer UI, deeper training, any window
- **Windows** menu: open the mini timer, Training, Reference or Achievements in separate windows, and pin them on top.
- New **mini timer** window that saves solves into the current session.
- Training: course overview page, recognition quiz, facts for each case (move count, what it does, starting position) and verified alternative algorithms.
- New lessons: cross, finger tricks, look-ahead and Roux.
- Clearer timer screen: an empty-state message for new sessions, a key hint, and visible arrows on drop-down lists.

### 3.0: Training
- A new **Training** section with courses for all 14 events, from beginner to advanced. It includes lessons, 342 algorithm cases verified by simulators and a spaced-repetition trainer.
- A notation **Reference** for every puzzle and **Achievements**.
- **Multi-window mode:** Training can be opened in separate windows next to the timer.
- A new custom installer replaces Inno Setup. It installs, updates and uninstalls the app, and switches between RU and EN.
- The 3x3 simulator now supports `x y z`, `M E S` and wide moves (`r`, `Rw`).

### 2.2: minimal redesign
- The UI has no borders or outlines. Cards are a shade lighter than the background, and the right column is now a single card.
- Buttons are quiet text that appears on hover. Yellow is used only where it means something: the selected event, PBs and penalties.
- Events in the header are now text tabs with a yellow underline.
- The scramble no longer sits in a box. The timer uses a lighter font, and there is more spacing.
- New minimal mode (**M**).
- The title bar is dark on Windows 10 and 11.
- The distribution chart now uses horizontal bars and appears after 5 solves.

### 2.1
- New Enigma Cube logo, window icon and exe icon. The UI colours are taken from the logo.
- Scramble previews for Pyraminx, Skewb and Square-1.
- New events: OH, 3BLD (with random `Rw Uw` orientation) and FMC (`R' U' F … R' U' F`).
- A distribution tab next to the progress chart.
- The installer is now built with one click, and the interface language follows the system.
- Fixed a Square-1 model bug that could produce scrambles you couldn't do on a real puzzle.

### 2.0: full rewrite
The app was rewritten from the original prototype. These bugs in the old version were fixed:
- 5x5 stopped generating new scrambles after a solve.
- Pyraminx, Skewb and Megaminx scrambles contained cube moves such as D and F.
- ao5 and ao12 were plain means without trimming and reset every 5 or 12 solves.
- The UI froze on every scramble because of network requests to google.com and an image server.
- The timer started when Space was pressed instead of when it was released.
- Images were loaded relative to the current folder, so the app crashed when launched from elsewhere.
