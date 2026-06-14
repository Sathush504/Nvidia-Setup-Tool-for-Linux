"""Modern Python tkinter GUI for the NVIDIA GPU Setup Tool.

Single-window application — detect, configure, authenticate, and install
all from one place. No CLI interaction needed.

Run:
    nvidia-setup          # default entry point
    python -m nvidia_setup
"""

from __future__ import annotations

import datetime
import logging
import platform
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

if platform.system() != "Linux":
    print("Error: Linux only.", file=sys.stderr)
    sys.exit(1)

from nvidia_setup.config import Config, load_config
from nvidia_setup.detector import SystemDetector, SystemInfo
from nvidia_setup.exceptions import NvidiaSetupError
from nvidia_setup.installer import DriverInstaller, InstallOptions
from nvidia_setup.logging_utils import setup_logging

# ── Palette ─────────────────────────────────────────────────────────────────
BG       = "#0d1117"   # main dark background
SIDEBAR  = "#161b22"   # sidebar
CARD     = "#1c2128"   # card background
CARD2    = "#21262d"   # slightly lighter card
BORDER   = "#30363d"   # subtle border
GREEN    = "#76b900"   # NVIDIA green (primary action)
GREEN_D  = "#5a8f00"   # darker green (hover)
WHITE    = "#e6edf3"
MUTED    = "#8b949e"
SUCCESS  = "#3fb950"
WARNING  = "#d29922"
ERROR    = "#f85149"
INFO     = "#58a6ff"

FONT_SANS  = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_H2    = ("Segoe UI", 12, "bold")
FONT_MONO  = ("Monospace", 9)

# ── Queue message tags ───────────────────────────────────────────────────────
_LOG      = "log"
_PROGRESS = "progress"
_STATUS   = "status"
_DONE     = "done"
_ERROR    = "error"
_REENABLE = "reenable"


class QueueLogHandler(logging.Handler):
    """Custom logging handler that puts messages in the GUI's queue."""
    def __init__(self, q: queue.Queue) -> None:
        super().__init__()
        self._q = q

    def emit(self, record: logging.LogRecord) -> None:
        """Process the log record and push it to the GUI event queue."""
        level_map = {
            logging.DEBUG: "MUTED",
            logging.INFO: "INFO",
            logging.WARNING: "WARNING",
            logging.ERROR: "ERROR",
            logging.CRITICAL: "ERROR",
        }
        tag = level_map.get(record.levelno, "INFO")
        msg = f"{record.name.split('.')[-1]} — {record.getMessage()}"
        self._q.put((_LOG, (tag, msg)))


class SudoPasswordDialog(tk.Toplevel):
    """A modal dialog to securely request the user's sudo password."""

    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.password: str | None = None
        self.cancelled = False

        self.title("Authentication Required")
        self.geometry("420x220")
        self.resizable(False, False)
        self.configure(bg=CARD)
        self.transient(parent)
        self.grab_set()

        # Center dialog relative to parent window
        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width() - 420) // 2
        py = parent.winfo_y() + (parent.winfo_height() - 220) // 2
        self.geometry(f"+{px}+{py}")

        self._build_widgets()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self._entry.focus_set()

    def _build_widgets(self) -> None:
        # Header/Icon
        tk.Label(self, text="🛡️", bg=CARD, fg=WHITE, font=("Segoe UI", 24)).pack(pady=(12, 0))

        # Title
        tk.Label(
            self, text="Authentication Required", bg=CARD, fg=WHITE,
            font=("Segoe UI", 11, "bold")
        ).pack()

        # Description
        desc_text = "NVIDIA Setup Tool needs root privileges to proceed.\nEnter your sudo password:"
        tk.Label(
            self, text=desc_text, bg=CARD, fg=MUTED,
            font=("Segoe UI", 9), justify=tk.CENTER
        ).pack(pady=(4, 8))

        # Entry row
        entry_frame = tk.Frame(self, bg=CARD)
        entry_frame.pack(fill=tk.X, padx=40)

        self._entry_var = tk.StringVar()
        self._entry = ttk.Entry(
            entry_frame, textvariable=self._entry_var, show="●",
            style="TEntry"
        )
        self._entry.pack(fill=tk.X, ipady=3)
        self._entry.bind("<Return>", lambda _e: self._on_ok())

        # Tip
        tk.Label(
            self, text="(leave blank if sudo uses cached creds / NOPASSWD)",
            bg=CARD, fg=MUTED, font=("Segoe UI", 8)
        ).pack(pady=(4, 0))

        # Buttons
        btn_frame = tk.Frame(self, bg=CARD)
        btn_frame.pack(fill=tk.X, padx=40, pady=16)

        self._cancel_btn = ttk.Button(
            btn_frame, text="Cancel", style="Gray.TButton",
            command=self._on_cancel
        )
        self._cancel_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self._ok_btn = ttk.Button(
            btn_frame, text="Authenticate", style="Green.TButton",
            command=self._on_ok
        )
        self._ok_btn.pack(side=tk.RIGHT)

    def _on_ok(self) -> None:
        self.password = self._entry_var.get()
        self.grab_release()
        self.destroy()

    def _on_cancel(self) -> None:
        self.cancelled = True
        self.grab_release()
        self.destroy()


