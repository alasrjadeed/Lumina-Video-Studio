#!/usr/bin/env python3
"""
Lumina Video Studio - Server Manager GUI
A standalone GUI to start/stop/manage servers without needing VS Code.
"""

import os
import sys
import signal
import subprocess
import threading
import time
import socket
import json
from pathlib import Path
from datetime import datetime

import customtkinter as ctk
from tkinter import messagebox

# ─── Configuration ───────────────────────────────────────────────────────────

PROJECT_DIR = Path(__file__).parent.resolve()
VENV_DIR = PROJECT_DIR / ".venv"
PID_FILE = Path("/tmp/lumina_pids")
FASTAPI_LOG = Path("/tmp/lumina_fastapi.log")
STREAMLIT_LOG = Path("/tmp/lumina_streamlit.log")
SETTINGS_FILE = PROJECT_DIR / ".server_gui_settings.json"

FASTAPI_HOST = "0.0.0.0"
FASTAPI_PORT = 8000
STREAMLIT_PORT = 8501
HEALTH_CHECK_INTERVAL = 5000  # ms

# ─── Theme ───────────────────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg": "#1a1a2e",
    "card": "#16213e",
    "accent": "#0f3460",
    "green": "#00d26a",
    "red": "#ff4757",
    "yellow": "#ffc312",
    "text": "#ffffff",
    "text_dim": "#a0a0b0",
    "border": "#2a2a4a",
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def is_port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except (ConnectionRefusedError, OSError, TimeoutError):
        return False


def read_pids():
    pids = {}
    if PID_FILE.exists():
        lines = PID_FILE.read_text().strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                pid = int(line)
                # Check if process is alive
                os.kill(pid, 0)
                pids[pid] = True
            except (ProcessLookupError, ValueError, PermissionError):
                pass
    return pids


def is_server_running(server_type):
    if server_type == "fastapi":
        return is_port_open(FASTAPI_PORT)
    elif server_type == "streamlit":
        return is_port_open(STREAMLIT_PORT)
    return False


def get_pid_for_server(server_type):
    """Find PID of a specific server by checking what's listening on its port."""
    target_port = FASTAPI_PORT if server_type == "fastapi" else STREAMLIT_PORT
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{target_port}"],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            return int(result.stdout.strip().split("\n")[0])
    except Exception:
        pass
    return None


def load_settings():
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except Exception:
            pass
    return {"auto_start_fastapi": False, "auto_start_streamlit": False, "minimize_to_tray": True}


def save_settings(settings):
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))


# ─── Server Manager ──────────────────────────────────────────────────────────

class ServerManager:
    def __init__(self):
        self.fastapi_process = None
        self.streamlit_process = None
        self._lock = threading.Lock()

    def start_fastapi(self, callback=None):
        with self._lock:
            if is_server_running("fastapi"):
                if callback:
                    callback(False, "FastAPI already running")
                return

            cmd = [
                str(VENV_DIR / "bin" / "python"), "-m", "uvicorn", "api.app:app",
                "--host", FASTAPI_HOST, "--port", str(FASTAPI_PORT),
                "--log-level", "info"
            ]
            log_file = open(FASTAPI_LOG, "w")
            self.fastapi_process = subprocess.Popen(
                cmd, cwd=str(PROJECT_DIR),
                stdout=log_file, stderr=log_file,
                start_new_session=True
            )
            self._save_pid(self.fastapi_process.pid)
            if callback:
                callback(True, f"FastAPI started (PID: {self.fastapi_process.pid})")

    def start_streamlit(self, callback=None):
        with self._lock:
            if is_server_running("streamlit"):
                if callback:
                    callback(False, "Streamlit already running")
                return

            cmd = [
                str(VENV_DIR / "bin" / "streamlit"), "run", "web/app.py",
                "--server.port", str(STREAMLIT_PORT),
                "--server.headless", "true",
                "--server.address", "0.0.0.0"
            ]
            log_file = open(STREAMLIT_LOG, "w")
            self.streamlit_process = subprocess.Popen(
                cmd, cwd=str(PROJECT_DIR),
                stdout=log_file, stderr=log_file,
                start_new_session=True
            )
            self._save_pid(self.streamlit_process.pid)
            if callback:
                callback(True, f"Streamlit started (PID: {self.streamlit_process.pid})")

    def stop_fastapi(self, callback=None):
        with self._lock:
            pid = get_pid_for_server("fastapi")
            if pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(1)
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                except ProcessLookupError:
                    pass
                self._remove_pid(pid)
            self.fastapi_process = None
            if callback:
                callback(True, "FastAPI stopped")

    def stop_streamlit(self, callback=None):
        with self._lock:
            pid = get_pid_for_server("streamlit")
            if pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(1)
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                except ProcessLookupError:
                    pass
                self._remove_pid(pid)
            self.streamlit_process = None
            if callback:
                callback(True, "Streamlit stopped")

    def stop_all(self, callback=None):
        self.stop_fastapi()
        self.stop_streamlit()
        if callback:
            callback(True, "All servers stopped")

    def start_all(self, callback=None):
        self.start_fastapi()
        time.sleep(2)
        self.start_streamlit()
        if callback:
            callback(True, "All servers starting...")

    def _save_pid(self, pid):
        with open(PID_FILE, "a") as f:
            f.write(f"{pid}\n")

    def _remove_pid(self, pid):
        if PID_FILE.exists():
            lines = PID_FILE.read_text().strip().split("\n")
            lines = [l for l in lines if l.strip() != str(pid)]
            PID_FILE.write_text("\n".join(lines) + "\n" if lines else "")


