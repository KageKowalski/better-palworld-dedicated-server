# Requirements Document

## Introduction

This feature covers three improvements to the server settings subsystem of the Palworld Dedicated Server wrapper: reducing the default idle timeout from 600 seconds to 300 seconds, censoring password values in the "settings" command output, and adding input validation with auto-correction for the "set" command to prevent malformed configuration files.

## Glossary

- **Wrapper**: The Python application that manages the Palworld Dedicated Server process lifecycle.
- **Management_Interface**: The interactive CLI component that accepts user commands via stdin.
- **Settings_Parser**: The component responsible for reading, writing, and validating PalWorldSettings.ini.
- **Settings_Command**: The CLI command that displays all current server settings to the user.
- **Set_Command**: The CLI command that modifies a single server setting value in PalWorldSettings.ini.
- **Password_Setting**: A setting whose key contains "Password" (e.g., AdminPassword, ServerPassword).
- **OptionSettings_Format**: The non-standard INI format used by PalWorldSettings.ini consisting of a single line: `OptionSettings=(Key1=Value1,Key2=Value2,...)` where string values are enclosed in double quotation marks, booleans are `True`/`False`, numeric values are integers or floats, and enum values are specific unquoted strings from a known set.
- **Value_Type**: One of: string (quoted), boolean (True/False), integer, float, or enum (unquoted string from defined allowed values).
- **Auto_Correction**: The process of automatically fixing a user-supplied value to match the expected OptionSettings_Format when the intended format can be safely inferred.

## Requirements

### Requirement 1: Reduce Default Idle Timeout

**User Story:** As a server operator, I want the default idle timeout to be 300 seconds (5 minutes) instead of 600 seconds, so that unused server resources are freed sooner without requiring manual configuration.

#### Acceptance Criteria

1. IF no `--idle-timeout` CLI argument is provided, THEN THE Wrapper SHALL use 300 as the default value for idle_timeout_seconds.
2. WHEN the user provides an explicit idle timeout value via the `--idle-timeout` CLI argument with a positive integer greater than or equal to 1, THE Wrapper SHALL use the user-specified value instead of the default.
3. THE Wrapper README documentation SHALL state that the default idle timeout is 300 seconds.
4. THE Wrapper README documentation SHALL describe the idle timeout behavior using "5 minutes" where it currently references "10 minutes".
5. THE Wrapper CLI help text for the `--idle-timeout` argument SHALL display 300 as the default value.

### Requirement 2: Censor Password Values in Settings Output

**User Story:** As a server operator, I want password values masked in the "settings" command output, so that sensitive credentials are not exposed in terminal output where they could be captured by screen recordings, logs, or shoulder-surfing.

#### Acceptance Criteria

1. WHEN the Settings_Command displays settings, THE Management_Interface SHALL replace the displayed value of each Password_Setting with a fixed mask string of exactly eight asterisk characters (`********`), regardless of the actual password length or whether the value is empty.
2. WHEN the Settings_Command displays settings, THE Management_Interface SHALL display non-password settings with their actual values unchanged.
3. WHEN a setting key contains the substring "Password" (case-sensitive), THE Management_Interface SHALL treat that setting as a Password_Setting.
4. THE Settings_Parser SHALL continue to store and read password values in their original unmasked form within PalWorldSettings.ini.
5. WHEN the Settings_Command displays a Password_Setting, THE Management_Interface SHALL display the setting key in its original unmasked form alongside the masked value.

### Requirement 3: Input Validation and Auto-Correction for Set Command

**User Story:** As a server operator, I want the "set" command to validate and auto-correct my input formatting, so that improperly formatted values do not corrupt the PalWorldSettings.ini file.

#### Acceptance Criteria

1. WHEN the user provides a string value without enclosing double quotation marks for a setting with Value_Type string, THE Set_Command SHALL automatically wrap the value in double quotation marks before writing to the file.
2. WHEN the user provides a string value already enclosed in double quotation marks for a setting with Value_Type string, THE Set_Command SHALL write the value as-is without adding additional quotation marks.
3. WHEN the user provides a boolean value in any letter casing (e.g., "true", "TRUE", "True", "false", "FALSE", "False") for a setting with Value_Type boolean, THE Set_Command SHALL normalize the value to the canonical form ("True" or "False") before writing.
4. IF the user provides a value that cannot be parsed as the expected Value_Type for a known setting (e.g., non-numeric text for an integer or float setting, or a value other than true/false for a boolean setting), THEN THE Set_Command SHALL reject the value, display an error message indicating the expected type and valid format, and SHALL NOT modify the configuration file.
5. WHEN the user provides a numeric value for a setting with Value_Type integer, THE Set_Command SHALL verify the value is a valid integer within the setting's defined min_value and max_value range and write it without decimal points.
6. IF the user provides an integer value that is parseable but falls outside the setting's defined min_value to max_value range, THEN THE Set_Command SHALL reject the value, display an error message indicating the allowed range, and SHALL NOT modify the configuration file.
7. WHEN the user provides a numeric value for a setting with Value_Type float, THE Set_Command SHALL verify the value is a valid number within the setting's defined min_value and max_value range and format it with six decimal places before writing.
8. IF the user provides a float value that is parseable but falls outside the setting's defined min_value to max_value range, THEN THE Set_Command SHALL reject the value, display an error message indicating the allowed range, and SHALL NOT modify the configuration file.
9. IF the user provides a value for an enum-type setting that does not match any entry in that setting's allowed_values list, THEN THE Set_Command SHALL reject the value, display the complete list of allowed values to the user, and SHALL NOT modify the configuration file.
10. WHEN the user provides a value for an enum-type setting that matches an entry in that setting's allowed_values list, THE Set_Command SHALL write the value as-is.
11. WHEN the user provides a value for a setting not defined in the known setting definitions, THE Set_Command SHALL write the value as-is without applying type-based validation or auto-correction.
12. WHEN the Set_Command applies auto-correction to a user-supplied value (quotation mark wrapping, boolean normalization, or float decimal formatting), THE Management_Interface SHALL display both the original and corrected values in the success message so the user is aware of the adjustment.

### Requirement 4: Settings Parser Format Handling

**User Story:** As a developer, I want the settings parser to correctly handle the quoting format for string values in OptionSettings_Format, so that the configuration file remains valid after writes.

#### Acceptance Criteria

1. WHEN writing a setting whose SettingDefinition value_type is str, THE Settings_Parser SHALL enclose the value in double quotation marks (Unicode U+0022) in the OptionSettings line, producing the format `Key="Value"`.
2. WHEN reading a setting whose SettingDefinition value_type is str and whose raw value in the file is enclosed in double quotation marks, THE Settings_Parser SHALL strip exactly the leading and trailing quotation marks from the returned value, returning the inner content unchanged.
3. WHEN reading a setting whose SettingDefinition value_type is str and whose raw value in the file is NOT enclosed in double quotation marks, THE Settings_Parser SHALL return the raw value as-is without modification.
4. WHEN writing and then reading back a string-typed setting value of up to 256 characters that does not itself contain double quotation marks, THE Settings_Parser SHALL return a value equal to the originally written value (round-trip property).
5. IF the string value being written contains a comma character, THEN THE Settings_Parser SHALL still enclose the value in double quotation marks so that the comma is not interpreted as a key-value pair delimiter during subsequent reads.
