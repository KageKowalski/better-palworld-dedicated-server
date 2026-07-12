"""Console detachment launcher for GUI mode on Windows.

Determines whether the current process needs to be re-spawned as a
detached GUI process, and if so, performs the spawn and exits.

Requirements: 1.1, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 5.4, 6.4
"""

import signal
import subprocess
import sys
from pathlib import Path

# Windows process creation flags
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008


def has_attached_console() -> bool:
    """Check if the current process has an attached console window (Windows only).

    Uses ctypes to call kernel32.GetConsoleWindow(). Returns False on non-Windows.

    Returns:
        True if a console window is attached to this process.
    """
    if sys.platform != "win32":
        return False

    import ctypes

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    hwnd = kernel32.GetConsoleWindow()
    return hwnd != 0


def should_detach(interface_mode: str, is_detached: bool) -> bool:
    """Determine if the process should perform console detachment.

    Returns True only when ALL four conditions are met:
    - interface_mode == "gui"
    - is_detached == False
    - has_attached_console() == True
    - sys.platform == "win32"

    Args:
        interface_mode: The selected interface mode ("gui" or "console").
        is_detached: Whether --detached flag is already present.

    Returns:
        True if detachment should be performed.
    """
    if interface_mode != "gui":
        return False
    if is_detached:
        return False
    if sys.platform != "win32":
        return False
    if not has_attached_console():
        return False
    return True


def resolve_pythonw() -> Path | None:
    """Resolve the path to pythonw.exe from sys.executable's directory.

    Looks for pythonw.exe in the same directory as (or parent directory of)
    sys.executable.

    Returns:
        Path to pythonw.exe if it exists, None otherwise.
    """
    exe_dir = Path(sys.executable).parent
    pythonw_path = exe_dir / "pythonw.exe"
    if pythonw_path.is_file():
        return pythonw_path
    return None


def detach_and_respawn(original_argv: list[str]) -> int:
    """Re-spawn the wrapper as a console-detached GUI process.

    Constructs the command line from the original arguments, appending
    --detached. Uses pythonw.exe if available, falls back to sys.executable.

    After spawning, polls the process for 2 seconds to detect immediate
    failures (e.g., TclError due to no display environment). If the process
    exits within that window, it is treated as a spawn failure.

    The command is constructed as:
        [interpreter, "-m", "src", ...original_args_without_script..., "--detached"]

    Args:
        original_argv: The original sys.argv (including script path at index 0).

    Returns:
        Exit code (0 on success, 1 on failure).
    """
    # Determine interpreter
    pythonw = resolve_pythonw()
    interpreter = str(pythonw) if pythonw is not None else sys.executable

    # Build command: use -m src to invoke the package
    # original_argv[0] is the script path or module indicator; skip it
    # and use -m src instead, then append the rest of the arguments
    args_without_script = original_argv[1:]
    cmd = [interpreter, "-m", "src"] + args_without_script + ["--detached"]

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
        )
    except OSError as e:
        print(f"Error: Failed to spawn GUI process: {e}", file=sys.stderr)
        return 1

    # Wait briefly to detect immediate failure (e.g., no display, import error)
    try:
        exit_code = proc.wait(timeout=2.0)
        # Process exited immediately - likely a failure (TclError, missing display, etc.)
        print(
            f"Error: GUI process exited immediately with code {exit_code}. "
            "This may indicate no display environment is available.",
            file=sys.stderr,
        )
        return 1
    except subprocess.TimeoutExpired:
        # Process is still running after 2s - it started successfully
        return 0


def install_ctrl_close_handler() -> None:
    """Install a signal handler that ignores CTRL_CLOSE_EVENT on Windows.

    On Windows, sets signal.SIGBREAK to SIG_IGN so that CTRL_CLOSE_EVENT
    does not terminate the detached GUI process.

    On non-Windows platforms, this is a no-op.
    """
    if sys.platform == "win32":
        # SIGBREAK corresponds to CTRL_CLOSE_EVENT and CTRL_BREAK_EVENT
        signal.signal(signal.SIGBREAK, signal.SIG_IGN)  # type: ignore[attr-defined]
