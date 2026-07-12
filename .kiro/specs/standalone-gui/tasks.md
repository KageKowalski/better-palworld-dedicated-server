# Implementation Plan: Standalone GUI

## Overview

This plan implements console detachment for the GUI mode, allowing the Palworld Server Wrapper GUI to operate independently of the launching PowerShell console. It covers the launcher module, logging enhancements, GUI output panel, CTRL_CLOSE_EVENT handling, and integration of all components into the existing entry point.

## Tasks

- [x] 1. Create the Launcher Module
  - [x] 1.1 Create `src/launcher.py` with core detachment functions
    - Implement `should_detach(interface_mode, is_detached)` that returns True only when interface_mode == "gui" AND is_detached == False AND has_attached_console() == True AND sys.platform == "win32"
    - Implement `has_attached_console()` using ctypes to call kernel32.GetConsoleWindow() on Windows, returning False on non-Windows
    - Implement `resolve_pythonw()` that looks for pythonw.exe in the parent directory of sys.executable, returns Path or None
    - Implement `detach_and_respawn(original_argv)` that constructs the command line with all original args plus --detached, uses pythonw.exe if available (fallback to sys.executable), creates process with CREATE_NO_WINDOW | DETACHED_PROCESS flags, stdin/stdout/stderr set to subprocess.DEVNULL, returns exit code 0 on success or 1 on failure
    - Implement `install_ctrl_close_handler()` that sets signal.signal(signal.SIGBREAK, signal.SIG_IGN) on Windows (no-op on other platforms)
    - _Requirements: 1.1, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 5.4, 6.4_

  - [ ]* 1.2 Write property tests for launcher decision logic
    - **Property 1: Detachment decision correctness**
    - Generate all combinations of (interface_mode in ["gui", "console"], is_detached in [True, False], has_console in [True, False], platform in ["win32", "linux", "darwin"]) and verify should_detach() returns True iff all four conditions hold
    - **Validates: Requirements 1.1, 1.3, 2.5, 6.2, 6.4, 6.6**

  - [ ]* 1.3 Write property tests for argument forwarding
    - **Property 2: Argument forwarding preservation**
    - Generate arbitrary argument lists (strings without --detached) and verify detach_and_respawn() constructs a command containing all original arguments plus exactly one --detached flag
    - **Validates: Requirements 1.4, 6.1**

  - [ ]* 1.4 Write property tests for interpreter resolution
    - **Property 3: Interpreter resolution fallback**
    - Generate filesystem states (pythonw.exe exists / doesn't exist in sys.executable's directory) and verify resolve_pythonw() returns correct Path or None
    - **Validates: Requirements 2.2, 2.3**

- [x] 2. Enhance the Logging System
  - [x] 2.1 Add `GuiLogHandler` class and enhance `WrapperLogger` in `src/logger.py`
    - Create `GuiLogHandler(logging.Handler)` class that accepts a callback function, filters at INFO level, formats records and invokes the callback
    - Add `add_console_handler()` method to WrapperLogger that creates a StreamHandler(stdout) at INFO level
    - Add `add_gui_handler(callback)` method to WrapperLogger that creates and attaches a GuiLogHandler
    - Modify `setup()` to accept a `mode` parameter ("console" or "gui") and optional `gui_callback` — adds console handler for console mode, GUI handler for gui mode, neither writes to stdout in GUI mode
    - Handle log file open errors gracefully: catch exceptions during handler setup, continue without file logging
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ]* 2.2 Write property tests for logging mode exclusivity
    - **Property 5: Logging mode exclusivity**
    - Generate mode selections ("gui" / "console") and verify that in GUI mode no StreamHandler(stdout) is present and in console mode no GuiLogHandler is present, and in both modes a RotatingFileHandler is present
    - **Validates: Requirements 4.1, 4.2, 4.4**

  - [ ]* 2.3 Write unit tests for GuiLogHandler
    - Test that messages at INFO and above are forwarded to the callback
    - Test that DEBUG messages are not forwarded
    - Test that exceptions in the callback are handled gracefully (handleError)
    - _Requirements: 4.3_

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Add the GUI Output Panel
  - [x] 4.1 Create `OutputPanel` class in `src/gui_interface.py`
    - Implement as a ttk.LabelFrame with text="Output"
    - Create a scrollable read-only Text widget with vertical scrollbar
    - Implement `append_message(message)` that inserts text, auto-scrolls to bottom, and trims lines exceeding MAX_LINES (1000)
    - Implement `clear()` method to clear all content
    - Use `root.after()` for thread-safe append from logging handler
    - _Requirements: 4.3, 3.2_

  - [ ]* 4.2 Write property tests for OutputPanel line cap
    - **Property 4: GUI output panel line cap**
    - Generate sequences of N messages where N > MAX_LINES and verify the panel never contains more than MAX_LINES lines
    - **Validates: Requirements 4.3**

  - [x] 4.3 Integrate OutputPanel into GuiInterface layout
    - Add OutputPanel between StatusDisplay and SettingsView in `_build_ui()`
    - Wire `append_message` as the `gui_callback` for `WrapperLogger.add_gui_handler()`
    - Ensure OutputPanel gets `fill="both", expand=True` for vertical space sharing with SettingsView
    - _Requirements: 4.3, 3.2_

