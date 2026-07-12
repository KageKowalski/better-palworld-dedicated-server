# Implementation Plan: Settings Safe Write

## Overview

This implementation plan converts the settings-safe-write design into discrete coding tasks. The approach builds the core data structures first (PendingSettingsQueue), then the routing logic (SettingsWriteHandler), integrates into WrapperCore lifecycle, and finally updates CLI and GUI interfaces. Property-based tests are placed immediately after the modules they verify to catch errors early.

## Tasks

- [x] 1. Create PendingSettingsQueue module
  - [x] 1.1 Create `src/pending_settings.py` with PendingSettingsQueue class and ApplyResult dataclass
    - Implement `ApplyResult` dataclass with fields: `applied_count`, `failed_key`, `error_message`, `remaining_count`
    - Implement `PendingSettingsQueue` class with `OrderedDict`-based internal storage
    - Implement `add(key, value)` method with last-writer-wins semantics and 100-key capacity check
    - Implement `clear()`, `is_empty()`, `count()`, `entries()` methods
    - Implement `apply(file_path)` method that drains entries via `SettingsParser.write_setting`, stops on first failure retaining remaining entries
    - Define `MAX_PENDING_ENTRIES = 100` module constant
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 2.3, 2.4, 2.5, 7.2_

  - [ ]* 1.2 Write property test: Queue last-writer-wins with order preservation (Property 3)
    - **Property 3: Queue last-writer-wins with order preservation**
    - Generate random sequences of `add(key, value)` operations with repeated keys using Hypothesis strategies
    - Verify final queue contains exactly one entry per distinct key with the most recently submitted value
    - Verify iterating entries yields keys in first-seen insertion order
    - **Validates: Requirements 3.1, 3.2**

  - [ ]* 1.3 Write property test: Queue capacity enforcement (Property 6)
    - **Property 6: Queue capacity enforcement**
    - Fill queue to exactly 100 distinct keys
    - Verify adding a new distinct key returns `False` (rejected)
    - Verify updating any existing key returns `True` (accepted) with value updated
    - **Validates: Requirements 3.3**

  - [ ]* 1.4 Write property test: Empty queue apply is a no-op (Property 7)
    - **Property 7: Empty queue apply is a no-op**
    - Generate random file content, apply empty queue
    - Verify file content is unchanged and `ApplyResult(applied_count=0, remaining_count=0)` is returned
    - **Validates: Requirements 3.4**

  - [ ]* 1.5 Write property test: Apply operation round-trip (Property 4)
    - **Property 4: Apply operation round-trip**
    - Generate a queue of valid settings, apply to a temporary file, read back
    - Verify all values match queued values, queue is empty after apply, `applied_count` equals original queue size
    - **Validates: Requirements 2.3, 2.4, 7.4, 7.5**

  - [ ]* 1.6 Write property test: Apply failure preserves remaining entries (Property 5)
    - **Property 5: Apply failure preserves remaining entries**
    - Generate a queue of N entries, mock `SettingsParser.write_setting` to fail at random position K
    - Verify entries K..N remain in queue in original order, entries 1..K-1 were written, `applied_count = K-1`, `remaining_count = N - K + 1`
    - **Validates: Requirements 2.5**

- [x] 2. Create SettingsWriteHandler module
  - [x] 2.1 Create `src/settings_write_handler.py` with SettingsWriteHandler class
    - Implement `SettingsWriteHandler.__init__` accepting `wrapper_core`, `pending_queue`, and `settings_file_path`
    - Define `SAFE_STATES = {ServerState.MONITORING}`
    - Implement `submit(key, value)` method that validates first, then routes to direct write (MONITORING) or queue (other states)
    - Return `tuple[ValidationResult, bool]` where `bool` indicates whether the setting was queued
    - Handle queue-full case by returning `ValidationResult(valid=False, error_message="Pending queue is full (100 entries maximum).")`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 3.5, 7.1_

  - [ ]* 2.2 Write property test: State-based routing with no silent discard (Property 1)
    - **Property 1: State-based routing with no silent discard**
    - Generate random valid settings and server states using Hypothesis
    - Verify MONITORING state results in direct file write with `valid=True` returned
    - Verify STARTING/RUNNING/STOPPING states result in queue addition with `valid=True` and file unchanged
    - **Validates: Requirements 1.1, 1.2, 1.4, 7.1**

  - [ ]* 2.3 Write property test: Validation gating (Property 2)
    - **Property 2: Validation gating**
    - Generate invalid settings (bad types, out-of-range values) across all server states
    - Verify they are always rejected with `valid=False`, file unchanged, queue unchanged
    - **Validates: Requirements 1.5, 3.5**

  - [ ]* 2.4 Write unit tests for SettingsWriteHandler
    - Test direct write success in MONITORING state
    - Test queuing behavior in STARTING, RUNNING, STOPPING states
    - Test validation rejection prevents write and queue
    - Test queue-full error response
    - Test direct write failure in MONITORING state returns failure without queuing
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6_

