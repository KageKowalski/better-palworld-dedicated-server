# Requirements Document

## Introduction

Palworld Dedicated Servers accumulate resources over long-running sessions, degrading performance. This feature introduces a regular maintenance cycle that automatically stops and restarts the server at a configurable interval (default 6 hours). During each maintenance window, the wrapper broadcasts a warning to connected players via RCON, stops the server gracefully, attempts to update the Palworld Dedicated Server software through Steam, and then restarts the server. This keeps the server fresh and up-to-date with minimal operator intervention.

## Glossary

- **Maintenance_Timer**: The asyncio-based timer component that tracks elapsed uptime and triggers a maintenance cycle at the configured interval.
- **Maintenance_Cycle**: The full sequence of operations performed during a scheduled maintenance window: broadcast warning, stop server, update server software, start server.
- **Wrapper**: The Palworld Server Wrapper application (WrapperCore), the central state machine coordinator.
- **RCON_Client**: The existing component that communicates with the Palworld Dedicated Server via the Source RCON protocol.
- **Process_Manager**: The existing component that manages the server subprocess lifecycle.
- **SteamCMD**: The Steam command-line tool used to install and update dedicated server software.
- **Maintenance_Interval**: The configurable duration (in seconds) between the server entering the RUNNING state and the next scheduled maintenance cycle.
- **Broadcast_Lead_Time**: The configurable duration (in seconds) before the server stops during a maintenance cycle, during which a warning broadcast is sent to players.

## Requirements

### Requirement 1: Configurable Maintenance Interval

**User Story:** As a server operator, I want to configure how often the server restarts for maintenance, so that I can balance uptime with performance.

#### Acceptance Criteria

1. THE Wrapper SHALL expose a `maintenance_interval_seconds` configuration field as an integer with a default value of 21600 (6 hours).
2. IF the `maintenance_interval_seconds` value is set below 3600 (1 hour), THEN THE Wrapper SHALL raise a validation error indicating the value is below the minimum allowed.
3. IF the `maintenance_interval_seconds` value is set above 86400 (24 hours), THEN THE Wrapper SHALL raise a validation error indicating the value exceeds the maximum allowed.
4. WHEN the `maintenance_interval_seconds` value is set to exactly 3600 or exactly 86400, THE Wrapper SHALL accept the value without raising a validation error.
5. IF the `maintenance_interval_seconds` value is not an integer, THEN THE Wrapper SHALL raise a validation error indicating the expected type.

### Requirement 2: Maintenance Timer Lifecycle

**User Story:** As a server operator, I want the maintenance timer to start automatically when the server is running, so that maintenance cycles happen without manual intervention.

#### Acceptance Criteria

1. WHEN the server transitions to the RUNNING state, THE Maintenance_Timer SHALL start counting from zero regardless of any previously accumulated time.
2. WHEN the server leaves the RUNNING state for any reason, THE Maintenance_Timer SHALL cancel and reset to zero.
3. WHEN the Maintenance_Timer elapsed time reaches the configured Maintenance_Interval (within a tolerance of the RCON poll interval), THE Maintenance_Timer SHALL trigger a Maintenance_Cycle.
4. WHILE the server is in the MONITORING, STARTING, or STOPPING state, THE Maintenance_Timer SHALL report `is_active()` as False and `elapsed_seconds()` as 0.
5. IF the Maintenance_Timer fires while a Maintenance_Cycle is already in progress, THEN THE Maintenance_Timer SHALL take no action and cancel itself.

### Requirement 3: Pre-Restart Player Broadcast

**User Story:** As a player on the server, I want to receive a warning before the server restarts for maintenance, so that I can save my progress and prepare for the downtime.

#### Acceptance Criteria

1. THE Wrapper SHALL expose a `maintenance_broadcast_lead_seconds` configuration field with a default value of 300 (5 minutes).
2. WHEN the `maintenance_broadcast_lead_seconds` value is set below 30, THE Wrapper SHALL reject the value with a validation error.
3. WHEN the `maintenance_broadcast_lead_seconds` value is set above 1800 (30 minutes), THE Wrapper SHALL reject the value with a validation error.
4. IF the `maintenance_broadcast_lead_seconds` value is greater than or equal to the configured `maintenance_interval_seconds` value, THEN THE Wrapper SHALL reject the value with a validation error.
5. WHEN the Maintenance_Timer reaches the Maintenance_Interval minus the Broadcast_Lead_Time, THE RCON_Client SHALL send a single broadcast message to all connected players that includes the remaining seconds until restart.
6. WHEN the broadcast message fails to send due to an RCON error, THE Wrapper SHALL log the failure and proceed with the Maintenance_Cycle after the Broadcast_Lead_Time elapses.
7. IF no players are connected when the broadcast is due, THEN THE Wrapper SHALL skip sending the broadcast message and proceed with the Maintenance_Cycle after the Broadcast_Lead_Time elapses.

