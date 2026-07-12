# Requirements Document

## Introduction

This feature introduces a safety mechanism that prevents direct writes to `PalWorldSettings.ini` while the Palworld dedicated server is running. The running server may not re-read changes and may overwrite the file on shutdown, making direct edits dangerous. Instead, changes made while the server is running are queued as pending changes and automatically applied when the server transitions to a stopped state (after `stop_server()` or during the stop phase of `restart_server()`). Both the CLI and GUI interfaces are covered.

## Design Alternatives Considered

The following approaches were evaluated:

1. **Block writes entirely (reject with error):** Simple to implement, but frustrates users who want to prepare multiple setting changes for the next restart. Users would have to stop the server, make changes, then start again — losing uptime unnecessarily.

2. **Temporary shadow file (write to a `.pending.ini`):** Write edits to a separate file while the server is running, then replace the live file on stop/restart. Adds filesystem complexity (two files to track) and risks orphaned temp files if the wrapper crashes.

3. **In-memory pending queue with apply-on-stop (CHOSEN):** Queue setting changes in memory while the server is running. Apply all pending changes to the live file atomically when the server transitions to MONITORING (after stop or during restart). Simple, no extra files, clear user feedback, and pending changes survive within the session. If the wrapper crashes, pending changes are lost — but this is acceptable because the live file was never corrupted.

4. **Write-through with RCON reload command:** Write directly and issue an RCON command to reload settings. Palworld's dedicated server does not support a settings-reload RCON command, making this infeasible.

The **in-memory pending queue** approach was selected as the primary design because it balances safety, simplicity, and user experience.

## Glossary

- **Wrapper**: The Palworld Server Wrapper application (`WrapperCore`) that manages the dedicated server lifecycle.
- **Settings_File**: The `PalWorldSettings.ini` file at the path specified by `WrapperConfig.settings_file_path`.
- **Pending_Queue**: An in-memory ordered collection of setting key-value pairs that have been submitted while the server is in a non-safe-to-write state.
- **Safe_State**: A server state in which direct writes to the Settings_File are permitted. Defined as `ServerState.MONITORING`.
- **Unsafe_State**: A server state in which direct writes to the Settings_File are dangerous. Defined as `ServerState.STARTING`, `ServerState.RUNNING`, or `ServerState.STOPPING`.
- **CLI**: The `ManagementInterface` command-line interface.
- **GUI**: The `GuiInterface` graphical interface (specifically `SettingsEditor`).
- **Apply_Operation**: The process of writing all Pending_Queue entries to the Settings_File and clearing the queue.

## Requirements

### Requirement 1: Gate Setting Writes Based on Server State

**User Story:** As a server administrator, I want setting writes to be blocked from reaching the live file while the server is running, so that the running server's configuration is not corrupted or silently overwritten on shutdown.

#### Acceptance Criteria

1. WHILE the Wrapper is in Safe_State, THE Settings_Write_Handler SHALL write setting changes directly to the Settings_File using SettingsParser.write_setting and return the ValidationResult from that write to the caller.
2. WHILE the Wrapper is in Unsafe_State, THE Settings_Write_Handler SHALL add setting changes to the Pending_Queue instead of writing to the Settings_File.
3. THE Settings_Write_Handler SHALL determine the current server state by calling WrapperCore.get_status().server_state before each write attempt.
4. WHEN a setting change is added to the Pending_Queue, THE Settings_Write_Handler SHALL return a ValidationResult with valid=True to the caller indicating the change was queued.
5. IF SettingsParser.validate_setting returns an invalid ValidationResult for the submitted key-value pair, THEN THE Settings_Write_Handler SHALL return that invalid ValidationResult to the caller without writing to the Settings_File or adding to the Pending_Queue.
6. IF SettingsParser.write_setting fails during a Safe_State write (returns a ValidationResult with valid=False), THEN THE Settings_Write_Handler SHALL return that failure ValidationResult to the caller without adding the entry to the Pending_Queue.

### Requirement 2: Apply Pending Changes on Server Stop

**User Story:** As a server administrator, I want my queued settings to be automatically applied when the server stops, so that I do not have to remember to manually apply changes.

