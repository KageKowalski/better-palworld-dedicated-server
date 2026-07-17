"""Shared pytest configuration and fixtures.

Prevents customtkinter/tkinter from causing pytest to hang on Windows by:
1. Injecting a fake customtkinter module into sys.modules BEFORE any test
   module is collected (pytest_configure runs before collection).
2. Patching tkinter.Tk.__init__ to raise if a real Tk root is created.
3. Using os._exit() at session end to bypass Tcl/Tk C-level cleanup hangs.

Background: CustomTkinter imports trigger Tcl/Tk C library initialization,
which can hang the pytest process on Windows (especially without a display or
during cleanup). By replacing customtkinter in sys.modules with a fake module
containing mock widget classes, we prevent any Tcl/Tk code from ever loading.
"""

import os
import sys
import types
from unittest.mock import MagicMock

import pytest


# =============================================================================
# Fake customtkinter module — injected before any src modules are imported
# =============================================================================

class _MockWidget:
    """Base class for fake customtkinter widgets.

    Supports being used as a base class (unlike MagicMock which has metaclass
    conflicts). All method calls return MagicMock instances so chained calls
    like widget.grid(...) work without errors.
    """

    def __init__(self, *args, **kwargs):
        pass

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    def __getattr__(self, name):
        # Return a MagicMock for any attribute access (grid, configure, etc.)
        mock = MagicMock()
        object.__setattr__(self, name, mock)
        return mock


class _MockCTkFrame(_MockWidget):
    """Fake CTkFrame that can be subclassed by ControlPanel, OutputPanel, etc."""
    pass


class _MockCTkButton(_MockWidget):
    """Fake CTkButton."""
    pass


class _MockCTkLabel(_MockWidget):
    """Fake CTkLabel."""
    pass


class _MockCTkEntry(_MockWidget):
    """Fake CTkEntry."""
    pass


class _MockCTkComboBox(_MockWidget):
    """Fake CTkComboBox."""
    pass


class _MockCTkTextbox(_MockWidget):
    """Fake CTkTextbox."""
    pass


class _MockCTkScrollableFrame(_MockWidget):
    """Fake CTkScrollableFrame."""
    pass


class _MockCTkToplevel(_MockWidget):
    """Fake CTkToplevel."""
    pass


class _MockCTk(_MockWidget):
    """Fake CTk (main window class)."""
    pass


def _build_fake_customtkinter():
    """Create a fake customtkinter module with all widget classes mocked."""
    mod = types.ModuleType("customtkinter")
    mod.__package__ = "customtkinter"
    mod.__path__ = []

    # Widget classes (can be subclassed)
    mod.CTkFrame = _MockCTkFrame
    mod.CTkButton = _MockCTkButton
    mod.CTkLabel = _MockCTkLabel
    mod.CTkEntry = _MockCTkEntry
    mod.CTkComboBox = _MockCTkComboBox
    mod.CTkTextbox = _MockCTkTextbox
    mod.CTkScrollableFrame = _MockCTkScrollableFrame
    mod.CTkToplevel = _MockCTkToplevel
    mod.CTk = _MockCTk

    # Commonly-used functions and constants
    mod.set_appearance_mode = MagicMock()
    mod.set_default_color_theme = MagicMock()
    mod.set_widget_scaling = MagicMock()
    mod.get_appearance_mode = MagicMock(return_value="dark")
    mod.StringVar = MagicMock
    mod.IntVar = MagicMock
    mod.BooleanVar = MagicMock
    mod.END = "end"
    mod.DISABLED = "disabled"
    mod.NORMAL = "normal"
    mod.LEFT = "left"
    mod.RIGHT = "right"
    mod.TOP = "top"
    mod.BOTTOM = "bottom"
    mod.BOTH = "both"
    mod.X = "x"
    mod.Y = "y"

    return mod


def pytest_configure(config):
    """Inject fake customtkinter into sys.modules before test collection.

    This runs before pytest collects test files and imports test modules.
    Since src.gui_interface and src.settings_panel do `import customtkinter`
    at module level, we must pre-empt that with a fake module to prevent
    Tcl/Tk initialization.
    """
    fake_ctk = _build_fake_customtkinter()
    sys.modules["customtkinter"] = fake_ctk
    # Also block any sub-module imports
    sys.modules["customtkinter.windows"] = types.ModuleType("customtkinter.windows")
    sys.modules["customtkinter.widgets"] = types.ModuleType("customtkinter.widgets")


def pytest_unconfigure(config):
    """Force-exit after all pytest output has been written.

    This is the last hook pytest calls, after all reporting is complete.
    The os._exit() call bypasses Python's normal cleanup/finalizer chain,
    which can hang due to Tcl/Tk C library state on Windows.
    """
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(getattr(config, "_exitstatus", 0))


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Capture exit status for use in pytest_unconfigure."""
    config._exitstatus = exitstatus


@pytest.fixture(autouse=True)
def _block_real_tk_creation(monkeypatch):
    """Prevent any test from accidentally creating a real tk.Tk() window.

    This patches tkinter.Tk.__init__ to raise RuntimeError when called
    directly. Tests that use @patch("src.gui_interface.tk.Tk") to provide
    a MagicMock are unaffected because the MagicMock replaces the entire
    class reference before any code uses it.
    """
    import tkinter as tk

    original_init = tk.Tk.__init__

    def guarded_init(self, *args, **kwargs):
        raise RuntimeError(
            "Real tk.Tk() instantiation is blocked in tests to prevent hangs. "
            "Use mock-based testing or @patch('src.gui_interface.tk.Tk')."
        )

    monkeypatch.setattr(tk.Tk, "__init__", guarded_init)
