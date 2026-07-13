# Implementation Plan: Server Settings Improvements

## Overview

This plan implements three improvements to the server settings subsystem: reducing the default idle timeout from 600s to 300s, censoring password values in the `settings` command output, and adding input validation with auto-correction to the `set` command. All changes are localized to `src/config.py`, `src/main.py`, `src/management_interface.py`, and `src/settings_parser.py`.

## Tasks

- [x] 1. Reduce default idle timeout
  - [x] 1.1 Update default idle timeout in config and CLI
    - Change `idle_timeout_seconds` default from `600` to `300` in `src/config.py` WrapperConfig
    - Change `--idle-timeout` argument default from `600` to `300` in `src/main.py` parse_args
    - Update help string to reference 300 as the default
    - Update README documentation to state 300 seconds / 5 minutes where it currently says 600 / 10 minutes
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 1.2 Write unit tests for idle timeout default
    - Test that WrapperConfig default idle_timeout_seconds is 300
    - Test that parse_args with no --idle-timeout flag produces 300
    - Test that parse_args with explicit --idle-timeout value uses that value
    - Test CLI help text displays 300 as default
    - _Requirements: 1.1, 1.2, 1.5_

  - [ ]* 1.3 Write property test for CLI idle timeout passthrough
    - **Property 10: CLI idle timeout passthrough**
    - For any positive integer N >= 1, passing `--idle-timeout N` produces config with `idle_timeout_seconds == N`
    - **Validates: Requirements 1.2**

- [x] 2. Implement password censoring in settings output
  - [x] 2.1 Add password masking logic to ManagementInterface._cmd_settings
    - Add `PASSWORD_MASK = "********"` constant to `src/management_interface.py`
    - Add `_is_password_setting(self, key: str) -> bool` helper method that returns `True` when key contains "Password" (case-sensitive)
    - Modify `_cmd_settings` to display `PASSWORD_MASK` instead of the actual value for password settings
    - Non-password settings continue to display their actual values unchanged
    - _Requirements: 2.1, 2.2, 2.3, 2.5_

  - [ ]* 2.2 Write unit tests for password masking
    - Test that settings with "Password" in key display "********"
    - Test that settings without "Password" in key display actual values
    - Test that the setting key itself is displayed unmasked alongside the masked value
    - Test edge cases: empty password, "AdminPassword", "ServerPassword"
    - _Requirements: 2.1, 2.2, 2.3, 2.5_

  - [ ]* 2.3 Write property test for password masking in display
    - **Property 1: Password masking in display**
    - For any setting key containing "Password" and any actual password value (including empty), display shows exactly `********`
    - **Validates: Requirements 2.1, 2.3, 2.5**

  - [ ]* 2.4 Write property test for non-password transparency
    - **Property 2: Non-password transparency in display**
    - For any setting key NOT containing "Password", display shows actual value unchanged
    - **Validates: Requirements 2.2**

- [x] 3. Checkpoint - Verify idle timeout and password masking
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Update SettingsParser for string quoting
  - [x] 4.1 Update _format_value to quote string-type settings
    - In `src/settings_parser.py` `_format_value`, when `definition.value_type == str`, return `f'"{value}"'` to wrap value in double quotes
    - Ensure this handles strings containing commas correctly (quotes prevent delimiter interpretation)
    - _Requirements: 4.1, 4.5_

  - [x] 4.2 Update _coerce_value to strip quotes on string-type read
    - In `src/settings_parser.py` `_coerce_value`, when `definition.value_type == str`, strip surrounding double quotes if present
    - If raw value is not quoted, return as-is
    - _Requirements: 4.2, 4.3_

  - [ ]* 4.3 Write property test for string setting write/read round-trip
    - **Property 9: String setting write/read round-trip**
    - For any string up to 256 chars not containing double quotes, write then read back produces original value
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5**

  - [ ]* 4.4 Write property test for password storage round-trip
    - **Property 3: Password storage round-trip**
    - For any password value (0–256 chars, no double quotes), writing and reading back via SettingsParser returns original unmasked value
    - **Validates: Requirements 2.4, 4.4**

