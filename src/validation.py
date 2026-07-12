"""Shared validation and auto-correction logic for server settings.

Provides type-aware validation and auto-correction for PalWorldSettings.ini
values based on SETTING_DEFINITIONS. Used by both the GUI and console
management interfaces to ensure consistent behavior.

Functions:
    validate_and_correct - Validate and auto-correct a setting value
    is_password_setting  - Check if a setting key is a password field
"""

from dataclasses import dataclass
from typing import Any

from src.settings_parser import SETTING_DEFINITIONS, SettingDefinition

PASSWORD_MASK = "********"


@dataclass
class CorrectionResult:
    """Result of input auto-correction for setting modification.

    Attributes:
        value: The corrected value to write.
        was_corrected: Whether auto-correction was applied.
        original_input: The user's original input string.
    """

    value: Any
    was_corrected: bool
    original_input: str


def is_password_setting(key: str) -> bool:
    """Check if a setting key is a password field.

    Args:
        key: The setting key name to check.

    Returns:
        True when key contains the substring "Password" (case-sensitive).
    """
    return "Password" in key


def validate_and_correct(key: str, value: str) -> CorrectionResult | str:
    """Validate and auto-correct a setting value based on its definition.

    Looks up the key in SETTING_DEFINITIONS internally. For keys not present
    in SETTING_DEFINITIONS, returns the value as-is without validation
    (per Requirement 6.9).

    Args:
        key: The setting key name.
        value: The user-provided value string.

    Returns:
        CorrectionResult with the corrected value on success, or an error
        message string on validation failure.
    """
    definition = SETTING_DEFINITIONS.get(key)

    if definition is None:
        # Unknown setting: return as-is without validation
        return CorrectionResult(value=value, was_corrected=False, original_input=value)

    return _validate_and_correct(key, value, definition)


def _validate_and_correct(
    key: str, value: str, definition: SettingDefinition
) -> CorrectionResult | str:
    """Validate and auto-correct a value based on its setting definition.

    Args:
        key: The setting key name.
        value: The user-provided value string.
        definition: The SettingDefinition for this setting.

    Returns:
        CorrectionResult with the corrected value on success, or an error
        message string on validation failure.
    """
    if definition.value_type == str:
        if definition.allowed_values is not None:
            # Enum validation: check against allowed_values list
            return _validate_enum(key, value, definition)
        else:
            # String auto-correction: handle quoting
            return _correct_string(value)
    elif definition.value_type == bool:
        return _correct_boolean(key, value)
    elif definition.value_type == int:
        return _validate_integer(key, value, definition)
    elif definition.value_type == float:
        return _validate_float(key, value, definition)

    # Fallback: pass as-is
    return CorrectionResult(value=value, was_corrected=False, original_input=value)


def _correct_string(value: str) -> CorrectionResult:
    """Auto-correct string values by handling quoting.

    - If already quoted with "...", strip outer quotes and pass inner content.
    - If not quoted, pass as-is (SettingsParser._format_value adds quotes on write).

    Args:
        value: The user-provided value string.

    Returns:
        CorrectionResult with the corrected string value.
    """
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        # Already quoted: strip outer quotes, pass inner content
        inner = value[1:-1]
        return CorrectionResult(
            value=inner, was_corrected=True, original_input=value
        )
    else:
        # Not quoted: pass as-is (write_setting will add quotes via _format_value)
        return CorrectionResult(
            value=value, was_corrected=False, original_input=value
        )


def _correct_boolean(key: str, value: str) -> CorrectionResult | str:
    """Normalize boolean values to canonical True/False form.

    Args:
        key: The setting key name (for error messages).
        value: The user-provided value string.

    Returns:
        CorrectionResult with normalized boolean, or error message string.
    """
    lower = value.lower()
    if lower == "true":
        normalized = "True"
    elif lower == "false":
        normalized = "False"
    else:
        return (
            f"Error: Setting '{key}' must be a boolean (True/False), "
            f"got: '{value}'"
        )

    was_corrected = value != normalized
    return CorrectionResult(
        value=normalized, was_corrected=was_corrected, original_input=value
    )


def _validate_integer(
    key: str, value: str, definition: SettingDefinition
) -> CorrectionResult | str:
    """Validate and parse an integer value, checking range constraints.

    Args:
        key: The setting key name (for error messages).
        value: The user-provided value string.
        definition: The SettingDefinition with min/max constraints.

    Returns:
        CorrectionResult with the parsed int, or error message string.
    """
    try:
        int_value = int(value)
    except ValueError:
        return (
            f"Error: Setting '{key}' must be an integer, got: '{value}'"
        )

    # Range validation
    if definition.min_value is not None and int_value < definition.min_value:
        return (
            f"Error: Setting '{key}' value {int_value} is out of range. "
            f"Allowed range: {definition.min_value} to {definition.max_value}."
        )
    if definition.max_value is not None and int_value > definition.max_value:
        return (
            f"Error: Setting '{key}' value {int_value} is out of range. "
            f"Allowed range: {definition.min_value} to {definition.max_value}."
        )

    return CorrectionResult(
        value=int_value, was_corrected=False, original_input=value
    )


def _validate_float(
    key: str, value: str, definition: SettingDefinition
) -> CorrectionResult | str:
    """Validate and parse a float value, checking range constraints.

    Args:
        key: The setting key name (for error messages).
        value: The user-provided value string.
        definition: The SettingDefinition with min/max constraints.

    Returns:
        CorrectionResult with the parsed float, or error message string.
    """
    try:
        float_value = float(value)
    except ValueError:
        return (
            f"Error: Setting '{key}' must be a float, got: '{value}'"
        )

    # Range validation
    if definition.min_value is not None and float_value < definition.min_value:
        return (
            f"Error: Setting '{key}' value {float_value} is out of range. "
            f"Allowed range: {definition.min_value} to {definition.max_value}."
        )
    if definition.max_value is not None and float_value > definition.max_value:
        return (
            f"Error: Setting '{key}' value {float_value} is out of range. "
            f"Allowed range: {definition.min_value} to {definition.max_value}."
        )

    was_corrected = value != f"{float_value:.6f}"
    return CorrectionResult(
        value=float_value, was_corrected=was_corrected, original_input=value
    )


def _validate_enum(
    key: str, value: str, definition: SettingDefinition
) -> CorrectionResult | str:
    """Validate a value against an enum-type setting's allowed values.

    Args:
        key: The setting key name (for error messages).
        value: The user-provided value string.
        definition: The SettingDefinition with allowed_values list.

    Returns:
        CorrectionResult with the value as-is, or error message string.
    """
    if value not in definition.allowed_values:
        allowed = ", ".join(definition.allowed_values)
        return (
            f"Error: Setting '{key}' value '{value}' is not valid. "
            f"Allowed values: {allowed}"
        )

    return CorrectionResult(
        value=value, was_corrected=False, original_input=value
    )
