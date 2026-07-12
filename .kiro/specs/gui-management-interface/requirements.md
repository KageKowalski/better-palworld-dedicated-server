# Requirements Document

## Introduction

This document specifies the requirements for a GUI-based management interface for the Palworld Dedicated Server Wrapper. The GUI replaces the existing console/CLI interface as the primary method for interacting with the wrapper while retaining the console interface as a secondary fallback mode. The GUI must replicate all current console functionality in a visually comfortable format while remaining lightweight to minimize resource consumption on the host machine.

## Glossary

- **GUI_Interface**: The graphical user interface window that provides visual controls and status displays for managing the Palworld Dedicated Server Wrapper.
- **Console_Interface**: The existing CLI-based management interface (ManagementInterface class) that reads commands from stdin and prints to stdout.
- **WrapperCore**: The central state machine coordinator that manages server lifecycle, player monitoring, idle timers, and maintenance cycles.
- **Interface_Selector**: The command-line argument parser logic that determines which interface mode (GUI or Console) to launch at startup.
- **Server_Control_Panel**: The section of the GUI_Interface that provides buttons for starting, stopping, and restarting the Dedicated Server.
- **Status_Display**: The section of the GUI_Interface that shows real-time server state, player count, idle timer, server PID, and uptime.
- **Settings_View**: The section of the GUI_Interface that displays all current server settings from PalWorldSettings.ini with password masking.
- **Settings_Editor**: The section of the GUI_Interface that allows modifying individual server settings with type validation and auto-correction feedback.
- **ServerState**: An enumeration representing the server lifecycle states: MONITORING, STARTING, RUNNING, STOPPING.
- **WrapperConfig**: The dataclass holding all configurable parameters for the wrapper including paths, ports, timing thresholds, and logging settings.

## Requirements

### Requirement 1: Interface Mode Selection

**User Story:** As a server administrator, I want to choose between a GUI or console interface at launch, so that I can use whichever mode suits my environment.

#### Acceptance Criteria

1. THE Interface_Selector SHALL accept a `--interface` command-line argument with allowed values `gui` and `console` (case-insensitive matching, e.g., `GUI`, `Console`, and `gui` are all accepted).
2. WHEN the `--interface` argument is omitted, THE Interface_Selector SHALL default to launching the GUI_Interface.
3. WHEN `--interface console` is specified, THE Interface_Selector SHALL launch the Console_Interface.
4. WHEN `--interface gui` is specified, THE Interface_Selector SHALL launch the GUI_Interface.
5. IF an invalid value is provided for `--interface`, THEN THE Interface_Selector SHALL display an error message indicating the valid options (`gui`, `console`) to stderr and exit with status code 2.
6. IF `gui` is selected (explicitly or by default) and the GUI environment is unavailable, THEN THE Interface_Selector SHALL display an error message indicating that the GUI cannot be initialized to stderr and exit with status code 1.
7. THE Interface_Selector SHALL resolve the `--interface` argument independently of all other command-line arguments, so that existing arguments (such as `--server-exe`, `--rcon-port`) continue to function without modification.

### Requirement 2: GUI Window and Layout

**User Story:** As a server administrator, I want a simple, organized GUI window, so that I can quickly find and use server management controls.

#### Acceptance Criteria

1. THE GUI_Interface SHALL display a single application window with the title "Palworld Server Wrapper" and a minimum size of 800×600 pixels.
2. THE GUI_Interface SHALL organize controls into visually separated sections using labeled borders or equivalent grouping widgets, containing: Server_Control_Panel, Status_Display, Settings_View, and Settings_Editor, where each section label is visible to the user.
3. THE GUI_Interface SHALL use a lightweight GUI toolkit that adds less than 50 MB additional RAM beyond the console-only baseline.
4. WHILE a long-running server operation is in progress, THE GUI_Interface SHALL continue processing user input events such that any button click or keyboard input receives a visual acknowledgment (e.g., button press animation, cursor change, or status text update) within 2 seconds.
5. WHEN the GUI_Interface window is closed by the user, THE GUI_Interface SHALL initiate the same shutdown sequence as the `quit` console command.
6. IF the GUI toolkit fails to initialize (e.g., no display environment available), THEN THE GUI_Interface SHALL log an error message indicating the failure reason and exit with a non-zero exit code within 5 seconds.

### Requirement 3: Server Control Operations

**User Story:** As a server administrator, I want buttons to start, stop, and restart the server, so that I can manage the server lifecycle without typing commands.

#### Acceptance Criteria

