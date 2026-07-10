# Implementation Plan: Palworld Server Wrapper

## Overview

This plan implements a Python asyncio-based wrapper for managing a Palworld Dedicated Server on Windows. The wrapper provides automatic idle shutdown, automatic startup on connection attempt, RCON-based player monitoring, a CLI management interface, and INI settings management. Implementation proceeds bottom-up: data models and configuration first, then individual components, then the core state machine, and finally integration wiring.

## Tasks

- [x] 1. Set up project structure, dependencies, and data models
  - [x] 1.1 Create project directory structure and install dependencies
    - Create the following directories: `src/`, `tests/property/`, `tests/unit/`, `tests/integration/`
    - Create `pyproject.toml` with dependencies: `rcon`, `pytest`, `pytest-asyncio`, `hypothesis`
    - Set Python version requirement to 3.11+
    - Create `src/__init__.py` and `tests/__init__.py`
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 1.2 Implement configuration data model (`src/config.py`)
    - Create `WrapperConfig` dataclass with all fields from the design: `server_exe_path`, `settings_file_path`, `game_port`, `rcon_port`, `rcon_password`, `idle_timeout_seconds`, `start_timeout_seconds`, `stop_timeout_seconds`, `rcon_poll_interval_seconds`, `log_file_path`, `log_max_size_mb`, `log_backup_count`
    - Add default values as specified in the design
    - Add validation method to reject `rcon_poll_interval_seconds` outside 1–30
    - _Requirements: 7.3_

  - [x] 1.3 Implement state and status data models (`src/models.py`)
    - Create `ServerState` enum with values: MONITORING, STARTING, RUNNING, STOPPING
    - Create `WrapperStatus` dataclass with: `server_state`, `player_count`, `idle_timer_active`, `idle_seconds`, `server_pid`, `uptime_seconds`
    - Create `StartResult`, `StopResult`, `RestartResult`, `RconQueryResult`, `ValidationResult` dataclasses
    - Create `StateTransitionEvent` dataclass with `timestamp`, `from_state`, `to_state`, `reason`
    - _Requirements: 1.1, 1.2, 2.1, 3.1, 3.2, 5.2, 5.3, 8.4_

  - [ ]* 1.4 Write property test for poll interval validation (Property 12)
    - **Property 12: Poll Interval Bounds**
    - Generate random integers; verify values < 1 or > 30 are rejected, values 1–30 are accepted
    - **Validates: Requirements 7.3**

- [x] 2. Implement Logger and Settings Parser
  - [x] 2.1 Implement logger module (`src/logger.py`)
    - Create `WrapperLogger` class using Python's `logging` module with `RotatingFileHandler`
    - Configure max 10 MB per file, 3 backup files
    - Add methods: `setup()`, `log_state_transition()`, `log_player_event()`, `log_error()`
    - All entries include ISO 8601 timestamps
    - _Requirements: 8.4, 8.6_

  - [x] 2.2 Implement settings parser (`src/settings_parser.py`)
    - Create `SettingDefinition` dataclass with `name`, `value_type`, `min_value`, `max_value`, `allowed_values`
    - Create `SettingsParser` class with methods: `read_settings()`, `write_setting()`, `validate_setting()`, `get_setting_definitions()`
    - Parse the `OptionSettings=(key=value,key=value,...)` single-line format under `[/Script/Pal.PalGameWorldSettings]`
    - Validate values against type and range constraints
    - Preserve file structure when writing (only modify the target value)
    - Handle file-not-found and malformed file errors gracefully
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6_

  - [ ]* 2.3 Write property test for settings validation (Property 6)
    - **Property 6: Settings Validation**
    - Generate random values for each setting type; verify accept/reject based on type and range
    - **Validates: Requirements 4.2, 4.3**

  - [ ]* 2.4 Write property test for settings round-trip preservation (Property 7)
    - **Property 7: Settings Round-Trip Preservation**
    - Generate valid settings dictionaries, write a modification, read back, verify only modified key changed
    - **Validates: Requirements 4.2**

  - [ ]* 2.5 Write property test for malformed configuration handling (Property 8)
    - **Property 8: Malformed Configuration Graceful Handling**
    - Generate random strings not conforming to `OptionSettings=(...)` format; verify parser returns error without crashing
    - **Validates: Requirements 4.6**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement Connection Listener and Idle Timer
  - [x] 4.1 Implement connection listener (`src/connection_listener.py`)
    - Create `ConnectionListener` class using `asyncio` UDP protocol (`loop.create_datagram_endpoint`)
    - Implement `start_listening()`, `stop_listening()`, `is_listening()` methods
    - Bind to UDP port 8211 and invoke callback on packet receipt
    - Release socket within 1 second when `stop_listening()` is called
    - _Requirements: 2.1, 2.3_

  - [x] 4.2 Implement idle timer (`src/idle_timer.py`)
    - Create `IdleTimer` class using `asyncio.get_event_loop().time()` for monotonic timing
    - Implement `start()`, `reset()`, `cancel()`, `is_active()`, `elapsed_seconds()` methods
    - Fire callback when elapsed time reaches configured threshold (default 600s)
    - Reset on player connect, cancel when server stops
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.6_

  - [ ]* 4.3 Write property test for idle timer lifecycle (Property 1)
    - **Property 1: Idle Timer Lifecycle Invariant**
    - Generate random sequences of state changes and player count transitions; verify timer is active iff state is RUNNING and player count is zero
    - **Validates: Requirements 1.1, 1.3, 1.6**

  - [ ]* 4.4 Write property test for idle shutdown threshold (Property 2)
    - **Property 2: Idle Shutdown Threshold**
    - Generate elapsed time values; verify shutdown triggered at >= 600s with 0 players, not triggered at < 600s
    - **Validates: Requirements 1.2**

  - [ ]* 4.5 Write property test for connection listener state invariant (Property 3)
    - **Property 3: Connection Listener State Invariant**
    - Generate random state sequences; verify listener is active iff state is MONITORING
    - **Validates: Requirements 2.1**

