# Project Context

## What This Is

A Python wrapper that sits around the Palworld Dedicated Server (`PalServer.exe`) on Windows. It monitors for player connections, auto-starts the server when someone tries to join, and auto-stops it when idle — conserving system resources.

## Architecture Overview

The wrapper is a **state machine** with four states:
- **MONITORING** — Server stopped, UDP listener active on port 8211
- **STARTING** — Server launching, waiting for port readiness (120s timeout)
- **RUNNING** — Server active, RCON polling for player count, idle timer tracking
- **STOPPING** — Graceful shutdown in progress (30s timeout before force kill)

## Component Map

| Module | Responsibility |
|--------|---------------|
| `src/wrapper_core.py` | State machine, coordinates all components |
| `src/connection_listener.py` | UDP socket listener for connection detection |
| `src/process_manager.py` | Subprocess lifecycle (start/stop/crash detection) |
| `src/rcon_client.py` | RCON queries for player count |
| `src/idle_timer.py` | Countdown timer that triggers shutdown |
| `src/settings_parser.py` | PalWorldSettings.ini read/write/validate |
| `src/management_interface.py` | Interactive CLI (stdin commands) |
| `src/logger.py` | Rotating file logger |
| `src/config.py` | Configuration dataclass |
| `src/models.py` | Shared enums, result types, status types |
| `src/main.py` | Entry point, argparse, wiring |

## Key Design Decisions

1. **Single process, asyncio** — All concurrency via async tasks, no threads (except `asyncio.to_thread` for blocking RCON lib and stdin)
2. **Callbacks over events** — Components notify WrapperCore via callbacks rather than a pub/sub system
3. **Result types over exceptions** — Expected failures return dataclasses; only unexpected errors raise
4. **UDP bind-and-release** — The wrapper binds the game port to detect connections, then releases it so the server can bind

## External Dependencies

- `rcon` — Source RCON protocol client (synchronous, wrapped with `asyncio.to_thread`)
- Palworld Dedicated Server uses `PalWorldSettings.ini` with a non-standard single-line `OptionSettings=(key=value,...)` format

## Configuration Defaults

- Game port: 8211 (UDP)
- RCON port: 25575 (TCP)
- Idle timeout: 600 seconds
- Start timeout: 120 seconds
- Stop timeout: 30 seconds
- RCON poll interval: 10 seconds (valid range: 1–30)
