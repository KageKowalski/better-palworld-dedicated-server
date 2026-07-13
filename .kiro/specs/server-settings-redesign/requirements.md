# Requirements Document

## Introduction

Redesign the Server Settings GUI to improve usability by providing clear descriptions, allowed values, default values, and current values for each setting key. The existing "Server Settings" (read-only view) and "Modify Setting" (edit form) panels will be consolidated into a unified settings interface that surfaces all relevant metadata inline, eliminating the guesswork currently required to understand and modify server configuration.

## Glossary

- **Settings_Panel**: The unified tkinter GUI panel that replaces the separate "Server Settings" and "Modify Setting" panels, displaying all setting metadata and edit controls in a single scrollable interface.
- **Setting_Row**: A single row within the Settings_Panel representing one server setting key, showing its description, default value, current value, and an input control for modification.
- **Setting_Definition**: The metadata record for a known setting key, including its name, value type, allowed range or values, description, and default value (sourced from SETTING_DEFINITIONS in settings_parser.py).
- **Settings_Parser**: The existing module responsible for reading and writing PalWorldSettings.ini configuration values.
- **Validation_Module**: The shared validation module (src/validation.py) that performs type-aware validation and auto-correction of setting values.
- **Notification_Bar**: The existing bottom-of-window notification component that displays success and error messages.

## Requirements

### Requirement 1: Unified Settings Panel Layout

**User Story:** As a server administrator, I want a single panel that shows all settings with their metadata and edit controls, so that I can understand and modify settings without switching between separate view and edit panels.

#### Acceptance Criteria

1. THE Settings_Panel SHALL replace the separate "Server Settings" view panel and "Modify Setting" editor panel with a single consolidated panel.
2. THE Settings_Panel SHALL display Setting_Rows within a vertically scrollable container.
3. THE Settings_Panel SHALL sort Setting_Rows alphabetically by key name using case-insensitive comparison.
4. THE Settings_Panel SHALL display one Setting_Row for each unique key found in the union of the settings file keys and the Setting_Definition records.
5. WHEN the settings file contains keys not present in Setting_Definition records, THE Settings_Panel SHALL display those unknown keys as Setting_Rows with a description of "No description available" and no default value shown.
6. WHEN the user clicks the "Refresh" button, THE Settings_Panel SHALL re-read the settings file and update all displayed current values.
7. IF the settings file cannot be read during a refresh, THEN THE Notification_Bar SHALL display an error message indicating the file read failure and THE Settings_Panel SHALL retain the previously displayed values.

### Requirement 2: Setting Description Display

**User Story:** As a server administrator, I want a clear description of what each setting key does, so that I can understand the purpose of a setting without consulting external documentation.

#### Acceptance Criteria

1. THE Setting_Row SHALL display the description text from the corresponding Setting_Definition record, positioned adjacent to the setting key name.
2. THE description text SHALL consist of one sentence with a maximum length of 120 characters.
3. WHEN a setting key is not present in the Setting_Definition records, THE Setting_Row SHALL display "No description available" as the description.
4. IF a Setting_Definition record exists but its description field is empty, THEN THE Setting_Row SHALL display "No description available" as the description.

### Requirement 3: Allowed Values Display

**User Story:** As a server administrator, I want to see what values are valid for each setting, so that I can set values correctly without trial and error.

#### Acceptance Criteria

1. WHEN a setting has a defined value type of boolean, THE Setting_Row SHALL indicate that allowed values are "True / False".
2. WHEN a setting has a defined value type of integer or float with both min and max constraints, THE Setting_Row SHALL display the allowed range in the format "min – max". WHEN only a min constraint is defined, THE Setting_Row SHALL display "min or above". WHEN only a max constraint is defined, THE Setting_Row SHALL display "max or below".
3. WHEN a setting has a defined list of allowed string values, THE Setting_Row SHALL display all allowed values as a comma-separated list (e.g., "None, Item, ItemAndEquipment, All").
4. WHEN a setting has a defined value type of string without allowed values or range constraints, THE Setting_Row SHALL indicate that the value accepts "Any text".
5. WHEN a setting key is not present in Setting_Definition records, THE Setting_Row SHALL indicate that allowed values are "Unknown".
6. WHEN a setting has a defined value type of integer or float with no min or max constraints, THE Setting_Row SHALL indicate that the value accepts "Any number".

### Requirement 4: Default and Current Value Display

**User Story:** As a server administrator, I want to see both the default value and current value for each setting, so that I can tell what has been changed from defaults.

#### Acceptance Criteria

