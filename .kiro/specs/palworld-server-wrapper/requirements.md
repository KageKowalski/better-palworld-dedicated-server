# Requirements Document

## Introduction

The better-palworld-dedicated-server project provides a lightweight Python wrapper around the Palworld Dedicated Server on Windows. The wrapper monitors player connections and manages the server process to conserve resources — automatically shutting the server down when idle and starting it when a connection is attempted. A secondary management interface allows the user to control the server and adjust settings.

## Glossary

- **Wrapper**: The Python application (better-palworld-dedicated-server) that monitors and manages the Palworld Dedicated Server process.
- **Dedicated_Server**: The Palworld Dedicated Server process installed via Steam on the host Windows machine.
- **Connection_Listener**: The component of the Wrapper that monitors incoming UDP traffic on port 8211.
- **Idle_Timer**: The component that tracks how long the Dedicated_Server has been running with zero connected players.
- **Management_Interface**: The local interface that allows the user to interact with the Wrapper and control the Dedicated_Server.
- **Server_Settings**: The configuration parameters for the Dedicated_Server that can be viewed and modified through the Management_Interface.
- **Player**: A remote user who connects to the Dedicated_Server via UDP port 8211.

## Requirements

### Requirement 1: Automatic Server Shutdown on Idle

**User Story:** As a server host, I want the Dedicated Server to automatically shut down after being idle for 600 seconds, so that system resources are not wasted when no players are connected.

#### Acceptance Criteria

1. WHEN the last Player disconnects from the Dedicated_Server, THE Idle_Timer SHALL begin counting elapsed seconds from zero.
2. WHEN the Idle_Timer reaches 600 seconds with zero connected Players, THE Wrapper SHALL send a graceful shutdown signal to the Dedicated_Server process.
3. WHEN a Player connects while the Idle_Timer is running but before 600 seconds have elapsed, THE Idle_Timer SHALL reset and stop counting.
4. IF the Dedicated_Server process does not terminate within 30 seconds of the shutdown signal, THEN THE Wrapper SHALL forcibly terminate the Dedicated_Server process.
5. WHEN the Dedicated_Server starts with zero connected Players, THE Idle_Timer SHALL begin counting within 1 second.
6. IF the Dedicated_Server is stopped by a manual command or crashes while the Idle_Timer is running, THEN THE Idle_Timer SHALL be cancelled.
7. IF the Dedicated_Server process does not terminate after forcible termination attempt, THEN THE Wrapper SHALL log a critical error and resume monitoring UDP port 8211.

### Requirement 2: Automatic Server Start on Connection Attempt

**User Story:** As a player, I want the server to start automatically when I attempt to connect, so that I do not need to contact the server host to turn it on.

#### Acceptance Criteria

1. WHILE the Dedicated_Server is not running and no start attempt is in progress, THE Connection_Listener SHALL monitor UDP port 8211 for incoming packets.
2. WHILE the Dedicated_Server is not running, WHEN an incoming UDP packet is detected on port 8211, THE Wrapper SHALL initiate a single start attempt for the Dedicated_Server process and discard any further incoming packets until the start attempt completes or fails.
3. WHEN the Wrapper initiates a Dedicated_Server start attempt, THE Connection_Listener SHALL stop monitoring and release UDP port 8211 within 1 second.
4. IF the Dedicated_Server process is not listening on UDP port 8211 within 120 seconds of the start attempt, THEN THE Wrapper SHALL log an error indicating the startup failure reason and resume monitoring UDP port 8211 for future connection attempts.
5. WHEN the Dedicated_Server process begins listening on UDP port 8211, THE Wrapper SHALL consider the start attempt successful.

### Requirement 3: Server Process Management

**User Story:** As a server host, I want to start, stop, and restart the Dedicated Server through the Management Interface, so that I can control the server without navigating to external tools.

#### Acceptance Criteria

1. WHEN the user issues a start command through the Management_Interface, THE Wrapper SHALL start the Dedicated_Server process and inform the user of success once the server is listening on UDP port 8211.
2. WHEN the user issues a stop command through the Management_Interface, THE Wrapper SHALL send a graceful shutdown signal to the Dedicated_Server process and inform the user of success once the process has terminated.
3. WHEN the user issues a restart command through the Management_Interface, THE Wrapper SHALL stop the Dedicated_Server and then start the Dedicated_Server once the process has terminated, informing the user of success once the restart is complete.
4. IF the user issues a start command while the Dedicated_Server is already running, THEN THE Management_Interface SHALL inform the user that the server is already running.
5. IF the user issues a stop command while the Dedicated_Server is not running, THEN THE Management_Interface SHALL inform the user that the server is not running.
6. IF the Dedicated_Server fails to start within 120 seconds after a manual start command, THEN THE Wrapper SHALL log an error and inform the user through the Management_Interface that the start failed.
7. IF the Dedicated_Server does not terminate within 30 seconds after a manual stop command, THEN THE Wrapper SHALL forcibly terminate the process and inform the user.
8. IF the user issues a restart command while the Dedicated_Server is not running, THEN THE Wrapper SHALL treat the command as a start command.

### Requirement 4: Server Settings Management

