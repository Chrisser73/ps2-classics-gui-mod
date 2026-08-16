import difflib
import hashlib
import json
import os
import queue
import re
import shutil
import sqlite3
import struct
import subprocess
import tempfile
import threading
import time
import tkinter as tk
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None
    ImageOps = None
    ImageTk = None


class _CompatibilityTableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._in_row = False
        self._in_cell = False
        self._cells = []
        self._cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "tr":
            self._in_row = True
            self._cells = []
            return

        if self._in_row and tag in {"td", "th"}:
            self._in_cell = True
            self._cell = {
                "parts": [],
                "class": attrs.get("class", ""),
                "meta": [],
            }
            return

        if self._in_cell and self._cell is not None:
            title = attrs.get("title")
            if title:
                self._cell["meta"].append(title)
            if tag in {"br", "div", "li", "p"}:
                self._cell["parts"].append(" | ")

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self._in_cell:
            text = "".join(self._cell["parts"])
            text = re.sub(r"\s+", " ", text).strip(" |")
            self._cell["text"] = text
            self._cells.append(self._cell)
            self._cell = None
            self._in_cell = False
            return

        if tag == "tr" and self._in_row:
            if self._cells:
                self.rows.append(self._cells)
            self._cells = []
            self._in_row = False

    def handle_data(self, data):
        if self._in_cell and self._cell is not None:
            self._cell["parts"].append(data)


class _DataCenterListParser(HTMLParser):
    SERIAL_RE = re.compile(
        r"\b(?:SLUS|SLES|SCUS|SCES|SLPM|SLPS|SCPS|SCAJ|SCKA|"
        r"SCED|TCES|TCUS|PBPX|PAPX|PCPX|SCCS)-[0-9]{5}\b",
        re.IGNORECASE,
    )

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.entries = {}
        self._in_row = False
        self._in_cell = False
        self._cells = []
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._in_row = True
            self._cells = []
        elif self._in_row and tag in {"td", "th"}:
            self._in_cell = True
            self._parts = []
        elif self._in_cell and tag in {"br", "div", "p"}:
            self._parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self._in_cell:
            value = re.sub(r"\s+", " ", "".join(self._parts)).strip()
            self._cells.append(value)
            self._parts = []
            self._in_cell = False
            return

        if tag == "tr" and self._in_row:
            self._store_row()
            self._cells = []
            self._in_row = False

    def handle_data(self, data):
        if self._in_cell:
            self._parts.append(data)

    def _store_row(self):
        for index, cell in enumerate(self._cells):
            match = self.SERIAL_RE.search(cell)
            if not match:
                continue

            serial = match.group(0).upper()
            title = ""
            for candidate in self._cells[index + 1:]:
                candidate = candidate.strip()
                if candidate and not self.SERIAL_RE.fullmatch(candidate):
                    title = candidate
                    break

            if title:
                self.entries.setdefault(serial, title)
            return


