# Better Palworld Dedicated Server

A lightweight wrapper that manages your Palworld Dedicated Server process on Windows. It automatically shuts the server down when nobody is playing and starts it back up when someone tries to connect — saving resources without any manual intervention.

## Features

- **Auto-start on connect** — Listens on the game port and launches the server when a player tries to join.
- **Auto-shutdown on idle** — Shuts the server down gracefully after a configurable idle timeout (default 5 minutes).
- **Scheduled maintenance** — Periodically restarts the server with a player warning broadcast, optionally running a SteamCMD update.
- **GUI interface (default)** — Graphical window with server control buttons, real-time status, unified settings panel, and output log.
- **Console interface** — Interactive prompt for headless or terminal-based usage.
- **Unified settings panel** — View and edit `PalWorldSettings.ini` values with descriptions, validation, and search/filter (both interfaces).
- **Crash recovery** — Resumes monitoring automatically if the server process dies.
- **Rotating log file** — Timestamped entries for state changes, player events, and errors.

## Requirements

- Windows
- Python 3.11+
- Palworld Dedicated Server installed (via Steam or SteamCMD)
- REST API enabled (default in recent versions) with `AdminPassword` set in `PalWorldSettings.ini`

### Python Dependencies

- `aiohttp` — Async HTTP client for REST API communication
- `customtkinter` — Modern themed GUI widget library (dark mode, rounded corners)

Both are installed automatically via `pip install -e .`

## Installation

```bash
git clone https://github.com/KageKowalski/better-palworld-dedicated-server.git
cd better-palworld-dedicated-server
pip install -e .
```

## Usage

```bash
palworld-wrapper --server-exe "C:\SteamLibrary\steamapps\common\PalServer\PalServer.exe" ^
                 --settings-file "C:\SteamLibrary\steamapps\common\PalServer\Pal\Saved\Config\WindowsServer\PalWorldSettings.ini" ^
                 --admin-password "your_admin_password"
```

Or run directly without installing:

```bash
python -m src.main --server-exe <path> --settings-file <path> --admin-password <password>
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--server-exe` | *(required)* | Path to `PalServer.exe` |
| `--settings-file` | *(required)* | Path to `PalWorldSettings.ini` |
| `--admin-password` | `""` | Admin password for REST API authentication (max 128 chars) |
| `--api-port` | `8212` | REST API TCP port (1–65535) |
| `--game-port` | `8211` | Game UDP port |
| `--idle-timeout` | `300` | Seconds with 0 players before auto-shutdown |
| `--poll-interval` | `10` | Seconds between player count checks (1–30) |
| `--maintenance-interval` | `21600` | Seconds between maintenance restarts (3600–86400) |
| `--maintenance-broadcast-lead` | `300` | Seconds before restart to warn players (30–1800) |
| `--steamcmd-path` | `""` | Path to `steamcmd.exe` (empty = skip updates) |
| `--steam-app-install-dir` | `""` | Palworld server install directory for SteamCMD |
| `--interface` | `gui` | Interface mode: `gui` or `console` |
| `--log-file` | `wrapper.log` | Log file path |

## GUI Interface

The default mode launches a standalone graphical window. It detaches from the launching console automatically — you can close the PowerShell window without affecting the wrapper or server.

| Section | Description |
|---------|-------------|
| **Server Control** | Start, Stop, and Restart buttons (enabled/disabled based on server state) |
| **Status Display** | Server state, player count, idle timer, PID, and uptime (auto-refreshes) |
| **Output Panel** | Scrollable real-time log of events and errors |
| **Server Settings** | Searchable/filterable list of all settings with inline editing and validation |
| **Help** | Opens a dialog describing all controls |
| **Quit** | Gracefully stops the server and closes the wrapper |

## Console Interface

Launch with `--interface console` to use an interactive terminal prompt:

| Command | Description |
|---------|-------------|
| `start` | Start the server |
| `stop` | Stop the server gracefully |
| `restart` | Restart the server |
| `status` | Show server state, player count, idle timer, uptime |
| `settings` | Display all current server settings |
| `set <key> <value>` | Change a server setting (validates before writing) |
| `help` | List available commands |
| `quit` | Shut down the wrapper and server |

## How It Works

1. The wrapper listens for UDP traffic on the game port.
2. When a player connects, it releases the port, launches the server, and waits for REST API readiness.
3. While running, it polls the REST API for player count.
4. When the last player leaves, the idle timer starts. If no one rejoins, the server shuts down and monitoring resumes.
5. On the maintenance interval, the wrapper sends an announcement via REST API, stops the server, optionally runs a SteamCMD update, and restarts.

> **Note:** The player whose connection triggers auto-start will need to reconnect once the server finishes launching (~1–2 minutes). The initial packet is consumed by the wrapper to detect intent.

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Can't bind to port 8211 | Ensure the Palworld server isn't already running. Check for port conflicts. |
| REST API not connecting | Verify `AdminPassword` in `PalWorldSettings.ini` matches `--admin-password`. Check REST API port (default 8212). |
| Idle timer too aggressive | Increase `--idle-timeout` (e.g., `600` for 10 minutes). |
| Wrapper exits immediately | Check `wrapper.log` for errors. Verify `--server-exe` and `--settings-file` paths exist. |
