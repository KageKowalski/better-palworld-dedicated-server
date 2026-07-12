"""Unit tests for src/launcher.py - console detachment functions.

Tests the core detachment logic including should_detach decision,
resolve_pythonw resolution, detach_and_respawn command construction,
and install_ctrl_close_handler behavior.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.launcher import (
    CREATE_NO_WINDOW,
    DETACHED_PROCESS,
    detach_and_respawn,
    has_attached_console,
    install_ctrl_close_handler,
    resolve_pythonw,
    should_detach,
)


class TestShouldDetach:
    """Tests for should_detach() decision logic."""

    @patch("src.launcher.has_attached_console", return_value=True)
    @patch("src.launcher.sys.platform", "win32")
    def test_returns_true_when_all_conditions_met(self, mock_console):
        """should_detach returns True when gui mode, not detached, has console, win32."""
        assert should_detach("gui", False) is True

    @patch("src.launcher.has_attached_console", return_value=True)
    @patch("src.launcher.sys.platform", "win32")
    def test_returns_false_for_console_mode(self, mock_console):
        """should_detach returns False when interface mode is console."""
        assert should_detach("console", False) is False

    @patch("src.launcher.has_attached_console", return_value=True)
    @patch("src.launcher.sys.platform", "win32")
    def test_returns_false_when_already_detached(self, mock_console):
        """should_detach returns False when already detached."""
        assert should_detach("gui", True) is False

    @patch("src.launcher.has_attached_console", return_value=False)
    @patch("src.launcher.sys.platform", "win32")
    def test_returns_false_when_no_console(self, mock_console):
        """should_detach returns False when no console is attached."""
        assert should_detach("gui", False) is False

    @patch("src.launcher.has_attached_console", return_value=True)
    @patch("src.launcher.sys.platform", "linux")
    def test_returns_false_on_linux(self, mock_console):
        """should_detach returns False on non-Windows platforms."""
        assert should_detach("gui", False) is False

    @patch("src.launcher.has_attached_console", return_value=True)
    @patch("src.launcher.sys.platform", "darwin")
    def test_returns_false_on_macos(self, mock_console):
        """should_detach returns False on macOS."""
        assert should_detach("gui", False) is False


class TestHasAttachedConsole:
    """Tests for has_attached_console() platform checks."""

    @patch("src.launcher.sys.platform", "linux")
    def test_returns_false_on_linux(self):
        """has_attached_console returns False on non-Windows."""
        assert has_attached_console() is False

    @patch("src.launcher.sys.platform", "darwin")
    def test_returns_false_on_macos(self):
        """has_attached_console returns False on macOS."""
        assert has_attached_console() is False


class TestResolvePythonw:
    """Tests for resolve_pythonw() interpreter resolution."""

    def test_returns_path_when_pythonw_exists(self, tmp_path):
        """resolve_pythonw returns Path when pythonw.exe exists."""
        # Create a fake pythonw.exe in the tmp directory
        fake_python = tmp_path / "python.exe"
        fake_python.touch()
        fake_pythonw = tmp_path / "pythonw.exe"
        fake_pythonw.touch()

        with patch("src.launcher.sys.executable", str(fake_python)):
            result = resolve_pythonw()
            assert result is not None
            assert result == fake_pythonw

    def test_returns_none_when_pythonw_missing(self, tmp_path):
        """resolve_pythonw returns None when pythonw.exe does not exist."""
        fake_python = tmp_path / "python.exe"
        fake_python.touch()

        with patch("src.launcher.sys.executable", str(fake_python)):
            result = resolve_pythonw()
            assert result is None


class TestDetachAndRespawn:
    """Tests for detach_and_respawn() command construction and execution."""

    def _make_mock_proc(self, wait_side_effect=None):
        """Create a mock process that simulates running (TimeoutExpired on wait)."""
        mock_proc = MagicMock()
        if wait_side_effect is None:
            # Default: process stays running (timeout expires)
            mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=2.0)
        else:
            mock_proc.wait.side_effect = wait_side_effect
        return mock_proc

    @patch("src.launcher.resolve_pythonw", return_value=None)
    @patch("src.launcher.subprocess.Popen")
    def test_success_returns_zero(self, mock_popen, mock_resolve):
        """detach_and_respawn returns 0 when process stays running past timeout."""
        mock_proc = self._make_mock_proc()
        mock_popen.return_value = mock_proc
        original_argv = ["script.py", "--interface", "gui", "--server-exe", "test.exe"]
        result = detach_and_respawn(original_argv)
        assert result == 0

    @patch("src.launcher.resolve_pythonw", return_value=None)
    @patch("src.launcher.subprocess.Popen")
    def test_command_includes_detached_flag(self, mock_popen, mock_resolve):
        """detach_and_respawn adds --detached to the command."""
        mock_proc = self._make_mock_proc()
        mock_popen.return_value = mock_proc
        original_argv = ["script.py", "--interface", "gui"]
        detach_and_respawn(original_argv)

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--detached" in cmd

    @patch("src.launcher.resolve_pythonw", return_value=None)
    @patch("src.launcher.subprocess.Popen")
    def test_command_preserves_original_args(self, mock_popen, mock_resolve):
        """detach_and_respawn preserves all original args (except script path)."""
        mock_proc = self._make_mock_proc()
        mock_popen.return_value = mock_proc
        original_argv = ["script.py", "--interface", "gui", "--server-exe", "/path/to/exe"]
        detach_and_respawn(original_argv)

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--interface" in cmd
        assert "gui" in cmd
        assert "--server-exe" in cmd
        assert "/path/to/exe" in cmd

    @patch("src.launcher.resolve_pythonw", return_value=None)
    @patch("src.launcher.subprocess.Popen")
    def test_uses_m_src_invocation(self, mock_popen, mock_resolve):
        """detach_and_respawn uses -m src to invoke the package."""
        mock_proc = self._make_mock_proc()
        mock_popen.return_value = mock_proc
        original_argv = ["script.py", "--interface", "gui"]
        detach_and_respawn(original_argv)

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "-m" in cmd
        assert "src" in cmd

    @patch("src.launcher.resolve_pythonw", return_value=Path("/path/to/pythonw.exe"))
    @patch("src.launcher.subprocess.Popen")
    def test_uses_pythonw_when_available(self, mock_popen, mock_resolve):
        """detach_and_respawn uses pythonw.exe as interpreter when available."""
        mock_proc = self._make_mock_proc()
        mock_popen.return_value = mock_proc
        original_argv = ["script.py", "--interface", "gui"]
        detach_and_respawn(original_argv)

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "/path/to/pythonw.exe"

    @patch("src.launcher.resolve_pythonw", return_value=None)
    @patch("src.launcher.subprocess.Popen")
    def test_falls_back_to_sys_executable(self, mock_popen, mock_resolve):
        """detach_and_respawn falls back to sys.executable when no pythonw."""
        mock_proc = self._make_mock_proc()
        mock_popen.return_value = mock_proc
        original_argv = ["script.py", "--interface", "gui"]
        detach_and_respawn(original_argv)

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert cmd[0] == sys.executable

    @patch("src.launcher.resolve_pythonw", return_value=None)
    @patch("src.launcher.subprocess.Popen")
    def test_sets_creation_flags(self, mock_popen, mock_resolve):
        """detach_and_respawn sets CREATE_NO_WINDOW | DETACHED_PROCESS flags."""
        mock_proc = self._make_mock_proc()
        mock_popen.return_value = mock_proc
        original_argv = ["script.py", "--interface", "gui"]
        detach_and_respawn(original_argv)

        call_args = mock_popen.call_args
        kwargs = call_args[1]
        expected_flags = CREATE_NO_WINDOW | DETACHED_PROCESS
        assert kwargs["creationflags"] == expected_flags

    @patch("src.launcher.resolve_pythonw", return_value=None)
    @patch("src.launcher.subprocess.Popen")
    def test_sets_devnull_streams(self, mock_popen, mock_resolve):
        """detach_and_respawn sets stdin/stdout/stderr to DEVNULL."""
        mock_proc = self._make_mock_proc()
        mock_popen.return_value = mock_proc
        original_argv = ["script.py", "--interface", "gui"]
        detach_and_respawn(original_argv)

        call_args = mock_popen.call_args
        kwargs = call_args[1]
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.DEVNULL

    @patch("src.launcher.resolve_pythonw", return_value=None)
    @patch("src.launcher.subprocess.Popen", side_effect=OSError("No such file"))
    def test_returns_one_on_oserror(self, mock_popen, mock_resolve):
        """detach_and_respawn returns 1 when Popen raises OSError."""
        original_argv = ["script.py", "--interface", "gui"]
        result = detach_and_respawn(original_argv)
        assert result == 1

    @patch("src.launcher.resolve_pythonw", return_value=None)
    @patch("src.launcher.subprocess.Popen", side_effect=OSError("Access denied"))
    def test_prints_error_on_failure(self, mock_popen, mock_resolve, capsys):
        """detach_and_respawn prints error to stderr on failure."""
        original_argv = ["script.py", "--interface", "gui"]
        detach_and_respawn(original_argv)

        captured = capsys.readouterr()
        assert "Error" in captured.err
        assert "Access denied" in captured.err

    @patch("src.launcher.resolve_pythonw", return_value=None)
    @patch("src.launcher.subprocess.Popen")
    def test_returns_one_when_process_exits_immediately(self, mock_popen, mock_resolve):
        """detach_and_respawn returns 1 when spawned process exits within 2s."""
        mock_proc = self._make_mock_proc(wait_side_effect=None)
        mock_proc.wait.side_effect = None
        mock_proc.wait.return_value = 1  # Process exited with code 1
        mock_popen.return_value = mock_proc
        original_argv = ["script.py", "--interface", "gui"]
        result = detach_and_respawn(original_argv)
        assert result == 1

    @patch("src.launcher.resolve_pythonw", return_value=None)
    @patch("src.launcher.subprocess.Popen")
    def test_prints_error_when_process_exits_immediately(self, mock_popen, mock_resolve, capsys):
        """detach_and_respawn prints error to stderr when process exits immediately."""
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 1
        mock_popen.return_value = mock_proc
        original_argv = ["script.py", "--interface", "gui"]
        detach_and_respawn(original_argv)

        captured = capsys.readouterr()
        assert "Error" in captured.err
        assert "exited immediately" in captured.err
        assert "code 1" in captured.err

    @patch("src.launcher.resolve_pythonw", return_value=None)
    @patch("src.launcher.subprocess.Popen")
    def test_prints_display_hint_when_process_exits_immediately(self, mock_popen, mock_resolve, capsys):
        """detach_and_respawn hints about display environment on immediate exit."""
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 1
        mock_popen.return_value = mock_proc
        original_argv = ["script.py", "--interface", "gui"]
        detach_and_respawn(original_argv)

        captured = capsys.readouterr()
        assert "display" in captured.err.lower()

    @patch("src.launcher.resolve_pythonw", return_value=None)
    @patch("src.launcher.subprocess.Popen")
    def test_waits_with_2_second_timeout(self, mock_popen, mock_resolve):
        """detach_and_respawn calls proc.wait with timeout=2.0."""
        mock_proc = self._make_mock_proc()
        mock_popen.return_value = mock_proc
        original_argv = ["script.py", "--interface", "gui"]
        detach_and_respawn(original_argv)

        mock_proc.wait.assert_called_once_with(timeout=2.0)

    @patch("src.launcher.resolve_pythonw", return_value=None)
    @patch("src.launcher.subprocess.Popen")
    def test_returns_one_when_process_exits_with_zero(self, mock_popen, mock_resolve):
        """detach_and_respawn returns 1 even if process exits immediately with code 0.

        Any immediate exit within the 2s window is treated as a failure since
        a properly started GUI should continue running.
        """
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0  # Process exited with code 0 (still early exit)
        mock_popen.return_value = mock_proc
        original_argv = ["script.py", "--interface", "gui"]
        result = detach_and_respawn(original_argv)
        assert result == 1


class TestInstallCtrlCloseHandler:
    """Tests for install_ctrl_close_handler() signal setup."""

    @patch("src.launcher.sys.platform", "linux")
    def test_noop_on_linux(self):
        """install_ctrl_close_handler is a no-op on non-Windows."""
        # Should not raise any errors
        install_ctrl_close_handler()

    @patch("src.launcher.sys.platform", "darwin")
    def test_noop_on_macos(self):
        """install_ctrl_close_handler is a no-op on macOS."""
        # Should not raise any errors
        install_ctrl_close_handler()
