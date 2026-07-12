# Requirements Document

## Introduction

The Palworld Server Wrapper currently requires the launching PowerShell console window to remain open for the GUI application to continue running. This is because on Windows, a Python process launched from a console is attached to that console; closing the console sends a CTRL_CLOSE_EVENT that terminates all attached processes.

This feature makes the GUI mode fully standalone — once launched, the GUI window operates independently of the PowerShell console that spawned it. The console can be closed without affecting the running GUI application. Console mode remains unchanged, and full functional parity between the two interface modes is maintained.

## Glossary

- **Wrapper**: The Palworld Server Wrapper application that manages the lifecycle of a Palworld Dedicated Server process.
- **Launcher**: A thin entry point script or mechanism responsible for re-spawning the Wrapper process in a console-detached state when GUI mode is selected.
- **GUI_Process**: The detached child process running the Wrapper with the tkinter-based graphical interface, independent of any console window.
- **Console_Mode**: The interface mode where the Wrapper uses stdin/stdout via a PowerShell console for user interaction.
- **GUI_Mode**: The interface mode where the Wrapper uses a tkinter window for user interaction, intended to operate without a visible console.
- **Console_Detachment**: The act of freeing a Windows process from its parent console so that closing the console does not terminate the process.
- **CREATE_NO_WINDOW**: A Windows process creation flag (0x08000000) that prevents a new console window from being allocated for a subprocess.
- **DETACHED_PROCESS**: A Windows process creation flag (0x00000008) that detaches a new process from the calling process's console.
- **pythonw_exe**: The Windows Python interpreter (`pythonw.exe`) that does not allocate a console window, suitable for GUI-only applications.

## Requirements

### Requirement 1: Console Detachment for GUI Mode

**User Story:** As a user, I want the GUI window to remain running after I close the PowerShell console that launched it, so that I do not need to keep an extra console window open.

#### Acceptance Criteria

1. WHEN the Wrapper is launched with `--interface gui`, THE Launcher SHALL re-spawn the Wrapper as a GUI_Process that has no associated console window and whose lifetime is independent of the launching console session.
2. IF the parent console window is closed while the GUI_Process is running, THEN THE GUI_Process SHALL continue operating with its GUI window visible and all server management functions intact.
3. WHEN the Wrapper is launched with `--interface console`, THE Launcher SHALL NOT perform Console_Detachment and SHALL run the Wrapper in the current console as before.
4. THE Launcher SHALL pass all command-line arguments from the original invocation to the GUI_Process without modification.
5. WHEN the GUI_Process is successfully created as an operating-system process, THE Launcher SHALL exit with code 0 within 5 seconds of spawning the GUI_Process.
6. IF the GUI_Process fails to spawn, THEN THE Launcher SHALL print an error message indicating the failure reason to stderr and exit with exit code 1.
7. IF the GUI_Process is spawned with `--interface gui` but no display environment is available, THEN THE Launcher SHALL treat the spawn as a failure, print an error message indicating the missing display to stderr, and exit with exit code 1.

### Requirement 2: Process Creation Mechanism

**User Story:** As a developer, I want the detachment mechanism to use well-defined Windows process creation flags, so that the solution is reliable and maintainable.

#### Acceptance Criteria

1. WHILE running on Windows, THE Launcher SHALL create the GUI_Process using `subprocess.Popen` with the `CREATE_NO_WINDOW` and `DETACHED_PROCESS` creation flags combined via bitwise OR in the `creationflags` parameter.
2. THE Launcher SHALL resolve `pythonw_exe` by looking for a file named `pythonw.exe` in the parent directory of `sys.executable` and SHALL use it as the interpreter for the GUI_Process to prevent any console window allocation.
3. IF `pythonw.exe` is not found in the parent directory of `sys.executable`, THEN THE Launcher SHALL fall back to `sys.executable` as the interpreter with both `CREATE_NO_WINDOW` and `DETACHED_PROCESS` creation flags applied.
4. THE Launcher SHALL set `stdin`, `stdout`, and `stderr` of the GUI_Process to `subprocess.DEVNULL` to prevent I/O errors after console detachment.
5. IF the platform is not Windows (`sys.platform != 'win32'`), THEN THE Launcher SHALL skip Console_Detachment and run the Wrapper directly in the current process.
6. IF `subprocess.Popen` raises an `OSError` during GUI_Process creation, THEN THE Launcher SHALL print an error message indicating the failure reason to stderr and exit with a non-zero exit code.

### Requirement 3: Functional Parity Between Modes

**User Story:** As a user, I want the GUI mode to support all the same features as console mode after detachment, so that I do not lose any functionality.

#### Acceptance Criteria