- [x] 3. Checkpoint - Ensure core modules pass all tests
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Integrate into WrapperCore lifecycle
  - [x] 4.1 Modify `src/wrapper_core.py` to own PendingSettingsQueue and apply pending on stop/restart
    - Import `PendingSettingsQueue` and `ApplyResult` from `src.pending_settings`
    - Create `PendingSettingsQueue` instance in `WrapperCore.__init__`
    - Add `pending_queue` property to expose the queue instance
    - Add `_notify_apply_result` callback mechanism (list of callables)
    - In `stop_server()`: call `self._pending_queue.apply(self._config.settings_file_path)` after transitioning to MONITORING but before restarting connection listener
    - In `restart_server()`: call `self._pending_queue.apply(self._config.settings_file_path)` between stop phase completing and start phase beginning
    - Fire apply result notification if `applied_count > 0` or `failed_key` is not None
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 7.3_

  - [ ]* 4.2 Write unit tests for WrapperCore pending integration
    - Test `pending_queue` property returns the queue instance
    - Test `stop_server()` calls apply and fires notification callback on success
    - Test `restart_server()` calls apply between stop and start phases
    - Test apply failure during restart still proceeds with server start
    - Test no notification fired when queue is empty (no-op)
    - _Requirements: 2.1, 2.2, 2.5, 2.6_

- [x] 5. Update ManagementInterface (CLI)
  - [x] 5.1 Modify `src/management_interface.py` to route set command through SettingsWriteHandler and add pending commands
    - Import `SettingsWriteHandler` and `PendingSettingsQueue`
    - Create `SettingsWriteHandler` instance during `ManagementInterface` initialization
    - Update `_cmd_set` to use `SettingsWriteHandler.submit()` instead of direct `SettingsParser.write_setting()`
    - Display "Setting '{key}' updated to '{value}'." for direct writes
    - Display "Setting '{key}' queued as '{value}'. It will be applied when the server stops." for queued writes
    - Register apply result notification callback to display: "N pending setting(s) applied to PalWorldSettings.ini." on success or "Error applying pending settings: {error_message}. M change(s) remain queued." on failure
    - Add `_cmd_pending` handler for the "pending" command that lists queued entries or "No pending setting changes."
    - Add `_cmd_pending_clear` handler for "pending clear" command that clears the queue and displays "Pending changes cleared." or "No pending setting changes." if already empty
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 6.1, 6.2, 6.3, 6.4_

  - [ ]* 5.2 Write unit tests for CLI feedback messages
    - Test "Setting '{key}' updated to '{value}'." output on direct write
    - Test "Setting '{key}' queued as '{value}'. It will be applied when the server stops." output on queued write
    - Test apply success notification message format
    - Test apply failure notification message format with error truncation to 200 characters
    - Test "pending" command output with entries and when empty
    - Test "pending clear" command output when queue has entries and when already empty
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 6.1, 6.2, 6.3, 6.4_

- [x] 6. Update GuiInterface (GUI)
  - [x] 6.1 Modify `src/gui_interface.py` to route SettingsEditor submit through SettingsWriteHandler and add pending indicator
    - Import `SettingsWriteHandler` and `PendingSettingsQueue`
    - Create `SettingsWriteHandler` instance during `GuiInterface` initialization
    - Update `SettingsEditor._on_submit()` to use `SettingsWriteHandler.submit()`
    - Display green success notification "Setting '{key}' set to '{value}' successfully." (auto-dismiss 5s) for direct writes
    - Display blue info notification "Setting '{key}' queued as '{value}'. Will apply on server stop/restart." (auto-dismiss 5s) for queued writes
    - Display pending count indicator "N change(s) pending" in SettingsEditor feedback area when queue is non-empty and server is in Unsafe_State
    - Add tooltip/expandable list showing each pending entry in "key = value" format
    - Register apply result notification callback: green "N pending setting(s) applied." (auto-dismiss 5s) on success or red persistent "Failed to apply pending settings: {error_message}. M change(s) remain queued." on failure
    - Implement notification replacement logic: new notification cancels previous auto-dismiss timer
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.5, 6.6_

  - [ ]* 6.2 Write unit tests for GUI notification behavior
    - Test green success notification text and auto-dismiss timing for direct writes
    - Test blue info notification text and auto-dismiss timing for queued writes
    - Test pending count indicator visibility and text when queue non-empty in unsafe state
    - Test apply success green notification with auto-dismiss
    - Test apply failure red persistent notification
    - Test notification replacement cancels previous timer
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.5_

- [x] 7. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All property tests use the Hypothesis library (already configured in the project)
- Property test files should be placed in `tests/property/test_pending_settings.py`
- Unit test files: `tests/unit/test_pending_settings.py`, `tests/unit/test_settings_write_handler.py`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "1.5", "1.6", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4"] },
    { "id": 3, "tasks": ["4.1"] },
    { "id": 4, "tasks": ["4.2", "5.1", "6.1"] },
    { "id": 5, "tasks": ["5.2", "6.2"] }
  ]
}
```
