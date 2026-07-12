# Better Palworld Dedicated Server

A lightweight wrapper that manages your Palworld Dedicated Server process on Windows. It automatically shuts the server down when nobody is playing and starts it back up when someone tries to connect — saving resources without any manual intervention.

## Features

- **GUI management interface** — A graphical window with buttons for server control, real-time status display, settings viewer/editor, and help documentation. Launches by default.
- **Auto-start on connect** — The wrapper listens on the game port. When a player tries to join, it launches the server automatically.
- **Auto-shutdown on idle** — After 5 minutes (configurable) with no players connected, the server shuts down gracefully.
- **Scheduled maintenance** — Automatically restarts the server at a configurable interval (default 6 hours), broadcasts a warning to players beforehand, and optionally updates the server via SteamCMD.
- **Player monitoring** — Tracks connected players via RCON polling.
- **Dual interface modes** — Choose between a GUI (default) or console interface via `--interface gui|console`.
- **Settings editor** — View and modify `PalWorldSettings.ini` values with type/range validation, without editing the file by hand (available in both GUI and console modes).
- **Crash recovery** — If the server process dies unexpectedly, the wrapper resumes monitoring for new connections.
- **Logging** — Rotating log file with timestamped entries for state changes, player events, and errors.

## Requirements

- Windows
- Python 3.11+
- Palworld Dedicated Server installed (via Steam)
- RCON enabled in your server settings (`RCONEnabled=True`, with a password set)
- **tkinter** — included in the Python standard library (no additional install needed). Required for the GUI interface.

## Installation

```bash
git clone https://github.com/KageKowalski/better-palworld-dedicated-server.git
cd better-palworld-dedicated-server
pip install -e .
```

## Usage

```bash
palworld-wrapper --server-exe "C:\SteamLibrary\steamapps\common\PalServer\PalServer.exe" \
                 --settings-file "C:\SteamLibrary\steamapps\common\PalServer\Pal\Saved\Config\WindowsServer\PalWorldSettings.ini" \
                 --rcon-password "your_rcon_password"
```

Or run directly:

```bash
python -m src.main --server-exe <path> --settings-file <path> --rcon-password <password>
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--interface` | `gui` | Interface mode: `gui` (graphical window) or `console` (interactive prompt) |
| `--server-exe` | *(required)* | Path to `PalServer.exe` |
| `--settings-file` | *(required)* | Path to `PalWorldSettings.ini` |
| `--rcon-password` | `""` | RCON admin password |
| `--rcon-port` | `25575` | RCON TCP port |
| `--game-port` | `8211` | Game UDP port |
| `--idle-timeout` | `300` | Seconds with 0 players before auto-shutdown |
| `--maintenance-interval` | `21600` | Seconds between maintenance restarts (3600–86400) |
| `--maintenance-broadcast-lead` | `300` | Seconds before restart to warn players (30–1800) |
| `--steamcmd-path` | `""` | Path to `steamcmd.exe` (empty = skip updates) |
| `--steam-app-install-dir` | `""` | Palworld server install directory for SteamCMD |
| `--poll-interval` | `10` | Seconds between player count checks (1–30) |
| `--log-file` | `wrapper.log` | Log file path |

## GUI Interface

By default, the wrapper launches a graphical management window (title: "Palworld Server Wrapper", minimum size 800×600).

### GUI Features

| Section | Description |
|---------|-------------|
| **Server Control** | Start, Stop, and Restart buttons. Buttons are enabled/disabled based on the current server state. A loading indicator appears during operations. |
| **Status Display** | Real-time display of server state, player count, idle timer, server PID, and uptime. Refreshes automatically every 1 second. |
| **Settings View** | All server settings shown alphabetically. Password values are masked. Includes a Refresh button. |
| **Settings Editor** | Modify any setting by entering a key and value. Type-aware validation and auto-correction feedback is shown before writing. |
| **Help** | Opens a dialog describing all GUI controls and fields. |
| **Quit** | Gracefully shuts down the server and closes the wrapper (same as closing the window). |

To use the console interface instead:

```bash
palworld-wrapper --interface console --server-exe <path> --settings-file <path> --rcon-password <password>
```

## Console Interface (Interactive Commands)

When running with `--interface console`, the wrapper presents a `>` prompt:

| Command | Description |
|---------|-------------|
| `start` | Start the server manually |
| `stop` | Stop the server gracefully |
| `restart` | Restart the server |
| `status` | Show server state, player count, idle timer, uptime |
| `settings` | Display all current server settings |
| `set <key> <value>` | Change a server setting (validates before writing) |
| `help` | List available commands |
| `quit` | Shut down the wrapper and server |

## How It Works

1. The wrapper starts in **monitoring mode**, listening for UDP traffic on the game port (retries binding with backoff if the port isn't immediately available).
2. When a player connects, it releases the port, launches `PalServer.exe`, and waits for the RCON TCP port (25575) to become available — a reliable signal that the server is fully initialized.
3. While running, it connects to RCON (with retry/backoff if the server is slow to initialize) and polls for player count every few seconds.
4. When the last player leaves, a 5-minute idle timer starts.
5. If no one rejoins before the timer expires, the server shuts down and the wrapper resumes monitoring.
6. On a configurable interval (default 6 hours), the wrapper broadcasts a warning to players, stops the server, runs a SteamCMD update (if configured), and restarts — keeping the server fresh and up-to-date.

> **Note:** The player whose connection triggers the auto-start will need to reconnect once the server finishes launching (roughly 1–2 minutes). The initial connection packet is consumed by the wrapper to detect intent — it cannot be forwarded to the server.

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Wrapper can't bind to port 8211 | Make sure the Palworld server isn't already running. The wrapper retries with backoff, but check for port conflicts. |
| Server starts but RCON never connects | Verify `RCONEnabled=True` and `AdminPassword` is set in `PalWorldSettings.ini`. The password must match `--rcon-password`. |
| Idle timer shuts down too quickly | Increase `--idle-timeout` (e.g., `--idle-timeout 600` for 10 minutes). |
| Wrapper exits immediately | Check `wrapper.log` for configuration errors. Ensure `--server-exe` and `--settings-file` paths are correct. |
| Player count stuck after disconnect | RCON may be lagging — the wrapper retries on the next poll interval. If persistent, restart the wrapper. |