- [x] 5. Implement input validation and auto-correction for set command
  - [x] 5.1 Add CorrectionResult helper and validation logic to _cmd_set
    - Add `CorrectionResult` dataclass to `src/management_interface.py` with fields: `value`, `was_corrected`, `original_input`
    - Implement string auto-correction: wrap unquoted values in quotes, strip outer quotes from already-quoted values and pass inner content
    - Implement boolean normalization: any casing of true/false normalized to "True"/"False"
    - Implement integer validation: parse as int, check min/max range from SettingDefinition
    - Implement float validation: parse as float, check min/max range from SettingDefinition
    - Implement enum validation: check value against allowed_values list
    - Unknown settings: write as-is without validation
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11_

  - [x] 5.2 Implement error messages and auto-correction feedback
    - On type validation failure: display error naming expected type (e.g., "must be an integer")
    - On out-of-range numeric: display error with allowed range [min, max]
    - On invalid enum: display complete list of allowed values
    - On non-boolean for bool setting: display error expecting True/False
    - On successful auto-correction: display both original input and corrected value in success message
    - _Requirements: 3.4, 3.6, 3.8, 3.9, 3.12_

  - [ ]* 5.3 Write property test for string quoting idempotence
    - **Property 4: String quoting idempotence**
    - For any string-type setting value, after auto-correction the value written to file is enclosed in exactly one pair of double quotes
    - **Validates: Requirements 3.1, 3.2, 4.1**

  - [ ]* 5.4 Write property test for boolean normalization
    - **Property 5: Boolean normalization**
    - For any case variation of "true"/"false", set command normalizes to exactly "True"/"False" before writing
    - **Validates: Requirements 3.3**

  - [ ]* 5.5 Write property test for invalid input rejection preserves file
    - **Property 6: Invalid input rejection preserves file**
    - For any known setting and any value that fails validation, the configuration file remains byte-for-byte identical
    - **Validates: Requirements 3.4, 3.6, 3.8, 3.9**

  - [ ]* 5.6 Write property test for valid numeric formatting
    - **Property 7: Valid numeric formatting**
    - For valid integers in range: written value has no decimal point. For valid floats in range: written value has exactly six decimal places
    - **Validates: Requirements 3.5, 3.7**

  - [ ]* 5.7 Write property test for auto-correction feedback
    - **Property 8: Auto-correction feedback**
    - For any set command where written value differs from original input, success message contains both original and corrected value
    - **Validates: Requirements 3.12**

- [x] 6. Checkpoint - Verify all validation and auto-correction logic
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Wire components and final integration
  - [x] 7.1 Wire updated _cmd_set to delegate corrected values to SettingsParser.write_setting
    - Ensure the corrected value (not the raw user input) is passed to `write_setting`
    - Verify the success message displays the corrected value when auto-correction occurred
    - Verify unknown settings bypass validation and write as-is
    - Ensure the existing "restart required" warning still displays when server is running
    - _Requirements: 3.1, 3.2, 3.3, 3.5, 3.7, 3.10, 3.11, 3.12_

  - [ ]* 7.2 Write unit tests for full set command flow
    - Test set with unquoted string value auto-corrects and writes quoted
    - Test set with already-quoted string value writes correctly
    - Test set with mixed-case boolean normalizes to True/False
    - Test set with valid integer in range succeeds
    - Test set with out-of-range integer rejects
    - Test set with invalid enum shows allowed values
    - Test set with unknown key writes as-is
    - Test set with non-numeric for int setting rejects
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.9, 3.10, 3.11_

- [x] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All property tests use `@settings(max_examples=100)` minimum per project conventions
- Test file for property tests: `tests/property/test_server_settings_improvements.py`
- Test file for unit tests: `tests/unit/test_settings_improvements.py`
- The implementation language is Python (as used throughout the existing codebase)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "4.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.2", "2.3", "2.4", "4.2"] },
    { "id": 2, "tasks": ["4.3", "4.4", "5.1"] },
    { "id": 3, "tasks": ["5.2"] },
    { "id": 4, "tasks": ["5.3", "5.4", "5.5", "5.6", "5.7"] },
    { "id": 5, "tasks": ["7.1"] },
    { "id": 6, "tasks": ["7.2"] }
  ]
}
```