- [x] 5. Integrate Launcher into Entry Point
  - [x] 5.1 Modify `src/main.py` to support detachment flow
    - Add `--detached` argument with `action="store_true"`, `default=False`, `help=argparse.SUPPRESS`
    - Import launcher module
    - After parse_args and build_config: if `launcher.should_detach(args.interface, args.detached)` returns True, call `launcher.detach_and_respawn(sys.argv)` and sys.exit with the result
    - Modify `run_wrapper()` signature to accept `is_detached` parameter
    - When `is_detached=True`, call `launcher.install_ctrl_close_handler()`
    - Pass interface mode to WrapperLogger setup (mode="gui" or "console") with gui_callback wired to OutputPanel
    - _Requirements: 1.1, 1.3, 5.4, 6.1, 6.2, 6.3_

  - [x] 5.2 Configure logging based on interface mode in `run_wrapper()`
    - Instantiate WrapperLogger and call setup with mode=interface_mode
    - For GUI mode: create OutputPanel first, then pass its append_message as gui_callback
    - For console mode: add console handler for stdout output
    - Handle log file open errors: report via stderr (console) or notification bar (GUI) and continue
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Wire Shutdown and Final Integration
  - [x] 7.1 Ensure graceful shutdown handles detached process correctly
    - Verify `_shutdown()` in GuiInterface disables all controls, shows "Shutting down..." in notification bar, calls WrapperCore.quit() with 30s timeout, destroys window
    - Ensure that when server is in MONITORING state, shutdown skips server stop and completes within 5 seconds
    - Verify that the entire server process tree is terminated (WrapperCore already handles taskkill /F /T)
    - _Requirements: 5.1, 5.2, 5.3, 5.5_

  - [x] 7.2 Add display environment detection for spawn failure
    - In `detach_and_respawn()`, after spawning, optionally verify the process started (poll for process existence within a short window)
    - If the spawned process exits immediately (e.g., TclError due to no display), the launcher reports the error and exits with code 1
    - _Requirements: 1.7, 6.5_

  - [ ]* 7.3 Write unit tests for integrated launcher flow
    - Test that main() with --interface gui triggers detach_and_respawn when has_console is True and platform is win32
    - Test that main() with --interface gui --detached skips re-spawn and proceeds to GUI init
    - Test that main() with --interface console never calls detach_and_respawn
    - Test that --detached does not appear in --help output (argparse.SUPPRESS)
    - _Requirements: 1.1, 1.3, 6.2, 6.3_

  - [ ]* 7.4 Write integration tests for shutdown flow
    - Test graceful shutdown when server is RUNNING (stop + cleanup + destroy within 30s)
    - Test quick shutdown when server is MONITORING (cleanup + destroy within 5s)
    - Test shutdown timeout behavior (force-destroy after 30s)
    - _Requirements: 5.1, 5.2, 5.5_

- [x] 8. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Update Documentation
  - [x] 9.1 Update `README.md` to document standalone GUI behavior
    - Add a section or update existing GUI mode documentation to explain that when launched in GUI mode, the PowerShell console is no longer required to remain open
    - Document any new flags or behaviors users should be aware of (e.g., the `--detached` flag is internal/hidden, but the user-visible behavior change should be described)
    - Clarify that the GUI window operates independently after launch and closing the originating console will not terminate the server
    - _Requirements: 1.1, 1.3, 6.2_

  - [x] 9.2 Update `.kiro/` directory documentation if applicable
    - Review and update any relevant steering files or specs documentation in the `.kiro/` directory to reflect the standalone GUI feature
    - Ensure spec documentation accurately describes the final implemented behavior
    - _Requirements: 1.1_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The design uses Python throughout, so all implementations use Python with type hints
- The existing `gui_interface.py` already implements most GUI widgets; this feature adds the OutputPanel and launcher integration
- CTRL_CLOSE_EVENT handling is Windows-specific; other platforms are no-ops

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "2.2", "2.3", "4.1"] },
    { "id": 2, "tasks": ["4.2", "4.3"] },
    { "id": 3, "tasks": ["5.1", "5.2"] },
    { "id": 4, "tasks": ["7.1", "7.2"] },
    { "id": 5, "tasks": ["7.3", "7.4"] },
    { "id": 6, "tasks": ["9.1", "9.2"] }
  ]
}
```