- [x] 5. Implement Process Manager and RCON Client
  - [x] 5.1 Implement process manager (`src/process_manager.py`)
    - Create `ProcessManager` class with methods: `start_server()`, `stop_server()`, `is_running()`, `wait_for_port()`, `get_pid()`
    - Launch `PalServer.exe` via `asyncio.create_subprocess_exec`
    - Poll port 8211 readiness using socket connect attempts with 120s timeout
    - Graceful shutdown via `process.terminate()` (CTRL_BREAK_EVENT on Windows)
    - Force kill via `process.kill()` after configurable timeout (default 30s)
    - Monitor for unexpected process termination via `process.wait()`
    - _Requirements: 1.4, 2.4, 2.5, 3.1, 3.2, 3.6, 3.7, 8.1_

  - [x] 5.2 Implement RCON client (`src/rcon_client.py`)
    - Create `RconClient` class with methods: `connect()`, `query_players()`, `disconnect()`
    - Connect to RCON port (default 25575) using `rcon` library
    - Issue `ShowPlayers` command and parse CSV-like response to count players
    - Player count = number of non-empty, non-header lines in response
    - Handle connection failures gracefully, returning `RconQueryResult` with error info
    - _Requirements: 5.1, 5.2, 5.3, 5.6, 5.7_

  - [ ]* 5.3 Write property test for player count tracking (Property 9)
    - **Property 9: Player Count Tracks RCON Response**
    - Generate sequences of RCON responses with varying player counts; verify wrapper updates count and logs connect/disconnect events
    - **Validates: Requirements 5.2, 5.3**

  - [ ]* 5.4 Write property test for player count non-negative invariant (Property 10)
    - **Property 10: Player Count Non-Negative Invariant**
    - Generate sequences of RCON responses including erroneous/unexpected values; verify stored count never drops below zero
    - **Validates: Requirements 5.4**

  - [ ]* 5.5 Write property test for RCON failure preservation (Property 11)
    - **Property 11: RCON Failure Preserves Count**
    - Generate sequences mixing successful and failed RCON queries; verify count is unchanged on failure
    - **Validates: Requirements 5.6**

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement Wrapper Core state machine
  - [x] 7.1 Implement wrapper core (`src/wrapper_core.py`)
    - Create `WrapperCore` class as the central state machine coordinator
    - Implement state transitions: MONITORING → STARTING → RUNNING → STOPPING → MONITORING
    - Implement `run()` as the main asyncio event loop entry point
    - Implement `handle_connection_detected()`: stop listener, start server
    - Implement `handle_idle_expired()`: initiate graceful shutdown
    - Implement `handle_server_crashed()`: log event, cancel timer, resume monitoring
    - Implement `start_server()`: launch process, wait for port, start RCON polling and idle timer
    - Implement `stop_server()`: graceful shutdown with force-kill fallback
    - Implement `restart_server()`: stop then start
    - Implement `get_status()`: return current `WrapperStatus`
    - Wire RCON polling loop with configurable interval (default 10s)
    - Update player count from RCON results; manage idle timer start/reset based on count
    - Detect crash via process monitor task; transition to MONITORING on unexpected termination
    - Ensure single start attempt on multiple UDP packets (Property 4)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 8.1, 8.2, 8.4, 8.5_

  - [ ]* 7.2 Write property test for single start attempt idempotence (Property 4)
    - **Property 4: Single Start Attempt Idempotence**
    - Generate sequences of N UDP packets while server is not running; verify exactly one start attempt initiated
    - **Validates: Requirements 2.2**

  - [ ]* 7.3 Write property test for command guard conditions (Property 5)
    - **Property 5: Command Guard Conditions**
    - Generate commands in incompatible states; verify rejection with informative message and state unchanged
    - **Validates: Requirements 3.4, 3.5**

  - [ ]* 7.4 Write property test for start error recovery (Property 13)
    - **Property 13: Start Error Recovery**
    - Generate error conditions during startup; verify wrapper transitions to MONITORING and resumes listening
    - **Validates: Requirements 8.2**

  - [ ]* 7.5 Write property test for state transitions produce log entries (Property 14)
    - **Property 14: State Transitions Produce Log Entries**
    - Generate random state transition events; verify each produces a log entry with ISO 8601 timestamp and description
    - **Validates: Requirements 8.4**