class PS2ClassicsGUIMod:
    APP_VERSION = "1.0.0"
    APP_NAME = "PS2 Classics GUI - Mod by Chrisser"
    APP_ID = "Chrisser.PS2ClassicsGUIMod"
    EMPTY_PACKAGE_KLICENSEE = "0" * 32

    PACKAGE_IMAGE_SIZES = {
        "ICON0.PNG": (320, 176),
        "PIC0.PNG": (1000, 560),
        "PIC1.PNG": (1920, 1080),
    }

    CONFIG_ARCHIVE_URLS = (
        "https://codeload.github.com/aldostools/webMAN-MOD/zip/refs/heads/master",
        "https://github.com/aldostools/webMAN-MOD/archive/refs/heads/master.zip",
    )
    CONFIG_ARCHIVE_PATH = "_Projects_/updater/PS2CONFIG/USRDIR/CONFIG/"
    DATACENTER_URLS = {
        "PAL-EU": "https://psxdatacenter.com/psx2/plist2.html",
        "NTSC-U": "https://psxdatacenter.com/psx2/ulist2.html",
        "NTSC-J/Asia": "https://psxdatacenter.com/psx2/jlist2.html",
    }

    COMPATIBILITY_CACHE_FILE = "comp_cache.db"
    COMPATIBILITY_LOCAL_HTML_NAMES = (
        "PS2 Classics Emulator Compatibility List - PS3 Developer wiki.html",
        "PS2_Classics_Emulator_Compatibility_List.html",
    )

    COMPATIBILITY_COLORS = {
        "PS2 Classic": ("#0088ee", "#ffffff"),
        "Playable": ("#99dd99", "#0055bb"),
        "Minor Issues": ("#eeee88", "#0055bb"),
        "Major Issues": ("#ee9933", "#772222"),
        "Unplayable": ("#ee4444", "#772222"),
        "Available": ("#bbbbbb", "#555555"),
        "Not Available": ("#dddddd", "#888888"),
    }

    # Shared UI theme
    COLOR_BG = "#1e1e1e"
    COLOR_PANEL = "#292929"
    COLOR_PANEL_ACTIVE = "#333333"
    COLOR_TEXT = "#ffffff"
    COLOR_TEXT_SOFT = "#dddddd"
    COLOR_TEXT_MUTED = "#cccccc"
    COLOR_DESCRIPTION = "#969696"
    COLOR_DESCRIPTION_DARK = "#8f8f8f"
    COLOR_LINK = "#69a7ff"
    COLOR_ENTRY_BG = "#f4f4f4"
    COLOR_ENTRY_FG = "#111111"
    COLOR_LOG_BG = "#101010"
    COLOR_LOG_FG = "#41e66c"
    COLOR_BUTTON = "#2d9b58"
    COLOR_BUTTON_ACTIVE = "#237c46"

    FONT_TITLE = ("Segoe UI", 17, "bold")
    FONT_PREVIEW_TITLE = ("Segoe UI", 13, "bold")
    FONT_SECTION = ("Segoe UI", 10, "bold")
    FONT_BOLD = ("Segoe UI", 9, "bold")
    FONT_BODY = ("Segoe UI", 9)
    FONT_SMALL = ("Segoe UI", 8)
    FONT_BUTTON = ("Segoe UI", 12, "bold")
    FONT_MONO = ("Consolas", 9)

    def __init__(self, root):
        self.root = root
        self.root.title(f"{self.APP_NAME} · v{self.APP_VERSION}")
        self.root.geometry("1180x840")
        self.root.minsize(1040, 720)
        self.root.configure(bg=self.COLOR_BG)

        if getattr(sys, "frozen", False):
            # Directory containing the generated EXE.
            exe_dir = Path(sys.executable).resolve().parent

            # Resolve external tools from the project root.
            if exe_dir.name.casefold() == "_build":
                self.script_dir = exe_dir.parent
            else:
                self.script_dir = exe_dir

            # Resolve embedded PyInstaller resources.
            self.resource_dir = Path(
                getattr(sys, "_MEIPASS", exe_dir)
            )
        else:
            self.script_dir = Path(__file__).resolve().parent
            self.resource_dir = self.script_dir

        # Window icons embedded by PyInstaller.
        ico_path = self.resource_dir / "app.ico"
        png_path = self.resource_dir / "app.png"
        self.window_icon = None

        # Keep the PhotoImage reference for the application lifetime.
        if png_path.is_file():
            try:
                self.window_icon = tk.PhotoImage(file=str(png_path))
                self.root.iconphoto(True, self.window_icon)
            except tk.TclError as error:
                print(f"Could not load PNG icon: {error}")

        # Prefer the multi-resolution ICO for Windows title bars.
        if os.name == "nt" and ico_path.is_file():
            try:
                self.root.iconbitmap(str(ico_path))
            except tk.TclError as error:
                print(f"Could not load ICO icon: {error}")

        # Session-only state; no machine-specific settings file.
        self.last_dirs = {}
        self.auto_asset_paths = {}
        self.manual_asset_paths = {}
        self.cleared_assets = set()
        self.building = False
        self.disc_id_cache_path = None
        self.disc_id_cache_value = None
        self.auto_config_path = ""
        self.auto_image_type_path = None
        self.config_update_running = False
        self.config_update_queue = queue.Queue()
        self.compatibility_queue = queue.Queue()
        self.compatibility_after_id = None
        self.compatibility_request_id = 0
        self.compatibility_spinner_after_id = None
        self.compatibility_spinner_index = 0
        self.compatibility_notes_expanded = False
        self._local_compatibility_rows = None
        self.compat_cache_running = False
        self.compat_cache_queue = queue.Queue()
        self.compatibility_source_override = None
        self._source_refresh_after_id = None
        self._last_source_refresh_path = None

        # Build source
        self.input_mode = tk.StringVar(value="raw")
        self.iso_path = tk.StringVar()
        self.edat_source_path = tk.StringVar()
        self.detected_disc_id = tk.StringVar()
        self.create_verification_report = tk.BooleanVar(value=False)
        self.create_individual_edat = tk.BooleanVar(value=False)
        self.keep_encrypted_artifacts = tk.BooleanVar(value=False)
        self.status_text = tk.StringVar(value="Ready")
        self.config_update_status = tk.StringVar(value="")
        self.compatibility_status = tk.StringVar(value="Not checked")
        self.compatibility_match = tk.StringVar(value="")
        self.compatibility_notes = tk.StringVar(value="")
        self.image_type_detection = tk.StringVar(value="")

        # Optional package assets
        self.icon0_path = tk.StringVar()
        self.pic0_path = tk.StringVar()
        self.pic1_path = tk.StringVar()
        self.snd0_path = tk.StringVar()
        self.param_hip_path = tk.StringVar()
        self.vmc_path = tk.StringVar()
        self.eid_root_key_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.make_npdata_path = tk.StringVar()

        # PKG metadata populated from source files.
        self.game_title = tk.StringVar()
        self.content_id = tk.StringVar()
        self.title_id = tk.StringVar()
        self.version = tk.StringVar()

        # Local encryption state
        default_klicensee = self.load_ps2_klicensee()
        self.package_klicensee = self.load_package_klicensee()
        self.klicensee = tk.StringVar(value=default_klicensee)
        self.ps2_key_required = self.ps2_key_file is None
        self.create_project_ps2_key = tk.BooleanVar(
            value=self.ps2_key_required
        )
        self.ps2_key_status = tk.StringVar()
        self.image_type = tk.StringVar(value="DVD5 / DVD9")
        self.target_type = tk.StringVar(value="CEX")
        self.add_limg = tk.BooleanVar(value=True)
        self.encrypt_vmc = tk.BooleanVar(value=False)

        self.preview_photo = None
        self._preview_after_id = None

        self.build_ui()
        self.load_existing_assets()
        self.load_existing_tools()
        self.root.after(100, self.update_live_preview)
        self.root.after(150, self.poll_config_update_queue)
        self.root.after(150, self.poll_compatibility_queue)
        self.root.after(150, self.poll_compat_cache_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # -------------------------------------------------------
    # Session paths
    # -------------------------------------------------------

    def get_initial_dir(self, key):
        candidate = self.last_dirs.get(key)
        if candidate and os.path.isdir(candidate):
            return candidate
        return str(self.script_dir)

    def remember_path(self, key, selected_path):
        if not selected_path:
            return

        path = Path(selected_path)
        directory = path if path.is_dir() else path.parent

        if directory.is_dir():
            self.last_dirs[key] = str(directory)

    def on_close(self):
        self.stop_compatibility_spinner()
        self.root.destroy()

    @staticmethod
    def parse_klicensee(data):
        """Parse a binary key or a hexadecimal Klicensee value."""
        if len(data) == 16:
            return data.hex().upper()

        text = data.decode("ascii", errors="ignore")
        match = re.search(
            r"(?i)Klicensee\s*=\s*(?:0x)?([0-9a-f]{32})",
            text,
        )
        if not match:
            match = re.fullmatch(
                r"\s*(?:0x)?([0-9a-f]{32})\s*",
                text,
                flags=re.IGNORECASE,
            )
        return match.group(1).upper() if match else ""

    def iter_local_files(self, filename):
        """Yield matching local files outside generated folders."""
        preferred = (
            self.script_dir / filename,
            self.script_dir / "scetool" / filename,
            self.script_dir / "PS2U10000" / filename,
        )
        seen = set()

        for candidate in preferred:
            if candidate.is_file():
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield candidate

        try:
            for candidate in self.script_dir.rglob(filename):
                if not candidate.is_file():
                    continue
                if any(
                    part.casefold() in {
                        ".git",
                        "_build",
                        "__pycache__",
                    }
                    for part in candidate.parts
                ):
                    continue
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield candidate
        except OSError:
            return

    def load_ps2_klicensee(self):
        """Load the root key or a local fallback from the original package."""
        self.ps2_key_file = None
        self.ps2_key_source_file = None
        self.ps2_klicensee_source = None
        self.ps2_klicensee_source_kind = None

        root_key = self.script_dir / "ps2.key"
        if root_key.is_file():
            try:
                value = self.parse_klicensee(root_key.read_bytes())
            except OSError:
                value = ""

            if value:
                self.ps2_key_file = root_key
                self.ps2_key_source_file = root_key
                self.ps2_klicensee_source = root_key
                self.ps2_klicensee_source_kind = "root ps2.key"
                return value

        preferred_sources = (
            self.script_dir / "scetool" / "ps2.key",
            self.script_dir / "PS2U10000" / "ps2.key",
        )
        seen = {root_key.resolve()}

        for candidate in preferred_sources:
            if not candidate.is_file():
                continue

            try:
                resolved = candidate.resolve()
                value = self.parse_klicensee(candidate.read_bytes())
            except OSError:
                continue

            seen.add(resolved)
            if value:
                self.ps2_key_source_file = candidate
                self.ps2_klicensee_source = candidate
                self.ps2_klicensee_source_kind = "fallback ps2.key"
                return value

        try:
            candidates = self.script_dir.rglob("ps2.key")
        except OSError:
            candidates = ()

        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except OSError:
                continue

            if resolved in seen or not candidate.is_file():
                continue

            if any(
                part.casefold() in {
                    ".git",
                    "_build",
                    "__pycache__",
                }
                for part in candidate.parts
            ):
                continue

            try:
                value = self.parse_klicensee(candidate.read_bytes())
            except OSError:
                continue

            if value:
                self.ps2_key_source_file = candidate
                self.ps2_klicensee_source = candidate
                self.ps2_klicensee_source_kind = "fallback ps2.key"
                return value

        return ""

    def load_package_klicensee(self):
        """Load a local package key or use an all-zero package key."""
        self.package_klicensee_source = None

        for candidate in self.iter_local_files("package.conf"):
            try:
                value = self.parse_klicensee(candidate.read_bytes())
            except OSError:
                continue
            if value:
                self.package_klicensee_source = candidate
                return value

        return self.EMPTY_PACKAGE_KLICENSEE

    def find_rap2rifkey(self):
        """Find the local RAP-to-klicensee converter."""
        return self.find_tool_recursive(
            "rap2rifkey.exe",
            "rap2rifkey",
        )

    def find_placeholder_rap(self):
        """Find the RAP matching the local PS2 Classics placeholder."""
        placeholder = self.get_placeholder_identity()
        content_id = str(placeholder.get("content_id", "")).strip()

        if not content_id:
            return None

        return self.find_rap_file(content_id)

    def get_ps2_key_generation_source(self):
        """Return the local converter and matching placeholder RAP."""
        converter = self.find_rap2rifkey()
        rap_path = self.find_placeholder_rap()

        if not converter or not rap_path:
            return None

        return converter, rap_path

    def generate_project_ps2_key_from_rap(self):
        """Generate and verify the root ps2.key from the placeholder RAP."""
        generation_source = self.get_ps2_key_generation_source()
        if not generation_source:
            raise RuntimeError(
                "Automatic ps2.key generation requires rap2rifkey.exe and "
                "the RAP matching the local PS2 Classics placeholder."
            )

        converter, rap_path = generation_source
        temporary_output = self.script_dir / "ps2.key.generated.tmp"
        temporary_output.unlink(missing_ok=True)

        try:
            self.run_command(
                [
                    converter,
                    rap_path,
                    temporary_output,
                ],
                converter.parent,
                stage="Generating ps2.key from the placeholder RAP…",
            )

            if not temporary_output.is_file():
                raise RuntimeError(
                    "rap2rifkey.exe did not create an output key file."
                )

            if temporary_output.stat().st_size != 16:
                raise RuntimeError(
                    "The key generated by rap2rifkey.exe is not 16 bytes."
                )

            key_bytes = temporary_output.read_bytes()
            value = self.parse_klicensee(key_bytes)

            if not re.fullmatch(r"[0-9A-F]{32}", value):
                raise RuntimeError(
                    "The key generated by rap2rifkey.exe is invalid."
                )

            target = self.write_project_ps2_key(key_bytes)
            self.klicensee.set(value)
            self.log(
                "ps2.key generated from placeholder RAP: "
                f"{rap_path.name}"
            )
            return target
        finally:
            temporary_output.unlink(missing_ok=True)

    @staticmethod
    def normalize_klicensee(value):
        """Normalize a user-entered hexadecimal Klicensee."""
        normalized = re.sub(r"\s+", "", str(value)).upper()
        if normalized.startswith("0X"):
            normalized = normalized[2:]
        return normalized

    def current_ps2_key_value(self):
        """Return the value from the currently detected ps2.key."""
        path = self.ps2_key_file
        if not path or not Path(path).is_file():
            return ""

        try:
            return self.parse_klicensee(Path(path).read_bytes())
        except OSError:
            return ""

    def valid_ps2_key_file(self):
        return bool(self.current_ps2_key_value())

    def resolve_ps2_klicensee(self):
        """
        Resolve the build key without user interaction.

        The editable field has priority. Otherwise the root key or the local
        fallback key from the original package is loaded again.
        """
        current = self.normalize_klicensee(self.klicensee.get())
        if re.fullmatch(r"[0-9A-F]{32}", current):
            if self.klicensee.get() != current:
                self.klicensee.set(current)
            return current

        discovered = self.load_ps2_klicensee()
        if re.fullmatch(r"[0-9A-F]{32}", discovered):
            self.klicensee.set(discovered)
            self.update_ps2_key_option_ui()
            return discovered

        return ""

    def update_ps2_key_option_ui(self):
        if not hasattr(self, "ps2_key_checkbox"):
            return

        root_value = self.current_ps2_key_value()
        field_value = self.normalize_klicensee(self.klicensee.get())
        valid_field = bool(re.fullmatch(r"[0-9A-F]{32}", field_value))

        source_value = ""
        source_file = getattr(self, "ps2_key_source_file", None)
        if source_file and Path(source_file).is_file():
            try:
                source_value = self.parse_klicensee(
                    Path(source_file).read_bytes()
                )
            except OSError:
                source_value = ""

        if not root_value:
            self.ps2_key_required = True
            if not self.create_project_ps2_key.get():
                self.create_project_ps2_key.set(True)
            self.ps2_key_checkbox.configure(
                state=tk.DISABLED,
                disabledforeground=self.COLOR_TEXT_SOFT,
            )
        else:
            self.ps2_key_required = False
            self.ps2_key_checkbox.configure(state=tk.NORMAL)

        if root_value:
            if valid_field and field_value != root_value:
                if self.create_project_ps2_key.get():
                    status = (
                        f"Detected: {self.ps2_key_file}. The edited "
                        "Klicensee will replace this file during the build."
                    )
                else:
                    status = (
                        f"Detected: {self.ps2_key_file}. The edited "
                        "Klicensee will be used for this build only."
                    )
            elif self.create_project_ps2_key.get():
                status = (
                    f"Detected: {self.ps2_key_file}. The root key will be "
                    "rewritten and verified during the build."
                )
            else:
                status = (
                    f"Detected: {self.ps2_key_file}. Enable the option to "
                    "rewrite the root key."
                )
        elif source_value and source_file:
            status = (
                f"Source detected: {source_file}. It will be copied to "
                f"{self.script_dir / 'ps2.key'}, verified and reloaded "
                "automatically during the build."
            )
        elif self.get_ps2_key_generation_source():
            converter, rap_path = self.get_ps2_key_generation_source()
            status = (
                f"Automatic generation ready: {converter.name} will convert "
                f"{rap_path.name} into the root ps2.key during the build."
            )
        elif valid_field:
            status = (
                "No root ps2.key was found. The current Klicensee will be "
                "written as a 16-byte root key, verified and reloaded during "
                "the build."
            )
        else:
            status = (
                "Automatic generation is unavailable. A matching placeholder "
                "RAP and rap2rifkey.exe are required, or enter a valid "
                "32-character Klicensee."
            )

        self.ps2_key_status.set(status)

    def on_ps2_key_option_changed(self):
        self.update_ps2_key_option_ui()
        self.schedule_build_readiness()

    def write_project_ps2_key(self, key_bytes):
        """Atomically create, validate and activate the root ps2.key."""
        target = self.script_dir / "ps2.key"
        temporary = self.script_dir / "ps2.key.tmp"

        try:
            temporary.write_bytes(key_bytes)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

        value = self.parse_klicensee(target.read_bytes())
        expected = key_bytes.hex().upper()
        if value != expected or target.stat().st_size != 16:
            raise RuntimeError(
                "The generated ps2.key failed the 16-byte validation."
            )

        self.ps2_key_file = target
        self.ps2_klicensee_source = target
        self.ps2_klicensee_source_kind = "ps2.key"
        self.ps2_key_required = False
        self.klicensee.set(value)
        self.create_project_ps2_key.set(False)
        self.update_ps2_key_option_ui()
        self.log(f"ps2.key created, verified and reloaded: {target}")
        return target

    # -------------------------------------------------------
    # GUI
    # -------------------------------------------------------

    def build_ui(self):
        title = tk.Label(
            self.root,
            text=f"{self.APP_NAME} · v{self.APP_VERSION}",
            font=self.FONT_TITLE,
            fg=self.COLOR_TEXT,
            bg=self.COLOR_BG,
        )
        title.pack(pady=(10, 7))

        main = tk.Frame(self.root, bg=self.COLOR_BG)
        main.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        # Scrollable form
        left_outer = tk.Frame(main, bg=self.COLOR_BG)
        left_outer.pack(side="left", fill="both", expand=True)

        left_canvas = tk.Canvas(
            left_outer,
            bg=self.COLOR_BG,
            highlightthickness=0,
        )
        left_scroll = ttk.Scrollbar(
            left_outer,
            orient="vertical",
            command=left_canvas.yview,
        )

        self.form_frame = tk.Frame(left_canvas, bg=self.COLOR_BG)
        window_id = left_canvas.create_window(
            (0, 0),
            window=self.form_frame,
            anchor="nw",
        )

        self.form_frame.bind(
            "<Configure>",
            lambda _event: left_canvas.configure(
                scrollregion=left_canvas.bbox("all")
            ),
        )
        left_canvas.bind(
            "<Configure>",
            lambda event: left_canvas.itemconfigure(
                window_id,
                width=max(1, event.width - 14),
            ),
        )
        left_canvas.configure(yscrollcommand=left_scroll.set)

        left_canvas.pack(side="left", fill="both", expand=True)
        left_scroll.pack(side="right", fill="y")

        # XMB preview
        right = tk.Frame(main, bg=self.COLOR_BG, width=500)
        right.pack(side="right", fill="y", padx=(18, 0))
        right.pack_propagate(False)

        tk.Label(
            right,
            text="PS3 XMB Preview",
            fg=self.COLOR_TEXT,
            bg=self.COLOR_BG,
            font=self.FONT_PREVIEW_TITLE,
        ).pack(pady=(3, 8))

        self.preview_canvas = tk.Canvas(
            right,
            width=470,
            height=330,
            bg="#05070b",
            highlightbackground="#555555",
            highlightthickness=1,
        )
        self.preview_canvas.pack()
        self.preview_canvas.bind("<Button-1>", self.on_preview_click)
        self.preview_canvas.bind("<Motion>", self.on_preview_motion)
        self.preview_canvas.bind(
            "<Leave>",
            lambda _event: self.preview_canvas.configure(cursor=""),
        )

        self.preview_info = tk.Label(
            right,
            text="",
            fg=self.COLOR_DESCRIPTION,
            bg=self.COLOR_BG,
            justify="left",
            wraplength=470,
            font=self.FONT_BODY,
        )
        self.preview_info.pack(fill="x", pady=(8, 0))

        github_link = tk.Label(
            right,
            text="github.com/Chrisser73",
            fg=self.COLOR_LINK,
            bg=self.COLOR_BG,
            cursor="hand2",
            font=("Segoe UI", 9, "underline"),
        )
        github_link.pack(pady=(14, 0))
        github_link.bind(
            "<Button-1>",
            lambda _event: webbrowser.open_new_tab(
                "https://github.com/Chrisser73"
            ),
        )

        source_frame = self.create_group("Build source")

        tk.Radiobutton(
            source_frame,
            text="Raw PS2 ISO / BIN (encrypt during this build)",
            variable=self.input_mode,
            value="raw",
            command=self.change_input_mode,
            fg=self.COLOR_TEXT_SOFT,
            bg=self.COLOR_BG,
            selectcolor=self.COLOR_PANEL_ACTIVE,
            activebackground=self.COLOR_BG,
            activeforeground=self.COLOR_TEXT,
        ).pack(anchor="w", padx=9, pady=(5, 1))

        tk.Radiobutton(
            source_frame,
            text="Existing ISO.BIN.ENC (package without re-encrypting)",
            variable=self.input_mode,
            value="encrypted",
            command=self.change_input_mode,
            fg=self.COLOR_TEXT_SOFT,
            bg=self.COLOR_BG,
            selectcolor=self.COLOR_PANEL_ACTIVE,
            activebackground=self.COLOR_BG,
            activeforeground=self.COLOR_TEXT,
        ).pack(anchor="w", padx=9, pady=(1, 5))

        self.individual_edat_checkbox = tk.Checkbutton(
            source_frame,
            text=(
                "Use a custom game-specific EDAT identity"
            ),
            variable=self.create_individual_edat,
            command=self.change_identity_mode,
            fg=self.COLOR_TEXT_SOFT,
            bg=self.COLOR_BG,
            selectcolor=self.COLOR_PANEL_ACTIVE,
            activebackground=self.COLOR_BG,
            activeforeground=self.COLOR_TEXT,
        )
        self.individual_edat_checkbox.pack(
            anchor="w",
            padx=28,
            pady=(2, 2),
        )

        tk.Label(
            source_frame,
            text=(
                "Off: create a fresh game EDAT with the universal PS2 Classics identity. "
                "On: use the package Content ID and a matching RAP."
            ),
            fg=self.COLOR_DESCRIPTION_DARK,
            bg=self.COLOR_BG,
            justify="left",
            anchor="w",
            wraplength=515,
            font=self.FONT_SMALL,
        ).pack(fill="x", padx=(46, 10), pady=(0, 5))

        self.add_file_row(
            "Source image",
            (
                "Raw image or an existing ISO.BIN.ENC."
            ),
            self.iso_path,
            self.browse_iso,
            required=True,
        )

        compatibility_frame = tk.Frame(self.form_frame, bg=self.COLOR_BG)
        compatibility_frame.pack(
            fill="x",
            padx=(0, 8),
            pady=(5, 0),
        )

        tk.Label(
            compatibility_frame,
            text="Compatibility",
            fg=self.COLOR_TEXT,
            bg=self.COLOR_BG,
            font=self.FONT_BOLD,
        ).pack(side="left")

        self.compatibility_status_label = tk.Label(
            compatibility_frame,
            textvariable=self.compatibility_status,
            fg=self.COLOR_TEXT_MUTED,
            bg=self.COLOR_PANEL,
            font=self.FONT_SMALL,
            padx=8,
            pady=2,
        )
        self.compatibility_status_label.pack(side="left", padx=(8, 0))

        self.compat_cache_button = tk.Button(
            compatibility_frame,
            text="Get cache",
            command=self.refresh_compatibility_cache,
            width=9,
            padx=2,
            pady=0,
            font=self.FONT_SMALL,
        )
        self.compat_cache_button.pack(side="right")
        self.update_compat_cache_button()

        self.compatibility_match_label = tk.Label(
            self.form_frame,
            textvariable=self.compatibility_match,
            fg=self.COLOR_DESCRIPTION,
            bg=self.COLOR_BG,
            justify="left",
            anchor="w",
            wraplength=540,
            font=self.FONT_SMALL,
        )
        self.compatibility_match_label.pack(
            fill="x",
            padx=(0, 8),
            pady=(2, 0),
        )

        self.compatibility_notes_button = tk.Button(
            self.form_frame,
            text="Notes",
            command=self.toggle_compatibility_notes,
            anchor="w",
            relief="flat",
            bd=0,
            state=tk.DISABLED,
            bg=self.COLOR_BG,
            activebackground=self.COLOR_BG,
            fg=self.COLOR_DESCRIPTION,
            activeforeground=self.COLOR_TEXT_SOFT,
            disabledforeground="#666666",
            font=self.FONT_SMALL,
            padx=0,
            pady=0,
        )
        self.compatibility_notes_button.pack(
            fill="x",
            padx=(0, 8),
            pady=(1, 0),
        )

        self.compatibility_notes_label = tk.Label(
            self.form_frame,
            textvariable=self.compatibility_notes,
            fg=self.COLOR_DESCRIPTION,
            bg=self.COLOR_BG,
            justify="left",
            anchor="w",
            wraplength=540,
            font=self.FONT_SMALL,
        )

        self.add_file_row(
            "ISO.BIN.EDAT sidecar",
            (
                "Matching EDAT for an existing encrypted image."
            ),
            self.edat_source_path,
            self.browse_edat_source,
        )
        self.add_file_row(
            "ICON0.PNG",
            (
                "XMB icon. A fallback path is filled automatically."
            ),
            self.icon0_path,
            self.browse_icon0,
            required=False,
        )
        self.add_file_row(
            "PIC1.PNG",
            "XMB background image.",
            self.pic1_path,
            self.browse_pic1,
        )
        self.add_file_row(
            "PIC0.PNG",
            "Full XMB information panel.",
            self.pic0_path,
            self.browse_pic0,
        )
        self.add_file_row(
            "SND0.AT3",
            "Music played while the game is selected.",
            self.snd0_path,
            self.browse_snd0,
        )
        self.add_file_row(
            "PS2 CONFIG",
            (
                "Emulator config; searched automatically by disc ID."
            ),
            self.param_hip_path,
            self.browse_param_hip,
        )

        config_actions = tk.Frame(self.form_frame, bg=self.COLOR_BG)
        config_actions.pack(
            fill="x",
            padx=(0, 8),
            pady=(4, 0),
        )

        self.config_update_slot = tk.Frame(
            config_actions,
            bg=self.COLOR_BG,
            width=92,
            height=24,
        )
        self.config_update_slot.pack(side="left")
        self.config_update_slot.pack_propagate(False)

        self.update_configs_button = tk.Button(
            self.config_update_slot,
            text="Update configs",
            command=self.update_configs,
            padx=4,
            pady=0,
            font=self.FONT_SMALL,
        )
        self.update_configs_button.pack(fill="both", expand=True)

        self.config_update_progress_frame = tk.Frame(
            self.config_update_slot,
            bg=self.COLOR_BG,
        )
        self.config_update_progress = ttk.Progressbar(
            self.config_update_progress_frame,
            mode="determinate",
            maximum=100,
        )
        self.config_update_progress.pack(fill="both", expand=True)

        self.rescan_configs_button = tk.Button(
            config_actions,
            text="Re-scan configs",
            command=self.rescan_configs,
            padx=4,
            pady=2,
            font=self.FONT_SMALL,
        )
        self.rescan_configs_button.pack(side="left", padx=(5, 0))

        tk.Label(
            self.form_frame,
            textvariable=self.config_update_status,
            fg=self.COLOR_DESCRIPTION,
            bg=self.COLOR_BG,
            justify="left",
            anchor="w",
            wraplength=540,
            font=self.FONT_SMALL,
        ).pack(fill="x", padx=(0, 8), pady=(2, 0))

        self.add_file_row(
            "make_npdata.exe (auto-detected)",
            (
                "Required only for game-specific EDAT mode."
            ),
            self.make_npdata_path,
            self.browse_make_npdata,
            required=False,
        )
        self.add_file_row(
            "Output folder",
            "Destination for the finished PKG and kept files.",
            self.output_dir,
            self.browse_output,
            required=True,
        )

        pkg_frame = self.create_group("PKG metadata · populated automatically")
        self.add_text_row(pkg_frame, "Game title", self.game_title, required=True)
        self.add_text_row(pkg_frame, "Package Content ID", self.content_id, required=True)
        self.add_text_row(pkg_frame, "Title ID", self.title_id, required=True)
        self.add_text_row(pkg_frame, "Version", self.version, required=True)
        self.add_text_row(
            pkg_frame,
            "Detected disc ID",
            self.detected_disc_id,
            description=(
                "Read from the selected image or EDAT."
            ),
        )

        encrypt_frame = self.create_group("Encryption options from PS2 Classics GUI")

        self.add_text_row(
            encrypt_frame,
            "Klicensee",
            self.klicensee,
            description=(
                "Loaded from ps2.key or generated from the local placeholder RAP."
            ),
            required=True,
        )

        self.ps2_key_checkbox = tk.Checkbutton(
            encrypt_frame,
            text="Create or replace the root ps2.key during the build",
            variable=self.create_project_ps2_key,
            command=self.on_ps2_key_option_changed,
            fg=self.COLOR_TEXT_SOFT,
            bg=self.COLOR_BG,
            selectcolor=self.COLOR_PANEL_ACTIVE,
            activebackground=self.COLOR_BG,
            activeforeground=self.COLOR_TEXT,
            anchor="w",
        )
        self.ps2_key_checkbox.pack(
            fill="x",
            anchor="w",
            padx=10,
            pady=(5, 1),
        )

        self.ps2_key_status_label = tk.Label(
            encrypt_frame,
            textvariable=self.ps2_key_status,
            fg=self.COLOR_DESCRIPTION_DARK,
            bg=self.COLOR_BG,
            justify="left",
            anchor="w",
            wraplength=550,
            font=self.FONT_SMALL,
        )
        self.ps2_key_status_label.pack(
            fill="x",
            anchor="w",
            padx=(28, 10),
            pady=(0, 4),
        )
        self.update_ps2_key_option_ui()

        option_grid = tk.Frame(encrypt_frame, bg=self.COLOR_BG)
        option_grid.pack(fill="x", padx=9, pady=(6, 9))
        option_grid.columnconfigure(0, weight=1)
        option_grid.columnconfigure(1, weight=1)

        image_group = tk.LabelFrame(
            option_grid,
            text="Image Type",
            fg=self.COLOR_TEXT,
            bg=self.COLOR_BG,
            font=self.FONT_BOLD,
        )
        image_group.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        self.image_type_buttons = []

        for text, value in (
            ("DVD5 / DVD9 (2048 Byte)", "DVD5 / DVD9"),
            ("CD / BIN (2352 Byte)", "CD"),
        ):
            button = tk.Radiobutton(
                image_group,
                text=text,
                variable=self.image_type,
                value=value,
                fg=self.COLOR_TEXT_SOFT,
                bg=self.COLOR_BG,
                selectcolor=self.COLOR_PANEL_ACTIVE,
                activebackground=self.COLOR_BG,
                activeforeground=self.COLOR_TEXT,
            )
            button.pack(anchor="w", padx=7, pady=2)
            self.image_type_buttons.append(button)

        tk.Label(
            image_group,
            textvariable=self.image_type_detection,
            fg=self.COLOR_DESCRIPTION_DARK,
            bg=self.COLOR_BG,
            justify="left",
            anchor="w",
            wraplength=245,
            font=self.FONT_SMALL,
        ).pack(fill="x", padx=7, pady=(2, 5))

        target_group = tk.LabelFrame(
            option_grid,
            text="Target",
            fg=self.COLOR_TEXT,
            bg=self.COLOR_BG,
            font=self.FONT_BOLD,
        )
        target_group.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        self.target_type_buttons = []

        for target in ("CEX", "DEX"):
            button = tk.Radiobutton(
                target_group,
                text=target,
                variable=self.target_type,
                value=target,
                fg=self.COLOR_TEXT_SOFT,
                bg=self.COLOR_BG,
                selectcolor=self.COLOR_PANEL_ACTIVE,
                activebackground=self.COLOR_BG,
                activeforeground=self.COLOR_TEXT,
            )
            button.pack(anchor="w", padx=7, pady=2)
            self.target_type_buttons.append(button)

        self.limg_checkbox = tk.Checkbutton(
            encrypt_frame,
            text="Add an LIMG sector before encryption",
            variable=self.add_limg,
            fg=self.COLOR_TEXT_SOFT,
            bg=self.COLOR_BG,
            selectcolor=self.COLOR_PANEL_ACTIVE,
            activebackground=self.COLOR_BG,
            activeforeground=self.COLOR_TEXT,
        )
        self.limg_checkbox.pack(anchor="w", padx=10, pady=(2, 4))

        tk.Label(
            encrypt_frame,
            text=(
                "Uses a temporary copy; the original image is unchanged."
            ),
            fg=self.COLOR_DESCRIPTION_DARK,
            bg=self.COLOR_BG,
            justify="left",
            anchor="w",
            wraplength=560,
            font=self.FONT_SMALL,
        ).pack(anchor="w", padx=28, pady=(0, 7))

        vmc_frame = self.create_group("VMC / VME")
        tk.Checkbutton(
            vmc_frame,
            text="Encrypt a VMC to VME during the build",
            variable=self.encrypt_vmc,
            command=self.update_vmc_state,
            fg=self.COLOR_TEXT_SOFT,
            bg=self.COLOR_BG,
            selectcolor=self.COLOR_PANEL_ACTIVE,
            activebackground=self.COLOR_BG,
            activeforeground=self.COLOR_TEXT,
        ).pack(anchor="w", padx=9, pady=(5, 2))

        self.vmc_controls = tk.Frame(vmc_frame, bg=self.COLOR_BG)
        self.vmc_controls.pack(fill="x", padx=9, pady=(0, 8))

        self.add_file_row_to_parent(
            self.vmc_controls,
            "VMC file",
            "Memory card to convert to VME.",
            self.vmc_path,
            self.browse_vmc,
        )
        self.add_file_row_to_parent(
            self.vmc_controls,
            "EID Root Key",
            "Key used only by specific DEX/VMC workflows.",
            self.eid_root_key_path,
            self.browse_eid_root_key,
        )
        self.update_vmc_state()
        self.individual_edat_checkbox.configure(state=tk.NORMAL)

        verification_frame = self.create_group("Post-build verification")
        verification_grid = tk.Frame(verification_frame, bg=self.COLOR_BG)
        verification_grid.pack(fill="x", padx=8, pady=(5, 8))
        verification_grid.columnconfigure(0, weight=1, uniform="verify")
        verification_grid.columnconfigure(1, weight=1, uniform="verify")

        verification_left = tk.Frame(verification_grid, bg=self.COLOR_BG)
        verification_left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        verification_right = tk.Frame(verification_grid, bg=self.COLOR_BG)
        verification_right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        tk.Checkbutton(
            verification_left,
            text="Keep a structural <PKG>_verification folder",
            variable=self.create_verification_report,
            fg=self.COLOR_TEXT_SOFT,
            bg=self.COLOR_BG,
            selectcolor=self.COLOR_PANEL_ACTIVE,
            activebackground=self.COLOR_BG,
            activeforeground=self.COLOR_TEXT,
            anchor="w",
            justify="left",
            wraplength=255,
        ).pack(fill="x", anchor="w")
        self.make_description_label(
            verification_left,
            "Keeps extracted files and verification.txt.",
            wraplength=250,
            padx=(22, 0),
            pady=(2, 0),
        )

        tk.Checkbutton(
            verification_right,
            text="Keep ISO.BIN.ENC, ISO.BIN.EDAT and RAP",
            variable=self.keep_encrypted_artifacts,
            fg=self.COLOR_TEXT_SOFT,
            bg=self.COLOR_BG,
            selectcolor=self.COLOR_PANEL_ACTIVE,
            activebackground=self.COLOR_BG,
            activeforeground=self.COLOR_TEXT,
            anchor="w",
            justify="left",
            wraplength=255,
        ).pack(fill="x", anchor="w")
        self.make_description_label(
            verification_right,
            "Keeps reusable encrypted files in the output folder.",
            wraplength=250,
            padx=(22, 0),
            pady=(2, 0),
        )

        readiness_frame, self.set_readiness_expanded = (
            self.create_collapsible_section(
                self.form_frame,
                "Build readiness · required fields are marked with *",
                expanded=False,
            )
        )

        self.readiness_label = tk.Label(
            readiness_frame,
            text="Checking build requirements…",
            fg=self.COLOR_TEXT_SOFT,
            bg=self.COLOR_BG,
            justify="left",
            anchor="w",
            wraplength=570,
            font=self.FONT_MONO,
        )
        self.readiness_label.pack(
            fill="x",
            padx=9,
            pady=(6, 4),
        )

        tk.Label(
            readiness_frame,
            text=(
                "MAKE PKG is enabled when every requirement reports OK."
            ),
            fg=self.COLOR_DESCRIPTION_DARK,
            bg=self.COLOR_BG,
            justify="left",
            anchor="w",
            wraplength=570,
            font=self.FONT_SMALL,
        ).pack(fill="x", padx=9, pady=(0, 8))

        self.progress = ttk.Progressbar(
            self.form_frame,
            mode="determinate",
            maximum=100,
        )
        self.progress.pack(fill="x", padx=(0, 8), pady=(12, 3))

        self.status_label = tk.Label(
            self.form_frame,
            textvariable=self.status_text,
            fg="#b8c7dc",
            bg=self.COLOR_BG,
            anchor="w",
            font=self.FONT_BODY,
        )
        self.status_label.pack(fill="x", padx=(0, 8), pady=(0, 7))

        log_frame, self.set_log_expanded = (
            self.create_collapsible_section(
                self.form_frame,
                "Process log",
                expanded=False,
            )
        )

        self.log_box = tk.Text(
            log_frame,
            height=9,
            bg=self.COLOR_LOG_BG,
            fg=self.COLOR_LOG_FG,
            insertbackground="#ffffff",
            font=self.FONT_MONO,
            wrap="word",
            relief="flat",
        )
        self.log_box.pack(
            fill="both",
            expand=True,
            padx=7,
            pady=7,
        )

        self.build_button = tk.Button(
            self.form_frame,
            text="MAKE PKG",
            command=self.build_pkg,
            bg=self.COLOR_BUTTON,
            activebackground=self.COLOR_BUTTON_ACTIVE,
            fg=self.COLOR_TEXT,
            activeforeground=self.COLOR_TEXT,
            disabledforeground="#5a5a5a",
            font=self.FONT_BUTTON,
            height=2,
            state=tk.DISABLED,
        )
        self.build_button.pack(fill="x", padx=(0, 8), pady=(10, 10))

        for variable in (
            self.icon0_path,
            self.pic0_path,
            self.pic1_path,
            self.game_title,
        ):
            variable.trace_add("write", self.schedule_preview)

        self.game_title.trace_add(
            "write",
            lambda *_args: self.schedule_compatibility_check(),
        )

        for variable in (
            self.iso_path,
            self.edat_source_path,
            self.output_dir,
            self.game_title,
            self.content_id,
            self.title_id,
            self.version,
            self.detected_disc_id,
            self.klicensee,
            self.create_project_ps2_key,
            self.vmc_path,
            self.make_npdata_path,
            self.input_mode,
            self.create_individual_edat,
            self.keep_encrypted_artifacts,
            self.icon0_path,
            self.pic0_path,
            self.pic1_path,
        ):
            variable.trace_add(
                "write",
                lambda *_args: self.schedule_build_readiness(),
            )

        self.encrypt_vmc.trace_add(
            "write",
            lambda *_args: self.schedule_build_readiness(),
        )

        self.klicensee.trace_add(
            "write",
            lambda *_args: self.update_ps2_key_option_ui(),
        )

        self.iso_path.trace_add(
            "write",
            lambda *_args: self.update_encrypt_option_state(),
        )
        self.iso_path.trace_add(
            "write",
            lambda *_args: self.schedule_compatibility_check(),
        )
        self.iso_path.trace_add(
            "write",
            lambda *_args: self.schedule_source_dependent_refresh(),
        )

        self._readiness_after_id = None
        self.update_encrypt_option_state()
        self.root.after(150, self.update_build_readiness)

    def make_entry(self, parent, variable):
        return tk.Entry(
            parent,
            textvariable=variable,
            bg=self.COLOR_ENTRY_BG,
            fg=self.COLOR_ENTRY_FG,
            insertbackground=self.COLOR_ENTRY_FG,
            relief="solid",
            bd=1,
            font=self.FONT_BODY,
        )

    def make_description_label(
        self,
        parent,
        text,
        wraplength=520,
        padx=(0, 8),
        pady=(0, 0),
    ):
        label = tk.Label(
            parent,
            text=text,
            fg=self.COLOR_DESCRIPTION,
            bg=self.COLOR_BG,
            justify="left",
            anchor="w",
            wraplength=wraplength,
            font=self.FONT_SMALL,
        )
        label.pack(fill="x", anchor="w", padx=padx, pady=pady)
        return label

    def create_collapsible_section(
        self,
        parent,
        title,
        expanded=False,
    ):
        """Create a compact section with a clickable disclosure header."""
        outer = tk.Frame(parent, bg=self.COLOR_BG)
        outer.pack(fill="x", padx=(0, 8), pady=(10, 0))

        header = tk.Button(
            outer,
            anchor="w",
            relief="flat",
            bd=0,
            bg=self.COLOR_PANEL,
            activebackground=self.COLOR_PANEL_ACTIVE,
            fg=self.COLOR_TEXT,
            activeforeground=self.COLOR_TEXT,
            font=self.FONT_SECTION,
            padx=8,
            pady=5,
        )
        header.pack(fill="x")

        body = tk.Frame(
            outer,
            bg=self.COLOR_BG,
            highlightbackground="#555555",
            highlightthickness=1,
        )

        state = {"expanded": bool(expanded)}

        def set_expanded(value):
            state["expanded"] = bool(value)
            header.configure(
                text=("▼ " if state["expanded"] else "▶ ") + title
            )
            if state["expanded"]:
                body.pack(fill="x")
            else:
                body.pack_forget()

        def toggle():
            set_expanded(not state["expanded"])

        header.configure(command=toggle)
        set_expanded(expanded)
        return body, set_expanded

    def create_group(self, title):
        frame = tk.LabelFrame(
            self.form_frame,
            text=title,
            fg=self.COLOR_TEXT,
            bg=self.COLOR_BG,
            font=self.FONT_SECTION,
        )
        frame.pack(fill="x", padx=(0, 8), pady=(10, 0))
        return frame

    def add_file_row(
        self,
        title,
        description,
        variable,
        command,
        required=False,
    ):
        self.add_file_row_to_parent(
            self.form_frame,
            title,
            description,
            variable,
            command,
            required=required,
        )

    def add_file_row_to_parent(
        self,
        parent,
        title,
        description,
        variable,
        command,
        required=False,
    ):
        tk.Label(
            parent,
            text=title + ("  *" if required else ""),
            fg=self.COLOR_TEXT,
            bg=self.COLOR_BG,
            font=self.FONT_BOLD,
        ).pack(anchor="w", padx=(0, 8), pady=(7, 0))

        self.make_description_label(
            parent,
            description,
            wraplength=520,
            padx=(0, 8),
        )

        row = tk.Frame(parent, bg=self.COLOR_BG)
        row.pack(fill="x", padx=(0, 8), pady=(2, 0))

        self.make_entry(row, variable).pack(
            side="left",
            fill="x",
            expand=True,
        )
        tk.Button(
            row,
            text="…",
            command=command,
            width=4,
        ).pack(side="left", padx=(5, 0))
        tk.Button(
            row,
            text="×",
            command=lambda: self.clear_field(variable),
            width=3,
        ).pack(side="left", padx=(3, 0))

    def add_text_row(
        self,
        parent,
        title,
        variable,
        description=None,
        required=False,
    ):
        row = tk.Frame(parent, bg=self.COLOR_BG)
        row.pack(fill="x", padx=9, pady=(5, 0))

        tk.Label(
            row,
            text=title + ("  *" if required else ""),
            width=16,
            anchor="w",
            fg=self.COLOR_TEXT_MUTED,
            bg=self.COLOR_BG,
        ).pack(side="left")

        self.make_entry(row, variable).pack(
            side="left",
            fill="x",
            expand=True,
        )

        if description:
            self.make_description_label(
                parent,
                description,
                wraplength=440,
                padx=(123, 8),
                pady=(1, 0),
            )

    def update_encrypt_option_state(self):
        """Enable raw-image options only when raw encryption is selected."""
        has_source = bool(self.iso_path.get().strip())
        raw_mode = self.input_mode.get() == "raw"

        image_state = tk.NORMAL if has_source and raw_mode else tk.DISABLED
        target_state = tk.NORMAL if has_source else tk.DISABLED

        for button in self.image_type_buttons:
            button.configure(state=image_state)

        for button in self.target_type_buttons:
            button.configure(state=target_state)

        self.limg_checkbox.configure(state=image_state)

    def change_input_mode(self):
        self.iso_path.set("")
        self.edat_source_path.set("")
        self.detected_disc_id.set("")
        self.game_title.set("")
        self.content_id.set("")
        self.title_id.set("")
        self.version.set("")
        self.disc_id_cache_path = None
        self.disc_id_cache_value = None
        self.auto_image_type_path = None
        self.image_type_detection.set("")
        self.reset_compatibility_display()

        if (
            self.auto_config_path
            and self.param_hip_path.get().strip() == self.auto_config_path
        ):
            self.param_hip_path.set("")
        self.auto_config_path = ""

        encrypted_mode = self.input_mode.get() == "encrypted"
        if encrypted_mode:
            self.create_individual_edat.set(False)
            self.individual_edat_checkbox.configure(state=tk.DISABLED)
        else:
            self.individual_edat_checkbox.configure(state=tk.NORMAL)

        self.update_encrypt_option_state()
        self.update_build_readiness()

    def change_identity_mode(self):
        if self.input_mode.get() == "encrypted":
            self.create_individual_edat.set(False)
            return

        # Refresh generated/template identity without retaining stale IDs.
        self.content_id.set("")
        self.title_id.set("")
        self.version.set("")
        if self.iso_path.get().strip():
            self.auto_populate_metadata()
        self.update_build_readiness()

    def update_vmc_state(self):
        state = tk.NORMAL if self.encrypt_vmc.get() else tk.DISABLED

        for widget in self.vmc_controls.winfo_children():
            self.set_widget_tree_state(widget, state)

    def set_widget_tree_state(self, widget, state):
        try:
            widget.configure(state=state)
        except tk.TclError:
            pass

        for child in widget.winfo_children():
            self.set_widget_tree_state(child, state)

    # -------------------------------------------------------
    # File selection
    # -------------------------------------------------------

    def choose_file(self, key, variable, title, filetypes):
        filename = filedialog.askopenfilename(
            title=title,
            initialdir=self.get_initial_dir(key),
            filetypes=filetypes,
        )

        if filename:
            variable.set(filename)
            self.remember_path(key, filename)
            return filename
        return None

    def browse_iso(self):
        encrypted_mode = self.input_mode.get() == "encrypted"

        if encrypted_mode:
            title = "Select an existing ISO.BIN.ENC"
            filetypes = [
                ("Encrypted PS2 image", "*.ENC *.enc"),
                ("ISO.BIN.ENC", "ISO.BIN.ENC"),
                ("All files", "*.*"),
            ]
        else:
            title = "Select a raw PS2 ISO or BIN image"
            filetypes = [
                ("PS2 images", "*.iso *.bin *.img"),
                ("ISO", "*.iso"),
                ("BIN", "*.bin"),
                ("All files", "*.*"),
            ]

        filename = filedialog.askopenfilename(
            title=title,
            initialdir=self.get_initial_dir("source"),
            filetypes=filetypes,
        )

        if filename:
            self.iso_path.set(filename)
            self.remember_path("source", filename)
            self.refresh_source_dependent_data(force=True)

    def schedule_source_dependent_refresh(self):
        if self._source_refresh_after_id is not None:
            try:
                self.root.after_cancel(self._source_refresh_after_id)
            except tk.TclError:
                pass

        self._source_refresh_after_id = self.root.after(
            300,
            self.refresh_source_dependent_data,
        )

    def refresh_source_dependent_data(self, force=False):
        self._source_refresh_after_id = None
        source_text = self.iso_path.get().strip()

        if not force and source_text == self._last_source_refresh_path:
            return

        self._last_source_refresh_path = source_text
        self.disc_id_cache_path = None
        self.disc_id_cache_value = None
        self.auto_image_type_path = None
        self.auto_config_path = ""
        self.param_hip_path.set("")

        if not source_text or not Path(source_text).is_file():
            self.detected_disc_id.set("")
            self.image_type_detection.set("")
            self.reset_compatibility_display()
            self.update_encrypt_option_state()
            self.update_build_readiness()
            return

        if self.input_mode.get() == "encrypted":
            self.image_type_detection.set("")
        else:
            self.auto_detect_image_type(source_text)

        self.auto_populate_metadata()
        self.populate_config_field(self.detected_disc_id.get().strip())
        self.schedule_compatibility_check()
        self.update_encrypt_option_state()
        self.update_build_readiness()

    def browse_edat_source(self):
        self.choose_file(
            "edat",
            self.edat_source_path,
            "Select ISO.BIN.EDAT",
            [
                ("ISO.BIN.EDAT", "*.EDAT *.edat"),
                ("All files", "*.*"),
            ],
        )
        if self.edat_source_path.get().strip():
            self.auto_populate_metadata()

    def browse_icon0(self):
        self.choose_image("icon0", self.icon0_path, "Select ICON0")

    def browse_pic0(self):
        self.choose_image("pic0", self.pic0_path, "Select PIC0")

    def browse_pic1(self):
        self.choose_image("pic1", self.pic1_path, "Select PIC1")

    def choose_image(self, key, variable, title):
        filename = self.choose_file(
            key,
            variable,
            title,
            [
                ("Images", "*.png *.jpg *.jpeg *.bmp *.webp"),
                ("All files", "*.*"),
            ],
        )
        if filename:
            asset_name = {
                "icon0": "ICON0.PNG",
                "pic0": "PIC0.PNG",
                "pic1": "PIC1.PNG",
            }.get(key)
            if asset_name:
                self.cleared_assets.discard(asset_name)
                self.auto_asset_paths.pop(asset_name, None)
                self.manual_asset_paths[asset_name] = filename
            self.schedule_preview()

    def browse_snd0(self):
        self.choose_file(
            "snd0",
            self.snd0_path,
            "Select SND0.AT3",
            [
                ("ATRAC3", "*.at3"),
                ("All files", "*.*"),
            ],
        )

    def browse_param_hip(self):
        selected = self.choose_file(
            "ps2_config",
            self.param_hip_path,
            "Select a PS2 CONFIG file",
            [
                ("PS2 CONFIG", "*.CONFIG *.config"),
                ("All files", "*.*"),
            ],
        )
        if selected:
            self.auto_config_path = ""

    def _urlopen_bytes(self, url, timeout=30):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0 Safari/537.36"
            ),
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        }
        request = urllib.request.Request(url, headers=headers)

        last_error = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=timeout,
                ) as response:
                    return response.read()
            except (urllib.error.HTTPError, urllib.error.URLError) as error:
                last_error = error
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))

        raise RuntimeError(f"Network request failed: {last_error}")

    def _urlopen_json(self, url, timeout=30):
        data = self._urlopen_bytes(url, timeout=timeout)
        return json.loads(data.decode("utf-8"))

    def update_configs(self):
        if self.config_update_running:
            return

        confirmed = messagebox.askyesno(
            "Update configs",
            (
                "Download the latest PS2 CONFIG files and overwrite matching "
                "files in the local CONFIGS folder?"
            ),
            parent=self.root,
        )
        if not confirmed:
            return

        self.config_update_running = True
        self.update_configs_button.pack_forget()
        self.config_update_progress["value"] = 0
        self.config_update_progress_frame.pack(fill="both", expand=True)
        self.rescan_configs_button.configure(state=tk.DISABLED)
        self.config_update_status.set("Preparing CONFIG update…")

        worker = threading.Thread(
            target=self._config_update_worker,
            daemon=True,
        )
        worker.start()

    @staticmethod
    def _archive_request_headers():
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0 Safari/537.36"
            ),
            "Accept": "application/zip,application/octet-stream,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _download_config_archive(self, destination):
        last_error = None

        for url in self.CONFIG_ARCHIVE_URLS:
            try:
                request = urllib.request.Request(
                    url,
                    headers=self._archive_request_headers(),
                )
                with urllib.request.urlopen(request, timeout=45) as response:
                    total_header = response.headers.get("Content-Length", "")
                    try:
                        total_bytes = int(total_header)
                    except (TypeError, ValueError):
                        total_bytes = 0

                    downloaded = 0
                    last_percent = -1
                    with open(destination, "wb") as output:
                        while True:
                            chunk = response.read(256 * 1024)
                            if not chunk:
                                break
                            output.write(chunk)
                            downloaded += len(chunk)

                            if total_bytes > 0:
                                download_fraction = min(
                                    1.0,
                                    downloaded / total_bytes,
                                )
                                percent = int(download_fraction * 70)
                            else:
                                # The exact archive size is unknown until EOF.
                                # Keep visible progress moving without pretending
                                # the download phase is already complete.
                                percent = min(65, 5 + downloaded // (2 * 1024 * 1024))

                            if percent != last_percent:
                                last_percent = percent
                                if total_bytes > 0:
                                    status = (
                                        "Downloading CONFIG archive… "
                                        f"{int(download_fraction * 100)}%"
                                    )
                                else:
                                    mib = downloaded / (1024 * 1024)
                                    status = f"Downloading CONFIG archive… {mib:.1f} MiB"
                                self.config_update_queue.put(
                                    ("progress", percent, status)
                                )

                if not destination.is_file() or destination.stat().st_size == 0:
                    raise RuntimeError("The downloaded archive is empty.")

                self.config_update_queue.put(
                    ("progress", 70, "CONFIG archive downloaded · installing…")
                )
                return url
            except Exception as error:
                last_error = error
                destination.unlink(missing_ok=True)

        raise RuntimeError(
            "Could not download the webMAN-MOD CONFIG archive: "
            f"{last_error}"
        )

    def _install_configs_from_archive(self, archive_path):
        config_root = self.script_dir / "CONFIGS"
        config_root.mkdir(parents=True, exist_ok=True)
        marker = self.CONFIG_ARCHIVE_PATH.casefold()

        with zipfile.ZipFile(archive_path, "r") as archive:
            members = []
            for info in archive.infolist():
                if info.is_dir():
                    continue

                normalized = info.filename.replace("\\", "/")
                lower_name = normalized.casefold()
                marker_index = lower_name.find(marker)
                if marker_index < 0:
                    continue

                relative_text = normalized[
                    marker_index + len(self.CONFIG_ARCHIVE_PATH):
                ]
                if not relative_text:
                    continue
                if relative_text.casefold().endswith((".html", ".htm")):
                    continue

                relative = PurePosixPath(relative_text)
                if relative.is_absolute() or ".." in relative.parts:
                    continue

                members.append((info, relative))

            if not members:
                raise RuntimeError(
                    "No PS2 CONFIG files were found in the downloaded archive."
                )

            total = len(members)
            for index, (info, relative) in enumerate(members, start=1):
                destination = config_root.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_name(destination.name + ".download")

                try:
                    with archive.open(info, "r") as source, open(
                        temporary,
                        "wb",
                    ) as target:
                        shutil.copyfileobj(source, target, length=256 * 1024)
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)

                if index == total or index % 25 == 0:
                    install_fraction = index / total
                    percent = 70 + int(install_fraction * 30)
                    self.config_update_queue.put(
                        (
                            "progress",
                            min(percent, 100),
                            (
                                f"Installing CONFIG files… {index} / {total} · "
                                f"{int(install_fraction * 100)}%"
                            ),
                        )
                    )

        return total

    def _config_update_worker(self):
        try:
            with tempfile.TemporaryDirectory(
                prefix="ps2_config_update_"
            ) as temporary_dir:
                archive_path = Path(temporary_dir) / "webman_mod.zip"
                self._download_config_archive(archive_path)
                count = self._install_configs_from_archive(archive_path)

            self.config_update_queue.put(("done", count))
        except Exception as error:
            self.config_update_queue.put(("error", str(error)))

    def poll_config_update_queue(self):
        try:
            while True:
                event = self.config_update_queue.get_nowait()
                event_type = event[0]

                if event_type == "progress":
                    self.config_update_progress["value"] = event[1]
                    self.config_update_status.set(event[2])
                    continue

                self.config_update_progress["value"] = 0
                self.config_update_progress_frame.pack_forget()
                self.update_configs_button.configure(
                    state=tk.NORMAL,
                    text="Update configs",
                )
                self.update_configs_button.pack(fill="both", expand=True)
                self.rescan_configs_button.configure(state=tk.NORMAL)
                self.config_update_running = False

                if event_type == "done":
                    count = event[1]
                    self.config_update_status.set(
                        f"Updated {count} CONFIG files."
                    )
                    self.log(f"CONFIG database updated: {count} files.")
                    self.rescan_configs(show_message=False)
                elif event_type == "error":
                    self.config_update_status.set("CONFIG update failed.")
                    self.log(f"CONFIG update failed: {event[1]}")
                    messagebox.showerror(
                        "CONFIG update failed",
                        event[1],
                        parent=self.root,
                    )
        except queue.Empty:
            pass

        try:
            self.root.after(150, self.poll_config_update_queue)
        except tk.TclError:
            pass

    def rescan_configs(self, show_message=True):
        disc_id = self.detected_disc_id.get().strip()
        if not disc_id and self.iso_path.get().strip():
            disc_id = self.refresh_disc_id_cache() or ""

        if not disc_id:
            self.config_update_status.set(
                "No disc ID is available for CONFIG matching."
            )
            if show_message:
                messagebox.showinfo(
                    "Re-scan configs",
                    "Select a source image with a detectable disc ID first.",
                    parent=self.root,
                )
            return None

        config_path = self.find_config_for_disc_id(disc_id)
        if config_path:
            self.auto_config_path = str(config_path)
            self.param_hip_path.set(self.auto_config_path)
            self.config_update_status.set(
                f"CONFIG found: {config_path.parent.name}/{config_path.name}"
            )
            self.log(f"CONFIG re-scan matched: {config_path}")
            self.schedule_build_readiness()
            return config_path

        self.config_update_status.set(
            f"No CONFIG found for {disc_id}."
        )
        if show_message:
            messagebox.showinfo(
                "Re-scan configs",
                f"No matching CONFIG was found for {disc_id}.",
                parent=self.root,
            )
        return None

    def compatibility_cache_path(self):
        return self.script_dir / self.COMPATIBILITY_CACHE_FILE

    def compatibility_cache_exists(self):
        path = self.compatibility_cache_path()
        if not path.is_file():
            return False

        try:
            with sqlite3.connect(path) as connection:
                row = connection.execute(
                    "SELECT value FROM meta WHERE key = 'schema_version'"
                ).fetchone()
            return bool(row and row[0] == "1")
        except (sqlite3.Error, OSError):
            return False

    def update_compat_cache_button(self):
        if not hasattr(self, "compat_cache_button"):
            return

        if self.compat_cache_running:
            self.compat_cache_button.configure(
                text="Loading…",
                state=tk.DISABLED,
            )
            return

        self.compat_cache_button.configure(
            text=(
                "Refresh"
                if self.compatibility_cache_exists()
                else "Build cache"
            ),
            state=tk.NORMAL,
        )

    def reset_compatibility_display(self):
        self.stop_compatibility_spinner()
        if self.compatibility_cache_exists():
            self.compatibility_status.set("Not checked")
        else:
            self.compatibility_status.set("No cache")

        self.compatibility_status_label.configure(
            bg=self.COLOR_PANEL,
            fg=self.COLOR_TEXT_MUTED,
        )
        self.compatibility_match.set("")
        self.compatibility_notes.set("")
        self.compatibility_notes_expanded = False
        self.compatibility_notes_label.pack_forget()
        self.compatibility_notes_button.configure(
            text="Notes",
            state=tk.DISABLED,
        )
        self.update_compat_cache_button()

    def toggle_compatibility_notes(self):
        if not self.compatibility_notes.get().strip():
            return

        self.compatibility_notes_expanded = (
            not self.compatibility_notes_expanded
        )
        self.compatibility_notes_button.configure(
            text=(
                "▼ Notes"
                if self.compatibility_notes_expanded
                else "▶ Notes"
            )
        )

        if self.compatibility_notes_expanded:
            self.compatibility_notes_label.pack(
                fill="x",
                padx=(12, 8),
                pady=(2, 3),
            )
        else:
            self.compatibility_notes_label.pack_forget()

    def refresh_compatibility_cache(self):
        if self.compat_cache_running:
            return

        self.compatibility_source_override = None

        if not self.compatibility_cache_exists():
            source = self.find_local_compatibility_snapshot()
            if source is None:
                selected = filedialog.askopenfilename(
                    title="Select PSDevWiki compatibility HTML snapshot",
                    initialdir=str(self.script_dir),
                    filetypes=[
                        ("HTML snapshot", "*.html *.htm"),
                        ("All files", "*.*"),
                    ],
                )
                if not selected:
                    return
                source = Path(selected)
            self.compatibility_source_override = source

        self.compat_cache_running = True
        self.update_compat_cache_button()

        worker = threading.Thread(
            target=self._compat_cache_worker,
            daemon=True,
        )
        worker.start()

    def find_local_compatibility_snapshot(self):
        for filename in self.COMPATIBILITY_LOCAL_HTML_NAMES:
            candidate = self.script_dir / filename
            if candidate.is_file():
                return candidate
        return None

    def _load_compatibility_source_html(self):
        candidates = []
        if self.compatibility_source_override:
            candidates.append(Path(self.compatibility_source_override))

        local_default = self.find_local_compatibility_snapshot()
        if local_default and local_default not in candidates:
            candidates.append(local_default)

        errors = []
        for candidate in candidates:
            try:
                text = candidate.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
                if (
                    "Compatibility Notes" in text
                    and "PS2 Classic" in text
                ):
                    return text, str(candidate)
                errors.append(f"{candidate}: unexpected page content")
            except OSError as error:
                errors.append(f"{candidate}: {error}")

        raise RuntimeError(
            "No local PSDevWiki compatibility snapshot is available. "
            "Copy the bundled comp_cache.db into the application root, or "
            "save the compatibility page as HTML and select that file."
            + ("\n\n" + "\n".join(errors[-3:]) if errors else "")
        )

    def _download_datacenter_title_maps(self):
        title_maps = {}
        title_errors = []

        for region_name, url in self.DATACENTER_URLS.items():
            try:
                data = self._urlopen_bytes(url, timeout=30)
                page = data.decode("windows-1252", errors="ignore")
                parser = _DataCenterListParser()
                parser.feed(page)
                if not parser.entries:
                    raise RuntimeError("no serial/title rows were found")
                title_maps[region_name] = parser.entries
            except Exception as error:
                title_errors.append(f"{region_name}: {error}")

        return title_maps, title_errors

    def _create_compatibility_database(self, temporary, rows, source_name):
        with sqlite3.connect(temporary) as connection:
            connection.execute(
                "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.execute(
                """
                CREATE TABLE compatibility (
                    id INTEGER PRIMARY KEY,
                    names TEXT NOT NULL,
                    pal TEXT NOT NULL,
                    ntsc_u TEXT NOT NULL,
                    ntsc_j TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    serials TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE titles (
                    region TEXT NOT NULL,
                    serial TEXT NOT NULL,
                    title TEXT NOT NULL,
                    PRIMARY KEY (region, serial)
                )
                """
            )
            connection.executemany(
                """
                INSERT INTO compatibility
                (names, pal, ntsc_u, ntsc_j, notes, serials)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        json.dumps(row.get("names", []), ensure_ascii=False),
                        (row.get("statuses") or ["", "", ""])[0],
                        (row.get("statuses") or ["", "", ""])[1],
                        (row.get("statuses") or ["", "", ""])[2],
                        row.get("notes", ""),
                        json.dumps(row.get("serials", []), ensure_ascii=False),
                    )
                    for row in rows
                ],
            )
            connection.executemany(
                "INSERT INTO meta(key, value) VALUES (?, ?)",
                {
                    "schema_version": "1",
                    "created_unix": str(int(time.time())),
                    "compatibility_source": source_name,
                    "compatibility_rows": str(len(rows)),
                    "title_rows": "0",
                }.items(),
            )
            connection.commit()

    @staticmethod
    def _refresh_title_table(database_path, title_maps):
        with sqlite3.connect(database_path) as connection:
            for region_name, entries in title_maps.items():
                connection.execute(
                    "DELETE FROM titles WHERE region = ?",
                    (region_name,),
                )
                connection.executemany(
                    "INSERT OR REPLACE INTO titles(region, serial, title) "
                    "VALUES (?, ?, ?)",
                    (
                        (region_name, serial, title)
                        for serial, title in entries.items()
                    ),
                )

            title_count = connection.execute(
                "SELECT COUNT(*) FROM titles"
            ).fetchone()[0]
            connection.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                ("title_rows", str(title_count)),
            )
            connection.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                ("title_refresh_unix", str(int(time.time()))),
            )
            connection.commit()
            return title_count

    def _compat_cache_worker(self):
        cache_path = self.compatibility_cache_path()
        temporary = cache_path.with_suffix(".db.tmp")
        temporary.unlink(missing_ok=True)

        try:
            if self.compatibility_cache_exists():
                shutil.copy2(cache_path, temporary)
                with sqlite3.connect(temporary) as connection:
                    compat_count = connection.execute(
                        "SELECT COUNT(*) FROM compatibility"
                    ).fetchone()[0]
            else:
                html_text, source_name = self._load_compatibility_source_html()
                rows = self._extract_compatibility_rows(html_text)
                if not rows:
                    raise RuntimeError(
                        "No compatibility rows were found in the HTML snapshot."
                    )
                self._create_compatibility_database(
                    temporary,
                    rows,
                    source_name,
                )
                compat_count = len(rows)

            title_maps, title_errors = self._download_datacenter_title_maps()
            title_count = self._refresh_title_table(temporary, title_maps)

            os.replace(temporary, cache_path)
            self._local_compatibility_rows = None
            self.compat_cache_queue.put(
                (
                    "done",
                    compat_count,
                    title_count,
                    title_errors,
                )
            )
        except Exception as error:
            self.compat_cache_queue.put(("error", str(error)))
        finally:
            temporary.unlink(missing_ok=True)

    def poll_compat_cache_queue(self):
        try:
            while True:
                event = self.compat_cache_queue.get_nowait()
                event_type = event[0]
                self.compat_cache_running = False
                self.update_compat_cache_button()

                if event_type == "done":
                    compat_count, title_count, title_errors = event[1:]
                    self.log(
                        "Compatibility cache updated: "
                        f"{compat_count} compatibility rows, "
                        f"{title_count} title mappings."
                    )
                    if title_errors:
                        self.log(
                            "Compatibility cache title warnings: "
                            + "; ".join(title_errors)
                        )
                    if self.iso_path.get().strip():
                        self.schedule_compatibility_check()
                    else:
                        self.reset_compatibility_display()
                    continue

                self.log(f"Compatibility cache update failed: {event[1]}")
                messagebox.showerror(
                    "Compatibility cache",
                    event[1],
                    parent=self.root,
                )
                self.reset_compatibility_display()
        except queue.Empty:
            pass

        try:
            self.root.after(150, self.poll_compat_cache_queue)
        except tk.TclError:
            pass

    def start_compatibility_spinner(self):
        self.stop_compatibility_spinner()
        self.compatibility_spinner_index = 0
        self._tick_compatibility_spinner()

    def stop_compatibility_spinner(self):
        if self.compatibility_spinner_after_id is not None:
            try:
                self.root.after_cancel(self.compatibility_spinner_after_id)
            except tk.TclError:
                pass
        self.compatibility_spinner_after_id = None

    def _tick_compatibility_spinner(self):
        frames = ("Checking ·", "Checking ··", "Checking ···")
        self.compatibility_status.set(
            frames[self.compatibility_spinner_index % len(frames)]
        )
        self.compatibility_spinner_index += 1
        try:
            self.compatibility_spinner_after_id = self.root.after(
                220,
                self._tick_compatibility_spinner,
            )
        except tk.TclError:
            self.compatibility_spinner_after_id = None

    def schedule_compatibility_check(self):
        if self.compatibility_after_id is not None:
            try:
                self.root.after_cancel(self.compatibility_after_id)
            except tk.TclError:
                pass

        if not self.iso_path.get().strip():
            self.reset_compatibility_display()
            self.compatibility_after_id = None
            return

        self.compatibility_after_id = self.root.after(
            450,
            self.start_compatibility_check,
        )

    def start_compatibility_check(self):
        self.compatibility_after_id = None
        source_text = self.iso_path.get().strip()
        if not source_text:
            self.reset_compatibility_display()
            return

        if not self.compatibility_cache_exists():
            self.stop_compatibility_spinner()
            self.compatibility_status.set("No cache")
            self.compatibility_status_label.configure(
                bg=self.COLOR_PANEL,
                fg=self.COLOR_TEXT_MUTED,
            )
            self.compatibility_match.set("")
            self.compatibility_notes.set("")
            self.compatibility_notes_button.configure(
                text="Notes",
                state=tk.DISABLED,
            )
            self.compatibility_notes_label.pack_forget()
            self.update_compat_cache_button()
            return

        self.compatibility_request_id += 1
        request_id = self.compatibility_request_id
        disc_id = self.detected_disc_id.get().strip()
        title = self.game_title.get().strip()

        self.start_compatibility_spinner()
        self.compatibility_status_label.configure(
            bg=self.COLOR_PANEL_ACTIVE,
            fg=self.COLOR_TEXT_SOFT,
        )
        self.compatibility_match.set("")
        self.compatibility_notes.set("")
        self.compatibility_notes_button.configure(
            text="Notes",
            state=tk.DISABLED,
        )
        self.compatibility_notes_label.pack_forget()
        self.compatibility_notes_expanded = False

        worker = threading.Thread(
            target=self._compatibility_worker,
            args=(request_id, disc_id, title, source_text),
            daemon=True,
        )
        worker.start()

    def load_local_compatibility_rows(self):
        if self._local_compatibility_rows is not None:
            return self._local_compatibility_rows

        cache_path = self.compatibility_cache_path()
        if not self.compatibility_cache_exists():
            raise RuntimeError("Compatibility cache is not available.")

        rows = []
        with sqlite3.connect(cache_path) as connection:
            for names, pal, ntsc_u, ntsc_j, notes, serials in connection.execute(
                """
                SELECT names, pal, ntsc_u, ntsc_j, notes, serials
                FROM compatibility
                """
            ):
                row_names = json.loads(names)
                row_serials = json.loads(serials)
                rows.append(
                    {
                        "names": row_names,
                        "statuses": [pal, ntsc_u, ntsc_j],
                        "notes": notes,
                        "serials": row_serials,
                        "_normalized_names": [
                            self.normalize_compatibility_title(value)
                            for value in row_names
                        ],
                        "_compact_serials": {
                            re.sub(r"[^A-Z0-9]", "", normalized)
                            for value in row_serials
                            for normalized in [self.normalize_disc_id(value)]
                            if normalized
                        },
                    }
                )

        self._local_compatibility_rows = rows
        return rows

    @staticmethod
    def datacenter_serial(disc_id):
        normalized = PS2ClassicsGUIMod.normalize_disc_id(disc_id or "")
        if not normalized:
            return ""

        match = re.fullmatch(
            r"([A-Z]{4})_([0-9]{3})\.([0-9]{2})",
            normalized,
        )
        if not match:
            return ""

        return f"{match.group(1)}-{match.group(2)}{match.group(3)}"

    def resolve_title_from_datacenter(self, disc_id):
        serial = self.datacenter_serial(disc_id)
        _region_index, region_name = self.compatibility_region(disc_id)
        if not serial or not self.compatibility_cache_exists():
            return "", "unavailable"

        try:
            with sqlite3.connect(self.compatibility_cache_path()) as connection:
                row = connection.execute(
                    "SELECT title FROM titles WHERE region = ? AND serial = ?",
                    (region_name, serial),
                ).fetchone()
            if row:
                return row[0], "cache"
        except sqlite3.Error:
            pass

        return "", "cache"

    @staticmethod
    def normalize_compatibility_title(value):
        value = unicodedata.normalize("NFKD", str(value))
        value = "".join(
            char for char in value
            if not unicodedata.combining(char)
        )
        value = value.casefold()
        value = value.replace("&", " and ")
        value = re.sub(
            r"\b(?:ps2|playstation\s*2|iso|bin|pal|ntsc|usa|europe|"
            r"japan|japanese|german|ger|english|eng)\b",
            " ",
            value,
        )
        value = re.sub(r"[^a-z0-9]+", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _extract_compatibility_rows(html_text):
        parser = _CompatibilityTableParser()
        parser.feed(html_text)
        parsed_rows = []
        serial_pattern = re.compile(
            r"(?:SLUS|SLES|SCUS|SCES|SLPM|SLPS|SCPS|SCAJ|SCKA|"
            r"SCED|TCES|TCUS|PBPX|PAPX|PCPX|SCCS)"
            r"[^0-9]{0,4}[0-9]{3}[^0-9]{0,3}[0-9]{2}",
            re.IGNORECASE,
        )

        for cells in parser.rows:
            if len(cells) < 5:
                continue
            if not all(
                "compatibility-tag" in cells[index].get("class", "")
                for index in (1, 2, 3)
            ):
                continue

            title_text = cells[0].get("text", "")
            names = []
            for part in re.split(r"\s*[|•]\s*", title_text):
                part = re.sub(r"\s+", " ", part).strip()
                if part and part not in names:
                    names.append(part)

            row_text = " ".join(
                [cell.get("text", "") for cell in cells]
                + [
                    meta
                    for cell in cells
                    for meta in cell.get("meta", [])
                ]
            )
            serials = serial_pattern.findall(row_text)

            parsed_rows.append(
                {
                    "names": names or [title_text],
                    "statuses": [
                        cells[1].get("text", "").strip(),
                        cells[2].get("text", "").strip(),
                        cells[3].get("text", "").strip(),
                    ],
                    "notes": cells[4].get("text", "").strip(),
                    "serials": serials,
                }
            )

        return parsed_rows

    @staticmethod
    def compatibility_region(disc_id):
        prefix = str(disc_id).upper()[:4]
        pal = {"SLES", "SCES", "SCED", "TCES"}
        ntsc_u = {"SLUS", "SCUS", "TCUS"}
        ntsc_j = {
            "SLPM", "SLPS", "SCPS", "SCAJ", "SCKA", "SCCS",
            "PAPX", "PBPX", "PCPX",
        }

        if prefix in pal:
            return 0, "PAL-EU"
        if prefix in ntsc_u:
            return 1, "NTSC-U"
        if prefix in ntsc_j:
            return 2, "NTSC-J/Asia"
        return None, "Region unknown"

    def _compatibility_title_score(self, query, candidate):
        query = self.normalize_compatibility_title(query)
        candidate = self.normalize_compatibility_title(candidate)
        if not query or not candidate:
            return 0.0
        if query == candidate:
            return 1.0

        sequence = difflib.SequenceMatcher(
            None,
            query,
            candidate,
        ).ratio()
        query_tokens = set(query.split())
        candidate_tokens = set(candidate.split())
        union = query_tokens | candidate_tokens
        overlap = (
            len(query_tokens & candidate_tokens) / len(union)
            if union
            else 0.0
        )

        containment = 0.0
        shorter = min(len(query), len(candidate))
        longer = max(len(query), len(candidate))
        if shorter >= 7 and (query in candidate or candidate in query):
            containment = 0.88 + 0.12 * (shorter / longer)

        return max(sequence, overlap, containment)

    def find_compatibility_match(self, rows, disc_id, title, source_text):
        normalized_disc = self.normalize_disc_id(disc_id or "")
        compact_disc = (
            re.sub(r"[^A-Z0-9]", "", normalized_disc)
            if normalized_disc
            else ""
        )

        if compact_disc:
            for row in rows:
                if compact_disc in row.get("_compact_serials", set()):
                    return row, 1.0, "disc ID"

        queries = []
        if title:
            queries.append(title)
        if source_text:
            source_title = self.clean_title_from_path(source_text)
            if source_title and source_title not in queries:
                queries.append(source_title)

        normalized_queries = [
            self.normalize_compatibility_title(value)
            for value in queries
        ]
        normalized_queries = [value for value in normalized_queries if value]
        if not normalized_queries:
            return None, 0.0, "none"

        # Exact normalized titles are common and should return immediately.
        for row in rows:
            names = row.get("_normalized_names") or [
                self.normalize_compatibility_title(value)
                for value in row.get("names", [])
            ]
            if any(query in names for query in normalized_queries):
                return row, 1.0, "title"

        # Cheap token/containment fallback avoids thousands of SequenceMatcher
        # calls in the worker thread, which can otherwise starve Tk's UI loop.
        best_row = None
        best_score = 0.0
        for row in rows:
            names = row.get("_normalized_names") or []
            for query in normalized_queries:
                query_tokens = set(query.split())
                for candidate in names:
                    if not candidate:
                        continue

                    score = 0.0
                    shorter = min(len(query), len(candidate))
                    longer = max(len(query), len(candidate))
                    if shorter >= 7 and (
                        query in candidate or candidate in query
                    ):
                        score = max(
                            score,
                            0.88 + 0.12 * (shorter / longer),
                        )

                    candidate_tokens = set(candidate.split())
                    union = query_tokens | candidate_tokens
                    if union:
                        score = max(
                            score,
                            len(query_tokens & candidate_tokens) / len(union),
                        )

                    if score > best_score:
                        best_score = score
                        best_row = row

        if best_row is not None and best_score >= 0.76:
            return best_row, best_score, "title"

        return None, best_score, "none"

    def _compatibility_worker(
        self,
        request_id,
        disc_id,
        title,
        source_text,
    ):
        try:
            rows = self.load_local_compatibility_rows()
            datacenter_title, datacenter_source = (
                self.resolve_title_from_datacenter(disc_id)
                if disc_id
                else ("", "unavailable")
            )

            lookup_title = datacenter_title or title
            row, _score, _match_method = self.find_compatibility_match(
                rows,
                disc_id,
                lookup_title,
                source_text,
            )

            if row is None and datacenter_title and title:
                row, _score, _match_method = self.find_compatibility_match(
                    rows,
                    disc_id,
                    title,
                    source_text,
                )

            region_index, region_name = self.compatibility_region(disc_id)
            serial = self.datacenter_serial(disc_id)

            if row is None:
                display_name = datacenter_title or title or "Unknown title"
                status = "Not listed"
                notes = ""
            else:
                statuses = row.get("statuses", [])
                if region_index is None:
                    region_index = next(
                        (
                            index
                            for index, value in enumerate(statuses)
                            if value not in {"", "Not Available"}
                        ),
                        0,
                    )
                    region_name = (
                        "PAL-EU", "NTSC-U", "NTSC-J/Asia"
                    )[region_index]

                status = (
                    statuses[region_index]
                    if region_index < len(statuses)
                    else "Unknown"
                )
                display_name = (
                    datacenter_title
                    or (row.get("names") or [title or "Unknown title"])[0]
                )
                notes = row.get("notes", "")

            details = [
                value
                for value in (region_name, display_name, serial)
                if value
            ]
            match_text = " · ".join(details)
            if datacenter_source == "cache" or self.compatibility_cache_exists():
                match_text += " (cache)"

            self.compatibility_queue.put(
                (
                    "result",
                    request_id,
                    {
                        "status": status or "Unknown",
                        "notes": notes,
                        "match": match_text,
                    },
                )
            )
        except Exception as error:
            self.compatibility_queue.put(
                ("error", request_id, str(error))
            )

    def poll_compatibility_queue(self):
        try:
            while True:
                event = self.compatibility_queue.get_nowait()
                event_type, request_id = event[0], event[1]

                if request_id != self.compatibility_request_id:
                    continue

                if event_type == "error":
                    self.stop_compatibility_spinner()
                    self.compatibility_status.set("Unavailable")
                    self.compatibility_status_label.configure(
                        bg=self.COLOR_PANEL,
                        fg=self.COLOR_TEXT_MUTED,
                    )
                    self.compatibility_match.set("")
                    self.compatibility_notes.set("")
                    self.compatibility_notes_button.configure(
                        text="Notes",
                        state=tk.DISABLED,
                    )
                    self.compatibility_notes_label.pack_forget()
                    continue

                self.stop_compatibility_spinner()
                result = event[2]
                status = result.get("status", "Unknown")
                colors = self.COMPATIBILITY_COLORS.get(
                    status,
                    (self.COLOR_PANEL, self.COLOR_TEXT_MUTED),
                )
                self.compatibility_status.set(status)
                self.compatibility_status_label.configure(
                    bg=colors[0],
                    fg=colors[1],
                )
                self.compatibility_match.set(result.get("match", ""))

                notes = result.get("notes", "").strip()
                self.compatibility_notes.set(notes)
                self.compatibility_notes_expanded = False
                self.compatibility_notes_label.pack_forget()
                self.compatibility_notes_button.configure(
                    text="▶ Notes" if notes else "Notes",
                    state=tk.NORMAL if notes else tk.DISABLED,
                )
        except queue.Empty:
            pass

        try:
            self.root.after(150, self.poll_compatibility_queue)
        except tk.TclError:
            pass

    def browse_vmc(self):
        self.choose_file(
            "vmc",
            self.vmc_path,
            "Select a VMC file",
            [
                ("Virtual Memory Card", "*.vmc *.bin"),
                ("All files", "*.*"),
            ],
        )

    def browse_eid_root_key(self):
        self.choose_file(
            "eid_root_key",
            self.eid_root_key_path,
            "Select an EID Root Key",
            [
                ("Key files", "*.key *.bin"),
                ("All files", "*.*"),
            ],
        )

    def browse_make_npdata(self):
        self.choose_file(
            "make_npdata",
            self.make_npdata_path,
            "Select make_npdata.exe",
            [
                ("make_npdata", "make_npdata.exe make_npdata"),
                ("Executables", "*.exe"),
                ("All files", "*.*"),
            ],
        )
        self.update_build_readiness()

    def browse_output(self):
        folder = filedialog.askdirectory(
            title="Select the output folder",
            initialdir=self.get_initial_dir("output"),
        )

        if folder:
            self.output_dir.set(folder)
            self.remember_path("output", folder)

    # -------------------------------------------------------
    # XMB preview
    # -------------------------------------------------------

    def load_existing_assets(self):
        # Expose fallback assets in the fields; clearing stays explicit.
        self.populate_default_asset_fields(force=True)

    def asset_variable_map(self):
        return {
            "ICON0.PNG": self.icon0_path,
            "PIC0.PNG": self.pic0_path,
            "PIC1.PNG": self.pic1_path,
        }

    def clear_field(self, variable):
        for asset_name, asset_variable in self.asset_variable_map().items():
            if variable is asset_variable:
                self.cleared_assets.add(asset_name)
                self.auto_asset_paths.pop(asset_name, None)
                self.manual_asset_paths.pop(asset_name, None)
                variable.set("")
                self.schedule_preview()
                return

        if variable is self.param_hip_path:
            self.auto_config_path = ""

        variable.set("")

    def populate_default_asset_fields(self, force=False):
        for asset_name, variable in self.asset_variable_map().items():
            if asset_name in self.cleared_assets:
                continue

            manual = self.manual_asset_paths.get(asset_name, "")
            if manual:
                if variable.get().strip() != manual:
                    variable.set(manual)
                continue

            current = variable.get().strip()
            old_auto = self.auto_asset_paths.get(asset_name, "")
            manually_selected = bool(
                current
                and Path(current).is_file()
                and current != old_auto
            )
            if manually_selected and not force:
                continue

            fallback = self.find_asset_fallback(asset_name)
            if fallback:
                value = str(fallback)
                variable.set(value)
                self.auto_asset_paths[asset_name] = value


    def load_existing_tools(self):
        candidate = self.find_tool_recursive(
            "make_npdata.exe",
            "make_npdata",
        )
        if candidate:
            self.make_npdata_path.set(str(candidate))

    @staticmethod
    def compact_disc_title_id(disc_id):
        if not disc_id:
            return ""
        compact = re.sub(r"[^A-Z0-9]", "", str(disc_id).upper())
        return compact[:9]

    def generated_content_id(self, disc_id, title_id):
        """Create a stable per-game package Content ID."""
        title_id = re.sub(r"[^A-Z0-9]", "", str(title_id).upper())[:9]
        if len(title_id) != 9:
            return ""
        return f"2P0001-{title_id}_00-PS2CLASSICS00000"

    @staticmethod
    def clean_title_from_path(path):
        name = Path(path).stem
        name = re.sub(
            r"(?i)(SLUS|SLES|SCUS|SCES|SLPM|SLPS|SCPS|SCAJ|SCKA|SCED|TCES|TCUS|PBPX)"
            r"[ _.-]*[0-9]{3}[ ._-]*[0-9]{2}",
            "",
            name,
        )
        name = re.sub(r"[_\.]+", " ", name)
        name = re.sub(r"\s+", " ", name).strip(" -_")
        return name or Path(path).stem

    def find_nearby_file(self, source, filename):
        source = Path(source)
        directories = [source.parent]
        current = source.parent
        for _ in range(3):
            current = current.parent
            directories.append(current)

        for directory in directories:
            candidate = directory / filename
            if candidate.is_file():
                return candidate

        return None

    def find_sidecar_edat(self, source=None):
        selected = self.edat_source_path.get().strip()
        if selected and Path(selected).is_file():
            return Path(selected)

        source_text = source or self.iso_path.get().strip()
        if not source_text:
            return None

        source_path = Path(source_text)
        candidates = [
            source_path.parent / "ISO.BIN.EDAT",
            source_path.with_name("ISO.BIN.EDAT"),
            source_path.parent.parent / "USRDIR" / "ISO.BIN.EDAT",
            source_path.parent.parent / "ISO.BIN.EDAT",
        ]

        for candidate in candidates:
            if candidate.is_file():
                return candidate

        return None

    def read_edat_basic_info(self, edat_path):
        data = Path(edat_path).read_bytes()
        if len(data) < 0x90 or data[:4] != b"NPD\x00":
            raise RuntimeError("The selected ISO.BIN.EDAT has no valid NPD header.")

        content_id = data[0x10:0x40].split(b"\x00", 1)[0].decode(
            "ascii", errors="replace"
        )
        flags, block_size, payload_size = struct.unpack_from(">IIQ", data, 0x80)
        return {
            "content_id": content_id,
            "flags": flags,
            "block_size": block_size,
            "payload_size": payload_size,
        }

    @staticmethod
    def disc_id_from_edat_payload(payload):
        text = payload.decode("ascii", errors="ignore").strip("\x00\r\n ")
        match = re.fullmatch(r"([A-Z]{4})_?([0-9]{3})\.?([0-9]{2})", text.upper())
        if not match:
            return None
        return f"{match.group(1)}_{match.group(2)}.{match.group(3)}"

    def decrypt_edat_for_metadata(self, edat_path, content_id):
        make_npdata = self.find_make_npdata()
        rap_path = self.find_rap_file(content_id)
        if not make_npdata or not rap_path:
            return None

        with tempfile.TemporaryDirectory(prefix="ps2_edat_meta_") as temp_name:
            temp_dir = Path(temp_name)
            klic = re.sub(r"\s+", "", self.klicensee.get())
            if not re.fullmatch(r"[0-9A-Fa-f]{32}", klic):
                return None
            (temp_dir / "klic.bin").write_bytes(bytes.fromhex(klic))
            output = temp_dir / "ISO.BIN.DAT"

            try:
                self.run_command(
                    [make_npdata, "-v", "-d", edat_path, output, "8", rap_path],
                    temp_dir,
                )
            except Exception:
                return None

            if not output.is_file():
                return None
            return self.disc_id_from_edat_payload(output.read_bytes())

    def find_nearby_sfo_values(self, source):
        sfo = self.find_nearby_file(source, "PARAM.SFO")
        if not sfo:
            return {}
        try:
            return self.sfo_to_values(sfo)
        except Exception:
            return {}

    def get_placeholder_identity(self):
        """Read the original GUI placeholder identity from PS2U10000."""
        template = self.find_template_dir()
        if not template:
            return {}

        values = {}
        sfo_path = template / "PARAM.SFO"
        edat_path = template / "USRDIR" / "ISO.BIN.EDAT"

        if sfo_path.is_file():
            try:
                sfo_values = self.sfo_to_values(sfo_path)
                values["title_id"] = str(
                    sfo_values.get("TITLE_ID", "")
                ).strip().upper()
                values["version"] = str(
                    sfo_values.get("VERSION")
                    or sfo_values.get("APP_VER")
                    or "01.00"
                ).strip()
            except Exception as error:
                self.log(f"Placeholder PARAM.SFO warning: {error}")

        if edat_path.is_file():
            try:
                info = self.read_edat_basic_info(edat_path)
                values["content_id"] = info["content_id"].upper()
            except Exception as error:
                self.log(f"Placeholder EDAT warning: {error}")

        if values.get("content_id") and not values.get("title_id"):
            values["title_id"] = (
                self.content_id_title_id(values["content_id"]) or ""
            )

        return values

    def auto_populate_metadata(self):
        source_text = self.iso_path.get().strip()
        if not source_text or not Path(source_text).is_file():
            return

        source = Path(source_text)
        encrypted_mode = self.input_mode.get() == "encrypted"
        individual_mode = (
            not encrypted_mode and self.create_individual_edat.get()
        )
        sfo_values = self.find_nearby_sfo_values(source)
        disc_id = None
        content_id = ""

        if encrypted_mode:
            edat = self.find_sidecar_edat(source)
            if edat:
                self.edat_source_path.set(str(edat))
                try:
                    info = self.read_edat_basic_info(edat)
                    content_id = info["content_id"].upper()
                    disc_id = self.decrypt_edat_for_metadata(edat, content_id)
                except Exception as error:
                    self.log(f"EDAT metadata warning: {error}")
            if not disc_id:
                disc_id = self.detect_disc_id(source)
        else:
            disc_id = self.detect_disc_id(source)

        if disc_id:
            self.detected_disc_id.set(disc_id)
            self.disc_id_cache_path = str(source.resolve())
            self.disc_id_cache_value = disc_id
        else:
            self.detected_disc_id.set("")

        self.populate_config_field(disc_id)

        title = str(sfo_values.get("TITLE", "")).strip()
        if not title:
            if encrypted_mode and source.parent.name.upper() == "USRDIR":
                title = source.parent.parent.name
            else:
                title = self.clean_title_from_path(source)

        if encrypted_mode:
            edat_content_id = content_id
            title_id = self.compact_disc_title_id(disc_id) if disc_id else ""
            if not title_id:
                nearby_title_id = str(
                    sfo_values.get("TITLE_ID", "")
                ).strip().upper()
                if nearby_title_id and nearby_title_id != "PS2U10000":
                    title_id = nearby_title_id
            if not title_id and edat_content_id:
                candidate_title_id = self.content_id_title_id(edat_content_id) or ""
                if candidate_title_id != "PS2U10000":
                    title_id = candidate_title_id
            version = str(
                sfo_values.get("VERSION")
                or sfo_values.get("APP_VER")
                or "01.00"
            ).strip()
            content_id = (
                self.generated_content_id(disc_id, title_id)
                if title_id
                else ""
            )
        else:
            title_id = self.compact_disc_title_id(disc_id) if disc_id else ""
            placeholder = self.get_placeholder_identity()
            version = str(
                sfo_values.get("VERSION")
                or sfo_values.get("APP_VER")
                or placeholder.get("version")
                or "01.00"
            ).strip()
            if title_id:
                content_id = self.generated_content_id(disc_id, title_id)

        if title:
            self.game_title.set(title)
        if title_id:
            self.title_id.set(title_id)
        if content_id:
            self.content_id.set(content_id)
        if version:
            self.version.set(version)

        self.populate_default_asset_fields()
        self.schedule_preview()
        self.schedule_compatibility_check()
        self.schedule_build_readiness()

    def asset_search_score(self, candidate, asset_name):
        score = 0
        path_text = str(candidate).upper()
        disc_id = self.detected_disc_id.get().upper()
        compact_disc = re.sub(r"[^A-Z0-9]", "", disc_id)

        if candidate.name.upper() == asset_name.upper():
            score += 10
        if candidate.parent == self.script_dir / "PS2Covers":
            score += 8
        if compact_disc and compact_disc in re.sub(r"[^A-Z0-9]", "", path_text):
            score += 30

        title_tokens = [
            token.upper()
            for token in re.findall(r"[A-Za-z0-9]+", self.game_title.get())
            if len(token) >= 4
        ]
        score += sum(3 for token in title_tokens if token in path_text)
        return score

    def find_asset_fallback(self, asset_name):
        candidates = []
        covers = self.script_dir / "PS2Covers"
        template = self.find_template_dir()

        direct_candidates = [
            covers / asset_name,
            self.script_dir / asset_name,
        ]
        if template:
            direct_candidates.append(template / asset_name)

        for candidate in direct_candidates:
            if candidate.is_file():
                candidates.append(candidate)

        if covers.is_dir():
            try:
                for candidate in covers.rglob("*"):
                    if (
                        candidate.is_file()
                        and candidate.name.upper() == asset_name.upper()
                    ):
                        candidates.append(candidate)
            except OSError:
                pass

        if not candidates:
            return None

        candidates = list(dict.fromkeys(candidates))
        candidates.sort(
            key=lambda item: self.asset_search_score(item, asset_name),
            reverse=True,
        )
        return candidates[0]

    def resolve_asset_path(self, asset_name, selected_text=None):
        # Empty fields intentionally disable the visible asset.
        if selected_text:
            selected = Path(selected_text)
            return selected if selected.is_file() else None
        if selected_text is None:
            return self.find_asset_fallback(asset_name)
        return None

    def copy_resolved_asset(self, asset_name, selected_text, destination):
        source = self.resolve_asset_path(asset_name, selected_text)
        if not source:
            return False

        destination = Path(destination)
        destination.unlink(missing_ok=True)
        self.copy_image_as_png(source, destination)
        self.validate_package_image_asset(asset_name, destination)
        self.log(f"{asset_name} source: {source}")
        return True

    def snapshot_package_asset_sources(self):
        """Freeze the visible/manual asset choices for the current build."""
        sources = {}
        for asset_name, variable in self.asset_variable_map().items():
            selected_text = (
                self.manual_asset_paths.get(asset_name)
                or variable.get().strip()
            )
            if not selected_text:
                sources[asset_name] = None
                continue

            source = Path(selected_text)
            if not source.is_file():
                raise RuntimeError(
                    f"{asset_name} source no longer exists: {source}"
                )
            sources[asset_name] = source.resolve()
        return sources

    def validate_package_image_asset(self, asset_name, path):
        path = Path(path)
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"{asset_name} was not written correctly.")

        target_size = self.PACKAGE_IMAGE_SIZES.get(asset_name.upper())
        if Image is None or not target_size:
            return

        with Image.open(path) as image:
            if image.format != "PNG":
                raise RuntimeError(f"{asset_name} is not a PNG file.")
            if image.size != target_size:
                raise RuntimeError(
                    f"{asset_name} has size {image.size[0]}x{image.size[1]}, "
                    f"expected {target_size[0]}x{target_size[1]}."
                )

    @staticmethod
    def point_in_rect(x, y, rect):
        return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]

    def preview_action_at(self, x, y):
        icon_rect = (45, 105, 185, 190)
        title_rect = (205, 108, 462, 158)
        panel_rect = (238, 166, 462, 317)

        if self.point_in_rect(x, y, icon_rect):
            return self.browse_icon0
        if self.point_in_rect(x, y, title_rect):
            return self.edit_game_title_from_preview
        if self.point_in_rect(x, y, panel_rect):
            return self.browse_pic0
        return self.browse_pic1

    def edit_game_title_from_preview(self):
        value = simpledialog.askstring(
            "Edit game title",
            "Game title:",
            initialvalue=self.game_title.get().strip(),
            parent=self.root,
        )
        if value is not None:
            normalized = re.sub(r"\s+", " ", value).strip()
            self.game_title.set(normalized)
            self.schedule_preview()
            self.schedule_build_readiness()

    def on_preview_click(self, event):
        self.preview_action_at(event.x, event.y)()

    def on_preview_motion(self, event):
        self.preview_canvas.configure(cursor="hand2")

    def schedule_preview(self, *_args):
        if self._preview_after_id is not None:
            self.root.after_cancel(self._preview_after_id)
        self._preview_after_id = self.root.after(
            120, self.update_live_preview
        )

    def open_rgba(self, path):
        with Image.open(path) as source:
            return source.convert("RGBA")

    def contain_on_canvas(self, image, size):
        result = Image.new("RGBA", size, (0, 0, 0, 0))
        fitted = ImageOps.contain(
            image,
            size,
            method=Image.Resampling.LANCZOS,
        )
        x = (size[0] - fitted.width) // 2
        y = (size[1] - fitted.height) // 2
        result.alpha_composite(fitted, (x, y))
        return result

    def update_live_preview(self):
        self._preview_after_id = None
        self.preview_canvas.delete("all")

        width, height = 470, 330

        if not all((Image, ImageOps, ImageTk, ImageDraw)):
            self.preview_canvas.create_text(
                width // 2,
                height // 2,
                text="Pillow is missing:\npip install Pillow",
                fill="#ffffff",
                justify="center",
                font=("Segoe UI", 14, "bold"),
            )
            return

        try:
            # Base XMB-style gradient.
            preview = Image.new("RGBA", (width, height), (0, 0, 0, 255))
            pixels = preview.load()

            gradient_start = 104
            for y in range(gradient_start, height):
                ratio = (y - gradient_start) / max(
                    1, height - gradient_start - 1
                )
                red = int(5 + 38 * ratio)
                green = int(10 + 78 * ratio)
                blue = int(18 + 112 * ratio)
                for x in range(width):
                    pixels[x, y] = (red, green, blue, 255)

            # PIC1 background with a dark overlay.
            pic1_path = self.resolve_asset_path(
                "PIC1.PNG", self.pic1_path.get().strip()
            )
            pic1 = str(pic1_path) if pic1_path else ""
            if pic1:
                image = ImageOps.fit(
                    self.open_rgba(pic1),
                    (width, height),
                    method=Image.Resampling.LANCZOS,
                )
                dark = Image.new(
                    "RGBA", (width, height), (0, 0, 0, 105)
                )
                image = Image.alpha_composite(image, dark)
                preview = Image.alpha_composite(preview, image)

            draw = ImageDraw.Draw(preview)

            # ICON0 area.
            icon_rect = (45, 105, 185, 190)
            icon0_path = self.resolve_asset_path(
                "ICON0.PNG", self.icon0_path.get().strip()
            )
            icon0 = str(icon0_path) if icon0_path else ""

            if icon0:
                icon = self.contain_on_canvas(
                    self.open_rgba(icon0),
                    (
                        icon_rect[2] - icon_rect[0],
                        icon_rect[3] - icon_rect[1],
                    ),
                )
                preview.alpha_composite(
                    icon, (icon_rect[0], icon_rect[1])
                )
            else:
                draw.rounded_rectangle(
                    icon_rect,
                    radius=3,
                    fill=(13, 17, 25, 230),
                    outline=(95, 115, 150, 255),
                    width=2,
                )
                draw.text(
                    (96, 141),
                    "ICON0",
                    anchor="mm",
                    fill=(230, 230, 230, 255),
                )

            # Game title.
            title = self.game_title.get().strip() or "PS2 Classics"
            draw.text(
                (215, 129),
                title,
                fill=(255, 255, 255, 255),
                stroke_width=1,
                stroke_fill=(0, 0, 0, 255),
            )

            # PIC0 is the complete information panel.
            panel = (238, 166, 462, 317)
            panel_size = (
                panel[2] - panel[0],
                panel[3] - panel[1],
            )
            pic0_path = self.resolve_asset_path(
                "PIC0.PNG", self.pic0_path.get().strip()
            )
            pic0 = str(pic0_path) if pic0_path else ""

            if pic0:
                complete_pic0 = self.contain_on_canvas(
                    self.open_rgba(pic0),
                    panel_size,
                )
                preview.alpha_composite(
                    complete_pic0,
                    (panel[0], panel[1]),
                )
            else:
                draw.rounded_rectangle(
                    panel,
                    radius=8,
                    fill=(18, 18, 25, 230),
                    outline=(218, 218, 218, 255),
                    width=2,
                )
                draw.rectangle(
                    (
                        panel[0] + 1,
                        panel[1] + 31,
                        panel[2] - 1,
                        panel[1] + 33,
                    ),
                    fill=(69, 78, 163, 255),
                )
                draw.text(
                    (panel[0] + 12, panel[1] + 10),
                    title,
                    fill=(255, 255, 255, 255),
                )
                draw.text(
                    (panel[0] + 12, panel[1] + 47),
                    "No PIC0.PNG selected",
                    fill=(236, 236, 236, 255),
                )

            self.preview_photo = ImageTk.PhotoImage(preview)
            self.preview_canvas.create_image(
                0, 0, image=self.preview_photo, anchor="nw"
            )

            selected = []
            for label, filename, variable in (
                ("ICON0", "ICON0.PNG", self.icon0_path),
                ("PIC1", "PIC1.PNG", self.pic1_path),
                ("PIC0", "PIC0.PNG", self.pic0_path),
            ):
                if self.resolve_asset_path(filename, variable.get().strip()):
                    selected.append(label)

            if self.snd0_path.get() and Path(self.snd0_path.get()).is_file():
                selected.append("SND0")
            if self.param_hip_path.get() and Path(self.param_hip_path.get()).is_file():
                selected.append("CONFIG")

            self.preview_info.config(
                text="Preview: "
                + (", ".join(selected) if selected else "no assets")
                + "\nClick the title to edit it; click an image area to choose its asset."
            )

        except Exception as error:
            self.preview_canvas.create_text(
                width // 2,
                height // 2,
                text=f"Preview error:\n{error}",
                fill="#ffffff",
                justify="center",
                width=420,
            )

    # -------------------------------------------------------
    # Logging and progress
    # -------------------------------------------------------

    def pump_ui(self):
        try:
            self.root.update_idletasks()
            self.root.update()
        except tk.TclError:
            pass

    def log(self, message):
        self.log_box.insert(tk.END, str(message) + "\n")
        self.log_box.see(tk.END)
        self.pump_ui()

    def set_status(self, message):
        self.status_text.set(str(message))
        self.pump_ui()

    def set_progress(self, value):
        try:
            self.progress.stop()
        except tk.TclError:
            pass
        self.progress.configure(mode="determinate")
        self.progress["value"] = value
        self.pump_ui()

    def begin_busy(self, message):
        self.status_text.set(str(message))
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.pump_ui()

    def end_busy(self):
        try:
            self.progress.stop()
        except tk.TclError:
            pass
        self.progress.configure(mode="determinate")
        self.pump_ui()

    def copy_file_with_progress(
        self, source, destination, start_value, end_value, label
    ):
        source = Path(source)
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        total = source.stat().st_size
        copied = 0
        chunk_size = 8 * 1024 * 1024
        self.set_status(label)

        with source.open("rb") as src, destination.open("wb") as dst:
            while True:
                chunk = src.read(chunk_size)
                if not chunk:
                    break
                dst.write(chunk)
                copied += len(chunk)
                ratio = copied / total if total else 1.0
                value = start_value + (end_value - start_value) * ratio
                self.progress.configure(mode="determinate")
                self.progress["value"] = value
                self.status_text.set(
                    f"{label} · {copied / (1024**2):,.0f} / "
                    f"{total / (1024**2):,.0f} MiB"
                )
                self.pump_ui()

        shutil.copystat(source, destination)
        self.set_progress(end_value)
        return destination

    def find_tool(self, *names):
        for name in names:
            candidate = self.script_dir / name
            if candidate.is_file():
                return candidate
        return None

    def find_tool_recursive(self, *names):
        wanted = {name.lower() for name in names}

        for name in names:
            candidate = self.script_dir / name
            if candidate.is_file():
                return candidate

        try:
            for candidate in self.script_dir.rglob("*"):
                if not candidate.is_file():
                    continue

                if candidate.name.lower() not in wanted:
                    continue

                if any(
                    part.lower().startswith("ps2_classics_gui_mod_")
                    for part in candidate.parts
                ):
                    continue

                return candidate
        except OSError:
            pass

        return None

    def find_make_npdata(self):
        selected_text = self.make_npdata_path.get().strip()
        if selected_text:
            selected = Path(selected_text)
            if selected.is_file():
                return selected

        return self.find_tool_recursive(
            "make_npdata.exe",
            "make_npdata",
        )

    def find_pkg_tool(self):
        # Prefer the packer shipped with the original GUI.
        tool = self.find_tool_recursive(
            "psn_package_npdrm.exe",
            "make_package_npdrm.exe",
        )
        if tool:
            return tool

        # Optional compatible pop-fe2/PSL1GHT packer.
        return self.find_tool_recursive("pkg.exe")

    def find_rap_file(self, content_id=None):
        content_id = (
            content_id
            or self.content_id.get().strip()
        )

        if not content_id:
            return None

        rap_name = content_id + ".rap"
        preferred = (
            self.script_dir / rap_name,
            self.script_dir / "exdata" / rap_name,
            self.script_dir / "EXDATA" / rap_name,
        )

        for candidate in preferred:
            if candidate.is_file() and candidate.stat().st_size == 16:
                return candidate

        try:
            for candidate in self.script_dir.rglob("*.rap"):
                if (
                    candidate.name.lower() == rap_name.lower()
                    and candidate.is_file()
                    and candidate.stat().st_size == 16
                ):
                    return candidate
        except OSError:
            pass

        return None

    def require_rap_file(self, content_id):
        """Return a user-provided matching RAP file."""
        rap_path = self.find_rap_file(content_id)
        if rap_path:
            return rap_path

        raise RuntimeError(
            "A matching 16-byte RAP file is required in the project root "
            "or an exdata folder for game-specific EDAT mode."
        )

    def refresh_disc_id_cache(self):
        if self.input_mode.get() == "encrypted":
            value = self.detected_disc_id.get().strip()
            return value or None

        path_text = self.iso_path.get().strip()
        path = Path(path_text) if path_text else None

        if not path or not path.is_file():
            self.disc_id_cache_path = None
            self.disc_id_cache_value = None
            return None

        resolved = str(path.resolve())

        if self.disc_id_cache_path == resolved:
            return self.disc_id_cache_value

        self.disc_id_cache_path = resolved
        self.disc_id_cache_value = self.detect_disc_id(path)
        if self.disc_id_cache_value:
            self.detected_disc_id.set(self.disc_id_cache_value)
        return self.disc_id_cache_value

    @staticmethod
    def format_edat_game_id(disc_id):
        """Return the ten-character make_npdata game ID format."""
        if not disc_id:
            return None

        match = re.fullmatch(
            r"([A-Z]{4})_?([0-9]{3})\.?([0-9]{2})",
            str(disc_id).upper(),
        )

        if not match:
            return None

        return (
            f"{match.group(1)}_"
            f"{match.group(2)}"
            f"{match.group(3)}"
        )

    @staticmethod
    def valid_content_id(value):
        return bool(
            re.fullmatch(
                r"[A-Z0-9]{6}-[A-Z0-9]{9}_[0-9]{2}-[A-Z0-9]{16}",
                value.strip().upper(),
            )
        )

    @staticmethod
    def valid_version(value):
        return bool(re.fullmatch(r"[0-9]{2}\.[0-9]{2}", value.strip()))

    def valid_image_file(self, path_text):
        path = Path(path_text.strip()) if path_text.strip() else None

        if not path or not path.is_file():
            return False

        if Image is None:
            return path.suffix.lower() == ".png"

        try:
            with Image.open(path) as image:
                image.verify()
            return True
        except Exception:
            return False

    def schedule_build_readiness(self):
        if getattr(self, "_readiness_after_id", None) is not None:
            try:
                self.root.after_cancel(self._readiness_after_id)
            except tk.TclError:
                pass

        self._readiness_after_id = self.root.after(
            180,
            self.update_build_readiness,
        )

    def get_build_requirements(self):
        source_text = self.iso_path.get().strip()
        output_text = self.output_dir.get().strip()
        content_id = self.content_id.get().strip().upper()
        title_id = self.title_id.get().strip().upper()
        version = self.version.get().strip()
        klicensee = re.sub(r"\s+", "", self.klicensee.get())
        encrypted_mode = self.input_mode.get() == "encrypted"
        individual_mode = (
            not encrypted_mode and self.create_individual_edat.get()
        )

        source_path = Path(source_text) if source_text else None
        source_ok = bool(source_path and source_path.is_file())
        disc_id = self.refresh_disc_id_cache() if source_ok else None
        edat_game_id = self.format_edat_game_id(disc_id)
        sidecar_edat = self.find_sidecar_edat(source_path) if source_ok else None

        output_ok = False
        if output_text:
            output_path = Path(output_text)
            output_ok = output_path.is_dir() or output_path.parent.is_dir()

        expected_title_id = self.content_id_title_id(content_id)
        make_npdata = self.find_make_npdata()
        ps2classic = self.find_tool_recursive("ps2classic.exe")
        pkg_tool = self.find_pkg_tool()
        template = self.find_template_dir()
        placeholder = self.get_placeholder_identity() if template else {}
        placeholder_rap = self.find_placeholder_rap() if template else None
        custom_rap = self.find_rap_file(content_id) if individual_mode else None
        edat_rap = custom_rap if individual_mode else placeholder_rap

        manual_config = bool(
            self.param_hip_path.get().strip()
            and Path(self.param_hip_path.get().strip()).is_file()
        )
        ps2classic_required = (
            not encrypted_mode or manual_config or self.encrypt_vmc.get()
        )

        selected_package_icon = self.resolve_asset_path(
            "ICON0.PNG", self.icon0_path.get().strip()
        )
        template_package_icon = (
            template / "ICON0.PNG" if template else None
        )
        package_icon = selected_package_icon or (
            template_package_icon
            if template_package_icon and template_package_icon.is_file()
            else None
        )

        requirements = [
            ("Build source", source_ok, source_text or "not selected"),
            (
                "Source mode",
                True,
                "existing ISO.BIN.ENC" if encrypted_mode else "raw PS2 image",
            ),
        ]

        if encrypted_mode:
            edat_ok = bool(sidecar_edat and sidecar_edat.is_file())
            requirements.append(
                (
                    "ISO.BIN.EDAT sidecar",
                    edat_ok,
                    str(sidecar_edat or "not found next to ISO.BIN.ENC"),
                )
            )
        else:
            requirements.append(
                (
                    "PS2 disc ID",
                    bool(edat_game_id),
                    edat_game_id or "could not be detected",
                )
            )
            requirements.append(
                (
                    "EDAT creation",
                    bool(make_npdata and edat_rap),
                    (
                        "custom package identity via "
                        + str(custom_rap or "missing matching RAP")
                        if individual_mode
                        else (
                            "universal PS2 Classics identity via "
                            + str(placeholder_rap or "missing placeholder RAP")
                        )
                    ),
                )
            )
            requirements.append(
                (
                    "make_npdata.exe",
                    bool(make_npdata),
                    str(make_npdata or "required to create ISO.BIN.EDAT"),
                )
            )

        content_ok = self.valid_content_id(content_id)
        content_details = content_id or "not discovered/generated"

        requirements.extend(
            [
                (
                    "Package ICON0",
                    bool(package_icon),
                    str(
                        package_icon
                        or "no manual, PS2Covers, program or template fallback"
                    ),
                ),
                ("Output folder", output_ok, output_text or "not selected"),
                (
                    "Game title",
                    bool(self.game_title.get().strip()),
                    self.game_title.get().strip() or "not discovered",
                ),
                ("Package Content ID", content_ok, content_details),
                (
                    "Title ID",
                    bool(expected_title_id) and title_id == expected_title_id,
                    title_id if title_id == expected_title_id else (
                        f"must be {expected_title_id or 'derived from Content ID'}"
                    ),
                ),
                (
                    "Version",
                    self.valid_version(version),
                    version or "not discovered/generated",
                ),
                (
                    "Klicensee",
                    bool(
                        re.fullmatch(r"[0-9A-Fa-f]{32}", klicensee)
                        or (
                            getattr(self, "ps2_key_source_file", None)
                            and Path(self.ps2_key_source_file).is_file()
                        )
                        or self.get_ps2_key_generation_source()
                    ),
                    (
                        str(self.ps2_klicensee_source or "manual field")
                        if re.fullmatch(r"[0-9A-Fa-f]{32}", klicensee)
                        else (
                            str(self.ps2_key_source_file)
                            if (
                                getattr(
                                    self,
                                    "ps2_key_source_file",
                                    None,
                                )
                                and Path(
                                    self.ps2_key_source_file
                                ).is_file()
                            )
                            else (
                                "generated from the matching placeholder RAP"
                                if self.get_ps2_key_generation_source()
                                else "no usable local key source"
                            )
                        )
                    ),
                ),
                (
                    "ps2.key",
                    bool(
                        self.valid_ps2_key_file()
                        or (
                            self.create_project_ps2_key.get()
                            and (
                                re.fullmatch(
                                    r"[0-9A-Fa-f]{32}",
                                    klicensee,
                                )
                                or (
                                    getattr(
                                        self,
                                        "ps2_key_source_file",
                                        None,
                                    )
                                    and Path(
                                        self.ps2_key_source_file
                                    ).is_file()
                                )
                                or self.get_ps2_key_generation_source()
                            )
                        )
                    ),
                    (
                        str(self.ps2_key_file)
                        if self.valid_ps2_key_file()
                        and not self.create_project_ps2_key.get()
                        else (
                            (
                                str(self.script_dir / "ps2.key")
                                + " will be generated from the placeholder RAP"
                            )
                            if self.get_ps2_key_generation_source()
                            else (
                                str(self.script_dir / "ps2.key")
                                + " will be created from the Klicensee field"
                            )
                        )
                    ),
                ),
                (
                    "ps2classic.exe",
                    bool(ps2classic) if ps2classic_required else True,
                    str(
                        ps2classic
                        or (
                            "not required for this package-only build"
                            if not ps2classic_required
                            else "missing"
                        )
                    ),
                ),
                (
                    "make_npdata.exe",
                    bool(make_npdata) if individual_mode else True,
                    str(
                        make_npdata
                        or (
                            "optional in placeholder/existing-EDAT mode"
                            if not individual_mode
                            else "missing"
                        )
                    ),
                ),
                (
                    "RAP license",
                    bool(self.find_rap_file(content_id))
                    if individual_mode
                    else True,
                    (
                        str(
                            self.find_rap_file(content_id)
                            or "matching RAP missing from root/exdata"
                        )
                        if individual_mode
                        else "not required for placeholder packaging"
                    ),
                ),
                (
                    "PS2 package template",
                    template is not None,
                    str(template or "PARAM.SFO or USRDIR is missing"),
                ),
                (
                    "PKG tool",
                    pkg_tool is not None,
                    str(pkg_tool or "psn_package_npdrm.exe or pkg.exe is missing"),
                ),
            ]
        )

        if self.encrypt_vmc.get():
            vmc_ok = Path(self.vmc_path.get().strip()).is_file()
            requirements.append(
                (
                    "VMC file",
                    vmc_ok,
                    self.vmc_path.get().strip()
                    or "VMC encryption is enabled but the file is missing",
                )
            )

        return requirements

    def update_build_readiness(self):
        self._readiness_after_id = None
        requirements = self.get_build_requirements()
        ready = all(ok for _label, ok, _details in requirements)

        lines = []

        for label, ok, details in requirements:
            symbol = "OK " if ok else "!! "
            lines.append(f"{symbol}{label}: {details}")

        self.readiness_label.configure(
            text="\n".join(lines),
            fg="#66e58a" if ready else "#ffb36b",
        )

        if not self.building:
            self.build_button.configure(
                state=tk.NORMAL if ready else tk.DISABLED,
                text="MAKE PKG" if ready else "MAKE PKG · Missing requirements",
            )

        return ready

    def copy_image_as_png(self, source, destination):
        if not source:
            return False

        source_path = Path(source)
        if not source_path.is_file():
            return False

        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if Image is None:
            if source_path.suffix.lower() == ".png":
                shutil.copy2(source_path, destination)
                return True
            raise RuntimeError("Pillow is required for image conversion.")

        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image).convert("RGBA")
            asset_name = destination.name.upper()
            target_size = self.PACKAGE_IMAGE_SIZES.get(asset_name)

            if target_size:
                resampling = getattr(Image, "Resampling", Image)
                fitted = ImageOps.contain(
                    image,
                    target_size,
                    method=resampling.LANCZOS,
                )
                canvas = Image.new("RGBA", target_size, (0, 0, 0, 0))
                x = (target_size[0] - fitted.width) // 2
                y = (target_size[1] - fitted.height) // 2
                canvas.alpha_composite(fitted, (x, y))
                canvas.save(destination, "PNG", optimize=True)
                self.log(
                    f"{asset_name} normalized to "
                    f"{target_size[0]}x{target_size[1]} without stretching: "
                    f"{source_path}"
                )
            else:
                image.save(destination, "PNG", optimize=True)

        return True

    def copy_optional(self, source, destination):
        if not source or not Path(source).is_file():
            return False

        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return True

    def find_template_dir(self):
        """Locate the package template shipped with the original GUI."""
        preferred = (
            self.script_dir / "PS2U10000",
            self.script_dir / "template",
        )

        for candidate in preferred:
            if (
                candidate.is_dir()
                and (candidate / "PARAM.SFO").is_file()
                and (candidate / "USRDIR").is_dir()
            ):
                return candidate

        # Scan direct child folders for a package template.
        try:
            children = list(self.script_dir.iterdir())
        except OSError:
            children = []

        for candidate in children:
            if (
                candidate.is_dir()
                and (candidate / "PARAM.SFO").is_file()
                and (candidate / "USRDIR").is_dir()
            ):
                return candidate

        return None

    @staticmethod
    def content_id_title_id(content_id):
        """Extract the nine-character title ID from a content ID."""
        match = re.match(
            r"^[A-Za-z0-9]{6}-([A-Za-z0-9]{9})_",
            content_id.strip(),
        )
        return match.group(1).upper() if match else None

    @staticmethod
    def _align(value, alignment=4):
        return (value + alignment - 1) & ~(alignment - 1)

    def read_param_sfo(self, sfo_path):
        """Read every entry from a PARAM.SFO file."""
        sfo_path = Path(sfo_path)
        data = sfo_path.read_bytes()

        if len(data) < 20:
            raise RuntimeError("PARAM.SFO is too small or damaged.")

        magic, version, key_table_offset, data_table_offset, entry_count = (
            struct.unpack_from("<4sIIII", data, 0)
        )

        if magic != b"\x00PSF":
            raise RuntimeError(
                f"Invalid PARAM.SFO magic: {magic!r}"
            )

        entries = []

        for index in range(entry_count):
            entry_offset = 0x14 + index * 0x10

            (
                key_offset,
                value_format,
                value_length,
                value_max_length,
                value_offset,
            ) = struct.unpack_from("<HHIII", data, entry_offset)

            key_start = key_table_offset + key_offset
            key_end = data.find(b"\x00", key_start)

            if key_end < 0:
                raise RuntimeError(
                    f"PARAM.SFO key {index} is damaged."
                )

            key = data[key_start:key_end].decode(
                "ascii",
                errors="replace",
            )

            absolute_value_offset = data_table_offset + value_offset
            raw_value = data[
                absolute_value_offset:
                absolute_value_offset + value_length
            ]

            entries.append(
                {
                    "key": key,
                    "format": value_format,
                    "length": value_length,
                    "max_length": value_max_length,
                    "raw": raw_value,
                }
            )

        return version, entries

    def write_param_sfo(self, sfo_path, version, entries):
        """Rebuild a PARAM.SFO while preserving all fields."""
        sfo_path = Path(sfo_path)

        key_table = bytearray()
        key_offsets = {}

        for entry in entries:
            key_offsets[entry["key"]] = len(key_table)
            key_table.extend(entry["key"].encode("ascii"))
            key_table.append(0)

        index_table_size = len(entries) * 0x10
        key_table_offset = 0x14 + index_table_size
        data_table_offset = self._align(
            key_table_offset + len(key_table),
            4,
        )

        data_table = bytearray()
        indexes = bytearray()

        for entry in entries:
            while len(data_table) % 4:
                data_table.append(0)

            value_offset = len(data_table)
            raw = bytes(entry["raw"])
            value_length = len(raw)
            value_max_length = max(
                int(entry.get("max_length", value_length)),
                value_length,
            )

            data_table.extend(raw)

            if value_max_length > value_length:
                data_table.extend(
                    b"\x00" * (value_max_length - value_length)
                )

            indexes.extend(
                struct.pack(
                    "<HHIII",
                    key_offsets[entry["key"]],
                    int(entry["format"]),
                    value_length,
                    value_max_length,
                    value_offset,
                )
            )

        header = struct.pack(
            "<4sIIII",
            b"\x00PSF",
            version,
            key_table_offset,
            data_table_offset,
            len(entries),
        )

        output = bytearray(header)
        output.extend(indexes)
        output.extend(key_table)

        if len(output) < data_table_offset:
            output.extend(
                b"\x00" * (data_table_offset - len(output))
            )

        output.extend(data_table)
        sfo_path.write_bytes(output)

    def patch_param_sfo(self, sfo_path, updates):
        """Patch SFO text fields and add missing required fields."""
        sfo_path = Path(sfo_path)
        version, entries = self.read_param_sfo(sfo_path)

        updates = dict(updates)
        title = str(updates.get("TITLE", "")).strip()
        if title:
            # PS3 HDD content can use localized TITLE_xx fields. Mirror the
            # selected title into all PS3 language slots to avoid stale/template
            # localized names overriding the default TITLE on the XMB.
            for language_index in range(20):
                updates[f"TITLE_{language_index:02d}"] = title

        by_key = {entry["key"]: entry for entry in entries}
        changed = []

        for key, value in updates.items():
            encoded = str(value).encode("utf-8") + b"\x00"

            if key in by_key:
                entry = by_key[key]

                if entry["format"] not in (0x0204, 0x0004):
                    self.log(
                        f"PARAM.SFO field {key} is not text "
                        "and was skipped."
                    )
                    continue

                entry["raw"] = encoded
                entry["length"] = len(encoded)
                entry["max_length"] = max(
                    int(entry["max_length"]),
                    self._align(len(encoded), 4),
                )
            else:
                entry = {
                    "key": key,
                    "format": 0x0204,
                    "length": len(encoded),
                    "max_length": max(8, self._align(len(encoded), 4)),
                    "raw": encoded,
                }
                entries.append(entry)
                by_key[key] = entry

            changed.append(key)

        # PS2 Classics titles use CATEGORY 2P.
        if "CATEGORY" in by_key:
            category = by_key["CATEGORY"]
            category["format"] = 0x0204
            category["raw"] = b"2P\x00"
            category["length"] = 3
            category["max_length"] = max(
                int(category["max_length"]),
                4,
            )
            if "CATEGORY" not in changed:
                changed.append("CATEGORY")
        else:
            entries.append(
                {
                    "key": "CATEGORY",
                    "format": 0x0204,
                    "length": 3,
                    "max_length": 4,
                    "raw": b"2P\x00",
                }
            )
            changed.append("CATEGORY")

        self.write_param_sfo(sfo_path, version, entries)

        # Verify the patched values.
        _, verify_entries = self.read_param_sfo(sfo_path)
        verify_keys = {entry["key"] for entry in verify_entries}

        required_keys = {
            "TITLE",
            "TITLE_ID",
            "CATEGORY",
            "VERSION",
        }
        missing = sorted(required_keys - verify_keys)

        if missing:
            raise RuntimeError(
                "PARAM.SFO could not be updated completely. "
                "Missing: " + ", ".join(missing)
            )

        self.log(
            "PARAM.SFO updated: "
            + ", ".join(dict.fromkeys(changed))
        )
        self.log(
            "PARAM.SFO check: VERSION is present and CATEGORY = 2P."
        )

    @staticmethod
    def detect_image_sector_size(image_path):
        """Detect 2048-byte ISO sectors or raw 2352-byte CD sectors."""
        image_path = Path(image_path)
        if not image_path.is_file():
            return None

        try:
            size = image_path.stat().st_size
            with image_path.open("rb") as handle:
                first_sector = handle.read(32)

                if (
                    len(first_sector) >= 12
                    and first_sector[:12]
                    == b"\x00" + (b"\xff" * 10) + b"\x00"
                ):
                    return 2352

                probes = (
                    (16 * 2048, 2048),
                    (16 * 2352, 2352),
                )

                for base_offset, sector_size in probes:
                    handle.seek(base_offset)
                    block = handle.read(96)
                    for user_offset in (0, 16, 24):
                        signature = block[user_offset:user_offset + 6]
                        if signature == b"\x01CD001":
                            return sector_size

            divisible_2048 = size > 0 and size % 2048 == 0
            divisible_2352 = size > 0 and size % 2352 == 0

            if divisible_2352 and not divisible_2048:
                return 2352
            if divisible_2048 and not divisible_2352:
                return 2048
        except OSError:
            return None

        return None

    def auto_detect_image_type(self, image_path):
        if self.input_mode.get() != "raw":
            self.image_type_detection.set("")
            return None

        image_path = Path(image_path)
        try:
            resolved = str(image_path.resolve())
        except OSError:
            resolved = str(image_path)

        if self.auto_image_type_path == resolved:
            return None

        self.auto_image_type_path = resolved
        sector_size = self.detect_image_sector_size(image_path)

        if sector_size == 2352:
            self.image_type.set("CD")
            self.image_type_detection.set(
                "Auto-detected: 2352-byte raw CD sectors. Manual override allowed."
            )
            self.log("Image type auto-detected: CD / BIN (2352 Byte).")
            return "CD"

        if sector_size == 2048:
            self.image_type.set("DVD5 / DVD9")
            self.image_type_detection.set(
                "Auto-detected: 2048-byte sectors. Manual override allowed."
            )
            self.log("Image type auto-detected: DVD5 / DVD9 (2048 Byte).")
            return "DVD5 / DVD9"

        self.image_type_detection.set(
            "Sector layout could not be detected automatically."
        )
        self.log("Image type could not be auto-detected; current selection kept.")
        return None

    @staticmethod
    def normalize_disc_id(value):
        value = str(value).upper()
        match = re.search(
            r"(SLUS|SLES|SCUS|SCES|SLPM|SLPS|SCPS|SCAJ|SCKA|"
            r"SCED|TCES|TCUS|PBPX|PAPX|PCPX|SCCS)"
            r"[^0-9]*([0-9]{3})[^0-9]*([0-9]{2})",
            value,
        )

        if not match:
            return None

        return f"{match.group(1)}_{match.group(2)}.{match.group(3)}"

    def detect_disc_id(self, image_path):
        """Detect the disc ID from the filename or the first 128 MiB."""
        image_path = Path(image_path)

        detected = self.normalize_disc_id(image_path.name)
        if detected:
            return detected

        pattern = re.compile(
            rb"(SLUS|SLES|SCUS|SCES|SLPM|SLPS|SCPS|SCAJ|SCKA|"
            rb"SCED|TCES|TCUS|PBPX|PAPX|PCPX|SCCS)"
            rb"[^0-9]{0,4}([0-9]{3})[^0-9]{0,3}([0-9]{2})",
            re.IGNORECASE,
        )

        max_read = 128 * 1024 * 1024
        chunk_size = 4 * 1024 * 1024
        read_total = 0
        overlap = b""

        try:
            with image_path.open("rb") as handle:
                while read_total < max_read:
                    chunk = handle.read(
                        min(chunk_size, max_read - read_total)
                    )
                    if not chunk:
                        break

                    haystack = overlap + chunk
                    match = pattern.search(haystack)

                    if match:
                        prefix = match.group(1).decode("ascii").upper()
                        number_a = match.group(2).decode("ascii")
                        number_b = match.group(3).decode("ascii")
                        return f"{prefix}_{number_a}.{number_b}"

                    overlap = haystack[-64:]
                    read_total += len(chunk)

        except OSError as error:
            self.log(f"The disc ID could not be read: {error}")

        return None

    def find_config_for_disc_id(self, disc_id):
        if not disc_id:
            return None

        configs_root = self.script_dir / "CONFIGS"
        if not configs_root.is_dir():
            return None

        compact_id = re.sub(r"[^A-Z0-9]", "", disc_id.upper())

        preferred_roots = [
            configs_root / "CUSTOM",
            configs_root / "NET",
            configs_root / "GX",
            configs_root / "SOFT",
            configs_root / "ALT",
            configs_root / "ENC",
            configs_root / "ORIGINAL",
            configs_root,
        ]

        seen = set()

        for root in preferred_roots:
            if not root.is_dir():
                continue

            for candidate in root.rglob("*"):
                if not candidate.is_file():
                    continue
                if candidate.suffix.lower() in {".html", ".htm"}:
                    continue

                try:
                    resolved = candidate.resolve()
                except OSError:
                    resolved = candidate

                if resolved in seen:
                    continue
                seen.add(resolved)

                compact_name = re.sub(
                    r"[^A-Z0-9]",
                    "",
                    candidate.name.upper(),
                )

                if compact_id in compact_name:
                    return candidate

        return None

    def populate_config_field(self, disc_id):
        """Fill the CONFIG field without replacing a manual selection."""
        current = self.param_hip_path.get().strip()
        current_is_auto = bool(
            current
            and self.auto_config_path
            and current == self.auto_config_path
        )
        manual_selection = bool(current and not current_is_auto)

        if manual_selection:
            return None

        config_path = self.find_config_for_disc_id(disc_id)
        if config_path:
            value = str(config_path)
            self.auto_config_path = value
            if current != value:
                self.param_hip_path.set(value)
            return config_path

        if current_is_auto:
            self.param_hip_path.set("")

        self.auto_config_path = ""
        return None

    def prepare_ps2_config(
        self,
        ps2classic,
        target,
        key_path,
        content_id,
        iso_path,
        usrdir,
        disc_id_override=None,
    ):
        """Select, discover and prepare a compatible PS2 CONFIG file."""
        config_source_text = self.param_hip_path.get().strip()
        config_source = (
            Path(config_source_text)
            if config_source_text
            else None
        )

        disc_id = disc_id_override or self.detect_disc_id(iso_path)

        if disc_id:
            self.log(f"Detected PS2 disc ID: {disc_id}")
        else:
            self.log("No PS2 disc ID was detected automatically.")

        if not config_source or not config_source.is_file():
            config_source = self.find_config_for_disc_id(disc_id)

            if config_source:
                self.auto_config_path = str(config_source)
                self.param_hip_path.set(self.auto_config_path)
                self.log(
                    "CONFIG found automatically: "
                    f"{config_source}"
                )

        if not config_source or not config_source.is_file():
            self.log(
                "No PS2 CONFIG was selected or found; "
                "the PKG will be built without an additional CONFIG."
            )
            return None

        config_output = Path(usrdir) / "CONFIG"

        # Copy CONFIG files that are already encrypted.
        source_upper = str(config_source).upper()
        already_encrypted = (
            config_source.name.upper() == "CONFIG"
            or config_source.suffix.upper() == ".ENC"
            or "\\ENC\\" in source_upper
            or "/ENC/" in source_upper
        )

        if already_encrypted:
            shutil.copy2(config_source, config_output)
            self.log(
                f"Already encrypted CONFIG copied: {config_source}"
            )
        else:
            if not ps2classic:
                raise RuntimeError(
                    "ps2classic.exe is required to encrypt the selected PS2 CONFIG."
                )
            self.log(f"Encrypting PS2 CONFIG: {config_source}")
            self.run_command(
                [
                    ps2classic,
                    "e",
                    target,
                    key_path,
                    config_source,
                    config_output,
                    "CONFIG",
                    content_id,
                ],
                self.script_dir,
            )

        if not config_output.is_file():
            raise RuntimeError(
                "The PS2 CONFIG could not be created as USRDIR/CONFIG."
            )

        self.log("PS2 CONFIG added as USRDIR/CONFIG.")
        return config_output

    def sha256_file(self, path, chunk_size=8 * 1024 * 1024):
        path = Path(path)
        digest = hashlib.sha256()
        total = path.stat().st_size
        processed = 0
        self.set_status(f"Checking SHA-256: {path.name}")

        with path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
                processed += len(chunk)
                if total:
                    self.status_text.set(
                        f"Checking SHA-256: {path.name} · "
                        f"{processed * 100 / total:.0f}%"
                    )
                self.pump_ui()

        return digest.hexdigest()

    def verify_iso_bin_edat_header(
        self,
        edat_path,
        content_id,
        expected_game_id,
    ):
        edat_path = Path(edat_path)
        data = edat_path.read_bytes()

        if len(data) < 0x100:
            raise RuntimeError(
                "ISO.BIN.EDAT is too small and therefore invalid."
            )

        if data[:4] != b"NPD\x00":
            raise RuntimeError(
                "ISO.BIN.EDAT does not contain a valid NPD header."
            )

        npd_version, license_type, npd_type = struct.unpack_from(
            ">III",
            data,
            4,
        )

        header_content_id = data[0x10:0x40].split(
            b"\x00",
            1,
        )[0].decode("ascii", errors="replace")

        flags, block_size, payload_size = struct.unpack_from(
            ">IIQ",
            data,
            0x80,
        )

        if header_content_id != content_id:
            raise RuntimeError(
                "ISO.BIN.EDAT Content ID does not match.\n"
                f"Expected: {content_id}\n"
                f"Found: {header_content_id}"
            )

        if license_type != 2:
            raise RuntimeError(
                "ISO.BIN.EDAT does not use the expected "
                f"Local-License 2, sondern {license_type}."
            )

        if npd_type != 1:
            raise RuntimeError(
                "ISO.BIN.EDAT does not use the expected "
                f"PS2-EDAT-Typ 01, sondern {npd_type:02X}."
            )

        if expected_game_id is not None:
            if payload_size != len(expected_game_id.encode("ascii")):
                raise RuntimeError(
                    "ISO.BIN.EDAT payload size does not match the disc ID.\n"
                    f"Expected: {len(expected_game_id)}\n"
                    f"Found: {payload_size}"
                )

        self.log(
            "ISO.BIN.EDAT Header OK: "
            f"NPD v{npd_version}, License={license_type}, "
            f"Type={npd_type:02X}, Block={block_size}, "
            f"Flags=0x{flags:08X}, ContentID={header_content_id}."
        )

        return {
            "content_id": header_content_id,
            "npd_version": npd_version,
            "license": license_type,
            "type": npd_type,
            "flags": flags,
            "block_size": block_size,
            "payload_size": payload_size,
            "sha256": self.sha256_file(edat_path),
        }

    def decrypt_and_verify_edat_payload(
        self,
        make_npdata,
        rap_path,
        edat_path,
        expected_game_id,
        verify_dir,
    ):
        verify_dir = Path(verify_dir)
        verify_dir.mkdir(parents=True, exist_ok=True)

        decrypted_path = verify_dir / "ISO.BIN.DAT"

        if decrypted_path.exists():
            decrypted_path.unlink()

        self.run_command(
            [
                make_npdata,
                "-v",
                "-d",
                edat_path,
                decrypted_path,
                "8",
                rap_path,
            ],
            verify_dir,
        )

        if not decrypted_path.is_file():
            raise RuntimeError(
                "make_npdata could not decrypt ISO.BIN.EDAT again "
                "for verification."
            )

        decrypted = decrypted_path.read_bytes()

        if decrypted != expected_game_id.encode("ascii"):
            raise RuntimeError(
                "The decrypted ISO.BIN.EDAT payload "
                "does not match the PS2 disc ID.\n"
                f"Erwartet: {expected_game_id!r}\n"
                f"Gefunden: {decrypted!r}"
            )

        self.log(
            "ISO.BIN.EDAT cryptographic verification passed: "
            f"Payload={expected_game_id}."
        )

        return decrypted_path

    def create_iso_bin_edat(
        self,
        make_npdata,
        rap_path,
        disc_id,
        content_id,
        klic_bin_path,
        usrdir,
        work_dir,
    ):
        expected_game_id = self.format_edat_game_id(disc_id)

        if not expected_game_id:
            raise RuntimeError(
                "A valid ISO.BIN.EDAT payload could not be created "
                "from the detected disc ID."
            )

        work_dir = Path(work_dir)
        usrdir = Path(usrdir)
        usrdir.mkdir(parents=True, exist_ok=True)

        gameid_path = work_dir / "gameid"
        gameid_path.write_bytes(expected_game_id.encode("ascii"))

        # make_npdata expects klic.bin in its working directory.
        local_klic = work_dir / "klic.bin"
        if Path(klic_bin_path).resolve() != local_klic.resolve():
            shutil.copy2(klic_bin_path, local_klic)

        edat_path = usrdir / "ISO.BIN.EDAT"

        if edat_path.exists():
            edat_path.unlink()

        self.log(
            "Creating a new ISO.BIN.EDAT for "
            f"disc ID {expected_game_id} and Content ID {content_id}."
        )

        # Match the make_npdata parameters used by pop-fe2:
        # EDAT, finalized, v3, uncompressed, 16 KiB,
        # Local license, PS2 type 01, custom klic mode 8.
        self.run_command(
            [
                make_npdata,
                "-v",
                "-e",
                gameid_path,
                edat_path,
                "1",
                "1",
                "3",
                "0",
                "16",
                "2",
                "01",
                content_id,
                "8",
                rap_path,
            ],
            work_dir,
        )

        if not edat_path.is_file():
            raise RuntimeError(
                "make_npdata did not create ISO.BIN.EDAT."
            )

        header_info = self.verify_iso_bin_edat_header(
            edat_path,
            content_id,
            expected_game_id,
        )

        verify_dir = work_dir / "edat_verification"
        verify_dir.mkdir(exist_ok=True)

        # Keep klic.bin available for verification.
        shutil.copy2(local_klic, verify_dir / "klic.bin")

        self.decrypt_and_verify_edat_payload(
            make_npdata,
            rap_path,
            edat_path,
            expected_game_id,
            verify_dir,
        )

        self.log(
            "ISO.BIN.EDAT created and verified: "
            f"{edat_path} · SHA-256 {header_info['sha256']}"
        )

        return edat_path, expected_game_id, header_info

    @staticmethod
    def _pkg_context(qa_digest, counter=0):
        qa_digest = bytes(qa_digest)
        context = bytearray(
            qa_digest[:8]
            + qa_digest[:8]
            + qa_digest[8:16]
            + qa_digest[8:16]
            + (b"\x00" * 32)
        )
        context[56:64] = int(counter).to_bytes(8, "big")
        return context

    @staticmethod
    def _pkg_increment_context(context):
        counter = int.from_bytes(context[56:64], "big")
        counter = (counter + 1) & 0xFFFFFFFFFFFFFFFF
        context[56:64] = counter.to_bytes(8, "big")

    def pkg_decrypt_range(
        self,
        handle,
        data_offset,
        qa_digest,
        relative_offset,
        length,
    ):
        if length <= 0:
            return b""

        first_block = relative_offset // 16
        inner_offset = relative_offset % 16
        required = inner_offset + length
        encrypted_length = ((required + 15) // 16) * 16

        context = self._pkg_context(qa_digest, first_block)
        handle.seek(data_offset + first_block * 16)
        encrypted = handle.read(encrypted_length)

        if len(encrypted) < required:
            raise RuntimeError(
                "The PKG is truncated or the file entry is invalid."
            )

        decrypted = bytearray()

        for offset in range(0, len(encrypted), 16):
            block = encrypted[offset:offset + 16]
            key_stream = hashlib.sha1(bytes(context)).digest()
            decrypted.extend(
                byte ^ key_stream[index]
                for index, byte in enumerate(block)
            )
            self._pkg_increment_context(context)

        return bytes(
            decrypted[inner_offset:inner_offset + length]
        )

    def read_pkg_index(self, pkg_path):
        pkg_path = Path(pkg_path)

        with pkg_path.open("rb") as handle:
            header = handle.read(0x80)

            if len(header) != 0x80:
                raise RuntimeError("The PKG header is incomplete.")

            (
                magic,
                pkg_type,
                pkg_info_offset,
                unknown,
                header_size,
                item_count,
            ) = struct.unpack_from(">6I", header, 0)

            package_size, data_offset, data_size = struct.unpack_from(
                ">QQQ",
                header,
                0x18,
            )

            content_id = header[0x30:0x60].split(
                b"\x00",
                1,
            )[0].decode("ascii", errors="replace")
            qa_digest = header[0x60:0x70]

            if magic != 0x7F504B47:
                raise RuntimeError("The file does not contain a valid PKG header.")

            if (pkg_type & 0xFF) != 1:
                raise RuntimeError(
                    f"Unsupported PKG type: 0x{pkg_type:08X}"
                )

            descriptor_data = self.pkg_decrypt_range(
                handle,
                data_offset,
                qa_digest,
                0,
                item_count * 0x20,
            )

            entries = []

            for index in range(item_count):
                values = struct.unpack_from(
                    ">IIQQII",
                    descriptor_data,
                    index * 0x20,
                )

                (
                    name_offset,
                    name_length,
                    file_offset,
                    file_size,
                    flags,
                    padding,
                ) = values

                name_raw = self.pkg_decrypt_range(
                    handle,
                    data_offset,
                    qa_digest,
                    name_offset,
                    name_length,
                )

                name = name_raw.split(b"\x00", 1)[0].decode(
                    "utf-8",
                    errors="replace",
                )
                normalized = name.replace("\\", "/").lstrip("/")

                entries.append(
                    {
                        "name": normalized,
                        "name_offset": name_offset,
                        "file_offset": file_offset,
                        "file_size": file_size,
                        "flags": flags,
                        "padding": padding,
                    }
                )

        return {
            "magic": magic,
            "type": pkg_type,
            "pkg_info_offset": pkg_info_offset,
            "unknown": unknown,
            "header_size": header_size,
            "item_count": item_count,
            "package_size": package_size,
            "data_offset": data_offset,
            "data_size": data_size,
            "content_id": content_id,
            "qa_digest": qa_digest,
            "entries": entries,
        }

    def extract_pkg_entry(self, pkg_path, pkg_info, entry, destination):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        with Path(pkg_path).open("rb") as handle:
            data = self.pkg_decrypt_range(
                handle,
                pkg_info["data_offset"],
                pkg_info["qa_digest"],
                entry["file_offset"],
                entry["file_size"],
            )

        destination.write_bytes(data)
        return destination

    def sfo_to_values(self, sfo_path):
        _version, entries = self.read_param_sfo(sfo_path)
        values = {}

        for entry in entries:
            raw = bytes(entry["raw"])

            if entry["format"] in (0x0204, 0x0004):
                values[entry["key"]] = raw.split(
                    b"\x00",
                    1,
                )[0].decode("utf-8", errors="replace")
            elif entry["format"] == 0x0404 and len(raw) >= 4:
                values[entry["key"]] = struct.unpack_from(
                    "<I",
                    raw,
                    0,
                )[0]
            else:
                values[entry["key"]] = raw.hex()

        return values

    def verify_finished_pkg(
        self,
        pkg_path,
        package_dir,
        package_content_id,
        edat_content_id,
        expected_title_id,
        expected_title,
        expected_version,
        expected_game_id,
        make_npdata,
        rap_path,
        klic_bin_path,
        output_dir,
    ):
        pkg_path = Path(pkg_path)
        package_dir = Path(package_dir)
        output_dir = Path(output_dir)

        verify_dir = output_dir / (
            pkg_path.stem + "_verification"
        )

        if verify_dir.exists():
            shutil.rmtree(verify_dir)

        verify_dir.mkdir(parents=True)
        pkg_info = self.read_pkg_index(pkg_path)

        if pkg_info["content_id"] != package_content_id:
            raise RuntimeError(
                "The PKG header Content ID does not match.\n"
                f"Expected: {package_content_id}\n"
                f"Found: {pkg_info['content_id']}"
            )

        if package_dir.name.upper() != expected_title_id.upper():
            raise RuntimeError(
                "The package install directory does not match TITLE_ID.\n"
                f"Directory: {package_dir.name}\n"
                f"TITLE_ID: {expected_title_id}"
            )

        entry_map = {
            entry["name"].upper(): entry
            for entry in pkg_info["entries"]
        }

        required_names = (
            "PARAM.SFO",
            "ICON0.PNG",
            "USRDIR/ISO.BIN.EDAT",
            "USRDIR/ISO.BIN.ENC",
        )

        missing = [
            name
            for name in required_names
            if name.upper() not in entry_map
        ]

        if missing:
            raise RuntimeError(
                "The completed PKG does not contain all required files:\n- "
                + "\n- ".join(missing)
            )

        extracted = {}

        verify_names = [
            "PARAM.SFO",
            "ICON0.PNG",
            "USRDIR/ISO.BIN.EDAT",
        ]
        for optional_asset in ("PIC0.PNG", "PIC1.PNG"):
            if optional_asset in entry_map:
                verify_names.append(optional_asset)

        for name in verify_names:
            entry = entry_map[name.upper()]
            destination = verify_dir / name
            extracted[name] = self.extract_pkg_entry(
                pkg_path,
                pkg_info,
                entry,
                destination,
            )

        # Compare metadata and XMB assets byte for byte.
        source_map = {
            "PARAM.SFO": package_dir / "PARAM.SFO",
            "ICON0.PNG": package_dir / "ICON0.PNG",
            "PIC0.PNG": package_dir / "PIC0.PNG",
            "PIC1.PNG": package_dir / "PIC1.PNG",
            "USRDIR/ISO.BIN.EDAT": (
                package_dir / "USRDIR" / "ISO.BIN.EDAT"
            ),
        }

        for name, extracted_path in extracted.items():
            source_hash = self.sha256_file(source_map[name])
            extracted_hash = self.sha256_file(extracted_path)

            if source_hash != extracted_hash:
                raise RuntimeError(
                    f"{name} was modified in the PKG or "
                    "was extracted incorrectly."
                )

        enc_entry = entry_map["USRDIR/ISO.BIN.ENC"]
        enc_source = package_dir / "USRDIR" / "ISO.BIN.ENC"

        if enc_entry["file_size"] != enc_source.stat().st_size:
            raise RuntimeError(
                "The ISO.BIN.ENC size inside the PKG does not match "
                "the generated file."
            )

        sfo_values = self.sfo_to_values(extracted["PARAM.SFO"])

        expected_sfo = {
            "TITLE": expected_title,
            "TITLE_ID": expected_title_id,
            "CATEGORY": "2P",
            "BOOTABLE": "1",
            "VERSION": expected_version,
        }

        for language_index in range(20):
            expected_sfo[f"TITLE_{language_index:02d}"] = expected_title

        for key, expected in expected_sfo.items():
            found = str(sfo_values.get(key, ""))

            if found != expected:
                raise RuntimeError(
                    f"PARAM.SFO {key} does not match: "
                    f"{found!r} statt {expected!r}."
                )

        self.verify_iso_bin_edat_header(
            extracted["USRDIR/ISO.BIN.EDAT"],
            edat_content_id,
            expected_game_id,
        )

        edat_payload_verified = False
        if all((expected_game_id, make_npdata, rap_path, klic_bin_path)):
            shutil.copy2(
                klic_bin_path,
                verify_dir / "klic.bin",
            )

            self.decrypt_and_verify_edat_payload(
                make_npdata,
                rap_path,
                extracted["USRDIR/ISO.BIN.EDAT"],
                expected_game_id,
                verify_dir,
            )
            edat_payload_verified = True
        else:
            self.log(
                "EDAT payload decryption was skipped because the required "
                "disc ID, RAP or make_npdata tool was unavailable."
            )

        report_lines = [
            "PS2 Classics PKG Verification",
            "=============================",
            f"PKG: {pkg_path}",
            f"PKG SHA-256: {self.sha256_file(pkg_path)}",
            f"Package Content ID: {pkg_info['content_id']}",
            f"EDAT/ENC Content ID: {edat_content_id}",
            f"Install directory: {package_dir.name}",
            f"Entries: {pkg_info['item_count']}",
            f"TITLE: {sfo_values.get('TITLE')}",
            f"TITLE_04: {sfo_values.get('TITLE_04')}",
            f"TITLE_ID: {sfo_values.get('TITLE_ID')}",
            f"CATEGORY: {sfo_values.get('CATEGORY')}",
            f"BOOTABLE: {sfo_values.get('BOOTABLE')}",
            f"VERSION: {sfo_values.get('VERSION')}",
            f"EDAT Payload: {expected_game_id or 'not decrypted'}",
            f"EDAT Payload Verified: {'Yes' if edat_payload_verified else 'No'}",
            f"ISO.BIN.ENC size: {enc_entry['file_size']}",
            "",
            "XMB assets:",
        ]

        for asset_name in ("ICON0.PNG", "PIC0.PNG", "PIC1.PNG"):
            asset_path = extracted.get(asset_name)
            if not asset_path:
                report_lines.append(f"{asset_name}: omitted")
                continue
            if Image is not None:
                with Image.open(asset_path) as image:
                    report_lines.append(
                        f"{asset_name}: {image.size[0]}x{image.size[1]} PNG · "
                        f"SHA-256 {self.sha256_file(asset_path)}"
                    )
            else:
                report_lines.append(
                    f"{asset_name}: SHA-256 {self.sha256_file(asset_path)}"
                )

        report_lines.extend(["", "PKG file list:"])

        for entry in sorted(
            pkg_info["entries"],
            key=lambda item: item["name"].upper(),
        ):
            report_lines.append(
                f"{entry['file_size']:>12}  "
                f"0x{entry['flags']:08X}  "
                f"{entry['name']}"
            )

        report_path = verify_dir / "verification.txt"
        report_path.write_text(
            "\n".join(report_lines) + "\n",
            encoding="utf-8",
        )

        self.log(
            "Finished PKG reopened and verified:"
        )
        self.log(f"  Package Content ID: {pkg_info['content_id']}")
        self.log(f"  EDAT/ENC Content ID: {edat_content_id}")
        self.log(f"  Install directory: {package_dir.name}")
        self.log(f"  PARAM.SFO: {expected_sfo}")
        self.log(f"  EDAT Payload: {expected_game_id or 'not decrypted'}")
        self.log(f"  EDAT Payload Verified: {'Yes' if edat_payload_verified else 'No'}")
        self.log(f"  Verification report: {report_path}")

        return report_path

    def ensure_npdrm_anchor(self, package_dir):
        """Require a generated or placeholder ISO.BIN.EDAT file."""
        edat = Path(package_dir) / "USRDIR" / "ISO.BIN.EDAT"

        if not edat.is_file():
            raise RuntimeError(
                "USRDIR/ISO.BIN.EDAT is missing from the package."
            )

        self.log(
            "NPDRM file present: "
            f"USRDIR/ISO.BIN.EDAT ({edat.stat().st_size} Bytes)"
        )

        return edat

    def validate_package_tree(self, package_dir):
        package_dir = Path(package_dir)

        required = {
            "PARAM.SFO": package_dir / "PARAM.SFO",
            "ICON0.PNG": package_dir / "ICON0.PNG",
            "USRDIR/ISO.BIN.EDAT": (
                package_dir / "USRDIR" / "ISO.BIN.EDAT"
            ),
            "USRDIR/ISO.BIN.ENC": (
                package_dir / "USRDIR" / "ISO.BIN.ENC"
            ),
        }

        missing = [
            label
            for label, path in required.items()
            if not path.is_file()
        ]

        for label, path in required.items():
            if path.is_file():
                self.log(
                    f"PKG check OK: {label} "
                    f"({path.stat().st_size} Bytes)"
                )

        if missing:
            raise RuntimeError(
                "The PS2 Classics package template is incomplete. "
                "Missing:\n- "
                + "\n- ".join(missing)
                + "\n\nThe PS2U10000 folder from the original GUI "
                  "must be complete and located next to ps2_classics_gui_mod.py."
            )

    def validate_inputs(self):
        requirements = self.get_build_requirements()
        errors = [
            f"{label}: {details}"
            for label, ok, details in requirements
            if not ok
        ]

        if errors:
            raise ValueError(
                "The build is not ready yet:\n\n- "
                + "\n- ".join(errors)
            )

    def run_command(self, command, cwd, stage=None):
        creationflags = (
            subprocess.CREATE_NO_WINDOW
            if os.name == "nt"
            else 0
        )

        command = [str(x) for x in command]
        self.log("> " + subprocess.list2cmdline(command))
        self.begin_busy(stage or f"Running {Path(command[0]).name}…")

        with tempfile.TemporaryFile(mode="w+b") as output_file:
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                stdout=output_file,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )

            while process.poll() is None:
                self.pump_ui()
                time.sleep(0.08)

            return_code = process.wait()
            output_file.seek(0)
            output = output_file.read().decode(
                "utf-8", errors="replace"
            ).strip()

        self.end_busy()

        if output:
            self.log(output)

        if return_code != 0:
            message = (
                f"{Path(command[0]).name} ended with exit code "
                f"{return_code}."
            )
            if output:
                message += f"\n\nTool output:\n{output}"
            raise RuntimeError(message)

        return output

    # -------------------------------------------------------
    # LIMG
    # -------------------------------------------------------

    def create_limg_copy(self, source, destination):
        """Create a temporary image copy with a PS2 Classics LIMG block."""
        source = Path(source)
        destination = Path(destination)

        self.copy_file_with_progress(
            source,
            destination,
            18,
            26,
            "Preparing temporary LIMG image",
        )

        is_cd = self.image_type.get() == "CD"
        block_size = 0x930 if is_cd else 0x800
        image_type = 2 if is_cd else 1
        pvd_base = 0x9318 if is_cd else 0x8000

        with destination.open("r+b") as handle:
            file_size = destination.stat().st_size
            if file_size >= 0x4000:
                handle.seek(-0x4000, os.SEEK_END)
                if handle.read(4) == b"LIMG":
                    self.log("LIMG already present; temporary image kept unchanged.")
                    return

            # ISO9660 Volume Space Size stores a big-endian sector count at
            # PVD + 0x54. Raw CD images have a 24-byte sector user-data offset.
            handle.seek(pvd_base + 0x54)
            sector_data = handle.read(4)
            if len(sector_data) != 4:
                raise RuntimeError(
                    "Could not read the ISO9660 sector count required for LIMG."
                )

            sector_count = struct.unpack(">I", sector_data)[0]
            if sector_count <= 0:
                raise RuntimeError(
                    "The ISO9660 sector count is invalid; LIMG was not created."
                )

            # LIMG alignment is based on the logical 2048-byte ISO data size,
            # even when the source is a raw 2352-byte CD/BIN image.
            remainder = (sector_count * 0x800) % 0x4000
            padding = (0x4000 - remainder) if remainder else 0

            handle.seek(0, os.SEEK_END)
            if padding:
                handle.write(b"\x00" * padding)

            header = bytearray(0x4000)
            header[0:4] = b"LIMG"
            struct.pack_into(">I", header, 4, image_type)
            struct.pack_into(">I", header, 8, sector_count)
            struct.pack_into(">I", header, 12, block_size)
            handle.write(header)

        self.log(
            "LIMG added: "
            f"type={'CD' if is_cd else 'DVD'}, "
            f"sector size={block_size}, "
            f"sectors={sector_count}, "
            f"padding={padding} bytes."
        )

    @staticmethod
    def disc_id_filename_component(value, fallback="PS2_DISC"):
        value = str(value).upper().strip()
        value = re.sub(r"[^A-Z0-9_]", "", value)
        value = re.sub(r"_+", "_", value).strip("_")
        return value or fallback

    @staticmethod
    def safe_filename_component(value, fallback="PS2_Game"):
        value = re.sub(r"[<>:\\|?*\x00-\x1F]", "_", str(value))
        value = re.sub(r"[^A-Za-z0-9._ -]+", "_", value)
        value = re.sub(r"[ _.-]{2,}", "_", value)
        value = value.strip(" ._-")
        return (value or fallback)[:100]

    # -------------------------------------------------------
    # Build
    # -------------------------------------------------------

    def build_pkg(self):
        # Populate only missing metadata. User edits remain untouched.
        if not all(
            (
                self.game_title.get().strip(),
                self.content_id.get().strip(),
                self.title_id.get().strip(),
                self.version.get().strip(),
            )
        ):
            self.auto_populate_metadata()

        try:
            self.validate_inputs()
        except Exception as error:
            messagebox.showerror(
                "Build requirements",
                str(error),
                parent=self.root,
            )
            self.update_ps2_key_option_ui()
            self.update_build_readiness()
            return

        self.log_box.delete("1.0", tk.END)
        self.building = True
        self.build_button.configure(
            state=tk.DISABLED,
            text="BUILDING…",
        )
        self.set_progress(0)
        self.set_status("Preparing build…")

        work_dir = None
        build_success = False
        final_pkg = None

        try:
            build_key_hex = self.resolve_ps2_klicensee()

            if (
                not build_key_hex
                and self.create_project_ps2_key.get()
                and self.get_ps2_key_generation_source()
            ):
                generated_key = self.generate_project_ps2_key_from_rap()
                build_key_hex = self.parse_klicensee(
                    generated_key.read_bytes()
                )

            if not re.fullmatch(r"[0-9A-F]{32}", build_key_hex):
                raise RuntimeError(
                    "No valid PS2 Classics Klicensee could be resolved or "
                    "generated from the local placeholder RAP."
                )

            build_key_bytes = bytes.fromhex(build_key_hex)

            if self.create_project_ps2_key.get():
                self.write_project_ps2_key(build_key_bytes)

            source_mode = self.input_mode.get()
            encrypted_mode = source_mode == "encrypted"
            individual_mode = (
                not encrypted_mode and self.create_individual_edat.get()
            )
            source_path = Path(self.iso_path.get().strip())
            output_dir = Path(self.output_dir.get().strip())
            output_dir.mkdir(parents=True, exist_ok=True)

            content_id = self.content_id.get().strip().upper()
            version = self.version.get().strip()
            target = self.target_type.get().lower()
            disc_id = self.refresh_disc_id_cache()
            expected_game_id = self.format_edat_game_id(disc_id)

            ps2classic = self.find_tool_recursive("ps2classic.exe")
            make_npdata = self.find_make_npdata()
            pkg_tool = self.find_pkg_tool()
            template_dir = self.find_template_dir()

            if not pkg_tool or not template_dir:
                raise RuntimeError(
                    "A previously validated package tool or template is no longer available."
                )

            if not encrypted_mode and (not ps2classic or not disc_id):
                raise RuntimeError(
                    "Raw-image mode requires ps2classic.exe and a detected "
                    "PS2 disc ID."
                )
            if not encrypted_mode and not make_npdata:
                raise RuntimeError(
                    "Raw-image mode requires make_npdata.exe to create "
                    "a fresh ISO.BIN.EDAT for the selected game."
                )

            self.log(f"--- PS2 Classics PKG Builder v{self.APP_VERSION} ---")
            self.log(f"Script: {Path(__file__).resolve()}")
            self.log(
                "Build source: "
                + ("existing ISO.BIN.ENC" if encrypted_mode else "raw PS2 image")
            )
            self.log(
                "EDAT identity: "
                + (
                    "existing sidecar"
                    if encrypted_mode
                    else (
                        "custom package Content ID with matching RAP"
                        if individual_mode
                        else "universal identity with game-specific payload"
                    )
                )
            )
            package_title_id = (
                self.content_id_title_id(content_id)
                or self.title_id.get().strip().upper()
            )
            if not package_title_id:
                raise RuntimeError("The Title ID could not be determined.")
            if package_title_id == "PS2U10000" and disc_id:
                raise RuntimeError(
                    "The package still resolves to the shared PS2U10000 placeholder. "
                    "Re-select the source image so a game-specific Title ID can be generated."
                )

            if encrypted_mode:
                sidecar_for_identity = self.find_sidecar_edat(source_path)
                if not sidecar_for_identity:
                    raise RuntimeError(
                        "ISO.BIN.EDAT was not found for the selected ISO.BIN.ENC."
                    )
                edat_content_id = self.read_edat_basic_info(
                    sidecar_for_identity
                )["content_id"].strip().upper()
            elif individual_mode:
                edat_content_id = content_id
            else:
                placeholder_identity = self.get_placeholder_identity()
                edat_content_id = str(
                    placeholder_identity.get("content_id", "")
                ).strip().upper()
                if not self.valid_content_id(edat_content_id):
                    raise RuntimeError(
                        "The universal placeholder Content ID could not be read "
                        "from PS2U10000/USRDIR/ISO.BIN.EDAT."
                    )

            self.log(f"Source: {source_path}")
            self.log(f"Disc ID: {disc_id or 'not decrypted'}")
            self.log(f"Package Content ID: {content_id}")
            self.log(f"EDAT/ENC Content ID: {edat_content_id}")
            self.log(f"Install Title ID: {package_title_id}")
            self.log(f"PKG tool: {pkg_tool}")
            self.log(f"Template: {template_dir}")

            work_dir = Path(
                tempfile.mkdtemp(
                    prefix="ps2_classics_gui_mod_",
                    dir=str(output_dir),
                )
            )
            package_dir = work_dir / package_title_id
            usrdir = package_dir / "USRDIR"

            shutil.copytree(
                template_dir,
                package_dir,
                dirs_exist_ok=True,
            )
            usrdir.mkdir(parents=True, exist_ok=True)
            self.log(f"Working folder: {work_dir}")
            self.log(f"Install directory: {package_dir.name}")
            self.set_progress(7)

            asset_sources = self.snapshot_package_asset_sources()
            for asset_name, source in asset_sources.items():
                self.log(
                    f"Build asset {asset_name}: "
                    f"{source if source else 'omitted'}"
                )

            self.title_id.set(package_title_id)
            param_sfo = package_dir / "PARAM.SFO"
            self.patch_param_sfo(
                param_sfo,
                {
                    "TITLE": self.game_title.get().strip(),
                    "TITLE_ID": package_title_id,
                    "APP_VER": version,
                    "VERSION": version,
                },
            )

            key_bytes = build_key_bytes
            key_path = work_dir / "ps2.key"
            klic_bin_path = work_dir / "klic.bin"
            key_path.write_bytes(key_bytes)
            klic_bin_path.write_bytes(key_bytes)
            self.set_progress(12)

            stale_edat = usrdir / "ISO.BIN.EDAT"
            if not encrypted_mode and stale_edat.exists():
                stale_edat.unlink()

            rap_path = None
            if individual_mode:
                rap_path = self.require_rap_file(edat_content_id)
            elif encrypted_mode:
                rap_path = self.find_rap_file(edat_content_id)
            else:
                rap_path = self.find_placeholder_rap()
                if not rap_path:
                    raise RuntimeError(
                        "The RAP matching the universal PS2 Classics placeholder "
                        "Content ID was not found. It is required to create a "
                        "fresh game-specific ISO.BIN.EDAT payload."
                    )

            enc_path = usrdir / "ISO.BIN.ENC"
            edat_path = usrdir / "ISO.BIN.EDAT"

            if encrypted_mode:
                sidecar_edat = self.find_sidecar_edat(source_path)
                if not sidecar_edat:
                    raise RuntimeError(
                        "ISO.BIN.EDAT was not found for the selected ISO.BIN.ENC."
                    )

                self.copy_file_with_progress(
                    source_path,
                    enc_path,
                    14,
                    42,
                    "Copying existing ISO.BIN.ENC",
                )
                shutil.copy2(sidecar_edat, edat_path)
                self.log(f"Existing ISO.BIN.ENC copied: {source_path}")
                self.log(f"Existing ISO.BIN.EDAT copied: {sidecar_edat}")

                edat_info = self.verify_iso_bin_edat_header(
                    edat_path,
                    edat_content_id,
                    expected_game_id,
                )

                if all((expected_game_id, make_npdata, rap_path)):
                    verify_dir = work_dir / "edat_input_verification"
                    verify_dir.mkdir(exist_ok=True)
                    shutil.copy2(klic_bin_path, verify_dir / "klic.bin")
                    self.decrypt_and_verify_edat_payload(
                        make_npdata,
                        rap_path,
                        edat_path,
                        expected_game_id,
                        verify_dir,
                    )
                else:
                    self.log(
                        "Existing EDAT header verified. Payload decryption "
                        "was skipped because metadata or a tool was unavailable."
                    )
            else:
                edat_path, expected_game_id, edat_info = self.create_iso_bin_edat(
                    make_npdata=make_npdata,
                    rap_path=rap_path,
                    disc_id=disc_id,
                    content_id=edat_content_id,
                    klic_bin_path=klic_bin_path,
                    usrdir=usrdir,
                    work_dir=work_dir,
                )
                self.set_progress(28)

                encrypt_input = source_path
                if self.add_limg.get():
                    encrypt_input = work_dir / (
                        source_path.stem + "_LIMG" + source_path.suffix
                    )
                    self.create_limg_copy(source_path, encrypt_input)

                if enc_path.exists():
                    enc_path.unlink()

                self.log("Encrypting the PS2 image to ISO.BIN.ENC…")
                self.run_command(
                    [
                        ps2classic,
                        "e",
                        target,
                        key_path,
                        encrypt_input,
                        enc_path,
                        "ISO.BIN.ENC",
                        edat_content_id,
                    ],
                    self.script_dir,
                    stage="Encrypting PS2 image to ISO.BIN.ENC",
                )

            if not enc_path.is_file() or enc_path.stat().st_size == 0:
                raise RuntimeError("A valid ISO.BIN.ENC was not produced or copied.")
            if not edat_path.is_file() or edat_path.stat().st_size == 0:
                raise RuntimeError("A valid ISO.BIN.EDAT was not produced or copied.")

            self.log(
                f"ISO.BIN.ENC: {enc_path.stat().st_size} bytes · "
                f"SHA-256 {self.sha256_file(enc_path)}"
            )
            self.set_progress(55)

            # Use the asset paths frozen at build start. A selected custom asset
            # must never silently fall back to the PS2U10000 template.
            icon0_source = asset_sources.get("ICON0.PNG")
            if icon0_source:
                if not self.copy_resolved_asset(
                    "ICON0.PNG",
                    str(icon0_source),
                    package_dir / "ICON0.PNG",
                ):
                    raise RuntimeError("The selected ICON0.PNG could not be copied.")
            else:
                template_icon = package_dir / "ICON0.PNG"
                if not template_icon.is_file():
                    raise RuntimeError("ICON0.PNG is required by the package.")
                self.validate_package_image_asset("ICON0.PNG", template_icon)
                self.log("ICON0.PNG kept from the package template.")

            pic1_source = asset_sources.get("PIC1.PNG")
            if pic1_source:
                if not self.copy_resolved_asset(
                    "PIC1.PNG",
                    str(pic1_source),
                    package_dir / "PIC1.PNG",
                ):
                    raise RuntimeError("The selected PIC1.PNG could not be copied.")
            else:
                (package_dir / "PIC1.PNG").unlink(missing_ok=True)
                self.log("PIC1.PNG omitted by user choice.")

            pic0_source = asset_sources.get("PIC0.PNG")
            if pic0_source:
                if not self.copy_resolved_asset(
                    "PIC0.PNG",
                    str(pic0_source),
                    package_dir / "PIC0.PNG",
                ):
                    raise RuntimeError("The selected PIC0.PNG could not be copied.")
            else:
                (package_dir / "PIC0.PNG").unlink(missing_ok=True)
                self.log("PIC0.PNG omitted by user choice.")

            snd0_text = self.snd0_path.get().strip()
            if snd0_text:
                if self.copy_optional(
                    snd0_text,
                    package_dir / "SND0.AT3",
                ):
                    self.log("SND0.AT3 copied.")
            else:
                (package_dir / "SND0.AT3").unlink(missing_ok=True)

            # CONFIG is optional. Existing encrypted CONFIG files can be copied
            # even in package-only mode. Raw CONFIG files require ps2classic.
            self.prepare_ps2_config(
                ps2classic=ps2classic,
                target=target,
                key_path=key_path,
                content_id=edat_content_id,
                iso_path=source_path,
                usrdir=usrdir,
                disc_id_override=disc_id,
            )
            self.set_progress(64)

            generated_vme = None
            if self.encrypt_vmc.get():
                if not ps2classic:
                    raise RuntimeError("ps2classic.exe is required for VMC encryption.")
                vmc = Path(self.vmc_path.get().strip())
                generated_vme = usrdir / (vmc.stem + ".VME")
                vmc_command = [
                    ps2classic,
                    "ve",
                    target,
                    vmc,
                    generated_vme,
                ]
                eid_key = self.eid_root_key_path.get().strip()
                if eid_key:
                    vmc_command.append(Path(eid_key))
                self.run_command(vmc_command, self.script_dir)
                if not generated_vme.is_file():
                    raise RuntimeError("The VME file was not created.")

            self.ensure_npdrm_anchor(package_dir)
            self.validate_package_tree(package_dir)

            package_conf = work_dir / "package.conf"
            package_lines = [
                f"ContentID = {content_id}",
                f"Klicensee = 0x{self.package_klicensee}",
                "DRMType = Local",
                "ContentType = PS2Game",
                f"PackageVersion = {version}",
            ]
            package_conf.write_bytes(
                ("\r\n".join(package_lines) + "\r\n").encode("ascii")
            )

            self.set_progress(72)
            pkg_name_lower = pkg_tool.name.lower()
            expected_generated_pkg = work_dir / f"{content_id}.pkg"

            if pkg_name_lower == "pkg.exe":
                package_command = [
                    pkg_tool,
                    "-c",
                    content_id,
                    package_dir,
                    expected_generated_pkg,
                ]
            elif pkg_name_lower == "psn_package_npdrm.exe":
                package_command = [
                    pkg_tool,
                    "-n",
                    package_conf.name,
                    package_dir.name,
                ]
            else:
                package_command = [
                    pkg_tool,
                    package_conf.name,
                    package_dir.name,
                ]

            self.log(f"Creating the PKG with {pkg_tool.name}…")
            self.run_command(
                package_command,
                work_dir,
                stage="Writing the PS3 PKG file",
            )
            self.set_progress(84)

            pkg_candidates = []
            if expected_generated_pkg.is_file():
                pkg_candidates.append(expected_generated_pkg)
            pkg_candidates.extend(
                candidate
                for candidate in work_dir.rglob("*.pkg")
                if candidate not in pkg_candidates
            )
            pkg_candidates.sort(
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            if not pkg_candidates:
                raise RuntimeError("The PKG tool finished without creating a PKG.")

            generated_pkg = pkg_candidates[0]
            safe_title = self.safe_filename_component(
                self.game_title.get().strip(),
                "PS2_Game",
            )
            safe_disc_id = self.disc_id_filename_component(
                disc_id or self.detected_disc_id.get().strip(),
                self.safe_filename_component(package_title_id, "PS2TITLE"),
            )
            final_pkg = output_dir / f"{safe_title}_{safe_disc_id}.pkg"
            if final_pkg.exists():
                final_pkg.unlink()
            shutil.move(str(generated_pkg), str(final_pkg))
            self.log(f"PKG created: {final_pkg}")
            self.set_progress(88)

            keep_verification = self.create_verification_report.get()
            verification_root = (
                output_dir
                if keep_verification
                else work_dir / "internal_verification"
            )
            verification_root.mkdir(parents=True, exist_ok=True)

            report_path = self.verify_finished_pkg(
                pkg_path=final_pkg,
                package_dir=package_dir,
                package_content_id=content_id,
                edat_content_id=edat_content_id,
                expected_title_id=package_title_id,
                expected_title=self.game_title.get().strip(),
                expected_version=version,
                expected_game_id=expected_game_id,
                make_npdata=make_npdata,
                rap_path=rap_path,
                klic_bin_path=klic_bin_path,
                output_dir=verification_root,
            )
            self.set_progress(97)

            rap_output = None
            if self.keep_encrypted_artifacts.get():
                self.copy_file_with_progress(
                    enc_path,
                    output_dir / "ISO.BIN.ENC",
                    97,
                    99,
                    "Keeping ISO.BIN.ENC in the output folder",
                )
                shutil.copy2(edat_path, output_dir / "ISO.BIN.EDAT")

                if rap_path and Path(rap_path).is_file():
                    exdata_output = output_dir / "exdata"
                    exdata_output.mkdir(exist_ok=True)
                    rap_output = exdata_output / f"{edat_content_id}.rap"
                    if rap_output.exists():
                        rap_output.unlink()
                    shutil.copy2(rap_path, rap_output)
                    self.log(f"RAP license copied: {rap_output}")

                self.log(
                    "Encrypted build artifacts were kept in the output folder."
                )
            else:
                self.log(
                    "ISO.BIN.ENC, ISO.BIN.EDAT and RAP were kept only "
                    "inside the PKG/build workspace and not copied next to the PKG."
                )

            if generated_vme and generated_vme.is_file():
                shutil.copy2(generated_vme, output_dir / generated_vme.name)

            self.set_progress(100)
            self.set_status("Build completed successfully")
            self.log("Build and internal PKG verification completed successfully.")
            self.log(f"PKG: {final_pkg}")
            if keep_verification:
                self.log(f"Persistent verification report: {report_path}")
            else:
                self.log("Verification was temporary; no _verification folder was kept.")
            self.log(
                f"EDAT payload: {expected_game_id or 'not decrypted'} · "
                f"SHA-256 {edat_info['sha256']}"
            )

            build_success = True

            message = (
                "The PS2 Classics PKG was created and verified.\n\n"
                f"PKG:\n{final_pkg}"
            )
            if rap_output:
                message += f"\n\nRAP kept at:\n{rap_output}"
            if keep_verification:
                message += f"\n\nVerification report:\n{report_path}"

            messagebox.showinfo("Success", message)

        except Exception as error:
            self.end_busy()
            self.set_status("Build failed")
            self.log(f"ERROR: {error}")
            if final_pkg and final_pkg.exists():
                self.log(
                    "A PKG file exists, but verification failed; it is not "
                    "considered a verified build."
                )
            messagebox.showerror("Build failed", str(error))

        finally:
            if work_dir and work_dir.exists():
                if build_success:
                    try:
                        shutil.rmtree(work_dir)
                    except Exception as cleanup_error:
                        self.log(
                            "The temporary folder could not be removed: "
                            f"{cleanup_error}"
                        )
                else:
                    self.log("Failed build folder kept for analysis:")
                    self.log(str(work_dir))

            self.building = False
            self.update_build_readiness()


if __name__ == "__main__":
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                PS2ClassicsGUIMod.APP_ID
            )
        except Exception:
            pass

    root = tk.Tk()
    gui = PS2ClassicsGUIMod(root)
    root.mainloop()
