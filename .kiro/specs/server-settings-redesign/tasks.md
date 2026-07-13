# Implementation Plan: Server Settings Redesign

## Overview

Consolidate the existing separate `SettingsView` and `SettingsEditor` panels into a single unified `SettingsPanel` with inline metadata display, search/filter, and per-row edit controls. Extend `SettingDefinition` with `description` and `default_value` fields, implement pure metadata formatting functions, and wire the new panel into the existing `GuiInterface` layout.

## Tasks

- [x] 1. Extend SettingDefinition and backfill metadata
  - [x] 1.1 Add `description` and `default_value` fields to the SettingDefinition dataclass
    - Add `description: str = ""` and `default_value: Any = None` fields to the dataclass in `src/settings_parser.py`
    - Update the class docstring to document the new fields
    - _Requirements: 6.1, 6.2_

  - [x] 1.2 Backfill all existing SETTING_DEFINITIONS entries with description and default_value
    - Populate `description` (10–120 chars, one sentence) and `default_value` for every entry in the `SETTING_DEFINITIONS` dict
    - Use Palworld Dedicated Server documented defaults
    - _Requirements: 6.3, 6.4, 6.5_

  - [ ]* 1.3 Write property test for setting definition metadata validity
    - **Property 8: All setting definitions have valid metadata**
    - Verify all entries have description between 10–120 chars and default_value populated for documented settings
    - **Validates: Requirements 6.3, 6.5**

- [x] 2. Implement metadata helper functions
  - [x] 2.1 Create `src/settings_helpers.py` with pure formatting functions
    - Implement `format_allowed_values(definition: SettingDefinition | None) -> str`
    - Implement `format_default_value(key: str, definition: SettingDefinition | None) -> str`
    - Implement `format_current_value(key: str, value: str | None) -> str`
    - Implement `values_differ(current: str, default: Any, definition: SettingDefinition | None) -> bool`
    - Implement `get_input_control_type(definition: SettingDefinition | None) -> str`
    - Use `is_password_setting()` from `src/validation.py` for password masking
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4_

  - [ ]* 2.2 Write property test for allowed values formatting
    - **Property 4: Allowed values formatting is deterministic and correct**
    - Test all branches: bool, numeric with min/max, allowed_values list, string, None
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

  - [ ]* 2.3 Write property test for password field masking
    - **Property 5: Password fields are always masked**
    - Test that keys containing "Password" always produce masked output for current and default values
    - **Validates: Requirements 4.3, 5.12**

  - [ ]* 2.4 Write property test for value difference detection
    - **Property 6: Value difference detection uses type-appropriate coercion**
    - Test string, int, float, bool type coercion edge cases
    - **Validates: Requirements 4.5**

  - [ ]* 2.5 Write property test for input control type selection
    - **Property 7: Input control type is determined by definition type and constraints**
    - Test combobox for bool/allowed_values, entry for everything else
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement SettingsPanel and SettingRow widgets
  - [x] 4.1 Create `src/settings_panel.py` with the `SettingsPanel` class
    - Implement as `ttk.LabelFrame` subclass replacing `SettingsView` and `SettingsEditor`
    - Include search input field (max 200 chars) with `StringVar` trace callback
    - Include scrollable canvas + frame container using the canvas-with-frame pattern
    - Include pending changes indicator (hidden when queue empty)
    - Include Refresh button that calls `SettingsParser.read_settings()` and rebuilds rows
    - Implement `refresh()` method to re-read settings and rebuild SettingRow widgets
    - Implement `filter_settings(search_text)` to show/hide rows based on case-insensitive substring match
    - Implement `update_pending_indicator()` to update the badge count
    - Display "No matching settings" message when filter returns zero results
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 7.1, 7.2, 7.3, 7.4, 7.5, 8.3, 8.4_

  - [x] 4.2 Create `SettingRow` class within `src/settings_panel.py`
    - Implement as `ttk.Frame` subclass displaying one setting key
    - Row layout: key name (bold) + description, allowed/default/current values, input control + Apply button
    - Use `get_input_control_type()` to decide between Combobox and Entry
    - Bold the current value label when it differs from default (using `values_differ()`)
    - Mask password fields in input control (`show="*"`)
    - Apply button calls `validate_and_correct()` then `SettingsWriteHandler.submit()`
    - Handle validation errors, auto-corrections, queue results, and write failures via NotificationBar
    - Update current value display on successful write
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 4.1, 4.2, 4.3, 4.5, 4.6, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.11, 5.12, 8.1, 8.2_

  - [ ]* 4.3 Write property test for sort ordering of setting rows
    - **Property 1: Setting rows are always sorted case-insensitively**
    - Generate arbitrary sets of setting keys and verify sort output
    - **Validates: Requirements 1.3, 7.4**

  - [ ]* 4.4 Write property test for union of file and definition keys
    - **Property 2: Displayed keys equal the union of file keys and definition keys**
    - Generate two arbitrary sets of keys and verify union with no duplicates or omissions
    - **Validates: Requirements 1.4**

  - [ ]* 4.5 Write property test for fallback text on unknown definitions
    - **Property 3: Fallback text for unknown or empty definitions**
    - Test that missing/empty definitions produce "No description available" and "Unknown" default
    - **Validates: Requirements 1.5, 2.3, 2.4, 4.4**

  - [ ]* 4.6 Write property test for search filter correctness
    - **Property 9: Search filter returns exactly matching rows**
    - Generate arbitrary settings collections and search strings, verify exact match set
    - **Validates: Requirements 7.2**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Integrate SettingsPanel into GuiInterface
  - [x] 6.1 Replace SettingsView and SettingsEditor with SettingsPanel in `_build_ui()`
    - Remove `SettingsView` and `SettingsEditor` instantiation from `src/gui_interface.py`
    - Add `SettingsPanel` instantiation in their place, passing `config`, `wrapper_core`, `settings_write_handler`, and `notification_bar`
    - Update any references to the old panels (status refresh, pending indicator updates)
    - _Requirements: 1.1_

  - [x] 6.2 Wire pending indicator and refresh into the GUI lifecycle
    - Call `settings_panel.update_pending_indicator()` when pending queue state changes (on apply result callback)
    - Ensure the existing `_on_apply_result` callback integrates with the new panel
    - Wire the Refresh button to call `settings_panel.refresh()`
    - _Requirements: 1.6, 8.3, 8.4_

  - [ ]* 6.3 Write unit tests for SettingsPanel integration
    - Test that SettingsPanel is created with correct dependencies
    - Test refresh triggers re-read and row rebuild
    - Test pending indicator visibility based on queue state
    - Test Apply button wiring through validate_and_correct → SettingsWriteHandler
    - Test notification messages for success, error, auto-correction, queued, and restart warning
    - Test search field clear restores all rows
    - Test "No matching settings" message on empty filter results
    - _Requirements: 1.6, 1.7, 5.7, 5.8, 5.9, 5.10, 7.3, 7.5, 8.2, 8.3, 8.4_

