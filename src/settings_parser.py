"""Settings parser for PalWorldSettings.ini file management.

Handles reading, writing, and validating Palworld dedicated server settings
from the non-standard INI format used by PalWorldSettings.ini.

The file uses a single-line format under [/Script/Pal.PalGameWorldSettings]:
    OptionSettings=(Key1=Value1,Key2=Value2,...)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.models import ValidationResult


@dataclass
class SettingDefinition:
    """Defines the constraints for a single server setting.

    Attributes:
        name: The setting key name as it appears in the INI file.
        value_type: The Python type for this setting (int, float, str, bool).
        min_value: Minimum allowed value (for numeric types).
        max_value: Maximum allowed value (for numeric types).
        allowed_values: Explicit list of allowed values (for enum-like settings).
    """

    name: str
    value_type: type  # int, float, str, bool
    min_value: Any = None
    max_value: Any = None
    allowed_values: list[Any] | None = None


# Common Palworld server setting definitions with their types and ranges
SETTING_DEFINITIONS: dict[str, SettingDefinition] = {
    "DayTimeSpeedRate": SettingDefinition(
        name="DayTimeSpeedRate", value_type=float, min_value=0.1, max_value=5.0
    ),
    "NightTimeSpeedRate": SettingDefinition(
        name="NightTimeSpeedRate", value_type=float, min_value=0.1, max_value=5.0
    ),
    "ExpRate": SettingDefinition(
        name="ExpRate", value_type=float, min_value=0.1, max_value=20.0
    ),
    "PalCaptureRate": SettingDefinition(
        name="PalCaptureRate", value_type=float, min_value=0.5, max_value=2.0
    ),
    "PalSpawnNumRate": SettingDefinition(
        name="PalSpawnNumRate", value_type=float, min_value=0.5, max_value=3.0
    ),
    "PalDamageRateAttack": SettingDefinition(
        name="PalDamageRateAttack", value_type=float, min_value=0.1, max_value=5.0
    ),
    "PalDamageRateDefense": SettingDefinition(
        name="PalDamageRateDefense", value_type=float, min_value=0.1, max_value=5.0
    ),
    "PlayerDamageRateAttack": SettingDefinition(
        name="PlayerDamageRateAttack", value_type=float, min_value=0.1, max_value=5.0
    ),
    "PlayerDamageRateDefense": SettingDefinition(
        name="PlayerDamageRateDefense", value_type=float, min_value=0.1, max_value=5.0
    ),
    "PlayerStomachDecreaceRate": SettingDefinition(
        name="PlayerStomachDecreaceRate", value_type=float, min_value=0.1, max_value=5.0
    ),
    "PlayerStaminaDecreaceRate": SettingDefinition(
        name="PlayerStaminaDecreaceRate", value_type=float, min_value=0.1, max_value=5.0
    ),
    "PlayerAutoHPRegeneRate": SettingDefinition(
        name="PlayerAutoHPRegeneRate", value_type=float, min_value=0.1, max_value=5.0
    ),
    "PlayerAutoHpRegeneRateInSleep": SettingDefinition(
        name="PlayerAutoHpRegeneRateInSleep", value_type=float, min_value=0.1, max_value=5.0
    ),
    "PalStomachDecreaceRate": SettingDefinition(
        name="PalStomachDecreaceRate", value_type=float, min_value=0.1, max_value=5.0
    ),
    "PalStaminaDecreaceRate": SettingDefinition(
        name="PalStaminaDecreaceRate", value_type=float, min_value=0.1, max_value=5.0
    ),
    "PalAutoHPRegeneRate": SettingDefinition(
        name="PalAutoHPRegeneRate", value_type=float, min_value=0.1, max_value=5.0
    ),
    "PalAutoHpRegeneRateInSleep": SettingDefinition(
        name="PalAutoHpRegeneRateInSleep", value_type=float, min_value=0.1, max_value=5.0
    ),
    "BuildObjectDamageRate": SettingDefinition(
        name="BuildObjectDamageRate", value_type=float, min_value=0.1, max_value=5.0
    ),
    "BuildObjectDeteriorationDamageRate": SettingDefinition(
        name="BuildObjectDeteriorationDamageRate",
        value_type=float,
        min_value=0.0,
        max_value=10.0,
    ),
    "CollectionDropRate": SettingDefinition(
        name="CollectionDropRate", value_type=float, min_value=0.1, max_value=5.0
    ),
    "CollectionObjectHpRate": SettingDefinition(
        name="CollectionObjectHpRate", value_type=float, min_value=0.1, max_value=5.0
    ),
    "CollectionObjectRespawnSpeedRate": SettingDefinition(
        name="CollectionObjectRespawnSpeedRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
    ),
    "EnemyDropItemRate": SettingDefinition(
        name="EnemyDropItemRate", value_type=float, min_value=0.1, max_value=5.0
    ),
    "DeathPenalty": SettingDefinition(
        name="DeathPenalty",
        value_type=str,
        allowed_values=["None", "Item", "ItemAndEquipment", "All"],
    ),
    "Difficulty": SettingDefinition(
        name="Difficulty",
        value_type=str,
        allowed_values=["None", "Normal", "Difficult"],
    ),
    "bEnablePlayerToPlayerDamage": SettingDefinition(
        name="bEnablePlayerToPlayerDamage", value_type=bool
    ),
    "bEnableFriendlyFire": SettingDefinition(
        name="bEnableFriendlyFire", value_type=bool
    ),
    "bEnableInvaderEnemy": SettingDefinition(
        name="bEnableInvaderEnemy", value_type=bool
    ),
    "bActiveUNKO": SettingDefinition(name="bActiveUNKO", value_type=bool),
    "bIsPvP": SettingDefinition(name="bIsPvP", value_type=bool),
    "bCanPickupOtherGuildDeathPenaltyDrop": SettingDefinition(
        name="bCanPickupOtherGuildDeathPenaltyDrop", value_type=bool
    ),
    "ServerPlayerMaxNum": SettingDefinition(
        name="ServerPlayerMaxNum", value_type=int, min_value=1, max_value=32
    ),
    "GuildPlayerMaxNum": SettingDefinition(
        name="GuildPlayerMaxNum", value_type=int, min_value=1, max_value=100
    ),
    "PalEggDefaultHatchingTime": SettingDefinition(
        name="PalEggDefaultHatchingTime", value_type=float, min_value=0.0, max_value=240.0
    ),
    "WorkSpeedRate": SettingDefinition(
        name="WorkSpeedRate", value_type=float, min_value=0.1, max_value=5.0
    ),
    "ServerName": SettingDefinition(name="ServerName", value_type=str),
    "ServerDescription": SettingDefinition(name="ServerDescription", value_type=str),
    "AdminPassword": SettingDefinition(name="AdminPassword", value_type=str),
    "ServerPassword": SettingDefinition(name="ServerPassword", value_type=str),
    "PublicPort": SettingDefinition(
        name="PublicPort", value_type=int, min_value=1024, max_value=65535
    ),
    "RCONPort": SettingDefinition(
        name="RCONPort", value_type=int, min_value=1024, max_value=65535
    ),
    "bIsUseBackupSaveData": SettingDefinition(
        name="bIsUseBackupSaveData", value_type=bool
    ),
}


class SettingsParser:
    """Reads, writes, and validates PalWorldSettings.ini configuration.

    The PalWorldSettings.ini file uses a non-standard format:
        [/Script/Pal.PalGameWorldSettings]
        OptionSettings=(Key1=Value1,Key2=Value2,...)

    This parser handles extracting and modifying individual key=value pairs
    while preserving the rest of the file structure.
    """

    @staticmethod
    def read_settings(file_path: Path) -> dict[str, Any]:
        """Read all settings from a PalWorldSettings.ini file.

        Args:
            file_path: Path to the PalWorldSettings.ini file.

        Returns:
            Dictionary mapping setting names to their parsed values.
            Returns an empty dict with an "__error__" key if the file
            cannot be read or parsed.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"__error__": f"File not found: {file_path}"}
        except OSError as e:
            return {"__error__": f"Cannot read file: {e}"}

        return SettingsParser._parse_settings_content(content)

    @staticmethod
    def write_setting(file_path: Path, key: str, value: Any) -> ValidationResult:
        """Write a single setting value to the PalWorldSettings.ini file.

        Only modifies the specified key's value; all other file content
        is preserved exactly as-is.

        Args:
            file_path: Path to the PalWorldSettings.ini file.
            key: The setting key to modify.
            value: The new value to set.

        Returns:
            ValidationResult indicating success or failure with error message.
        """
        # Validate the setting before writing
        validation = SettingsParser.validate_setting(key, value)
        if not validation.valid:
            return validation

        # Read the file
        try:
            content = file_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ValidationResult(
                valid=False, error_message=f"File not found: {file_path}"
            )
        except OSError as e:
            return ValidationResult(
                valid=False, error_message=f"Cannot read file: {e}"
            )

        # Find and replace the specific key=value in the OptionSettings line
        new_content = SettingsParser._replace_setting_in_content(
            content, key, value
        )
        if new_content is None:
            return ValidationResult(
                valid=False,
                error_message=f"Could not find setting '{key}' in file or file is malformed",
            )

        # Write the modified content back
        try:
            file_path.write_text(new_content, encoding="utf-8")
        except OSError as e:
            return ValidationResult(
                valid=False, error_message=f"Cannot write file: {e}"
            )

        return ValidationResult(valid=True)

    @staticmethod
    def validate_setting(key: str, value: Any) -> ValidationResult:
        """Validate a setting value against its definition constraints.

        Args:
            key: The setting key name.
            value: The value to validate.

        Returns:
            ValidationResult indicating whether the value is valid.
        """
        definition = SETTING_DEFINITIONS.get(key)
        if definition is None:
            # Unknown settings are accepted without constraint checks
            return ValidationResult(valid=True)

        # Type validation
        if definition.value_type == bool:
            if not isinstance(value, bool) and value not in ("True", "False", True, False):
                return ValidationResult(
                    valid=False,
                    error_message=f"Setting '{key}' must be a boolean, got: {value!r}",
                )
        elif definition.value_type == int:
            try:
                int_value = int(value)
            except (ValueError, TypeError):
                return ValidationResult(
                    valid=False,
                    error_message=f"Setting '{key}' must be an integer, got: {value!r}",
                )
            # Range validation
            if definition.min_value is not None and int_value < definition.min_value:
                return ValidationResult(
                    valid=False,
                    error_message=(
                        f"Setting '{key}' value {int_value} is below "
                        f"minimum {definition.min_value}"
                    ),
                )
            if definition.max_value is not None and int_value > definition.max_value:
                return ValidationResult(
                    valid=False,
                    error_message=(
                        f"Setting '{key}' value {int_value} is above "
                        f"maximum {definition.max_value}"
                    ),
                )
        elif definition.value_type == float:
            try:
                float_value = float(value)
            except (ValueError, TypeError):
                return ValidationResult(
                    valid=False,
                    error_message=f"Setting '{key}' must be a float, got: {value!r}",
                )
            # Range validation
            if definition.min_value is not None and float_value < definition.min_value:
                return ValidationResult(
                    valid=False,
                    error_message=(
                        f"Setting '{key}' value {float_value} is below "
                        f"minimum {definition.min_value}"
                    ),
                )
            if definition.max_value is not None and float_value > definition.max_value:
                return ValidationResult(
                    valid=False,
                    error_message=(
                        f"Setting '{key}' value {float_value} is above "
                        f"maximum {definition.max_value}"
                    ),
                )
        elif definition.value_type == str:
            if not isinstance(value, str):
                return ValidationResult(
                    valid=False,
                    error_message=f"Setting '{key}' must be a string, got: {value!r}",
                )

        # Allowed values validation (for enum-like settings)
        if definition.allowed_values is not None:
            str_value = str(value)
            if str_value not in definition.allowed_values:
                return ValidationResult(
                    valid=False,
                    error_message=(
                        f"Setting '{key}' value '{str_value}' is not in "
                        f"allowed values: {definition.allowed_values}"
                    ),
                )

        return ValidationResult(valid=True)

    @staticmethod
    def get_setting_definitions() -> dict[str, SettingDefinition]:
        """Return all known setting definitions.

        Returns:
            Dictionary mapping setting names to their SettingDefinition objects.
        """
        return SETTING_DEFINITIONS.copy()

    @staticmethod
    def _parse_settings_content(content: str) -> dict[str, Any]:
        """Parse the OptionSettings line from file content.

        Args:
            content: The full file content as a string.

        Returns:
            Dictionary of parsed settings, or dict with "__error__" key on failure.
        """
        # Find the OptionSettings line
        option_settings_str = None
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("OptionSettings="):
                option_settings_str = stripped
                break

        if option_settings_str is None:
            return {"__error__": "Malformed file: no OptionSettings line found"}

        # Extract content between parentheses
        # Format: OptionSettings=(Key1=Value1,Key2=Value2,...)
        eq_pos = option_settings_str.index("=")
        remainder = option_settings_str[eq_pos + 1:]

        if not remainder.startswith("(") or not remainder.endswith(")"):
            return {"__error__": "Malformed file: OptionSettings value not wrapped in parentheses"}

        inner = remainder[1:-1]  # Strip the parentheses

        if not inner:
            return {}

        # Parse key=value pairs separated by commas
        settings: dict[str, Any] = {}
        pairs = SettingsParser._split_setting_pairs(inner)

        for pair in pairs:
            if "=" not in pair:
                continue
            key, _, raw_value = pair.partition("=")
            key = key.strip()
            raw_value = raw_value.strip()
            if key:
                settings[key] = SettingsParser._coerce_value(key, raw_value)

        return settings

    @staticmethod
    def _split_setting_pairs(inner: str) -> list[str]:
        """Split the inner OptionSettings content into key=value pairs.

        Handles nested parentheses (e.g., quoted strings with commas)
        by tracking parenthesis depth.

        Args:
            inner: The content inside the outer parentheses.

        Returns:
            List of key=value pair strings.
        """
        pairs = []
        current = []
        depth = 0

        for char in inner:
            if char == "(":
                depth += 1
                current.append(char)
            elif char == ")":
                depth -= 1
                current.append(char)
            elif char == "," and depth == 0:
                pairs.append("".join(current))
                current = []
            else:
                current.append(char)

        # Don't forget the last pair
        if current:
            pairs.append("".join(current))

        return pairs

    @staticmethod
    def _coerce_value(key: str, raw_value: str) -> Any:
        """Coerce a raw string value to its appropriate Python type.

        Uses the setting definition to determine the expected type.
        Falls back to string if no definition exists.

        Args:
            key: The setting key name.
            raw_value: The raw string value from the file.

        Returns:
            The value coerced to the appropriate type.
        """
        definition = SETTING_DEFINITIONS.get(key)
        if definition is None:
            return raw_value

        if definition.value_type == bool:
            return raw_value.lower() == "true"
        elif definition.value_type == int:
            try:
                return int(raw_value)
            except ValueError:
                return raw_value
        elif definition.value_type == float:
            try:
                return float(raw_value)
            except ValueError:
                return raw_value
        else:
            return raw_value

    @staticmethod
    def _replace_setting_in_content(
        content: str, key: str, value: Any
    ) -> str | None:
        """Replace a single setting value in the file content.

        Preserves the entire file structure, only modifying the target
        key's value within the OptionSettings line.

        Args:
            content: The full file content.
            key: The setting key to modify.
            value: The new value to set.

        Returns:
            The modified file content, or None if the key was not found
            or the file is malformed.
        """
        lines = content.splitlines(keepends=True)
        option_line_idx = None

        for idx, line in enumerate(lines):
            if line.strip().startswith("OptionSettings="):
                option_line_idx = idx
                break

        if option_line_idx is None:
            return None

        original_line = lines[option_line_idx]
        stripped = original_line.strip()

        # Find the OptionSettings=(...) portion
        eq_pos = stripped.index("=")
        remainder = stripped[eq_pos + 1:]

        if not remainder.startswith("(") or not remainder.endswith(")"):
            return None

        inner = remainder[1:-1]

        # Format the value for writing
        formatted_value = SettingsParser._format_value(key, value)

        # Find and replace the specific key=value pair
        pairs = SettingsParser._split_setting_pairs(inner)
        found = False
        new_pairs = []

        for pair in pairs:
            if "=" not in pair:
                new_pairs.append(pair)
                continue
            pair_key, _, _ = pair.partition("=")
            if pair_key.strip() == key:
                new_pairs.append(f"{key}={formatted_value}")
                found = True
            else:
                new_pairs.append(pair)

        if not found:
            return None

        # Reconstruct the OptionSettings line
        new_inner = ",".join(new_pairs)
        new_option_line = f"OptionSettings=({new_inner})"

        # Preserve the original line's leading whitespace and trailing newline
        leading_whitespace = original_line[: len(original_line) - len(original_line.lstrip())]
        trailing = ""
        if original_line.endswith("\r\n"):
            trailing = "\r\n"
        elif original_line.endswith("\n"):
            trailing = "\n"

        lines[option_line_idx] = leading_whitespace + new_option_line + trailing
        return "".join(lines)

    @staticmethod
    def _format_value(key: str, value: Any) -> str:
        """Format a value for writing to the INI file.

        Args:
            key: The setting key (used to look up type definition).
            value: The value to format.

        Returns:
            String representation suitable for the INI file.
        """
        definition = SETTING_DEFINITIONS.get(key)

        if definition is not None:
            if definition.value_type == bool:
                if isinstance(value, bool):
                    return "True" if value else "False"
                return str(value)
            elif definition.value_type == float:
                float_val = float(value)
                return f"{float_val:.6f}"
            elif definition.value_type == int:
                return str(int(value))
            elif definition.value_type == str:
                return f'"{value}"'

        return str(value)
