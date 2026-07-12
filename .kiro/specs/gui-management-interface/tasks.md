# Implementation Plan: GUI Management Interface

## Overview

This plan implements a tkinter-based GUI management interface for the Palworld Dedicated Server Wrapper. The implementation proceeds incrementally: first extracting shared validation logic, then building the GUI components (control panel, status display, settings view/editor, help dialog, notification bar), modifying the entry point for interface selection, and finally wiring everything together with async integration and property-based tests.

## Tasks

- [x] 1. Extract shared validation logic into `src/validation.py`
  - [x] 1.1 Create `src/validation.py` with extracted validation functions
    - Extract `CorrectionResult` dataclass from `src/management_interface.py`
    - Extract `_validate_and_correct`, `_correct_string`, `_correct_boolean`, `_validate_integer`, `_validate_float`, `_validate_enum` as standalone functions (not methods)
    - The public API: `validate_and_correct(key: str, value: str) -> CorrectionResult | str` that looks up `SETTING_DEFINITIONS` internally
    - Include `PASSWORD_MASK` constant and `is_password_setting(key: str) -> bool` helper
    - _Requirements: 6.2, 6.4, 6.9_

  - [x] 1.2 Refactor `src/management_interface.py` to use `src/validation.py`
    - Replace inline validation methods with imports from `src/validation.py`
    - Remove `CorrectionResult` class and `PASSWORD_MASK` constant from this file
    - Remove `_validate_and_correct`, `_correct_string`, `_correct_boolean`, `_validate_integer`, `_validate_float`, `_validate_enum` methods
    - Import and call `validate_and_correct()` and `is_password_setting()` from `src/validation.py`
    - Ensure all existing unit tests still pass after refactoring
    - _Requirements: 6.2_

  - [x]* 1.3 Write property test for validation round-trip parity
    - **Property 3: Settings validation round-trip parity**
    - **Validates: Requirements 6.2, 6.4, 6.9**
    - Generate random (key, value) pairs including defined settings with various types
    - Verify `validate_and_correct()` from `src/validation.py` produces identical results whether called directly or via the console interface's original logic

- [x] 2. Implement core GUI framework and control panel
  - [x] 2.1 Create `src/gui_interface.py` with `GuiInterface` class skeleton and async loop
    - Implement `GuiInterface.__init__()` that creates `tk.Tk()` root window (title "Palworld Server Wrapper", minsize 800x600)
    - Implement `async run()` method with cooperative scheduling loop (`root.update()` every ~33ms)
    - Handle `TclError` on init: log error, exit with code 1
    - Implement `_shutdown()` method with 30-second timeout using `asyncio.wait_for()`
    - Wrap `root.update()` in try/except for graceful handling of window destruction
    - _Requirements: 2.1, 2.4, 2.6, 8.2, 8.5, 8.6, 9.1, 9.4_

  - [x] 2.2 Implement `ControlPanel` widget class
    - Create `ControlPanel(ttk.LabelFrame)` with "Server Control" label
    - Add "Start Server", "Stop Server", "Restart Server" buttons
    - Implement `update_button_states(state: ServerState)` with correct enable/disable logic per state
    - Implement `set_loading(loading: bool)` to show/hide loading indicator and disable all buttons
    - Wire button callbacks to `GuiInterface._execute_server_operation()`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.9_

  - [x]* 2.3 Write property test for button state consistency
    - **Property 1: Button state consistency with server state**
    - **Validates: Requirements 3.4, 3.5, 3.6**
    - Generate random `ServerState` values; verify `update_button_states()` produces correct enabled/disabled mapping

  - [x] 2.4 Implement `NotificationBar` widget class
    - Create `NotificationBar(ttk.Frame)` at the bottom of the main window
    - Implement `show_success(message)` with auto-dismiss after 5 seconds via `root.after()`
    - Implement `show_error(message)` that persists until user dismisses
    - Implement `dismiss()` method and dismiss button [×]
    - _Requirements: 3.7, 3.8_

  - [x] 2.5 Implement `_execute_server_operation()` async method
    - Create asyncio task for the requested operation (start/stop/restart)
    - Set `operation_in_progress = True`, call `set_loading(True)` on control panel
    - On completion: show success/error notification, refresh button states
    - Ensure GUI remains responsive during operation (non-blocking)
    - _Requirements: 3.7, 3.8, 3.9, 9.2_

