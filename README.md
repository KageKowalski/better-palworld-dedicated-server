# Better Palworld Dedicated Server

A lightweight wrapper that manages your Palworld Dedicated Server process on Windows. It automatically shuts the server down when nobody is playing and starts it back up when someone tries to connect — saving resources without any manual intervention.

## Features

- **Auto-start on connect** — The wrapper listens on the game port. When a player tries to join, it launches the server automatically.
- **Auto-shutdown on idle** — After 10 minutes (configurable) with no players connected, the server shuts down gracefully.
- **Player monitoring** — Tracks connected players via RCON polling.
- **CLI management** — Start, stop, restart, check status, and modify server settings from an interactive prompt.
- **Settings editor** — View and modify `PalWorldSettings.ini` values with type/range validation, without editing the file by hand.
- **Crash recovery** — If the server process dies unexpectedly, the wrapper resumes monitoring for new connections.
- **Logging** — Rotating log file with timestamped entries for state changes, player events, and errors.

## Requirements

- Windows
- Python 3.11+
- Palworld Dedicated Server installed (via Steam)
- RCON enabled in your server settings (`RCONEnabled=True`, with a password set)

## Installation

```bash
git clone https://github.com/your-username/better-palworld-dedicated-server.git
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
| `--server-exe` | *(required)* | Path to `PalServer.exe` |
| `--settings-file` | *(required)* | Path to `PalWorldSettings.ini` |
| `--rcon-password` | `""` | RCON admin password |
| `--rcon-port` | `25575` | RCON TCP port |
| `--game-port` | `8211` | Game UDP port |
| `--idle-timeout` | `600` | Seconds with 0 players before auto-shutdown |
| `--poll-interval` | `10` | Seconds between player count checks (1–30) |
| `--log-file` | `wrapper.log` | Log file path |

## Interactive Commands

Once running, the wrapper presents a `>` prompt:

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
4. When the last player leaves, a 10-minute idle timer starts.
5. If no one rejoins before the timer expires, the server shuts down and the wrapper resumes monitoring.

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```
