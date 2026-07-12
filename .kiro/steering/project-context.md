# Project Context

## What This Is

A Python wrapper that sits around the Palworld Dedicated Server (`PalServer.exe`) on Windows. It monitors for player connections, auto-starts the server when someone tries to join, and auto-stops it when idle — conserving system resources. It provides a dual-interface architecture: a tkinter-based GUI (default) and a console/CLI interface (secondary fallback). In GUI mode, the wrapper automatically detaches from the launching console, allowing the PowerShell window to be closed without affecting the running GUI application.

## Architecture Overview

The wrapper is a **state machine** with four states:
- **MONITORING** — Server stopped, UDP listener active on port 8211 (retries bind with exponential backoff on transient OS errors)
- **STARTING** — Server launching, waiting for RCON TCP port 25575 readiness (120s timeout)
- **RUNNING** — Server active, RCON polling for player count (initial connection retries with backoff), idle timer tracking
- **STOPPING** — Graceful shutdown in progress (30s timeout before force kill)

**Interface mode** is selectable via `--interface gui|console` (default: `gui`). The GUI uses tkinter with cooperative async scheduling; the console interface reads from stdin. Both interfaces call the same WrapperCore API.

**Console detachment (GUI mode):** On Windows, when launched in GUI mode with an attached console, the launcher automatically re-spawns the wrapper as a detached process (using `pythonw.exe` if available, with `CREATE_NO_WINDOW | DETACHED_PROCESS` flags) and the original process exits. A hidden `--detached` flag prevents infinite re-spawn loops. The detached GUI process ignores `CTRL_CLOSE_EVENT` via `signal.SIGBREAK` handling.

## Component Map

| Module | Responsibility |
|--------|---------------|
| `src/wrapper_core.py` | State machine, coordinates all components |
| `src/connection_listener.py` | UDP socket listener for connection detection |
| `src/process_manager.py` | Subprocess lifecycle (start/stop/crash detection) |
| `src/rcon_client.py` | RCON queries for player count |
| `src/idle_timer.py` | Countdown timer that triggers shutdown |
| `src/settings_parser.py` | PalWorldSettings.ini read/write/validate (handles string quoting on write/read) |
| `src/gui_interface.py` | Tkinter-based GUI management interface — cooperative async scheduling with `root.update()` every ~33ms, widgets as `ttk.LabelFrame` subclasses, includes OutputPanel for log display |
| `src/management_interface.py` | Interactive CLI (stdin commands), password masking; delegates validation to `src/validation.py` |
| `src/validation.py` | Shared input validation and auto-correction logic (`validate_and_correct()`, `CorrectionResult` dataclass, `is_password_setting()`) — used by both GUI and console interfaces |
| `src/launcher.py` | Console detachment for GUI mode — detects attached console, resolves `pythonw.exe`, re-spawns as detached process with `--detached` flag, installs CTRL_CLOSE_EVENT handler |
| `src/logger.py` | Rotating file logger with mode-aware handler routing (StreamHandler for console, GuiLogHandler callback for GUI) |
| `src/config.py` | Configuration dataclass |
| `src/models.py` | Shared enums, result types, status types |
| `src/main.py` | Entry point, argparse (including `--interface gui\|console` and hidden `--detached`), launcher integration, wiring |
| `src/__main__.py` | Enables `python -m src` invocation |

## Key Design Decisions

1. **Single process, asyncio** — All concurrency via async tasks, no threads (except `asyncio.to_thread` for blocking RCON lib and stdin)
2. **Callbacks over events** — Components notify WrapperCore via callbacks rather than a pub/sub system
3. **Result types over exceptions** — Expected failures return dataclasses; only unexpected errors raise
4. **UDP bind-and-release** — The wrapper binds the game port to detect connections, then releases it so the server can bind
5. **RCON port for readiness detection** — Server readiness is checked by TCP-connecting to the RCON port (25575), not the game UDP port (8211), since TCP probes work reliably and RCON availability means the server is fully initialized
6. **Retry with backoff** — UDP port binding and RCON initial connection both use retry loops with exponential backoff to handle transient failures (OS socket cleanup delays, slow server initialization)
7. **Validation at the presentation layer** — Input validation and auto-correction lives in the shared `src/validation.py` module (used by both GUI and console), while SettingsParser handles raw file I/O formatting
8. **Password masking at display time** — Password values are stored unmasked in the file but displayed as `********` in both GUI settings view and console `settings` command output
9. **Tkinter cooperative async scheduling** — The GUI integrates with asyncio by calling `root.update()` every ~33ms from an asyncio coroutine instead of running tkinter's blocking `mainloop()`, ensuring WrapperCore background tasks are never starved
10. **Shared validation module** — Validation logic extracted to `src/validation.py` so both GUI and console interfaces produce identical validation/auto-correction behavior without code duplication
11. **Dual-interface architecture** — GUI is the default interface; console is the secondary fallback. Both share the same WrapperCore API and validation logic, differing only in presentation
12. **Console detachment via launcher** — In GUI mode on Windows, `src/launcher.py` re-spawns the process as a detached child using `pythonw.exe` (or `python.exe` with `CREATE_NO_WINDOW | DETACHED_PROCESS` flags as fallback), then exits. A hidden `--detached` flag prevents infinite re-spawn loops
13. **Mode-aware logging** — The logger routes operational output to stdout (console mode) or a GUI OutputPanel callback (GUI mode), while always maintaining file logging. GUI mode never writes to stdout/stderr

## External Dependencies

- `rcon` — Source RCON protocol client (synchronous, wrapped with `asyncio.to_thread`)
- Palworld Dedicated Server uses `PalWorldSettings.ini` with a non-standard single-line `OptionSettings=(key=value,...)` format

## Configuration Defaults

- Game port: 8211 (UDP)
- RCON port: 25575 (TCP)
- Idle timeout: 300 seconds
- Start timeout: 120 seconds
- Stop timeout: 30 seconds
- RCON poll interval: 10 seconds (valid range: 1–30)