- [x] 3. Checkpoint - Verify core framework
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement status display and settings view
  - [x] 4.1 Implement `StatusDisplay` widget class
    - Create `StatusDisplay(ttk.LabelFrame)` with "Server Status" label
    - Show fields: State (uppercase), Player Count, Idle Timer, Server PID (conditional), Uptime (conditional)
    - Implement `update_status(status: WrapperStatus)` to refresh all fields
    - Omit PID field when `server_pid is None`; omit Uptime field when `uptime_seconds is None`
    - Format idle timer as "{elapsed}s elapsed ({threshold}s threshold)" when active, "Not active" when inactive
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [x] 4.2 Implement periodic status refresh scheduling
    - Call `_wrapper_core.get_status()` every 1 second via `root.after()` or asyncio scheduling
    - Update `StatusDisplay` and `ControlPanel` button states on each refresh
    - _Requirements: 4.9_

  - [x]* 4.3 Write property test for status display field presence
    - **Property 4: Status display field presence based on WrapperStatus**
    - **Validates: Requirements 4.5, 4.6, 4.7, 4.8**
    - Generate random `WrapperStatus` instances with None/non-None values for pid/uptime; verify field presence logic

  - [x]* 4.4 Write property test for idle timer display format
    - **Property 5: Idle timer display format correctness**
    - **Validates: Requirements 4.3, 4.4**
    - Generate random `WrapperStatus` with `idle_timer_active` True/False and random seconds; verify format string

  - [x] 4.5 Implement `SettingsView` widget class
    - Create `SettingsView(ttk.LabelFrame)` with "Server Settings" label
    - Display all settings sorted alphabetically in "Key = Value" format
    - Mask values for keys containing "Password" (case-sensitive) with "********"
    - Handle `__error__` key: display error message, no setting rows
    - Handle empty dict: display "No settings found in configuration file."
    - Add "Refresh" button that re-reads settings via `SettingsParser`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x]* 4.6 Write property test for password masking
    - **Property 2: Password masking in settings display**
    - **Validates: Requirements 5.2**
    - Generate random settings dicts with keys containing/not-containing "Password"; verify masking logic

  - [x]* 4.7 Write property test for settings alphabetical ordering
    - **Property 7: Settings display alphabetical ordering**
    - **Validates: Requirements 5.1**
    - Generate random non-error settings dicts; verify output is sorted alphabetically by key

- [x] 5. Checkpoint - Verify status and settings display
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement settings editor and help dialog
  - [x] 6.1 Implement `SettingsEditor` widget class
    - Create `SettingsEditor(ttk.LabelFrame)` with "Modify Setting" label
    - Add Key input field (max 128 chars) and Value input field (max 1024 chars)
    - Add "Apply" button triggering `_on_submit()`
    - Validate using `validate_and_correct()` from `src/validation.py`
    - Display auto-correction feedback (original → corrected) when applicable
    - Display validation error messages without writing to file
    - On success: show confirmation, refresh `SettingsView`, warn if server is RUNNING
    - Handle unknown keys: write as raw string without type validation
    - Handle file system errors gracefully
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9_

  - [x] 6.2 Implement `HelpDialog` class
    - Create `HelpDialog(tk.Toplevel)` as a modal dialog
    - Include descriptions for: Start/Stop/Restart buttons, all Status_Display fields, Settings_View, Settings_Editor workflow, Quit button
    - Add scrollable text area for content
    - Add "Close" button to dismiss without affecting server state
    - Handle resource loading failure with error message
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 6.3 Implement shutdown controls (Quit button and window close)
    - Add "Quit" button to the main window that invokes `_shutdown()`
    - Bind `WM_DELETE_WINDOW` protocol to `_shutdown()`
    - During shutdown: disable all controls, show "Shutting down..." status
    - Wait up to 30 seconds for `WrapperCore.quit()` to complete
    - Force-close and log warning on timeout; log error and close on exception
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 7. Modify `src/main.py` for interface selection
  - [x] 7.1 Add `--interface` argument and interface selector logic
    - Add `--interface` argument with default "gui", choices ["gui", "console"]
    - Implement case-insensitive type function for the argument
    - Invalid values: argparse exits with code 2 and error message to stderr
    - Modify `run_wrapper()` to accept `interface_mode` parameter
    - If "gui": import and instantiate `GuiInterface`; if "console": use existing `ManagementInterface`
    - If GUI mode fails to initialize (TclError): log error to stderr, exit with code 1
    - Ensure `--interface` is independent of all other arguments
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [x]* 7.2 Write property test for interface selector argument normalization
    - **Property 6: Interface selector argument normalization**
    - **Validates: Requirements 1.1, 1.5**
    - Generate random case variations of "gui"/"console" and random invalid strings; verify acceptance/rejection