**User Story:** As a server host, I want to view and modify Dedicated Server settings through the Management Interface, so that I can configure the server without manually editing configuration files.

#### Acceptance Criteria

1. WHEN the user requests server settings through the Management_Interface, THE Wrapper SHALL read the current Server_Settings from the Dedicated_Server configuration file and display them.
2. WHEN the user modifies a setting through the Management_Interface, THE Wrapper SHALL validate that the provided value is within the acceptable range and type for that setting before writing the updated value to the Dedicated_Server configuration file.
3. IF the user provides a setting value that is outside the acceptable range or of an incorrect type, THEN THE Wrapper SHALL reject the modification and inform the user through the Management_Interface that the value is invalid.
4. WHILE the Dedicated_Server is running AND the user modifies a setting through the Management_Interface, THE Management_Interface SHALL warn the user that the setting change requires a server restart to take effect.
5. IF the Dedicated_Server configuration file is not found at the expected path, THEN THE Wrapper SHALL log an error and inform the user through the Management_Interface.
6. IF the Dedicated_Server configuration file exists but cannot be parsed, THEN THE Wrapper SHALL log an error and inform the user through the Management_Interface that the configuration file is malformed.

### Requirement 5: Connection Monitoring

**User Story:** As a server host, I want the Wrapper to reliably track connected players, so that idle detection and automatic shutdown function correctly.

#### Acceptance Criteria

1. WHILE the Dedicated_Server is running, THE Wrapper SHALL query the connected Player count via RCON at an interval no more frequent than once per second and no less frequent than once every 30 seconds.
2. WHEN the RCON query reports a higher Player count than the previously recorded count, THE Wrapper SHALL update the connected Player count to match the RCON-reported value and log a player connection event.
3. WHEN the RCON query reports a lower Player count than the previously recorded count, THE Wrapper SHALL update the connected Player count to match the RCON-reported value and log a player disconnection event.
4. THE Wrapper SHALL never allow the connected Player count to drop below zero.
5. WHEN the Dedicated_Server process starts, THE Wrapper SHALL initialize the connected Player count to zero.
6. IF the RCON query fails, THEN THE Wrapper SHALL retain the last known Player count, log the failure, and retry on the next polling interval.
7. IF the RCON query fails on 5 consecutive attempts, THEN THE Wrapper SHALL log a warning and continue retrying on the next polling interval.

### Requirement 6: Management Interface Availability

**User Story:** As a server host, I want a local interface for interacting with the Wrapper, so that I can monitor status and issue commands conveniently.

#### Acceptance Criteria

1. THE Management_Interface SHALL provide a way for the user to view the current status of the Dedicated_Server (running or stopped).
2. THE Management_Interface SHALL provide a way for the user to view the number of currently connected Players.
3. WHILE the Idle_Timer is active, THE Management_Interface SHALL display the elapsed idle time in whole seconds. IF the Idle_Timer is not active, THEN THE Management_Interface SHALL indicate that no idle timer is running.
4. WHILE the Wrapper is running, THE Management_Interface SHALL accept and begin processing a user command within 2 seconds of input, including while Dedicated_Server operations are in progress.
5. WHEN the Dedicated_Server status, connected Player count, or Idle_Timer value changes, THE Management_Interface SHALL reflect the updated value within 2 seconds of the change occurring.

### Requirement 7: Lightweight Resource Usage

**User Story:** As a server host, I want the Wrapper to use minimal system resources, so that it does not interfere with the Dedicated Server or other processes on the host.

#### Acceptance Criteria

1. WHILE idle and monitoring for connections, THE Wrapper SHALL consume less than 50 MB of memory.
2. WHILE the Dedicated_Server is running, THE Wrapper SHALL consume no more than 2% of a single CPU core on average over any 60-second window.
3. THE Wrapper SHALL poll for player connections via RCON at intervals between 1 and 30 seconds and SHALL NOT use busy-wait loops or sub-second polling.
4. THE Wrapper SHALL use no more than 2 background threads or async tasks for its monitoring and interface operations.

### Requirement 8: Reliability and Error Handling

**User Story:** As a server host, I want the Wrapper to handle errors gracefully and continue running, so that the server management remains available even when unexpected situations occur.

#### Acceptance Criteria

1. IF the Dedicated_Server process crashes unexpectedly, THEN THE Wrapper SHALL detect the termination within 5 seconds, log the event, and resume monitoring UDP port 8211 for new connection attempts.
2. IF the Wrapper encounters an error while starting the Dedicated_Server, THEN THE Wrapper SHALL log the error and remain in the monitoring state.
3. IF the Wrapper encounters an error while reading or writing Server_Settings, THEN THE Wrapper SHALL log the error and inform the user through the Management_Interface without terminating.
4. THE Wrapper SHALL log the following state transitions to a log file: server started, server stopped, server crashed, player connected, player disconnected, idle timer started, idle timer expired, and errors encountered. Each log entry SHALL include a timestamp and a description of the event.
5. IF the Wrapper encounters an unhandled exception in its own operation, THEN THE Wrapper SHALL log the exception and continue running without terminating.
6. IF the log file exceeds 10 MB, THEN THE Wrapper SHALL rotate the log file by renaming the current file and starting a new one, retaining a maximum of 3 rotated log files.
