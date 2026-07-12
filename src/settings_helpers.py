"""Pure formatting functions for setting metadata display.

Derives display strings from SettingDefinition metadata for use in the
unified SettingsPanel. All functions are deterministic and side-effect free.
"""

from typing import Any

from src.settings_parser import SettingDefinition
from src.validation import is_password_setting

PASSWORD_MASK = "********"


def format_allowed_values(definition: SettingDefinition | None) -> str:
    """Return the allowed values display string for a setting.

    Args:
        definition: The setting's definition, or None for unknown settings.

    Returns:
        A human-readable string describing what values are valid.
    """
    if definition is None:
        return "Unknown"

    if definition.value_type == bool:
        return "True / False"

    if definition.value_type in (int, float):
        has_min = definition.min_value is not None
        has_max = definition.max_value is not None
        if has_min and has_max:
            return f"{definition.min_value} \u2013 {definition.max_value}"
        if has_min:
            return f"{definition.min_value} or above"
        if has_max:
            return f"{definition.max_value} or below"
        return "Any number"

    if definition.allowed_values is not None:
        return ", ".join(str(v) for v in definition.allowed_values)

    return "Any text"


def format_default_value(key: str, definition: SettingDefinition | None) -> str:
    """Return the default value display string, with password masking.

    Args:
        key: The setting key name.
        definition: The setting's definition, or None for unknown settings.

    Returns:
        The formatted default value, masked if password, or "Unknown" if
        no definition or default is available.
    """
    if definition is None or definition.default_value is None:
        return "Unknown"

    if is_password_setting(key):
        return PASSWORD_MASK

    return str(definition.default_value)


def format_current_value(key: str, value: str | None) -> str:
    """Return the current value display string, with password masking.

    Args:
        key: The setting key name.
        value: The current value read from the settings file, or None.

    Returns:
        The formatted current value, masked if password, or empty string
        if value is None.
    """
    if value is None:
        return ""

    if is_password_setting(key):
        return PASSWORD_MASK

    return value


def values_differ(
    current: str, default: Any, definition: SettingDefinition | None
) -> bool:
    """Compare current and default values using type-appropriate coercion.

    Args:
        current: The current value as a string from the settings file.
        default: The default value from the definition (typed).
        definition: The setting's definition for type information.

    Returns:
        True if the values are semantically different, False otherwise.
        Returns False if default is None (can't compare).
    """
    if default is None:
        return False

    if definition is not None and definition.value_type == bool:
        # Compare boolean interpretation of current string vs default bool
        current_bool = current.lower() == "true"
        return current_bool != default

    if definition is not None and definition.value_type in (int, float):
        try:
            current_num = definition.value_type(current)
            return current_num != default
        except (ValueError, TypeError):
            # Can't convert — treat as different
            return True

    # String comparison (or definition is None)
    return current != str(default)


def get_input_control_type(definition: SettingDefinition | None) -> str:
    """Return 'combobox' or 'entry' based on value type and constraints.

    Args:
        definition: The setting's definition, or None for unknown settings.

    Returns:
        "combobox" for boolean types or settings with allowed_values,
        "entry" for everything else.
    """
    if definition is None:
        return "entry"

    if definition.value_type == bool:
        return "combobox"

    if definition.allowed_values is not None and len(definition.allowed_values) > 0:
        return "combobox"

    return "entry"
