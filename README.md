<p align="center">
  <img src="app.png" alt="PS2 Classics GUI - Mod by Chrisser" width="180">
</p>

<h1 align="center">PS2 Classics GUI - Mod by Chrisser</h1>

<p align="center">
  A modern Python/Tkinter front-end for PS2 Classics GUI v2.2.3, with a live
  XMB preview, automatic metadata and image-type detection, CONFIG updates,
  PSDevWiki compatibility lookup, local key handling and a Windows EXE builder.
</p>

The original Visual Basic 5 front-end can crash on modern Windows systems
while selecting or processing files. This project replaces only that legacy
interface and continues to use the original toolchain installed locally by
the user.

## Features

- Live PS3 XMB-style preview with clickable ICON0, PIC0, PIC1 and game-title areas.
- Automatic game metadata and disc-ID detection.
- Automatic image-type detection for 2048-byte DVD and 2352-byte CD/BIN images,
  with manual override still available.
- Automatic PS2 CONFIG lookup by disc ID.
- **Update Configs** downloads the latest PS2 CONFIG collection from webMAN-MOD
  into the local `CONFIGS` folder while keeping the expected subfolder layout.
- **Re-scan Configs** checks the selected game again after an update or local
  CONFIG change.
- PSDevWiki PS2 Classics compatibility lookup with region-aware status display.
- Expandable **Notes** section for compatibility notes when available.
- Local compatibility cache so the last downloaded list remains usable if the
  website is temporarily unavailable.
- Automatic local `ps2.key` detection, restoration/generation from available
  local original-package data, validation and reuse.
- Raw ISO/BIN encryption and existing ISO.BIN.ENC packaging workflows.
- Optional game-specific EDAT workflow when the required local files are available.
- Collapsible build-readiness and process-log sections with responsive progress.
- Normalized PKG filenames using the game title and detected disc ID.
- Integrated PyInstaller production build through `build.bat`.

## Preview

![PS2 Classics GUI - Mod by Chrisser preview](preview.jpg)

## Setup

### Requirements

- Windows 10 or Windows 11
- [PS2 Classics GUI v2.2.3 by Aldo Vargas](https://www.psx-place.com/resources/ps2-classics-gui.638/)
- Python 3 with Tkinter and Tcl/Tk
- Pillow
- PyInstaller only when building the EXE

Install the Python packages:

```bat
py -3 -m pip install --upgrade Pillow PyInstaller
```

### Installation

1. Download and extract the original `ps2classics_GUI_2.2.3` package.
2. Copy these files into the root of that folder:
   - `ps2_classics_gui_mod.py`
   - `start.bat`
   - `build.bat`
   - `app.ico`
   - `app.png`
3. Keep the original package files and folders in place.

The mod automatically detects and reuses the locally installed tools,
templates, CONFIG files, covers and key files.

## How to run

Start the source version with:

```bat
start.bat
```

or:

```bat
py -3 ps2_classics_gui_mod.py
```

The normal workflow is handled through the GUI. No terminal commands are
required for package creation.

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

The EXE includes Python, Tkinter and Pillow. The original PS2 Classics GUI
toolchain remains external and must still be present in the same installation.

## Notes

- The GUI searches the original installation for the files required by each
  workflow.
- Missing requirements are shown in the collapsible build-readiness panel.
- A matching PS2 CONFIG is inserted automatically when one is found.
- CONFIG updates are written into the existing local `CONFIGS` folder.
- Compatibility information is informational only and does not block a build.
- Existing local key material can be detected, restored to the project root,
  validated and reused automatically.
- The application does not store machine-specific paths in a settings file.

## Legal notice

This repository contains only the replacement front-end, its own assets,
documentation and build scripts. It does not provide the original toolchain
or third-party/proprietary content.

This is an unofficial community project and is not affiliated with or
endorsed by Sony Interactive Entertainment, Aldo Vargas or the authors of the
external tools it can call.

Use the software only with content, backups, tools, keys and licenses that you
are legally authorized to use. This project is not intended for piracy or
unlawful circumvention, and the author expressly distances himself from such
use.