1. THE Server_Control_Panel SHALL provide a "Start Server" button that invokes WrapperCore.start_server().
2. THE Server_Control_Panel SHALL provide a "Stop Server" button that invokes WrapperCore.stop_server().
3. THE Server_Control_Panel SHALL provide a "Restart Server" button that invokes WrapperCore.restart_server().
4. WHILE the server is in MONITORING state, THE Server_Control_Panel SHALL enable the "Start Server" and "Restart Server" buttons and disable the "Stop Server" button.
5. WHILE the server is in RUNNING state, THE Server_Control_Panel SHALL enable the "Stop Server" and "Restart Server" buttons and disable the "Start Server" button.
6. WHILE the server is in STARTING or STOPPING state, THE Server_Control_Panel SHALL disable all server control buttons and display a loading indicator until the state transitions to MONITORING or RUNNING.
7. WHEN a server control operation completes with a success result (success=True), THE GUI_Interface SHALL display a success notification for a minimum of 5 seconds or until the user dismisses it.
8. IF a server control operation returns a failure result (success=False), THEN THE GUI_Interface SHALL display an error notification containing the error_message field value, and the notification SHALL remain visible until the user dismisses it.
9. WHILE a server control operation is executing, THE GUI_Interface SHALL remain responsive to user interaction within 200 milliseconds of input.

### Requirement 4: Real-Time Status Display

**User Story:** As a server administrator, I want to see the current server status at a glance, so that I can monitor server health without issuing commands.

#### Acceptance Criteria

1. THE Status_Display SHALL show the current ServerState value (MONITORING, STARTING, RUNNING, STOPPING) in uppercase text.
2. THE Status_Display SHALL show the current connected player count as an integer greater than or equal to zero.
3. WHILE the idle timer is active, THE Status_Display SHALL show the elapsed idle seconds and the configured idle timeout threshold in the format "{elapsed}s elapsed ({threshold}s threshold)".
4. WHILE the idle timer is not active, THE Status_Display SHALL display "Not active" for the idle timer field.
5. WHILE the server process is running and server_pid is available, THE Status_Display SHALL show the server process PID as an integer.
6. IF the server process PID is not available, THEN THE Status_Display SHALL omit the server PID field from the output.
7. WHILE uptime_seconds is available (not None), THE Status_Display SHALL show the server uptime as an integer number of seconds.
8. IF uptime_seconds is not available, THEN THE Status_Display SHALL omit the uptime field from the output.
9. THE Status_Display SHALL refresh automatically at an interval between 500 milliseconds and 2 seconds to reflect the current WrapperCore state.

### Requirement 5: Server Settings Display

**User Story:** As a server administrator, I want to view all server settings in the GUI, so that I can review configuration without opening the settings file manually.

#### Acceptance Criteria

1. THE Settings_View SHALL display all key-value pairs read from PalWorldSettings.ini sorted alphabetically by key name, rendering each entry in "Key = Value" format.
2. WHEN a setting key contains the substring "Password" (case-sensitive), THE Settings_View SHALL display the value as "********" instead of the actual value.
3. IF the settings file cannot be read (SettingsParser returns a dict containing the "__error__" key), THEN THE Settings_View SHALL display the error message from the "__error__" value and SHALL NOT display any key-value setting rows.
4. THE Settings_View SHALL provide a refresh control that, when activated, re-reads PalWorldSettings.ini via SettingsParser and replaces the displayed settings list with the newly read data.
5. IF SettingsParser returns an empty dict with no "__error__" key, THEN THE Settings_View SHALL display an informational message indicating that no settings were found in the configuration file.

### Requirement 6: Server Settings Modification

**User Story:** As a server administrator, I want to modify server settings through the GUI with validation feedback, so that I can change configuration safely without editing files manually.

#### Acceptance Criteria

1. THE Settings_Editor SHALL provide input fields for specifying the setting key and the new value, where the setting key is a non-empty string of up to 128 characters and the value is a string of up to 1024 characters.
2. WHEN the user submits a setting modification, THE Settings_Editor SHALL validate and auto-correct the input using the same type-aware logic as the Console_Interface (boolean normalization to True/False, integer range checking against min_value/max_value, float range checking against min_value/max_value, enum validation against the allowed_values list, string quote stripping when the value is wrapped in double quotes).
3. WHEN auto-correction is applied, THE Settings_Editor SHALL display both the original input and the corrected value to the user before writing to the settings file.
4. IF validation fails for the submitted value, THEN THE Settings_Editor SHALL display a validation error message indicating the reason for failure (type mismatch, out-of-range value, or disallowed enum value) without writing to the settings file.
5. WHEN a setting is successfully written, THE Settings_Editor SHALL display a confirmation message including the setting key and the written value.
6. WHILE the server is in RUNNING state, WHEN a setting is successfully modified, THE Settings_Editor SHALL display a warning indicating that a server restart is required for the change to take effect.
7. WHEN a setting is successfully written, THE Settings_View SHALL update to reflect the new value within the same user action (no manual refresh required).
8. IF the settings file cannot be read or written due to a file system error, THEN THE Settings_Editor SHALL display an error message indicating the file operation failure without modifying any data.
9. WHEN the user submits a setting key that is not present in the known SETTING_DEFINITIONS, THE Settings_Editor SHALL write the value as a raw string without applying type-aware validation or auto-correction.