- [x] 8. Implement Management Interface
  - [x] 8.1 Implement management interface (`src/management_interface.py`)
    - Create `ManagementInterface` class running on the asyncio event loop
    - Use `asyncio` stdin reader for non-blocking input
    - Display: server status, player count, idle timer elapsed seconds
    - Implement commands: `start`, `stop`, `restart`, `status`, `settings`, `set <key> <value>`, `quit`
    - Integrate with `WrapperCore` for command execution
    - Accept and begin processing input within 2 seconds including during server operations
    - Reflect status changes within 2 seconds of occurrence
    - Warn user when modifying settings while server is running (restart required)
    - Handle guard conditions: inform user if start issued while running, stop issued while not running
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 9. Implement application entry point and wiring
  - [x] 9.1 Create application entry point (`src/main.py`)
    - Parse command-line arguments or configuration file for `WrapperConfig` values
    - Instantiate all components: `WrapperLogger`, `ConnectionListener`, `ProcessManager`, `RconClient`, `IdleTimer`, `SettingsParser`, `WrapperCore`, `ManagementInterface`
    - Wire components together and start the asyncio event loop
    - Handle top-level unhandled exceptions: log and continue
    - _Requirements: 7.1, 7.2, 7.4, 8.5_

  - [ ]* 9.2 Write unit tests for RCON client response parsing
    - Test `ShowPlayers` response parsing: header handling, empty response, single player, multiple players
    - Test connection failure handling
    - _Requirements: 5.2, 5.3, 5.6_

  - [ ]* 9.3 Write unit tests for management interface command parsing
    - Test command parsing for all supported commands
    - Test invalid command handling
    - Test guard condition messages
    - _Requirements: 3.4, 3.5, 6.4_

  - [ ]* 9.4 Write unit tests for process manager
    - Mock `subprocess` calls; verify start/stop/force-kill sequences
    - Verify port-readiness polling logic
    - Verify crash detection via process.wait()
    - _Requirements: 1.4, 3.6, 3.7, 8.1_

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The wrapper targets Windows and Python 3.11+
- Runtime dependencies: `rcon` (Source RCON protocol), `asyncio` (stdlib)
- Test dependencies: `pytest`, `pytest-asyncio`, `hypothesis`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["1.4", "2.1", "2.2"] },
    { "id": 3, "tasks": ["2.3", "2.4", "2.5", "4.1", "4.2"] },
    { "id": 4, "tasks": ["4.3", "4.4", "4.5", "5.1", "5.2"] },
    { "id": 5, "tasks": ["5.3", "5.4", "5.5"] },
    { "id": 6, "tasks": ["7.1"] },
    { "id": 7, "tasks": ["7.2", "7.3", "7.4", "7.5", "8.1"] },
    { "id": 8, "tasks": ["9.1"] },
    { "id": 9, "tasks": ["9.2", "9.3", "9.4"] }
  ]
}
```