1. EACH Setting_Row SHALL display the default value for the setting key as defined in its Setting_Definition record.
2. EACH Setting_Row SHALL display the current value as read from the settings file.
3. WHEN a setting key is a password field (key contains the substring "Password", case-sensitive), THE Setting_Row SHALL mask both the current value and the default value display with "********".
4. WHEN a setting key is not present in the Setting_Definition records, THE Setting_Row SHALL display "Unknown" as the default value.
5. WHEN the current value differs from the default value after type-appropriate coercion (string comparison for string types, numeric comparison for numeric types, boolean comparison for boolean types), THE Setting_Row SHALL display the current value in bold text to indicate a non-default configuration.
6. WHEN the settings file cannot be read or a setting key has no current value, THE Setting_Row SHALL display an empty string as the current value.

### Requirement 5: Inline Setting Modification

**User Story:** As a server administrator, I want to edit a setting value directly within its row, so that I can modify settings without needing to remember and type the key name separately.

#### Acceptance Criteria

1. EACH Setting_Row SHALL provide an input control appropriate to the setting's value type for entering a new value, pre-populated with the setting's current value.
2. WHEN the setting value type is boolean, THE input control SHALL be a dropdown with "True" and "False" options.
3. WHEN the setting value type is string with a defined list of allowed values, THE input control SHALL be a dropdown containing all allowed values.
4. WHEN the setting value type is integer, float, or unconstrained string, THE input control SHALL be a text entry field.
5. EACH Setting_Row SHALL include an "Apply" button that submits the input value to the Validation_Module for validation, auto-correction, and writing via the SettingsWriteHandler.
6. WHEN the "Apply" button is clicked, THE Validation_Module SHALL validate and auto-correct the input value before the SettingsWriteHandler routes it to file write or pending queue based on server state.
7. IF validation fails, THEN THE Notification_Bar SHALL display the validation error message returned by the Validation_Module.
8. WHEN a value is successfully written and auto-correction was applied, THE Notification_Bar SHALL display a success confirmation message that includes the original input and the corrected value that was written.
9. WHEN a value is successfully written and no auto-correction was applied, THE Notification_Bar SHALL display a success confirmation message.
10. WHEN a value is successfully written and the server is in RUNNING state, THE Notification_Bar SHALL append a warning that a restart is required for the change to take effect.
11. WHEN a value is successfully written, THE Setting_Row SHALL update its displayed current value and the input control value to reflect the new value.
12. WHEN a setting key is a password field, THE input control SHALL mask the entered text.

### Requirement 6: Setting Definition Metadata Extension

**User Story:** As a developer, I want setting definitions to include description text and default values, so that the GUI can surface this metadata to users.

#### Acceptance Criteria

1. THE Setting_Definition dataclass SHALL include a "description" field of type str containing a human-readable explanation of the setting.
2. THE Setting_Definition dataclass SHALL include a "default_value" field containing the server's default value for the setting, typed to match the setting's value type (str, int, float, or bool). WHEN no documented default exists, THE default_value SHALL be None.
3. WHEN a new Setting_Definition is added, THE description field SHALL be populated with a concise explanation (one sentence, maximum 120 characters, minimum 10 characters).
4. WHEN a new Setting_Definition is added, THE default_value field SHALL match the Palworld Dedicated Server's documented default for that setting.
5. ALL existing Setting_Definition records SHALL be backfilled with description and default_value fields.

### Requirement 7: Search and Filter

**User Story:** As a server administrator, I want to search and filter settings by name or description, so that I can quickly locate a specific setting without scrolling through the entire list.

#### Acceptance Criteria

1. THE Settings_Panel SHALL include a search input field with a maximum length of 200 characters, positioned above the settings list.
2. WHEN the user types text into the search field, THE Settings_Panel SHALL filter Setting_Rows to show only those whose key name or description contains the search text as a substring (case-insensitive), updating the displayed results within 100 milliseconds of each keystroke without requiring a submit action.
3. WHEN the search field is cleared, THE Settings_Panel SHALL display all Setting_Rows in alphabetical order.
4. WHEN Setting_Rows are filtered, THE Settings_Panel SHALL preserve alphabetical sorting by key name among the visible results.
5. IF no Setting_Rows match the search text, THEN THE Settings_Panel SHALL display a "No matching settings" message in the list area in place of the Setting_Rows.

### Requirement 8: Pending Settings Integration

**User Story:** As a server administrator, I want settings modifications to integrate with the existing pending queue system, so that changes made while the server is running are safely queued and applied on restart.

#### Acceptance Criteria

1. WHEN a setting modification is submitted while the server is in an unsafe state (STARTING, RUNNING, or STOPPING), THE Settings_Panel SHALL route the change through the existing SettingsWriteHandler which validates and adds to the PendingSettingsQueue.
2. WHEN a setting is successfully queued, THE Notification_Bar SHALL display a message indicating the setting was queued and will apply on server stop or restart.
3. THE Settings_Panel SHALL display a pending changes indicator (e.g., badge or label showing the count of queued entries) when the PendingSettingsQueue is not empty.
4. WHEN the PendingSettingsQueue becomes empty (after apply or clear), THE pending changes indicator SHALL be hidden.