### Requirement 4: Maintenance Cycle Execution

**User Story:** As a server operator, I want the maintenance cycle to stop the server gracefully, so that player data is saved before the restart.

#### Acceptance Criteria

1. WHEN a Maintenance_Cycle is triggered, THE Wrapper SHALL stop the server using the existing graceful shutdown procedure (RCON Shutdown command followed by process tree kill).
2. WHEN the server stop completes successfully during a Maintenance_Cycle, THE Wrapper SHALL proceed to the software update step.
3. IF the server stop fails during a Maintenance_Cycle (graceful shutdown and force-stop both fail), THEN THE Wrapper SHALL log the failure and proceed to the software update step.
4. WHEN the Maintenance_Cycle completes the update step, THE Wrapper SHALL start the server using the existing start procedure.
5. WHILE a Maintenance_Cycle is in progress, THE Wrapper SHALL transition through the states RUNNING → STOPPING → MONITORING → STARTING → RUNNING.
6. WHILE a Maintenance_Cycle is in the MONITORING state, THE connection listener SHALL remain inactive to prevent external connection attempts from triggering a separate start sequence.

### Requirement 5: Server Software Update via SteamCMD

**User Story:** As a server operator, I want the server software to be updated during maintenance windows, so that the server stays current without additional downtime.

#### Acceptance Criteria

1. THE Wrapper SHALL expose a `steamcmd_path` configuration field with a default value of empty string for the path to the SteamCMD executable.
2. THE Wrapper SHALL expose a `steam_app_install_dir` configuration field with a default value of empty string for the Palworld Dedicated Server installation directory.
3. WHEN the server is stopped during a Maintenance_Cycle, THE Wrapper SHALL invoke SteamCMD to update app ID 2394010 (Palworld Dedicated Server) using the configured `steam_app_install_dir` as the installation directory.
4. WHEN SteamCMD completes with a success exit code, THE Wrapper SHALL log that the update completed successfully.
5. WHEN SteamCMD completes with a non-zero exit code, THE Wrapper SHALL log the error and proceed to start the server without blocking the restart.
6. WHEN SteamCMD does not complete within 300 seconds, THE Wrapper SHALL terminate the SteamCMD process, log a timeout error, and proceed to start the server.
7. IF the `steamcmd_path` configuration is empty or the executable is not found, THEN THE Wrapper SHALL skip the update step, log a warning, and proceed to start the server.
8. IF the `steam_app_install_dir` configuration is empty or the directory path is not found, THEN THE Wrapper SHALL skip the update step, log a warning, and proceed to start the server.

### Requirement 6: Maintenance Cycle and Idle Timer Interaction

**User Story:** As a server operator, I want the maintenance timer and idle timer to work together without conflicts, so that the server behaves predictably.

#### Acceptance Criteria

1. WHILE the Maintenance_Timer is active, THE Idle_Timer SHALL continue to start, count, and reset based on player count without being paused, suspended, or modified by the Maintenance_Timer.
2. WHEN the Idle_Timer expires before the Maintenance_Timer, THE Wrapper SHALL perform the idle shutdown procedure and cancel the Maintenance_Timer.
3. WHEN the Maintenance_Timer triggers a Maintenance_Cycle, THE Wrapper SHALL cancel the Idle_Timer before beginning the Maintenance_Cycle shutdown sequence.
4. WHEN the server is restarted after a Maintenance_Cycle, THE Maintenance_Timer SHALL start counting from zero for the next cycle and THE Idle_Timer SHALL resume operating based on the connected player count.
5. WHILE a Maintenance_Cycle broadcast phase is in progress, IF the Idle_Timer expires, THEN THE Wrapper SHALL allow the Maintenance_Cycle to continue and suppress the idle shutdown.

### Requirement 7: Maintenance Cycle Logging

**User Story:** As a server operator, I want maintenance activities to be logged, so that I can review the maintenance history and troubleshoot issues.

#### Acceptance Criteria

1. WHEN a Maintenance_Cycle begins, THE Wrapper SHALL log an INFO-level message indicating the maintenance cycle has started.
2. WHEN a player broadcast is sent successfully, THE Wrapper SHALL log an INFO-level message containing the broadcast message content.
3. IF a player broadcast fails to send, THEN THE Wrapper SHALL log a WARNING-level message containing the broadcast message content and the reason for failure.
4. WHEN the SteamCMD update step completes, THE Wrapper SHALL log the outcome (success, failure, timeout, or skipped) at INFO level for success or skipped and at WARNING level for failure or timeout.
5. IF the server stop fails during a Maintenance_Cycle and a force-stop is performed, THEN THE Wrapper SHALL log a WARNING-level message indicating the force-stop occurred.
6. WHEN a Maintenance_Cycle completes and the server is back in the RUNNING state, THE Wrapper SHALL log an INFO-level message containing the total duration of the maintenance window in seconds, measured from the start of the Maintenance_Cycle to the server entering the RUNNING state.