- [x] 8. Integration wiring and final assembly
  - [x] 8.1 Wire all GUI components together in `GuiInterface._build_ui()`
    - Instantiate and layout: ControlPanel, StatusDisplay, SettingsView, SettingsEditor, Help/Quit buttons, NotificationBar
    - Use labeled frames (`ttk.LabelFrame`) for visual grouping per Requirement 2.2
    - Set up callbacks between components (e.g., SettingsEditor → SettingsView refresh)
    - Connect Help button to `HelpDialog`, Quit button to `_shutdown()`
    - Ensure minimum window size 800×600 pixels
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 10.1, 10.2, 10.3_

  - [x]* 8.2 Write unit tests for GUI initialization and shutdown
    - Test that `GuiInterface.__init__()` raises `RuntimeError` when display unavailable
    - Test shutdown sequence handles timeout correctly
    - Test shutdown sequence handles WrapperCore exception correctly
    - Test window close event triggers shutdown
    - _Requirements: 2.6, 8.2, 8.3, 8.5, 8.6_

  - [x]* 8.3 Write integration tests for async loop cooperation
    - Verify cooperative async loop doesn't block WrapperCore operations (50ms constraint)
    - Verify settings modification end-to-end: edit → validate → write → refresh view
    - _Requirements: 9.1, 9.2, 9.3_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Update project documentation
  - [x] 10.1 Update `README.md` to document the new GUI interface
    - Add a section describing the GUI management interface and its features
    - Document the `--interface gui|console` command-line flag (GUI is the default)
    - Explain that the console interface remains available as a secondary mode
    - Update any existing usage/quickstart instructions to reflect the new default behavior
    - Add a note about the tkinter requirement (Python stdlib, no additional install needed)
  - [x] 10.2 Update `.kiro/steering/` files if applicable
    - Review existing steering files for any references to the console-only interface that need updating
    - Add or update any project conventions related to the new GUI module (e.g., widget naming patterns, async integration patterns)
    - Ensure steering files reflect the dual-interface architecture (GUI primary, console secondary)

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The design uses tkinter (Python stdlib) so no additional dependencies are needed
- The cooperative async pattern (`root.update()` every ~33ms) is critical for non-blocking integration with asyncio
- All validation logic is shared between GUI and console via `src/validation.py`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["2.1", "2.4"] },
    { "id": 3, "tasks": ["2.2", "2.5", "4.1", "4.5"] },
    { "id": 4, "tasks": ["2.3", "4.2", "4.3", "4.4", "4.6", "4.7"] },
    { "id": 5, "tasks": ["6.1", "6.2", "6.3"] },
    { "id": 6, "tasks": ["7.1"] },
    { "id": 7, "tasks": ["7.2", "8.1"] },
    { "id": 8, "tasks": ["8.2", "8.3"] },
    { "id": 9, "tasks": ["10.1", "10.2"] }
  ]
}
```
