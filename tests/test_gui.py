"""Unit tests for nvidia_setup.gui (tkinter GUI)."""

from __future__ import annotations

import platform
import threading
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

# Skip entire module if not on Linux or tkinter not available
pytestmark = [
    pytest.mark.skipif(
        platform.system() != "Linux", reason="GUI tests only run on Linux"
    ),
]


def _has_display() -> bool:
    """Return True if a display server is available."""
    import os
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


@pytest.fixture()
def root():
    """Create and yield a hidden tkinter root, then destroy it."""
    if not _has_display():
        pytest.skip("No display available (headless CI)")
    r = tk.Tk()
    r.withdraw()  # hide immediately
    yield r
    r.destroy()


class TestNvidiaSetupAppInit:
    def test_initialises_without_error(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import NvidiaSetupApp
        with patch.object(
            NvidiaSetupApp, "_start_detect"
        ), patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)
            assert app is not None

    def test_widgets_created(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import NvidiaSetupApp
        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)
            assert app._install_btn is not None
            assert app._detect_btn is not None
            assert app._console is not None
            assert app._prog_bar is not None


class TestQueueProcessing:
    def test_log_message_appended(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import NvidiaSetupApp, _LOG
        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)

        app._push(_LOG, ("INFO", "Test log message"))
        app._drain_queue()  # drain once

        app._console.config(state=tk.NORMAL)
        content = app._console.get("1.0", tk.END)
        app._console.config(state=tk.DISABLED)
        assert "Test log message" in content

    def test_progress_update(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import NvidiaSetupApp, _PROGRESS
        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)

        app._push(_PROGRESS, (42.0, "Step 42"))
        app._drain_queue()
        assert app._prog_var.get() == pytest.approx(42.0)


class TestInstallGuard:
    def test_no_gpu_shows_error(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import NvidiaSetupApp
        from nvidia_setup.detector import SystemInfo

        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)

        app._info = SystemInfo(gpu_detected=False)

        with patch("tkinter.messagebox.showerror") as mock_err:
            app._on_install()
            mock_err.assert_called_once()

    def test_wsl_shows_error(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import NvidiaSetupApp
        from nvidia_setup.detector import SystemInfo

        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)

        app._info = SystemInfo(gpu_detected=True, is_wsl=True)

        with patch("tkinter.messagebox.showerror") as mock_err:
            app._on_install()
            mock_err.assert_called_once()

    def test_nothing_selected_shows_warning(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import NvidiaSetupApp
        from nvidia_setup.detector import SystemInfo

        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)

        app._info = SystemInfo(gpu_detected=True, is_wsl=False, arch="x86_64")
        app._want_driver.set(False)
        app._want_cuda.set(False)

        with patch("tkinter.messagebox.showwarning") as mock_warn:
            app._on_install()
            mock_warn.assert_called_once()

    def test_install_cancelled_on_dialog_close(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import NvidiaSetupApp
        from nvidia_setup.detector import SystemInfo

        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)

        app._info = SystemInfo(gpu_detected=True, is_wsl=False, arch="x86_64")
        app._want_driver.set(True)

        with patch("tkinter.messagebox.askyesno", return_value=True), \
             patch("nvidia_setup.gui.SudoPasswordDialog") as mock_dlg_class, \
             patch.object(root, "wait_window") as mock_wait:
            
            mock_dlg = MagicMock()
            mock_dlg.cancelled = True
            mock_dlg_class.return_value = mock_dlg

            app._on_install()
            assert not app._busy


class TestSudoPasswordDialog:
    def test_dialog_ok(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import SudoPasswordDialog
        dialog = SudoPasswordDialog(root)
        dialog._entry_var.set("secret123")
        dialog._on_ok()
        assert dialog.password == "secret123"
        assert not dialog.cancelled

    def test_dialog_cancel(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import SudoPasswordDialog
        dialog = SudoPasswordDialog(root)
        dialog._on_cancel()
        assert dialog.cancelled


class TestLaunchFunction:
    def test_launch_unavailable_without_display(self) -> None:
        """launch() should not raise ImportError — tkinter is stdlib."""
        from nvidia_setup.gui import launch  # noqa: F401 — just import check


class TestCmdGui:
    def test_returns_1_if_no_tkinter(self) -> None:
        import builtins
        real_import = builtins.__import__

        def blocked_import(name: str, *args, **kwargs):
            if name == "tkinter":
                raise ImportError("no tkinter")
            return real_import(name, *args, **kwargs)

        from nvidia_setup.cli import cmd_gui
        import argparse
        args = argparse.Namespace(config=None)

        with patch("builtins.__import__", side_effect=blocked_import):
            rc = cmd_gui(args)
        assert rc == 1