#### Acceptance Criteria

1. WHEN the server transitions from STOPPING to MONITORING after a stop_server() call, THE Wrapper SHALL execute the Apply_Operation before the connection listener is restarted.
2. WHEN the server transitions from STOPPING to MONITORING during the stop phase of restart_server(), THE Wrapper SHALL execute the Apply_Operation before starting the server again.
3. WHEN the Apply_Operation is executed, THE Apply_Operation SHALL write each entry in the Pending_Queue to the Settings_File in the order the entries were queued.
4. WHEN the Apply_Operation completes successfully, THE Pending_Queue SHALL be empty.
5. IF a write failure occurs during the Apply_Operation, THEN THE Wrapper SHALL log the error, retain the failed entry and all subsequent entries in the Pending_Queue, and report the failure via the CLI and GUI feedback mechanisms defined in Requirements 4 and 5.
6. IF a write failure occurs during the Apply_Operation that was triggered by restart_server(), THEN THE Wrapper SHALL proceed with restarting the server after reporting the failure, leaving the remaining Pending_Queue entries in place for the next stop cycle.

### Requirement 3: Pending Queue Behavior

**User Story:** As a server administrator, I want to queue multiple setting changes and have later values override earlier ones for the same key, so that only the final intended value is applied.

#### Acceptance Criteria

1. WHEN multiple changes for the same setting key are added to the Pending_Queue, THE Pending_Queue SHALL retain only the most recent value for that key while preserving the key's original insertion position.
2. THE Pending_Queue SHALL preserve the insertion order of distinct keys (the order in which keys were first added), such that iterating the queue yields keys in first-seen order.
3. THE Pending_Queue SHALL support at least 100 distinct pending setting entries while preserving all stored key-value pairs and their insertion order. IF an entry is submitted that would cause the Pending_Queue to exceed 100 distinct keys, THEN THE Settings_Write_Handler SHALL reject the submission and return an error indicating the queue is full.
4. IF the Pending_Queue is empty when the Apply_Operation is invoked, THEN THE Apply_Operation SHALL complete immediately without performing any file writes to the Settings_File.
5. WHEN a setting change is submitted while the Wrapper is in Unsafe_State, THE Settings_Write_Handler SHALL validate the setting key and value using SettingsParser.validate_setting before adding the entry to the Pending_Queue, and SHALL reject invalid entries with a validation error instead of queuing them.

### Requirement 4: CLI Feedback for Pending Changes

**User Story:** As a server administrator using the CLI, I want clear feedback about whether my setting change was applied immediately or queued, so that I understand the current state of my changes.

#### Acceptance Criteria

1. WHEN a setting change is written directly to the Settings_File (Safe_State), THE CLI SHALL display the message "Setting '{key}' updated to '{value}'." where {key} is the setting key name and {value} is the final written value (after any auto-correction).
2. WHEN a setting change is added to the Pending_Queue (Unsafe_State), THE CLI SHALL display the message "Setting '{key}' queued as '{value}'. It will be applied when the server stops." where {key} is the setting key name and {value} is the final stored value (after any auto-correction).
3. WHEN the Apply_Operation is executed successfully and one or more entries were applied, THE CLI SHALL display the message "N pending setting(s) applied to PalWorldSettings.ini." where N is the count of applied settings.
4. IF the Apply_Operation encounters a write failure, THEN THE CLI SHALL display the message "Error applying pending settings: {error_message}. M change(s) remain queued." where {error_message} is the underlying write error description (truncated to 200 characters if longer) and M is the number of entries still in the Pending_Queue.
5. WHEN the Apply_Operation completes automatically during a server stop or restart transition, THE CLI SHALL display the apply result message (criterion 3 or 4) within 2 seconds of the Apply_Operation completing, without requiring user input.
6. WHEN the Apply_Operation is triggered but the Pending_Queue is empty (no-op), THE CLI SHALL NOT display any apply-related message.

### Requirement 5: GUI Feedback for Pending Changes

**User Story:** As a server administrator using the GUI, I want visual feedback about queued changes and confirmation when they are applied, so that I can verify my configuration intentions.