1. THE GUI_Process SHALL provide Start, Stop, and Restart buttons that invoke the same WrapperCore lifecycle operations (start_server, stop_server, restart_server) as the console mode commands.
2. THE GUI_Process SHALL display server status fields (state, player count, idle timer elapsed and threshold, PID when running, uptime when running) refreshed every 1000 milliseconds.
3. THE GUI_Process SHALL provide a settings view displaying all settings from PalWorldSettings.ini sorted alphabetically, and a settings editor that validates and writes modified values using the same validation logic as the console "set" command.
4. WHEN the GUI window close event is triggered, THE GUI_Process SHALL disable all controls, invoke WrapperCore.quit() with a maximum timeout of 30 seconds, and destroy the window.
5. IF a lifecycle operation (start, stop, or restart) fails, THEN THE GUI_Process SHALL display an error notification containing the error message returned by WrapperCore.
6. THE GUI_Process SHALL run the idle timer that automatically stops the server when the configured idle_timeout_seconds elapses with zero connected players, identical to the console mode behavior.
7. THE GUI_Process SHALL run RCON polling for player count updates at the configured rcon_poll_interval_seconds interval, retaining the last known player count on query failure, identical to console mode behavior.
8. THE GUI_Process SHALL run the maintenance timer cycle (broadcast warning, stop server, update via SteamCMD, restart server) at the configured maintenance_interval_seconds, identical to console mode behavior.
9. WHILE a lifecycle operation is in progress, THE GUI_Process SHALL disable all control buttons and display a loading indicator until the operation completes.

### Requirement 4: Logging Strategy

**User Story:** As a developer, I want all application output logged to a file in both modes, so that I can debug issues; and as an operator, I want operational information surfaced in my active interface (console or GUI), so that I can monitor the application without reading log files.

#### Acceptance Criteria

1. THE Wrapper SHALL write all log output (debug, informational, warning, and error messages) to the configured log file path regardless of whether it is running in Console_Mode or GUI_Mode.
2. WHILE running in Console_Mode, THE Wrapper SHALL additionally print operational-level information (server state changes, player count updates, command acknowledgements, and error summaries) to stdout to assist the operator.
3. WHILE running in GUI_Mode, THE Wrapper SHALL additionally display operational-level information (server state changes, player count updates, command acknowledgements, and error summaries) in a designated output section of the GUI window to assist the operator.
4. WHILE running in GUI_Mode, THE Wrapper SHALL NOT write log output to stdout or stderr (since no console is available after detachment).
5. IF the log file cannot be opened or written to at startup, THEN THE Wrapper SHALL report the failure through the active interface (stderr in Console_Mode, an error notification in the GUI notification bar in GUI_Mode) and SHALL continue operation without file logging.
6. IF the log file becomes unavailable during operation, THEN THE Wrapper SHALL report the failure through the active interface and SHALL continue normal server management operations without interruption.

### Requirement 5: Graceful Shutdown of Detached Process

**User Story:** As a user, I want the detached GUI to shut down cleanly when I close the window, so that the server state is preserved and no orphan processes remain.

#### Acceptance Criteria

1. WHEN the user closes the GUI window, THE GUI_Process SHALL disable all interactive controls, display a shutdown status indication, and invoke the existing graceful shutdown sequence (stop the server process if running, disconnect RCON, cancel background tasks, and release the UDP listener).
2. WHEN the graceful shutdown sequence completes or the 30-second timeout elapses (whichever comes first), THE GUI_Process SHALL destroy the GUI window and exit with code 0.
3. WHEN the GUI_Process exits, THE GUI_Process SHALL have terminated the entire server process tree (the server executable and all of its child processes) so that no orphan child processes remain.
4. IF a Windows CTRL_CLOSE_EVENT is received by the GUI_Process, THEN THE GUI_Process SHALL ignore the event and continue running (the GUI window close is the authoritative shutdown trigger).
5. IF the server is not running (state is MONITORING) when the user closes the GUI window, THEN THE GUI_Process SHALL skip the server stop step and proceed directly to cleanup and exit within 5 seconds.

### Requirement 6: Detection of Already-Detached State

**User Story:** As a developer, I want the application to detect when it is already running as a detached process, so that it does not attempt to re-detach infinitely.

#### Acceptance Criteria

1. THE Launcher SHALL pass a `--detached` flag (or equivalent internal marker such as an environment variable) to the GUI_Process to indicate it is already running in detached mode.
2. WHEN the `--detached` flag is present, THE Wrapper SHALL skip the re-spawn logic and proceed directly to GUI initialization without spawning any additional child processes.
3. THE `--detached` flag SHALL NOT appear in the `--help` output or be listed as a user-facing command-line argument in any public documentation (it is an internal implementation detail).
4. IF `--interface gui` is specified without `--detached` and the process has an attached console (determined by a platform-specific console detection check, e.g., `kernel32.GetConsoleWindow() != 0` on Windows), THEN THE Launcher SHALL perform the detach-and-respawn sequence.
5. IF the detach-and-respawn sequence is initiated but the spawned GUI_Process fails to start within 5 seconds, THEN THE Launcher SHALL NOT retry the spawn, SHALL print an error message to stderr, and SHALL exit with a non-zero exit code, preventing infinite re-spawn loops.
6. IF a user manually supplies `--detached` from the command line without the process actually being console-free, THEN THE Wrapper SHALL accept the flag and proceed to GUI initialization without performing detachment (the flag is treated as authoritative).
