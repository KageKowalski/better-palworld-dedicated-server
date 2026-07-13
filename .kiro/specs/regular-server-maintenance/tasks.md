# Implementation Plan: Regular Server Maintenance

## Overview

Implement a scheduled maintenance cycle for the Palworld Server Wrapper that automatically stops the server, runs SteamCMD updates, and restarts at configurable intervals. This adds three new components (`MaintenanceTimer`, `SteamUpdater`, data models) and integrates them into the existing `WrapperCore` state machine alongside the `IdleTimer`.

## Tasks

- [x] 1. Add maintenance configuration fields and validation
  - [x] 1.1 Add maintenance fields to WrapperConfig
    - Add `maintenance_interval_seconds: int = 21600`, `maintenance_broadcast_lead_seconds: int = 300`, `steamcmd_path: str = ""`, and `steam_app_install_dir: str = ""` fields to the `WrapperConfig` dataclass in `src/config.py`
    - Extend the `validate()` method to check: `maintenance_interval_seconds` is int in [3600, 86400], `maintenance_broadcast_lead_seconds` is int in [30, 1800], and `maintenance_broadcast_lead_seconds < maintenance_interval_seconds`
    - Raise `ValueError` with descriptive messages for each validation failure
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 3.1, 3.2, 3.3, 3.4_

  - [x]* 1.2 Write property tests for configuration validation
    - **Property 1: Maintenance interval out-of-range rejection**
    - **Property 2: Maintenance interval type rejection**
    - **Property 3: Broadcast lead time out-of-range rejection**
    - **Property 4: Broadcast lead time must be less than maintenance interval**
    - **Validates: Requirements 1.2, 1.3, 1.5, 3.2, 3.3, 3.4**
    - Create `tests/property/test_maintenance_properties.py` with hypothesis strategies generating out-of-range integers, non-integer types, and invalid (interval, broadcast_lead) pairs
    - Use `@settings(max_examples=100)` minimum per property

  - [x]* 1.3 Write unit tests for configuration validation
    - Create `tests/unit/test_maintenance_config.py`
    - Test default values are correct (21600, 300, "", "")
    - Test boundary acceptance (3600, 86400 for interval; 30, 1800 for broadcast lead)
    - Test validation error messages are descriptive
    - Test cross-field validation (broadcast_lead >= interval rejected)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 3.1, 3.2, 3.3, 3.4_

