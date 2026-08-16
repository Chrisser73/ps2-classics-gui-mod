<p align="center">
  <img src="app.png" alt="PS2 Classics GUI - Mod by Chrisser" width="180">
</p>

<h1 align="center">PS2 Classics GUI - Mod by Chrisser</h1>

<p align="center">
  A modern Python/Tkinter front-end for PS2 Classics GUI v2.2.3, with a live
  XMB preview, automatic metadata and image-type detection, CONFIG updates,
  local compatibility data, QoL improvements and a Windows EXE builder.
</p>

#### Why?

The original Visual Basic 5 front-end can crash on modern Windows systems
while selecting or processing files. This project replaces only that legacy
interface and continues to use the original toolchain installed locally by
the user.

## Features

- Live XMB-style preview with clickable ICON0, PIC0, PIC1 and game-title areas.
- Automatic ICON0, PIC0 and PIC1 normalization from JPG/PNG sources. Images keep their aspect ratio, are centered on transparent 320x176, 1000x560 and 1920x1080 canvases.
- Automatic metadata, ID and image-type detection for DVD/CD.
- Automatic CONFIG lookup and insertion by ID.
- **Update Configs** downloads the current CONFIG archive into the existing local `CONFIGS` folder.
- **Re-scan Configs** checks the selected game again after an update or local CONFIG change.
- Local PS2 Classics compatibility cache with expandable compatibility notes.
- Optional title-map refresh for improved ID to title matching.
- Automatic detection and restoration/generation of required local files.
- Collapsible build-readiness panel showing missing requirements.
- Options for retaining build artifacts for inspection.
- Extended post-build verification.
- Collapsible process-log section.
- Integrated PyInstaller production build through `build.bat`.

## Preview

![PS2 Classics GUI - Mod by Chrisser preview](preview.jpg)

## Setup

### Requirements

- Windows 10 or Windows 11
- PS2 Classics GUI v2.2.3 by Aldo Vargas from psx-place
- Python 3 with Tkinter and Tcl/Tk
- Pillow
- PyInstaller only when building the EXE

Install the Python packages:

```bat
py -3 -m pip install --upgrade Pillow PyInstaller
```

### Installation

1. Download and extract the original `ps2classics_GUI_2.2.3` package.
2. Copy these files into the root of that folder (and keep the original package files and folders in place):
   - `ps2_classics_gui_mod.py`
   - `start.bat`
3. (optional)
   - `build.bat` (build .exe)
   - `app.ico` (for .exe build)
   - `app.png` (for .exe build)
   - `comp_cache.db` (compatibility check)

The mod automatically detects and reuses the locally installed tools,
templates, CONFIG files, covers and so on...

## How to run

Start the source version with:

```bat
start.bat
```

or:

```bat
py -3 ps2_classics_gui_mod.py
```

## Building the Windows EXE

Make sure Python 3, pip, Tkinter/Tcl-Tk, Pillow and PyInstaller are installed,
then run:

```bat
build.bat
```

The finished EXE is written to:

```text
_build\
```

Copy the generated EXE from `_build` into the root of
`ps2classics_GUI_2.2.3` before using it normally.

The original toolchain remains external and must still be present in the same installation.

## Legal notice

## Legal notice

This repository contains an independently developed replacement front-end and
only includes its own source code, assets, documentation and build scripts.

It does **not** contain, redistribute or provide:

- Source code copied from the original PS2 Classics GUI or other third-party software.
- Decompiled, disassembled or otherwise extracted proprietary code.
- Proprietary binaries, executables, libraries or components from the original toolchain.
- Copyrighted files.
- Protected material.
- Proprietary templates, assets or resources belonging to third parties.

The project is designed only to provide a replacement user interface and to
interoperate with tools and files that the user supplies separately and is
legally authorized to use.

References to PlayStation, PS2, PS3, PS2 Classics, Sony, Aldo Vargas or other
third-party products and projects are used only for identification,
compatibility and interoperability purposes. No ownership of third-party
names, trademarks, software or assets is claimed.

This is an unofficial community project and is not affiliated with, sponsored
by or endorsed by Sony Interactive Entertainment, Aldo Vargas or the authors
of any external tools it can use.

Users are responsible for obtaining and using any external software, game content, and other files legally. This project is not intended to facilitate piracy, copyright infringement or unlawful circumvention of technological protection measures.

If you believe that material in this repository infringes your rights, please
contact the repository owner so the matter can be reviewed and addressed.