- [x] 7. Remove legacy SettingsView and SettingsEditor classes
  - [x] 7.1 Delete `SettingsView` and `SettingsEditor` classes from `src/gui_interface.py`
    - Remove the class definitions and any associated imports no longer needed
    - Update or remove related unit tests in `tests/unit/` that reference the old classes
    - _Requirements: 1.1_

- [x] 8. Update documentation
  - [x] 8.1 Update README.md and .kiro documentation
    - Update root README.md with any new user-facing operational information about the unified settings panel
    - Update `.kiro/steering/project-context.md` to reflect the new `SettingsPanel` replacing `SettingsView` and `SettingsEditor`
    - Update the Component Map table to include `src/settings_panel.py` and `src/settings_helpers.py`
    - _Requirements: N/A (documentation maintenance)_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The project uses `hypothesis` for property-based tests and `pytest` for unit tests
- All property tests should use `@settings(max_examples=100)` minimum per project conventions
- GUI unit tests use mock-based approach (patch `tk.Tk` and tkinter objects) per project conventions

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "2.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4", "2.5"] },
    { "id": 4, "tasks": ["4.1", "4.2"] },
    { "id": 5, "tasks": ["4.3", "4.4", "4.5", "4.6"] },
    { "id": 6, "tasks": ["6.1"] },
    { "id": 7, "tasks": ["6.2"] },
    { "id": 8, "tasks": ["6.3", "7.1"] },
    { "id": 9, "tasks": ["8.1"] }
  ]
}
```
