# PS2 Classics GUI - Mod by Chrisser

A modern Python/Tkinter replacement front-end for the legacy
`PS2Classics_GUI.exe`.

The mod is designed to be placed inside an existing PS2 Classics GUI v2.2.3
installation. It reuses the locally installed tools, templates, covers and
configuration files instead of redistributing them.

## Purpose

The original PS2 Classics GUI is a useful front-end for `ps2classic.exe` and
the existing PS2 Classics package workflow. This mod was created because the
legacy GUI can terminate immediately after an ISO is selected on current
Windows systems, including Windows 11.

The original application was built as a Visual Basic 5 front-end and depends
on the VB5 runtime and legacy controls. Its package also contains older
runtime, DLL and OCX components. The original author has described limitations
of the old VB5 image controls, while support discussions recommend avoiding
spaces and special characters in paths, granting full folder access, running
the application as administrator and, in some cases, adding it to the Windows
DEP exclusion list.

Those workarounds point to compatibility problems in the legacy front-end:
old runtime/control behavior, path handling, permissions and DEP can all be
involved when the GUI begins processing a selected ISO. Community reports
confirm the same immediate ISO-selection crash, but there is no single
authoritative diagnosis proving one universal cause for every system or ISO.

This replacement therefore avoids the VB5/OCX interface layer and implements
the workflow in Python 3 and Tkinter with explicit path handling, validation,
tool discovery, progress reporting and error messages.

The command-line tools, package templates and local data remain external.
This project replaces only the front-end and does not redistribute the
original encryption, packaging or template files.

Original PS2 Classics GUI v2.2.3:

https://www.psx-place.com/resources/ps2-classics-gui.638/

## Main differences

- Native Python 3 and Tkinter interface.
- Modern Windows-compatible GUI without the legacy VB5 front-end.
- Live PS3 XMB-style preview.
- Clickable ICON0, PIC0, PIC1 and game-title areas.
- Automatic source metadata and disc-ID detection.
- Automatic CONFIG, cover, template and tool discovery.
- Raw ISO/BIN encryption and existing ISO.BIN.ENC packaging modes.
- Optional game-specific EDAT workflow through a local `make_npdata.exe`.
- Visible build-readiness checks.
- Collapsible readiness and process-log panels.
- Responsive progress reporting during large file operations.
- Optional package verification and retained build artifacts.
- Normalized output filenames using game title and disc ID.
- No persistent machine-specific settings file.

## Repository scope

This repository is intended to contain only the files written for this mod:

```text
ps2_classics_gui_mod.py
start.bat
build.bat
README.md
.gitignore
```

It intentionally does not include:

- `PS2Classics_GUI.exe`
- `ps2classic.exe`
- `psn_package_npdrm.exe`
- `make_npdata.exe`
- third-party DLL or OCX files
- `PS2U10000`
- `PS2Covers`
- `CONFIGS`
- RAP, RIF, EDAT, ENC, PKG, ISO or BIN files
- game artwork, audio or copyrighted game data
- local application icons or generated EXE builds

## Local setup

1. Download and extract the original PS2 Classics GUI v2.2.3 package.
2. Copy these mod files into its root folder:
   - `ps2_classics_gui_mod.py`
   - `start.bat`
   - `build.bat`
   - `app.ico`
   - `app.png`
3. Keep the original tools and folders in the same root, including the
   `PS2U10000` template and the required package tools.
4. Install Python 3.
5. Install Pillow:

```bat
py -3 -m pip install --upgrade Pillow
```

Expected local structure:

```text
PS2Classics_GUI\
├── ps2_classics_gui_mod.py
├── start.bat
├── build.bat
├── app.ico
├── app.png
├── PS2Classics_GUI.exe
├── ps2classic.exe
├── psn_package_npdrm.exe
├── PS2U10000\
├── PS2Covers\
├── CONFIGS\
└── ...
```

## Running from source

Start with:

```bat
start.bat
```

or:

```bat
py -3 ps2_classics_gui_mod.py
```

The source version requires Python 3, Tkinter and Pillow. Standard Windows
Python installations normally include Tkinter.

## Optional make_npdata support

`make_npdata.exe` is optional and is only required for the game-specific EDAT
mode.

A referenced Make_npdata GUI project and binary can be found here:

https://gitlab.com/Das_PS3/Make_npdata_GUI/-/blob/master/Make%20npdata%20GUI/make_npdata.exe?ref_type=heads

An open-source make_npdata implementation is also available here:

https://github.com/aniruddh22/make_npdata

Third-party binaries are not bundled by this project. Verify their source,
license and integrity before using or redistributing them.

### RAP handling

The mod does not create RAP or RIF license files. Game-specific EDAT mode
requires an existing matching 16-byte RAP file supplied by the user.

The matching RAP can be placed in:

```text
<project root>\
<project root>\exdata\
<project root>\EXDATA\
```

## Local key handling

The source code does not embed the two legacy key literals previously used by
the prototype.

### PS2 Classics EDAT key

The GUI searches the existing local installation for a valid `ps2.key`,
including:

```text
<project root>\ps2.key
<project root>\scetool\ps2.key
```

A 16-byte binary key or a 32-character hexadecimal text key is accepted. If
no valid local `ps2.key` is found, the Klicensee field remains empty and must
be filled by the user before building.

### Package configuration key

The GUI reads the Klicensee from an existing local `package.conf` when one is
available. Otherwise, it uses an all-zero package configuration key.

The PS2 Classics EDAT key remains the relevant key for the encrypted PS2
content. The package configuration key is not embedded in this repository.

Background discussion:

https://www.psx-place.com/threads/template-make_package_npdrm-package-conf-for-ps2classic.17997/

## Building the Windows EXE

Requirements:

- Windows
- Python 3
- pip
- Pillow
- PyInstaller
- local `app.ico`
- local `app.png`

Install build dependencies:

```bat
py -3 -m pip install --upgrade Pillow PyInstaller
```

Run:

```bat
build.bat
```

The builder:

- checks Python 3;
- checks pip;
- checks Pillow;
- checks PyInstaller;
- reads the version from `APP_VERSION`;
- embeds `app.ico` and `app.png`;
- creates a single windowed EXE;
- removes temporary PyInstaller files;
- writes only the finished EXE to `_build`.

Example output:

```text
_build\
└── PS2 Classics GUI - Mod by Chrisser v0.9.8.exe
```

The EXE can remain inside `_build`. The application automatically resolves the
external original GUI tools from the parent project root. It can also be
copied directly into the project root.

## Git setup inside the original GUI folder

The included `.gitignore` uses an allow-list. This lets the Git repository
live directly inside the extracted original GUI folder while tracking only
the source and documentation files created for this mod.

The original GUI distribution, local icons, third-party tools, templates,
keys, game files and generated builds remain untracked.

## Legal and usage notice

This project is an unofficial community front-end and is not affiliated with,
endorsed by or sponsored by Sony Interactive Entertainment.

Use it only with content, backups, keys and licenses that you are legally
authorized to use. The repository does not grant rights to any third-party
software, console files, game data, artwork, keys or licenses.

Removing third-party binaries and data from the repository reduces
redistribution risk, but it does not guarantee that every use of the software
is lawful in every jurisdiction. Repository owners and users remain
responsible for reviewing the laws and licenses that apply to them.