- [x] 2. Implement MaintenanceTimer component
  - [x] 2.1 Create the MaintenanceTimer class
    - Create `src/maintenance_timer.py` following the same asyncio Task + sleep pattern as `src/idle_timer.py`
    - Implement `__init__` accepting `interval_seconds`, `broadcast_lead_seconds`, `on_broadcast_due` callback, and `on_maintenance_due` callback
    - Implement `async start()` that resets elapsed time to zero and creates an asyncio task sleeping until broadcast time, fires `on_broadcast_due`, then sleeps until maintenance time and fires `on_maintenance_due`
    - Implement `cancel()` that cancels the task, resets `_start_time` to None
    - Implement `is_active()` and `elapsed_seconds()` matching the IdleTimer interface
    - Support both sync and async callbacks (same pattern as IdleTimer)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.5_

  - [x]* 2.2 Write property test for MaintenanceTimer inactive state
    - **Property 5: Maintenance timer inactive in non-RUNNING states**
    - **Validates: Requirements 2.1, 2.2, 2.4**
    - Create test in `tests/property/test_maintenance_properties.py` verifying that after `cancel()`, `is_active()` is False and `elapsed_seconds()` is 0
    - Use `deadline=None` in hypothesis settings

  - [x]* 2.3 Write unit tests for MaintenanceTimer
    - Create `tests/unit/test_maintenance_timer.py`
    - Test `start()` sets `is_active()` to True
    - Test `cancel()` sets `is_active()` to False and `elapsed_seconds()` to 0
    - Test broadcast callback fires at `interval - broadcast_lead` seconds (mock asyncio.sleep)
    - Test maintenance callback fires at `interval` seconds
    - Test `start()` resets elapsed time to zero (no accumulation from prior start)
    - Test re-entrance: calling `start()` while active restarts from zero
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 3. Implement SteamUpdater component
  - [x] 3.1 Create the SteamUpdater class and UpdateResult dataclass
    - Add `UpdateResult` dataclass to `src/models.py` with fields: `success: bool`, `skipped: bool = False`, `error_message: str | None = None`, `timed_out: bool = False`
    - Create `src/steam_updater.py` with `SteamUpdater` class
    - Implement `__init__` accepting `steamcmd_path`, `install_dir`, `app_id=2394010`, `timeout_seconds=300`
    - Implement `async update()` that: validates paths exist (returns `skipped=True` if empty/not found), invokes SteamCMD via `asyncio.create_subprocess_exec` with args `[+force_install_dir <install_dir> +login anonymous +app_update <app_id> validate +quit]`, enforces timeout with process termination, returns appropriate `UpdateResult`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [x]* 3.2 Write unit tests for SteamUpdater
    - Create `tests/unit/test_steam_updater.py`
    - Test returns `skipped=True` when `steamcmd_path` is empty
    - Test returns `skipped=True` when `steam_app_install_dir` is empty
    - Test returns `skipped=True` when executable path doesn't exist (mock Path.exists)
    - Test returns `success=True` on exit code 0 (mock subprocess)
    - Test returns `success=False` with error message on non-zero exit code
    - Test returns `timed_out=True` and terminates process after timeout (mock asyncio.wait_for)
    - Test correct command-line arguments passed to subprocess
    - _Requirements: 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Integrate maintenance cycle into WrapperCore
  - [x] 5.1 Add MaintenanceCycleResult dataclass and maintenance state to WrapperCore
    - Add `MaintenanceCycleResult` dataclass to `src/models.py` with fields: `success: bool`, `update_result: UpdateResult | None = None`, `duration_seconds: float = 0.0`, `error_message: str | None = None`
    - Add `_maintenance_timer: MaintenanceTimer | None`, `_steam_updater: SteamUpdater`, and `_maintenance_in_progress: bool = False` instance attributes to `WrapperCore.__init__`
    - Instantiate `MaintenanceTimer` and `SteamUpdater` from config values
    - _Requirements: 4.1, 4.5, 5.1, 5.2_

  - [x] 5.2 Implement broadcast and maintenance callbacks in WrapperCore
    - Add `async _handle_broadcast_due()` method: check player count > 0, if so send RCON broadcast message including remaining seconds until restart; if RCON fails, log WARNING and continue; if no players, skip broadcast
    - Add `async _handle_maintenance_due()` method: set `_maintenance_in_progress = True`, cancel IdleTimer and MaintenanceTimer, call `_run_maintenance_cycle()`
    - Add `async _run_maintenance_cycle()` method: stop server (proceed even if stop fails), call `_steam_updater.update()`, start server, set `_maintenance_in_progress = False`, log total duration
    - _Requirements: 3.5, 3.6, 3.7, 4.1, 4.2, 4.3, 4.4, 5.3, 7.1, 7.6_

  - [x] 5.3 Modify existing WrapperCore methods for maintenance integration
    - Modify `_enter_running_state()` to also start the `MaintenanceTimer`
    - Modify `handle_idle_expired()` to check `_maintenance_in_progress`; if True, suppress idle shutdown and log
    - Modify `handle_connection_detected()` to ignore connections when `_maintenance_in_progress` is True
    - Modify `stop_server()` to cancel `MaintenanceTimer` alongside IdleTimer
    - Modify `_cleanup()` to cancel `MaintenanceTimer`
    - Ensure connection listener is NOT started during MONITORING phase when `_maintenance_in_progress` is True
    - _Requirements: 2.1, 2.2, 4.5, 4.6, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x]* 5.4 Write property tests for maintenance cycle behavior
    - **Property 6: Maintenance cycle state transition sequence**
    - **Property 7: Connection listener inactive during maintenance MONITORING**
    - **Property 8: Idle timer non-interference**
    - **Property 9: Timer reset after maintenance cycle**
    - **Validates: Requirements 4.5, 4.6, 6.1, 6.4**
    - Add to `tests/property/test_maintenance_properties.py`
    - Use mocked ProcessManager, RconClient, and asyncio.create_subprocess_exec
    - Use `deadline=None` for async tests

  - [x]* 5.5 Write unit tests for maintenance cycle integration
    - Create `tests/unit/test_maintenance_cycle.py`
    - Test full cycle state transitions: RUNNING → STOPPING → MONITORING → STARTING → RUNNING
    - Test connection listener not started during maintenance MONITORING
    - Test idle timer cancelled at cycle start
    - Test maintenance timer cancelled at cycle start
    - Test both timers restarted after cycle completes
    - Test broadcast skipped when player count is 0
    - Test broadcast sent when players are connected
    - Test cycle proceeds when broadcast fails
    - Test cycle proceeds when stop fails
    - Test cycle proceeds when update fails/is skipped
    - Test `_maintenance_in_progress` prevents re-entrant cycle
    - Test idle expiry suppressed during broadcast phase
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 6. Implement maintenance logging
  - [x] 6.1 Add logging statements to maintenance cycle methods
    - Log INFO when maintenance cycle begins
    - Log INFO when broadcast sent successfully (include message content)
    - Log WARNING when broadcast fails (include message content and reason)
    - Log INFO for successful SteamCMD update, WARNING for failure/timeout, INFO for skipped
    - Log WARNING when server stop fails and force-stop is performed
    - Log INFO when maintenance cycle completes with total duration in seconds
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [x] 7. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The `MaintenanceTimer` follows the same asyncio pattern as the existing `IdleTimer` for consistency
- The `SteamUpdater` uses the project's result-type-over-exceptions pattern
- All new modules follow the existing coding standards (type hints, Google-style docstrings, snake_case naming)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "3.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.2", "2.3", "3.2"] },
    { "id": 2, "tasks": ["5.1"] },
    { "id": 3, "tasks": ["5.2", "5.3"] },
    { "id": 4, "tasks": ["5.4", "5.5", "6.1"] }
  ]
}
```