### Requirement 7: Help and Documentation Display

**User Story:** As a server administrator, I want to access help information within the GUI, so that I can understand available features without consulting external documentation.

#### Acceptance Criteria

1. THE GUI_Interface SHALL provide a clearly labeled "Help" button that, when activated, opens a help dialog or section displaying feature documentation.
2. THE GUI_Interface help content SHALL include a description for each server control button (Start Server, Stop Server, Restart Server), each Status_Display field (server state, player count, idle timer, server PID, uptime), the Settings_View section, the Settings_Editor workflow (specifying a key, entering a value, and the auto-correction behavior), and the Quit button.
3. WHEN the help dialog or section is open, THE GUI_Interface SHALL allow the user to dismiss it and return to the main interface without affecting server state.
4. IF the help content cannot be displayed due to a resource loading failure, THEN THE GUI_Interface SHALL display an error message indicating that help content is unavailable.

### Requirement 8: Shutdown and Cleanup

**User Story:** As a server administrator, I want the GUI to shut down the wrapper cleanly, so that the server state is preserved and no resources leak.

#### Acceptance Criteria

1. THE GUI_Interface SHALL provide a "Quit" button that initiates wrapper shutdown.
2. WHEN the "Quit" button is pressed, THE GUI_Interface SHALL invoke WrapperCore.quit(), wait for the cleanup sequence to complete (up to a maximum of 30 seconds), and then close the application window.
3. WHEN the operating system window close event is received, THE GUI_Interface SHALL perform the same shutdown sequence as the "Quit" button.
4. WHILE a shutdown is in progress, THE GUI_Interface SHALL disable all interactive control buttons (Start, Stop, Restart, Quit, and settings modification controls) and display a status indication that shutdown is in progress.
5. IF the cleanup sequence does not complete within 30 seconds, THEN THE GUI_Interface SHALL force-close the application window and log a warning indicating the cleanup timed out.
6. IF WrapperCore.quit() raises an exception during shutdown, THEN THE GUI_Interface SHALL log the error and close the application window without leaving the window in a stuck state.

### Requirement 9: Async Integration

**User Story:** As a developer, I want the GUI to integrate with the existing asyncio event loop, so that the GUI does not block WrapperCore operations or background tasks.

#### Acceptance Criteria

1. THE GUI_Interface SHALL run its event loop concurrently with the asyncio event loop used by WrapperCore such that neither loop is blocked for more than 50 milliseconds at a time.
2. WHILE a WrapperCore operation (start_server, stop_server, restart_server) is in progress, THE GUI_Interface SHALL remain responsive to user input within 200 milliseconds.
3. WHILE the GUI_Interface is active, THE WrapperCore background tasks (RCON polling, idle timer, maintenance timer, connection listener) SHALL continue executing within their configured intervals (e.g., RCON polls within ±1 second of rcon_poll_interval_seconds).
4. IF an unhandled exception occurs within the GUI_Interface event loop, THEN THE asyncio event loop and WrapperCore SHALL continue operating without termination, and the error SHALL be logged.
5. WHEN the GUI_Interface window is closed by the user, THE GUI_Interface SHALL invoke WrapperCore.quit() to initiate a graceful shutdown of the wrapper.

### Requirement 10: Lightweight Resource Usage

**User Story:** As a server administrator, I want the GUI to use minimal system resources, so that the wrapper remains lightweight as originally designed.

#### Acceptance Criteria

1. THE GUI_Interface SHALL use a GUI toolkit that is either part of the Python standard library or adds no more than one additional third-party package to the project's dependencies.
2. WHILE the GUI_Interface is in steady-state operation (at least 30 seconds after window initialization, with no active user interaction), THE GUI_Interface SHALL consume less than 50 MB of additional RAM compared to the console-only mode baseline measured under the same server state.
3. WHILE the GUI_Interface is in steady-state operation (at least 30 seconds after window initialization, with no active user interaction), THE GUI_Interface SHALL consume less than 5% additional CPU averaged over a 60-second measurement window compared to the console-only mode baseline measured under the same server state.