#### Acceptance Criteria

1. WHEN a setting change is written directly to the Settings_File (Safe_State), THE GUI SHALL display a success notification with the message "Setting '{key}' set to '{value}' successfully." in green text that auto-dismisses after 5 seconds.
2. WHEN a setting change is added to the Pending_Queue (Unsafe_State), THE GUI SHALL display an info notification with the message "Setting '{key}' queued as '{value}'. Will apply on server stop/restart." in blue text that auto-dismisses after 5 seconds.
3. WHEN the Apply_Operation is executed successfully, THE GUI SHALL display a success notification with the message "N pending setting(s) applied." in green text that auto-dismisses after 5 seconds, where N is the count of settings written.
4. IF the Apply_Operation encounters a write failure, THEN THE GUI SHALL display an error notification with the message "Failed to apply pending settings: {error_message}. M change(s) remain queued." in red text that persists until the user dismisses it, where M is the number of entries still in the Pending_Queue.
5. WHEN a new notification is triggered while an existing notification is displayed, THE GUI SHALL replace the existing notification immediately, cancelling any pending auto-dismiss timer from the previous notification.

### Requirement 6: Pending Changes Visibility

**User Story:** As a server administrator, I want to view all currently pending setting changes, so that I can verify what will be applied on the next stop or restart.

#### Acceptance Criteria

1. WHEN the user issues the "pending" command in the CLI, THE CLI SHALL display a header line "Pending setting changes:" followed by all entries in the Pending_Queue, each on its own line in the format "  {key} = {value}", listed in insertion order.
2. IF the Pending_Queue is empty and the user issues the "pending" command, THEN THE CLI SHALL display the message "No pending setting changes.".
3. WHEN the user issues the "pending clear" command in the CLI, THE CLI SHALL remove all entries from the Pending_Queue and display "Pending changes cleared.".
4. IF the Pending_Queue is already empty when the user issues the "pending clear" command, THEN THE CLI SHALL display the message "No pending setting changes.".
5. WHILE the Wrapper is in Unsafe_State and the Pending_Queue is non-empty, THE GUI SettingsEditor feedback area SHALL display "N change(s) pending" where N is the current count of distinct keys in the Pending_Queue, and this indicator SHALL remain visible until either the Wrapper transitions to Safe_State or the Pending_Queue becomes empty.
6. WHILE the Wrapper is in Unsafe_State and the Pending_Queue is non-empty, THE GUI SettingsEditor feedback area SHALL display a tooltip or expandable list showing each pending entry in "key = value" format sorted by insertion order when the user hovers over or clicks the pending indicator.

### Requirement 7: Data Integrity Guarantees

**User Story:** As a server administrator, I want assurance that no setting change is silently lost or partially applied, so that my configuration is always in a known-good state.

#### Acceptance Criteria

1. THE Settings_Write_Handler SHALL guarantee that every submitted setting change that passes validation is either written to the Settings_File or stored in the Pending_Queue (no silent discard). IF a submitted setting change fails validation, THEN THE Settings_Write_Handler SHALL return an error result to the caller indicating the rejection reason (explicit rejection is not considered silent discard).
2. THE Apply_Operation SHALL write settings atomically per entry: each key-value write either updates the Settings_File to include the new value or leaves the Settings_File unchanged for that key (partial writes within a single entry are not permitted).
3. IF the Wrapper process terminates unexpectedly while the Pending_Queue is non-empty, THEN THE Settings_File SHALL remain in the state produced by the last successfully completed write operation (no incomplete or corrupted content shall be present in the file).
4. WHEN a valid setting key-value pair (one that passes SettingsParser.validate_setting with ValidationResult.valid == True) is submitted WHILE the Wrapper is in Safe_State, THE Settings_Write_Handler SHALL write it such that immediately reading the Settings_File produces the submitted value for that key.
5. WHEN a valid setting key-value pair is submitted WHILE the Wrapper is in Unsafe_State and the Apply_Operation subsequently completes successfully, THE Settings_File SHALL contain the submitted value for that key after the Apply_Operation finishes.
