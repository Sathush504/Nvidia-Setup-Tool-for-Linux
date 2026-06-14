"""Unit tests for nvidia_setup.gui (tkinter GUI)."""

from __future__ import annotations

import platform
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
        from nvidia_setup.gui import _LOG, NvidiaSetupApp
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
        from nvidia_setup.gui import _PROGRESS, NvidiaSetupApp
        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)

        app._push(_PROGRESS, (42.0, "Step 42"))
        app._drain_queue()
        assert app._prog_var.get() == pytest.approx(42.0)


class TestInstallGuard:
    def test_no_gpu_shows_error(self, root: tk.Tk) -> None:
        from nvidia_setup.detector import SystemInfo
        from nvidia_setup.gui import NvidiaSetupApp

        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)

        app._info = SystemInfo(gpu_detected=False)

        with patch("tkinter.messagebox.showerror") as mock_err:
            app._on_install()
            mock_err.assert_called_once()

    def test_wsl_shows_error(self, root: tk.Tk) -> None:
        from nvidia_setup.detector import SystemInfo
        from nvidia_setup.gui import NvidiaSetupApp

        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)

        app._info = SystemInfo(gpu_detected=True, is_wsl=True)

        with patch("tkinter.messagebox.showerror") as mock_err:
            app._on_install()
            mock_err.assert_called_once()

    def test_nothing_selected_shows_warning(self, root: tk.Tk) -> None:
        from nvidia_setup.detector import SystemInfo
        from nvidia_setup.gui import NvidiaSetupApp

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
        from nvidia_setup.detector import SystemInfo
        from nvidia_setup.gui import NvidiaSetupApp

        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)

        app._info = SystemInfo(gpu_detected=True, is_wsl=False, arch="x86_64")
        app._want_driver.set(True)

        with patch("tkinter.messagebox.askyesno", return_value=True), \
             patch("nvidia_setup.gui.SudoPasswordDialog") as mock_dlg_class, \
             patch.object(root, "wait_window"):

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

        import argparse

        from nvidia_setup.cli import cmd_gui
        args = argparse.Namespace(config=None)

        with patch("builtins.__import__", side_effect=blocked_import):
            rc = cmd_gui(args)
        assert rc == 1


class TestGuiDetailed:
    def test_on_redetect_not_busy(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import NvidiaSetupApp
        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)
            app._busy = False
            with patch.object(app, "_start_detect") as mock_start:
                app._on_redetect()
                mock_start.assert_called_once()

    def test_on_redetect_busy(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import NvidiaSetupApp
        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)
            app._busy = True
            with patch.object(app, "_start_detect") as mock_start:
                app._on_redetect()
                mock_start.assert_not_called()

    def test_on_install_busy(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import NvidiaSetupApp
        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)
            app._busy = True
            with patch("tkinter.messagebox.showerror") as mock_err:
                app._on_install()
                mock_err.assert_not_called()

    def test_on_install_cancel_confirmation(self, root: tk.Tk) -> None:
        from nvidia_setup.detector import SystemInfo
        from nvidia_setup.gui import NvidiaSetupApp
        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)
        app._info = SystemInfo(gpu_detected=True, is_wsl=False, arch="x86_64")
        app._want_driver.set(True)
        app._want_cuda.set(True)
        app._dry_run.set(True)
        with patch("tkinter.messagebox.askyesno", return_value=False) as mock_ask:
            app._on_install()
            mock_ask.assert_called_once()
            assert not app._busy

    def test_detect_worker_success(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import NvidiaSetupApp
        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)
        with patch("nvidia_setup.gui.SystemDetector") as mock_det:
            mock_info = MagicMock()
            mock_info.warnings = ["Warn 1"]
            mock_det.return_value.detect.return_value = mock_info
            app._detect_worker()
            # Queue should contain STATUS, success LOG, warning LOG, REENABLE
            items = []
            while not app._q.empty():
                items.append(app._q.get()[0])
            assert "status" in items
            assert "log" in items
            assert "reenable" in items

    def test_detect_worker_failure(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import NvidiaSetupApp
        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)
        with patch("nvidia_setup.gui.SystemDetector", side_effect=RuntimeError("fail")):
            app._detect_worker()
            items = []
            while not app._q.empty():
                items.append(app._q.get()[0])
            assert "log" in items
            assert "reenable" in items

    def test_install_worker_success(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import NvidiaSetupApp
        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)
        from nvidia_setup.installer import InstallOptions
        opts = InstallOptions()
        with patch("nvidia_setup.gui.DriverInstaller") as mock_inst:
            mock_res = MagicMock(success=True, reboot_required=True)
            mock_inst.return_value.install.return_value = mock_res
            app._install_worker(opts, "pw")
            items = []
            while not app._q.empty():
                items.append(app._q.get()[0])
            assert "done" in items
            assert "reenable" in items

    def test_install_worker_failure(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import NvidiaSetupApp
        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)
        from nvidia_setup.exceptions import InstallationError
        from nvidia_setup.installer import InstallOptions
        opts = InstallOptions()
        err_exc = InstallationError("install failed")
        with patch("nvidia_setup.gui.DriverInstaller", side_effect=err_exc):
            app._install_worker(opts, "pw")
            items = []
            while not app._q.empty():
                items.append(app._q.get()[0])
            assert "error" in items
            assert "reenable" in items


    def test_drain_queue_done_reboot(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import _DONE, NvidiaSetupApp
        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)
        app._push(_DONE, True)
        with patch("tkinter.messagebox.askyesno", return_value=True) as mock_ask, \
             patch("subprocess.Popen") as mock_popen:
            app._drain_queue()
            mock_ask.assert_called_once()
            mock_popen.assert_called_once()

    def test_drain_queue_done_no_reboot(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import _DONE, NvidiaSetupApp
        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)
        app._push(_DONE, False)
        with patch("tkinter.messagebox.showinfo") as mock_info:
            app._drain_queue()
            mock_info.assert_called_once()

    def test_drain_queue_error(self, root: tk.Tk) -> None:
        from nvidia_setup.gui import _ERROR, NvidiaSetupApp
        with patch.object(NvidiaSetupApp, "_start_detect"), \
             patch.object(NvidiaSetupApp, "_drain_queue"):
            app = NvidiaSetupApp(root)
        app._push(_ERROR, "Something went wrong")
        with patch("tkinter.messagebox.showerror") as mock_err:
            app._drain_queue()
            mock_err.assert_called_once()

    def test_launch(self) -> None:
        from nvidia_setup.gui import launch
        with patch("tkinter.Tk") as mock_tk, \
             patch("nvidia_setup.gui.NvidiaSetupApp") as mock_app:
            launch()
            mock_tk.assert_called_once()
            mock_app.assert_called_once()