class NvidiaSetupApp:
    """Full-featured NVIDIA Setup GUI — everything in one window."""

    def __init__(self, root: tk.Tk, config: Config | None = None) -> None:
        self._root = root
        self._cfg  = config or load_config()
        self._q: queue.Queue[tuple[str, object]] = queue.Queue()
        self._info: SystemInfo | None = None
        self._busy = False

        # Attach custom logging handler
        self._log_handler = QueueLogHandler(self._q)
        logger = logging.getLogger("nvidia_setup")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(self._log_handler)

        self._root.title("NVIDIA GPU Setup Tool  v1.1")
        self._root.geometry("950x720")
        self._root.minsize(800, 600)
        self._root.configure(bg=BG)
        self._root.resizable(True, True)

        self._style()
        self._layout()
        self._root.after(300, self._start_detect)
        self._root.after(80,  self._drain_queue)

    # ── ttk styling ─────────────────────────────────────────────────────────

    def _style(self) -> None:
        s = ttk.Style(self._root)
        s.theme_use("clam")
        s.configure(".",            background=BG, foreground=WHITE,
                    font=FONT_SANS, borderwidth=0, relief="flat")
        s.configure("TFrame",       background=BG)
        s.configure("Card.TFrame",  background=CARD)
        s.configure("Side.TFrame",  background=SIDEBAR)
        s.configure("TLabel",       background=BG,   foreground=WHITE)
        s.configure("Card.TLabel",  background=CARD, foreground=WHITE)
        s.configure("Muted.TLabel", background=CARD, foreground=MUTED,
                    font=("Segoe UI", 9))
        s.configure("TCheckbutton", background=CARD, foreground=WHITE,
                    indicatorcolor=GREEN)
        s.map("TCheckbutton",       background=[("active", CARD)])
        s.configure("Green.TButton", background=GREEN, foreground="#000",
                    font=("Segoe UI", 10, "bold"), padding=(16, 7))
        s.map("Green.TButton",      background=[("active", GREEN_D),
                                                ("disabled", CARD2)],
                                    foreground=[("disabled", MUTED)])
        s.configure("Gray.TButton", background=CARD2, foreground=WHITE,
                    font=FONT_SANS, padding=(12, 7))
        s.map("Gray.TButton",       background=[("active", BORDER)])
        s.configure("Horizontal.TProgressbar",
                    troughcolor=CARD2, background=GREEN, thickness=14)
        s.configure("TSeparator",   background=BORDER)
        s.configure("TEntry",       fieldbackground=CARD2, foreground=WHITE,
                    insertcolor=WHITE, borderwidth=1, relief="solid")

    # ── Layout ───────────────────────────────────────────────────────────────

    def _layout(self) -> None:
        # ── Sidebar ─────────────────────────────────────────────────────────
        side = tk.Frame(self._root, bg=SIDEBAR, width=200)
        side.pack(side=tk.LEFT, fill=tk.Y)
        side.pack_propagate(False)

        # Logo block
        logo_f = tk.Frame(side, bg=SIDEBAR, pady=20)
        logo_f.pack(fill=tk.X)
        tk.Label(logo_f, text="⬛", bg=SIDEBAR, fg=GREEN,
                 font=("Segoe UI", 28)).pack()
        tk.Label(logo_f, text="NVIDIA", bg=SIDEBAR, fg=GREEN,
                 font=("Segoe UI", 14, "bold")).pack()
        tk.Label(logo_f, text="Setup Tool", bg=SIDEBAR, fg=MUTED,
                 font=("Segoe UI", 9)).pack()

        tk.Frame(side, bg=BORDER, height=1).pack(fill=tk.X, padx=16, pady=8)

        # System info labels in sidebar
        info_f = tk.Frame(side, bg=SIDEBAR, padx=16, pady=4)
        info_f.pack(fill=tk.X)
        tk.Label(info_f, text="SYSTEM", bg=SIDEBAR, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor=tk.W)

        self._sb_gpu = self._sidebar_row(info_f, "GPU", "Detecting…")
        self._sb_drv = self._sidebar_row(info_f, "Driver", "—")
        self._sb_cuda = self._sidebar_row(info_f, "CUDA", "—")
        self._sb_os   = self._sidebar_row(info_f, "OS", "—")
        self._sb_disk = self._sidebar_row(info_f, "Disk", "—")

        # Version at bottom
        tk.Label(side, text="v2.0.0  •  Python GUI", bg=SIDEBAR, fg=MUTED,
                 font=("Segoe UI", 8)).pack(side=tk.BOTTOM, pady=12)

        # ── Main content ─────────────────────────────────────────────────────
        main = tk.Frame(self._root, bg=BG)
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_header(main)
        self._build_status_cards(main)
        self._build_install_section(main)
        self._build_action_bar(main)
        self._build_console(main)

    def _sidebar_row(self, parent: tk.Frame, label: str, value: str) -> tk.Label:
        row = tk.Frame(parent, bg=SIDEBAR, pady=2)
        row.pack(fill=tk.X)
        tk.Label(row, text=label, bg=SIDEBAR, fg=MUTED,
                 font=("Segoe UI", 8), width=6, anchor=tk.W).pack(side=tk.LEFT)
        val = tk.Label(row, text=value, bg=SIDEBAR, fg=WHITE,
                       font=("Segoe UI", 8), anchor=tk.W)
        val.pack(side=tk.LEFT, fill=tk.X, expand=True)
        return val

    def _build_header(self, parent: tk.Frame) -> None:
        hdr = tk.Frame(parent, bg=BG, padx=24, pady=18)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="GPU Driver & CUDA Setup", bg=BG, fg=WHITE,
                 font=("Segoe UI", 18, "bold")).pack(side=tk.LEFT)
        self._detect_btn = ttk.Button(hdr, text="↻  Re-detect",
                                      style="Gray.TButton",
                                      command=self._on_redetect)
        self._detect_btn.pack(side=tk.RIGHT)
        tk.Frame(parent, bg=BORDER, height=1).pack(fill=tk.X)

    def _build_status_cards(self, parent: tk.Frame) -> None:
        f = tk.Frame(parent, bg=BG, padx=24, pady=14)
        f.pack(fill=tk.X)
        tk.Label(f, text="System Status", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(0, 8))

        cards_row = tk.Frame(f, bg=BG)
        cards_row.pack(fill=tk.X)

        self._card_gpu  = self._status_card(cards_row, "GPU",    "⏳ Detecting…",   INFO)
        self._card_drv  = self._status_card(cards_row, "Driver", "⏳ Detecting…",   INFO)
        self._card_cuda = self._status_card(cards_row, "CUDA",   "⏳ Detecting…",   INFO)

        tk.Frame(parent, bg=BORDER, height=1).pack(fill=tk.X)

    def _status_card(self, parent: tk.Frame, title: str, text: str,
                     color: str) -> dict:
        """Build one status card, return widget references for update."""
        card = tk.Frame(parent, bg=CARD, bd=0, padx=14, pady=12,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        dot = tk.Label(card, text="●", bg=CARD, fg=color, font=("Segoe UI", 14))
        dot.pack(anchor=tk.W)
        ttl = tk.Label(card, text=title, bg=CARD, fg=WHITE,
                       font=("Segoe UI", 10, "bold"))
        ttl.pack(anchor=tk.W)
        val = tk.Label(card, text=text, bg=CARD, fg=MUTED,
                       font=("Segoe UI", 9), wraplength=180, justify=tk.LEFT)
        val.pack(anchor=tk.W)
        return {"dot": dot, "val": val}

    def _update_card(self, card: dict, text: str, color: str) -> None:
        card["dot"].config(fg=color)
        card["val"].config(text=text)

    def _build_install_section(self, parent: tk.Frame) -> None:
        f = tk.Frame(parent, bg=BG, padx=24, pady=14)
        f.pack(fill=tk.X)
        tk.Label(f, text="What to Install", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(0, 8))

        row = tk.Frame(f, bg=BG)
        row.pack(fill=tk.X)

        self._want_driver = tk.BooleanVar(value=True)
        self._want_cuda   = tk.BooleanVar(value=False)
        self._dry_run     = tk.BooleanVar(value=False)

        self._chk_driver = self._option_tile(
            row, "NVIDIA Driver",
            "Latest proprietary driver (cuda-drivers / akmod-nvidia)",
            self._want_driver,
        )
        self._chk_cuda = self._option_tile(
            row, "CUDA Toolkit",
            f"GPU computing toolkit  ({self._cfg.cuda_package_name})",
            self._want_cuda,
        )
        self._chk_dry = self._option_tile(
            row, "Dry Run",
            "Preview commands without executing",
            self._dry_run,
        )

        tk.Frame(parent, bg=BORDER, height=1).pack(fill=tk.X)

    def _option_tile(self, parent: tk.Frame, title: str, desc: str,
                     var: tk.BooleanVar) -> ttk.Checkbutton:
        card = tk.Frame(parent, bg=CARD, padx=14, pady=10,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        cb = ttk.Checkbutton(card, text=title, variable=var, style="TCheckbutton")
        cb.pack(anchor=tk.W)
        tk.Label(card, text=desc, bg=CARD, fg=MUTED,
                 font=("Segoe UI", 8), wraplength=190).pack(anchor=tk.W, pady=(2, 0))
        return cb


    def _build_action_bar(self, parent: tk.Frame) -> None:
        bar = tk.Frame(parent, bg=BG, padx=24, pady=12)
        bar.pack(fill=tk.X)

        self._install_btn = ttk.Button(bar, text="⚡  Install Now",
                                       style="Green.TButton",
                                       command=self._on_install)
        self._install_btn.pack(side=tk.LEFT)

        self._prog_lbl = tk.Label(bar, text="", bg=BG, fg=MUTED,
                                  font=("Segoe UI", 9))
        self._prog_lbl.pack(side=tk.LEFT, padx=16)

        ttk.Button(bar, text="✕  Quit", style="Gray.TButton",
                   command=self._root.destroy).pack(side=tk.RIGHT)

        # Progress bar
        self._prog_var = tk.DoubleVar(value=0.0)
        self._prog_bar = ttk.Progressbar(parent, variable=self._prog_var,
                                         maximum=100,
                                         style="Horizontal.TProgressbar")
        self._prog_bar.pack(fill=tk.X, padx=24, pady=(0, 4))

    def _build_console(self, parent: tk.Frame) -> None:
        tk.Frame(parent, bg=BORDER, height=1).pack(fill=tk.X)
        tk.Label(parent, text="  Output Log", bg=BG, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor=tk.W, padx=24, pady=(4, 0))
        self._console = scrolledtext.ScrolledText(
            parent, bg="#010409", fg=SUCCESS,
            font=FONT_MONO, height=9, state=tk.DISABLED,
            relief=tk.FLAT, insertbackground=SUCCESS,
            selectbackground=BORDER,
        )
        self._console.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        for tag, col in [("INFO", INFO), ("SUCCESS", SUCCESS),
                         ("WARNING", WARNING), ("ERROR", ERROR),
                         ("MUTED", MUTED)]:
            self._console.tag_config(tag, foreground=col)

    # ── Event handlers ───────────────────────────────────────────────────────

    def _on_redetect(self) -> None:
        if self._busy:
            return
        self._detect_btn.state(["disabled"])
        self._start_detect()

    def _on_install(self) -> None:
        if self._busy:
            return
        if not self._info or not self._info.gpu_detected:
            messagebox.showerror("No GPU Found",
                                 "No NVIDIA GPU detected.\nClick ↻ Re-detect first.")
            return
        if self._info.is_wsl:
            messagebox.showerror("WSL Detected",
                                 "Cannot install NVIDIA drivers inside WSL.")
            return
        if not self._want_driver.get() and not self._want_cuda.get():
            messagebox.showwarning("Nothing Selected",
                                   "Select Driver and/or CUDA Toolkit to install.")
            return

        dry = self._dry_run.get()

        items = []
        if self._want_driver.get():
            items.append("• NVIDIA Driver")
        if self._want_cuda.get():
            items.append(f"• CUDA Toolkit ({self._cfg.cuda_package_name})")
        if dry:
            items.append("  [DRY RUN — no changes will be made]")

        if not messagebox.askyesno(
            "Confirm Installation",
            "The following will be installed:\n\n" + "\n".join(items)
            + "\n\nRequires internet access and sudo.\nContinue?",
        ):
            return

        pw = None
        if not dry:
            dialog = SudoPasswordDialog(self._root)
            self._root.wait_window(dialog)
            if dialog.cancelled:
                return
            pw = dialog.password.strip() if dialog.password else None

        self._set_busy(True)
        opts = InstallOptions(
            install_driver=self._want_driver.get(),
            install_cuda=self._want_cuda.get(),
            dry_run=dry,
            skip_confirmation=True,
        )
        threading.Thread(
            target=self._install_worker, args=(opts, pw), daemon=True
        ).start()

    # ── Workers ─────────────────────────────────────────────────────────────

    def _start_detect(self) -> None:
        self._set_busy(True)
        threading.Thread(target=self._detect_worker, daemon=True).start()

    def _detect_worker(self) -> None:
        self._push(_LOG, ("MUTED", "Detecting system…"))
        try:
            info = SystemDetector().detect()
            self._info = info
            self._push(_STATUS, info)
            self._push(_LOG, ("SUCCESS", "Detection complete."))
            for w in info.warnings:
                self._push(_LOG, ("WARNING", w))
        except Exception as exc:  # noqa: BLE001
            self._push(_LOG, ("ERROR", f"Detection error: {exc}"))
        finally:
            self._push(_REENABLE, None)

    def _install_worker(self, opts: InstallOptions, pw: str | None) -> None:
        def cb(fraction: float, msg: str) -> None:
            self._push(_PROGRESS, (fraction * 100, msg))
            self._push(_LOG, ("INFO", msg))

        try:
            installer = DriverInstaller(opts, config=self._cfg, sudo_password=pw)
            result = installer.install(self._info, progress_callback=cb)  # type: ignore[arg-type]
            if result.success:
                self._push(_LOG, ("SUCCESS", "✓ Installation finished!"))
                self._push(_DONE, result.reboot_required)
            else:
                self._push(_LOG, ("ERROR", "Installation ended with errors."))
                self._push(_ERROR, "Installation ended with errors.")
        except NvidiaSetupError as exc:
            self._push(_LOG, ("ERROR", str(exc)))
            self._push(_ERROR, str(exc))
        except Exception as exc:  # noqa: BLE001
            self._push(_LOG, ("ERROR", f"Unexpected: {exc}"))
            self._push(_ERROR, str(exc))
        finally:
            self._push(_REENABLE, None)
            self._push(_PROGRESS, (0.0, ""))

    # ── Queue ────────────────────────────────────────────────────────────────

    def _push(self, kind: str, payload: object) -> None:
        self._q.put((kind, payload))

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == _LOG:
                    level, msg = payload  # type: ignore[misc]
                    self._log(level, msg)
                elif kind == _PROGRESS:
                    pct, msg = payload  # type: ignore[misc]
                    self._prog_var.set(pct)
                    if msg:
                        self._prog_lbl.config(text=msg)
                elif kind == _STATUS:
                    self._apply_status(payload)  # type: ignore[arg-type]
                elif kind == _REENABLE:
                    self._set_busy(False)
                    self._detect_btn.state(["!disabled"])
                elif kind == _DONE:
                    reboot = bool(payload)
                    msg = "✓ Installation complete!"
                    if reboot:
                        msg += "\n\nA reboot is required to activate the driver."
                        if messagebox.askyesno("Reboot?", msg + "\n\nReboot now?"):
                            subprocess.Popen(["sudo", "reboot"])
                    else:
                        messagebox.showinfo("Done", msg)
                elif kind == _ERROR:
                    messagebox.showerror("Installation Failed", str(payload))
        except queue.Empty:
            pass
        finally:
            self._root.after(80, self._drain_queue)

    # ── UI helpers ───────────────────────────────────────────────────────────

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = ["disabled"] if busy else ["!disabled"]
        self._install_btn.state(state)
        self._detect_btn.state(state)

    def _apply_status(self, info: SystemInfo) -> None:
        # Status cards
        if info.gpu_detected:
            self._update_card(self._card_gpu, info.gpu_model, SUCCESS)
        else:
            self._update_card(self._card_gpu, "Not detected", ERROR)

        if info.driver_installed:
            self._update_card(self._card_drv, f"v{info.driver_version}", SUCCESS)
        else:
            self._update_card(self._card_drv, "Not installed", WARNING)

        if info.cuda_installed:
            self._update_card(self._card_cuda, f"CUDA {info.cuda_version}", SUCCESS)
        else:
            self._update_card(self._card_cuda, "Not installed", MUTED)

        # Sidebar
        gpu_color = SUCCESS if info.gpu_detected else ERROR
        self._sb_gpu.config(text=info.gpu_model[:22] or "None", fg=gpu_color)
        self._sb_drv.config(text=info.driver_version if info.driver_installed else "—",
                            fg=SUCCESS if info.driver_installed else MUTED)
        self._sb_cuda.config(text=info.cuda_version if info.cuda_installed else "—",
                             fg=SUCCESS if info.cuda_installed else MUTED)
        self._sb_os.config(text=f"{info.distro_id} {info.distro_version}")
        self._sb_disk.config(text=f"{info.free_disk_gb:.1f} GB",
                             fg=WARNING if info.free_disk_gb < 5 else WHITE)

    def _log(self, level: str, msg: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self._console.config(state=tk.NORMAL)
        self._console.insert(tk.END, line, level)
        self._console.see(tk.END)
        self._console.config(state=tk.DISABLED)


# ── Entry points ─────────────────────────────────────────────────────────────

def launch(config: Config | None = None) -> None:
    """Create the Tk root and run the event loop."""
    root = tk.Tk()
    root.tk_setPalette(background=BG, foreground=WHITE)
    NvidiaSetupApp(root, config=config)
    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    w, h = root.winfo_width(), root.winfo_height()
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
    root.mainloop()


if __name__ == "__main__":
    setup_logging("INFO")
    launch()