# ─── Main GUI ────────────────────────────────────────────────────────────────

class ServerManagerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.manager = ServerManager()
        self.settings = load_settings()
        self.log_update_id = None

        # Window setup
        self.title("Lumina Video Studio - Server Manager")
        self.geometry("900x750")
        self.minsize(800, 650)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Try to set icon
        icon_path = PROJECT_DIR / "icon.png"
        if icon_path.exists():
            try:
                self.iconphoto(False, ctk.CTkImage(light_image=None, dark_image=None, size=(32, 32)))
            except Exception:
                pass

        self._build_ui()
        self._update_status()
        self._schedule_log_update()

        # Auto-start
        if self.settings.get("auto_start_fastapi"):
            self.after(500, lambda: self._start_server("fastapi"))
        if self.settings.get("auto_start_streamlit"):
            self.after(1500, lambda: self._start_server("streamlit"))

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ── Header ──
        header = ctk.CTkFrame(self, fg_color=COLORS["accent"], corner_radius=0, height=60)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text="  ◆  Lumina Video Studio",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text"]
        ).grid(row=0, column=0, padx=10, pady=12, sticky="w")

        local_ip = get_local_ip()
        ctk.CTkLabel(
            header,
            text=f"API: {local_ip}:{FASTAPI_PORT}  |  Web: {local_ip}:{STREAMLIT_PORT}",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_dim"]
        ).grid(row=0, column=1, padx=10, pady=12, sticky="e")

        # ── Control Panel ──
        controls = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        controls.grid(row=1, column=0, sticky="ew", padx=20, pady=(15, 5))
        controls.grid_columnconfigure(0, weight=1)
        controls.grid_columnconfigure(1, weight=1)
        controls.grid_columnconfigure(2, weight=0)
        controls.grid_columnconfigure(3, weight=0)

        # FastAPI Card
        self.fastapi_card = self._create_server_card(
            controls, "FastAPI Server", "REST API + WebSocket", FASTAPI_PORT, 0
        )

        # Streamlit Card
        self.streamlit_card = self._create_server_card(
            controls, "Streamlit Web UI", "Browser Interface", STREAMLIT_PORT, 1
        )

        # Start All Button
        ctk.CTkButton(
            controls, text="▶  Start All",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["green"], hover_color="#00b85c",
            text_color="#000000",
            height=50, width=130, corner_radius=8,
            command=lambda: self._start_server("all")
        ).grid(row=0, column=2, padx=(10, 5), pady=10, sticky="e")

        # Stop All Button
        ctk.CTkButton(
            controls, text="■  Stop All",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["red"], hover_color="#e03040",
            text_color="#ffffff",
            height=50, width=130, corner_radius=8,
            command=lambda: self._stop_server("all")
        ).grid(row=0, column=3, padx=(5, 0), pady=10, sticky="e")

        # ── Notebook (Tabs) ──
        self.notebook = ctk.CTkTabview(self, fg_color=COLORS["card"], segmented_button_fg_color=COLORS["accent"])
        self.notebook.grid(row=2, column=0, sticky="nsew", padx=20, pady=(5, 10))

        # Logs Tab
        logs_tab = self.notebook.add("Logs")
        logs_tab.grid_columnconfigure(0, weight=1)
        logs_tab.grid_rowconfigure(1, weight=1)

        log_controls = ctk.CTkFrame(logs_tab, fg_color="transparent")
        log_controls.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        log_controls.grid_columnconfigure(1, weight=1)

        self.log_source = ctk.CTkSegmentedButton(
            log_controls,
            values=["FastAPI", "Streamlit", "Both"],
            font=ctk.CTkFont(size=12),
            command=self._on_log_source_change
        )
        self.log_source.set("FastAPI")
        self.log_source.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        ctk.CTkButton(
            log_controls, text="Clear", width=60, height=28,
            fg_color=COLORS["border"], hover_color=COLORS["accent"],
            command=self._clear_logs
        ).grid(row=0, column=1, padx=5, pady=5, sticky="e")

        ctk.CTkButton(
            log_controls, text="Open Log Folder", width=110, height=28,
            fg_color=COLORS["border"], hover_color=COLORS["accent"],
            command=self._open_log_folder
        ).grid(row=0, column=2, padx=5, pady=5, sticky="e")

        self.log_text = ctk.CTkTextbox(
            logs_tab, fg_color="#0d1117", text_color="#c9d1d9",
            font=ctk.CTkFont(family="monospace", size=12),
            corner_radius=6, border_width=1, border_color=COLORS["border"],
            wrap="word", state="disabled"
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Status Tab
        status_tab = self.notebook.add("Status")
        status_tab.grid_columnconfigure(0, weight=1)
        status_tab.grid_rowconfigure(0, weight=1)

        self.status_frame = ctk.CTkScrollableFrame(
            status_tab, fg_color=COLORS["card"]
        )
        self.status_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.status_frame.grid_columnconfigure(0, weight=1)

        self._build_status_panel()

        # Settings Tab
        settings_tab = self.notebook.add("Settings")
        settings_tab.grid_columnconfigure(0, weight=1)

        self._build_settings_panel(settings_tab)

        # ── Bottom Status Bar ──
        self.status_bar = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=0, height=30)
        self.status_bar.grid(row=3, column=0, sticky="ew")
        self.status_bar.grid_columnconfigure(1, weight=1)

        self.status_indicator = ctk.CTkLabel(
            self.status_bar, text="●", font=ctk.CTkFont(size=14),
            text_color=COLORS["red"]
        )
        self.status_indicator.grid(row=0, column=0, padx=(10, 5), pady=4)

        self.status_text = ctk.CTkLabel(
            self.status_bar, text="Checking servers...",
            font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]
        )
        self.status_text.grid(row=0, column=1, padx=5, pady=4, sticky="w")

        self.time_text = ctk.CTkLabel(
            self.status_bar, text="",
            font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]
        )
        self.time_text.grid(row=0, column=2, padx=10, pady=4, sticky="e")

    def _create_server_card(self, parent, title, subtitle, port, col):
        card = ctk.CTkFrame(
            parent, fg_color=COLORS["card"],
            corner_radius=10, border_width=1, border_color=COLORS["border"]
        )
        card.grid(row=0, column=col, padx=10, pady=10, sticky="nsew")
        card.grid_columnconfigure(1, weight=1)

        # Status dot
        dot = ctk.CTkLabel(card, text="●", font=ctk.CTkFont(size=20), text_color=COLORS["red"])
        dot.grid(row=0, column=0, rowspan=2, padx=(12, 5), pady=10)

        # Title
        ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"]
        ).grid(row=0, column=1, padx=5, pady=(10, 0), sticky="sw")

        # Subtitle + port
        ctk.CTkLabel(
            card, text=f"{subtitle}  •  Port {port}",
            font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"]
        ).grid(row=1, column=1, padx=5, pady=(0, 5), sticky="nw")

        # Buttons frame
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")

        start_btn = ctk.CTkButton(
            btn_frame, text="Start", width=70, height=30,
            fg_color=COLORS["green"], hover_color="#00b85c",
            text_color="#000000", font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=6,
            command=lambda: self._start_server("fastapi" if col == 0 else "streamlit")
        )
        start_btn.pack(side="left", padx=(0, 5))

        stop_btn = ctk.CTkButton(
            btn_frame, text="Stop", width=70, height=30,
            fg_color=COLORS["red"], hover_color="#e03040",
            text_color="#ffffff", font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=6,
            command=lambda: self._stop_server("fastapi" if col == 0 else "streamlit")
        )
        stop_btn.pack(side="left", padx=5)

        open_btn = ctk.CTkButton(
            btn_frame, text="Open", width=70, height=30,
            fg_color=COLORS["accent"], hover_color="#1a4a80",
            text_color="#ffffff", font=ctk.CTkFont(size=12),
            corner_radius=6,
            command=lambda: self._open_browser("fastapi" if col == 0 else "streamlit")
        )
        open_btn.pack(side="left", padx=5)

        return {"card": card, "dot": dot, "start": start_btn, "stop": stop_btn, "open": open_btn}

    def _build_status_panel(self):
        # Title
        ctk.CTkLabel(
            self.status_frame, text="Server Health & Info",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text"]
        ).grid(row=0, column=0, padx=10, pady=(5, 15), sticky="w")

        info_items = [
            ("Project Directory", str(PROJECT_DIR)),
            ("Python Environment", str(VENV_DIR / "bin" / "python")),
            ("FastAPI Port", str(FASTAPI_PORT)),
            ("Streamlit Port", str(STREAMLIT_PORT)),
            ("Local IP", get_local_ip()),
            ("FastAPI Log", str(FASTAPI_LOG)),
            ("Streamlit Log", str(STREAMLIT_LOG)),
            ("PID File", str(PID_FILE)),
        ]

        for i, (label, value) in enumerate(info_items):
            row = i + 1
            ctk.CTkLabel(
                self.status_frame, text=label,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLORS["text"]
            ).grid(row=row, column=0, padx=15, pady=3, sticky="w")
            ctk.CTkLabel(
                self.status_frame, text=value,
                font=ctk.CTkFont(size=12, family="monospace"),
                text_color=COLORS["text_dim"]
            ).grid(row=row, column=1, padx=15, pady=3, sticky="w")

        # Health checks
        health_row = len(info_items) + 2
        ctk.CTkLabel(
            self.status_frame, text="Health Checks",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text"]
        ).grid(row=health_row, column=0, columnspan=2, padx=10, pady=(20, 10), sticky="w")

        self.health_fastapi = ctk.CTkLabel(
            self.status_frame, text="● FastAPI: Checking...",
            font=ctk.CTkFont(size=12), text_color=COLORS["yellow"]
        )
        self.health_fastapi.grid(row=health_row + 1, column=0, columnspan=2, padx=15, pady=3, sticky="w")

        self.health_streamlit = ctk.CTkLabel(
            self.status_frame, text="● Streamlit: Checking...",
            font=ctk.CTkFont(size=12), text_color=COLORS["yellow"]
        )
        self.health_streamlit.grid(row=health_row + 2, column=0, columnspan=2, padx=15, pady=3, sticky="w")

    def _build_settings_panel(self, parent):
        parent.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(
            parent, text="Settings",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text"]
        ).grid(row=0, column=0, padx=15, pady=(15, 10), sticky="w")

        # Auto-start FastAPI
        self.auto_fastapi = ctk.CTkSwitch(
            parent, text="Auto-start FastAPI on launch",
            font=ctk.CTkFont(size=13),
            onvalue=True, offvalue=False,
            command=self._save_settings
        )
        self.auto_fastapi.grid(row=1, column=0, padx=20, pady=8, sticky="w")
        if self.settings.get("auto_start_fastapi"):
            self.auto_fastapi.select()

        # Auto-start Streamlit
        self.auto_streamlit = ctk.CTkSwitch(
            parent, text="Auto-start Streamlit on launch",
            font=ctk.CTkFont(size=13),
            onvalue=True, offvalue=False,
            command=self._save_settings
        )
        self.auto_streamlit.grid(row=2, column=0, padx=20, pady=8, sticky="w")
        if self.settings.get("auto_start_streamlit"):
            self.auto_streamlit.select()

        # Separator
        sep = ctk.CTkFrame(parent, fg_color=COLORS["border"], height=1)
        sep.grid(row=3, column=0, sticky="ew", padx=20, pady=15)

        # Quick actions
        ctk.CTkLabel(
            parent, text="Quick Actions",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"]
        ).grid(row=4, column=0, padx=15, pady=(5, 10), sticky="w")

        actions_frame = ctk.CTkFrame(parent, fg_color="transparent")
        actions_frame.grid(row=5, column=0, padx=15, pady=5, sticky="w")

        ctk.CTkButton(
            actions_frame, text="Open API Docs", width=130, height=35,
            fg_color=COLORS["accent"], hover_color="#1a4a80",
            font=ctk.CTkFont(size=12),
            command=lambda: self._open_url(f"http://localhost:{FASTAPI_PORT}/docs")
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            actions_frame, text="Open Web UI", width=130, height=35,
            fg_color=COLORS["accent"], hover_color="#1a4a80",
            font=ctk.CTkFont(size=12),
            command=lambda: self._open_url(f"http://localhost:{STREAMLIT_PORT}")
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            actions_frame, text="Open Config", width=130, height=35,
            fg_color=COLORS["accent"], hover_color="#1a4a80",
            font=ctk.CTkFont(size=12),
            command=self._open_config
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            actions_frame, text="Open Project", width=130, height=35,
            fg_color=COLORS["accent"], hover_color="#1a4a80",
            font=ctk.CTkFont(size=12),
            command=self._open_project_folder
        ).pack(side="left", padx=5)

    def _start_server(self, target):
        def _cb(ok, msg):
            self.after(0, lambda: self._log(f"[START] {msg}"))
            self.after(2000, self._update_status)

        if target == "all":
            threading.Thread(target=self.manager.start_all, args=(_cb,), daemon=True).start()
            self._log("[START] Starting all servers...")
        elif target == "fastapi":
            threading.Thread(target=self.manager.start_fastapi, args=(_cb,), daemon=True).start()
            self._log("[START] Starting FastAPI...")
        elif target == "streamlit":
            threading.Thread(target=self.manager.start_streamlit, args=(_cb,), daemon=True).start()
            self._log("[START] Starting Streamlit...")

        self.after(3000, self._update_status)

    def _stop_server(self, target):
        def _cb(ok, msg):
            self.after(0, lambda: self._log(f"[STOP] {msg}"))
            self.after(1000, self._update_status)

        if target == "all":
            threading.Thread(target=self.manager.stop_all, args=(_cb,), daemon=True).start()
            self._log("[STOP] Stopping all servers...")
        elif target == "fastapi":
            threading.Thread(target=self.manager.stop_fastapi, args=(_cb,), daemon=True).start()
            self._log("[STOP] Stopping FastAPI...")
        elif target == "streamlit":
            threading.Thread(target=self.manager.stop_streamlit, args=(_cb,), daemon=True).start()
            self._log("[STOP] Stopping Streamlit...")

        self.after(2000, self._update_status)

    def _update_status(self):
        api_up = is_server_running("fastapi")
        web_up = is_server_running("streamlit")

        # FastAPI card
        self.fastapi_card["dot"].configure(text_color=COLORS["green"] if api_up else COLORS["red"])

        # Streamlit card
        self.streamlit_card["dot"].configure(text_color=COLORS["green"] if web_up else COLORS["red"])

        # Status bar
        if api_up and web_up:
            self.status_indicator.configure(text_color=COLORS["green"])
            self.status_text.configure(text="All servers running")
        elif api_up or web_up:
            self.status_indicator.configure(text_color=COLORS["yellow"])
            names = []
            if api_up: names.append("FastAPI")
            if web_up: names.append("Streamlit")
            self.status_text.configure(text=f"{', '.join(names)} running")
        else:
            self.status_indicator.configure(text_color=COLORS["red"])
            self.status_text.configure(text="All servers stopped")

        self.time_text.configure(text=datetime.now().strftime("%H:%M:%S"))

        # Health tab
        if hasattr(self, "health_fastapi"):
            api_color = COLORS["green"] if api_up else COLORS["red"]
            api_status = "Running" if api_up else "Stopped"
            self.health_fastapi.configure(
                text=f"● FastAPI: {api_status} (port {FASTAPI_PORT})",
                text_color=api_color
            )

            web_color = COLORS["green"] if web_up else COLORS["red"]
            web_status = "Running" if web_up else "Stopped"
            self.health_streamlit.configure(
                text=f"● Streamlit: {web_status} (port {STREAMLIT_PORT})",
                text_color=web_color
            )

        # Schedule next check
        self.after(HEALTH_CHECK_INTERVAL, self._update_status)

    def _on_log_source_change(self, value):
        self._refresh_logs()

    def _clear_logs(self):
        source = self.log_source.get()
        if source == "FastAPI" or source == "Both":
            FASTAPI_LOG.write_text("")
        if source == "Streamlit" or source == "Both":
            STREAMLIT_LOG.write_text("")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _refresh_logs(self):
        source = self.log_source.get()
        lines = []

        if source in ("FastAPI", "Both") and FASTAPI_LOG.exists():
            try:
                content = FASTAPI_LOG.read_text()
                if source == "Both":
                    lines.append("═══ FastAPI Log ═══\n")
                lines.append(content)
            except Exception:
                pass

        if source in ("Streamlit", "Both") and STREAMLIT_LOG.exists():
            try:
                content = STREAMLIT_LOG.read_text()
                if source == "Both":
                    lines.append("\n═══ Streamlit Log ═══\n")
                lines.append(content)
            except Exception:
                pass

        text = "".join(lines)
        # Keep last 5000 chars
        if len(text) > 5000:
            text = "...\n" + text[-5000:]

        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("1.0", text)
        self.log_text.configure(state="disabled")

        # Auto-scroll to bottom
        self.log_text.see("end")

    def _schedule_log_update(self):
        self._refresh_logs()
        self.log_update_id = self.after(3000, self._schedule_log_update)

    def _log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _open_browser(self, server_type):
        import webbrowser
        if server_type == "fastapi":
            webbrowser.open(f"http://localhost:{FASTAPI_PORT}/docs")
        elif server_type == "streamlit":
            webbrowser.open(f"http://localhost:{STREAMLIT_PORT}")

    def _open_url(self, url):
        import webbrowser
        webbrowser.open(url)

    def _open_config(self):
        config_file = PROJECT_DIR / "config.yaml"
        if config_file.exists():
            subprocess.Popen(["xdg-open", str(config_file)])
        else:
            messagebox.showwarning("Not Found", "config.yaml not found")

    def _open_project_folder(self):
        subprocess.Popen(["xdg-open", str(PROJECT_DIR)])

    def _open_log_folder(self):
        subprocess.Popen(["xdg-open", "/tmp"])

    def _save_settings(self):
        self.settings["auto_start_fastapi"] = self.auto_fastapi.get()
        self.settings["auto_start_streamlit"] = self.auto_streamlit.get()
        save_settings(self.settings)

    def _on_close(self):
        # Ask user what to do
        api_up = is_server_running("fastapi")
        web_up = is_server_running("streamlit")

        if api_up or web_up:
            result = messagebox.askyesnocancel(
                "Close Server Manager",
                "Servers are still running.\n\n"
                "Yes = Keep servers running & close GUI\n"
                "No = Stop servers & close GUI\n"
                "Cancel = Don't close"
            )
            if result is True:
                self.destroy()
            elif result is False:
                self.manager.stop_all()
                time.sleep(1)
                self.destroy()
            # else: cancel, do nothing
        else:
            self.destroy()


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    # Ensure we're in the right directory
    os.chdir(str(PROJECT_DIR))

    app = ServerManagerGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
