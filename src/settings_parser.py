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
        description: Human-readable explanation of the setting (max 120 chars).
        default_value: The server's documented default value (None if unknown).
        category: Grouping category matching official docs (Performances,
            Server management, Features, Game balances).
        raw_string: If True, string values are written without surrounding quotes.
            Used for parenthesized list values like CrossplayPlatforms.
    """

    name: str
    value_type: type  # int, float, str, bool
    min_value: Any = None
    max_value: Any = None
    allowed_values: list[Any] | None = None
    description: str = ""
    default_value: Any = None
    category: str = ""
    raw_string: bool = False


# Canonical category ordering matching the official Palworld Server Guide.
SETTING_CATEGORIES: list[str] = [
    "Performances",
    "Server management",
    "Features",
    "Game balances",
]


# Complete Palworld server setting definitions with types, ranges, and defaults.
# Sources: official Palworld Server Guide and DefaultPalWorldSettings.ini.
SETTING_DEFINITIONS: dict[str, SettingDefinition] = {
    # --- Game balances: Rate multipliers ---
    "DayTimeSpeedRate": SettingDefinition(
        name="DayTimeSpeedRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Daytime progression speed.",
        default_value=1.0,
        category="Game balances",
    ),
    "NightTimeSpeedRate": SettingDefinition(
        name="NightTimeSpeedRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Nighttime progression speed.",
        default_value=1.0,
        category="Game balances",
    ),
    "ExpRate": SettingDefinition(
        name="ExpRate",
        value_type=float,
        min_value=0.1,
        max_value=20.0,
        description="EXP gain multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "PalCaptureRate": SettingDefinition(
        name="PalCaptureRate",
        value_type=float,
        min_value=0.5,
        max_value=2.0,
        description="Capture rate multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "PalSpawnNumRate": SettingDefinition(
        name="PalSpawnNumRate",
        value_type=float,
        min_value=0.5,
        max_value=3.0,
        description="Pal spawn rate. Impacts performance.",
        default_value=1.0,
        category="Game balances",
    ),
    "PalDamageRateAttack": SettingDefinition(
        name="PalDamageRateAttack",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Damage dealt by Pals multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "PalDamageRateDefense": SettingDefinition(
        name="PalDamageRateDefense",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Damage taken by Pals multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "PlayerDamageRateAttack": SettingDefinition(
        name="PlayerDamageRateAttack",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Damage dealt by players multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "PlayerDamageRateDefense": SettingDefinition(
        name="PlayerDamageRateDefense",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Damage taken by players multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "PlayerStomachDecreaceRate": SettingDefinition(
        name="PlayerStomachDecreaceRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Player hunger depletion rate multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "PlayerStaminaDecreaceRate": SettingDefinition(
        name="PlayerStaminaDecreaceRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Player stamina depletion rate multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "PlayerAutoHPRegeneRate": SettingDefinition(
        name="PlayerAutoHPRegeneRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Player natural HP regen multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "PlayerAutoHpRegeneRateInSleep": SettingDefinition(
        name="PlayerAutoHpRegeneRateInSleep",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Player HP regen while sleeping multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "PalStomachDecreaceRate": SettingDefinition(
        name="PalStomachDecreaceRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Pal hunger depletion rate multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "PalStaminaDecreaceRate": SettingDefinition(
        name="PalStaminaDecreaceRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Pal stamina depletion rate multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "PalAutoHPRegeneRate": SettingDefinition(
        name="PalAutoHPRegeneRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Pal natural HP regen multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "PalAutoHpRegeneRateInSleep": SettingDefinition(
        name="PalAutoHpRegeneRateInSleep",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Pal HP regen while sleeping (in Palbox) multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "BuildObjectHpRate": SettingDefinition(
        name="BuildObjectHpRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Building HP multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "BuildObjectDamageRate": SettingDefinition(
        name="BuildObjectDamageRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Damage multiplier to buildings.",
        default_value=1.0,
        category="Game balances",
    ),
    "BuildObjectDeteriorationDamageRate": SettingDefinition(
        name="BuildObjectDeteriorationDamageRate",
        value_type=float,
        min_value=0.0,
        max_value=10.0,
        description="Building decay speed multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "CollectionDropRate": SettingDefinition(
        name="CollectionDropRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Gatherable items multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "CollectionObjectHpRate": SettingDefinition(
        name="CollectionObjectHpRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Gatherable objects health multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "CollectionObjectRespawnSpeedRate": SettingDefinition(
        name="CollectionObjectRespawnSpeedRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Gatherable objects respawn interval multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "EnemyDropItemRate": SettingDefinition(
        name="EnemyDropItemRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Dropped item quantity multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "EquipmentDurabilityDamageRate": SettingDefinition(
        name="EquipmentDurabilityDamageRate",
        value_type=float,
        min_value=0.0,
        max_value=5.0,
        description="Equipment durability loss multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "ItemWeightRate": SettingDefinition(
        name="ItemWeightRate",
        value_type=float,
        min_value=0.0,
        max_value=5.0,
        description="Item weight multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "ItemCorruptionMultiplier": SettingDefinition(
        name="ItemCorruptionMultiplier",
        value_type=float,
        min_value=0.0,
        max_value=10.0,
        description="Item corruption speed multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    "MonsterFarmActionSpeedRate": SettingDefinition(
        name="MonsterFarmActionSpeedRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Item production speed multiplier from ranch.",
        default_value=1.0,
        category="Game balances",
    ),
    "PalEggDefaultHatchingTime": SettingDefinition(
        name="PalEggDefaultHatchingTime",
        value_type=float,
        min_value=0.0,
        max_value=240.0,
        description="Time to hatch a Huge Egg (hours). Other eggs scale from this.",
        default_value=1.0,
        category="Game balances",
    ),
    "WorkSpeedRate": SettingDefinition(
        name="WorkSpeedRate",
        value_type=float,
        min_value=0.1,
        max_value=5.0,
        description="Pal work speed multiplier.",
        default_value=1.0,
        category="Game balances",
    ),
    # --- Game balances: Death and penalties ---
    "DeathPenalty": SettingDefinition(
        name="DeathPenalty",
        value_type=str,
        allowed_values=["None", "Item", "ItemAndEquipment", "All"],
        description="Items lost on death: None, Item, ItemAndEquipment, or All.",
        default_value="Item",
        category="Game balances",
        raw_string=True,
    ),
    "BlockRespawnTime": SettingDefinition(
        name="BlockRespawnTime",
        value_type=float,
        min_value=0.0,
        max_value=60.0,
        description="Cooldown before you can respawn after death (seconds).",
        default_value=5.0,
        category="Game balances",
    ),
    "RespawnPenaltyDurationThreshold": SettingDefinition(
        name="RespawnPenaltyDurationThreshold",
        value_type=float,
        min_value=0.0,
        max_value=3600.0,
        description="Survival-time threshold (sec) for applying respawn penalty.",
        default_value=0.0,
        category="Game balances",
    ),
    "RespawnPenaltyTimeScale": SettingDefinition(
        name="RespawnPenaltyTimeScale",
        value_type=float,
        min_value=0.0,
        max_value=10.0,
        description="Multiplier applied to the respawn cooldown.",
        default_value=2.0,
        category="Game balances",
    ),
    # --- Game balances: Guilds ---
    "GuildPlayerMaxNum": SettingDefinition(
        name="GuildPlayerMaxNum",
        value_type=int,
        min_value=1,
        max_value=100,
        description="Max player number per guild.",
        default_value=20,
        category="Game balances",
    ),
    "GuildRejoinCooldownMinutes": SettingDefinition(
        name="GuildRejoinCooldownMinutes",
        value_type=int,
        min_value=0,
        max_value=10080,
        description="Guild rejoin cooldown (minutes).",
        default_value=0,
        category="Game balances",
    ),
    # --- Game balances: PvP ---
    "bAdditionalDropItemWhenPlayerKillingInPvPMode": SettingDefinition(
        name="bAdditionalDropItemWhenPlayerKillingInPvPMode",
        value_type=bool,
        description="Drop a special item when killing a player in PvP.",
        default_value=False,
        category="Game balances",
    ),
    "AdditionalDropItemWhenPlayerKillingInPvPMode": SettingDefinition(
        name="AdditionalDropItemWhenPlayerKillingInPvPMode",
        value_type=str,
        description="Item ID to drop when killing a player in PvP.",
        default_value="PlayerDropItem",
        category="Game balances",
    ),
    "AdditionalDropItemNumWhenPlayerKillingInPvPMode": SettingDefinition(
        name="AdditionalDropItemNumWhenPlayerKillingInPvPMode",
        value_type=int,
        min_value=0,
        max_value=100,
        description="Quantity of item to drop on PvP kill.",
        default_value=1,
        category="Game balances",
    ),
    "bDisplayPvPItemNumOnWorldMap_BaseCamp": SettingDefinition(
        name="bDisplayPvPItemNumOnWorldMap_BaseCamp",
        value_type=bool,
        description="Show PvP-exclusive item count per base on map.",
        default_value=False,
        category="Features",
    ),
    "bDisplayPvPItemNumOnWorldMap_Player": SettingDefinition(
        name="bDisplayPvPItemNumOnWorldMap_Player",
        value_type=bool,
        description="Show player locations and PvP item count on map.",
        default_value=False,
        category="Features",
    ),
    # --- Game balances: Misc ---
    "Difficulty": SettingDefinition(
        name="Difficulty",
        value_type=str,
        allowed_values=["None", "Normal", "Difficult"],
        description="Server difficulty preset.",
        default_value="None",
        category="Game balances",
        raw_string=True,
    ),
    "SupplyDropSpan": SettingDefinition(
        name="SupplyDropSpan",
        value_type=int,
        min_value=0,
        max_value=9999,
        description="Meteorite / supply drop interval (minutes).",
        default_value=180,
        category="Game balances",
    ),
    "DenyTechnologyList": SettingDefinition(
        name="DenyTechnologyList",
        value_type=str,
        description="Comma-separated Technology IDs to disable.",
        default_value="",
        category="Game balances",
        raw_string=True,
    ),
    # --- Features: Boolean toggles ---
    "bEnablePlayerToPlayerDamage": SettingDefinition(
        name="bEnablePlayerToPlayerDamage",
        value_type=bool,
        description="Enable damage between players.",
        default_value=False,
        category="Features",
    ),
    "bEnableFriendlyFire": SettingDefinition(
        name="bEnableFriendlyFire",
        value_type=bool,
        description="Enable friendly fire within the same guild.",
        default_value=False,
        category="Features",
    ),
    "bEnableInvaderEnemy": SettingDefinition(
        name="bEnableInvaderEnemy",
        value_type=bool,
        description="Enable base invasion events.",
        default_value=True,
        category="Features",
    ),
    "bActiveUNKO": SettingDefinition(
        name="bActiveUNKO",
        value_type=bool,
        description="Enable UNKO system.",
        default_value=False,
        category="Features",
    ),
    "bEnableAimAssistPad": SettingDefinition(
        name="bEnableAimAssistPad",
        value_type=bool,
        description="Enable aim assist for controller.",
        default_value=True,
        category="Features",
    ),
    "bEnableAimAssistKeyboard": SettingDefinition(
        name="bEnableAimAssistKeyboard",
        value_type=bool,
        description="Enable aim assist for keyboard/mouse.",
        default_value=False,
        category="Features",
    ),
    "bIsMultiplay": SettingDefinition(
        name="bIsMultiplay",
        value_type=bool,
        description="Enable multiplayer mode.",
        default_value=False,
        category="Features",
    ),
    "bIsPvP": SettingDefinition(
        name="bIsPvP",
        value_type=bool,
        description="Enable PvP mode.",
        default_value=False,
        category="Features",
    ),
    "bHardcore": SettingDefinition(
        name="bHardcore",
        value_type=bool,
        description="Enable Hardcore mode. Cannot respawn on death.",
        default_value=False,
        category="Features",
    ),
    "bPalLost": SettingDefinition(
        name="bPalLost",
        value_type=bool,
        description="Permanently lose Pals on death.",
        default_value=False,
        category="Features",
    ),
    "bCharacterRecreateInHardcore": SettingDefinition(
        name="bCharacterRecreateInHardcore",
        value_type=bool,
        description="Allow character recreation upon death in Hardcore.",
        default_value=False,
        category="Features",
    ),
    "bCanPickupOtherGuildDeathPenaltyDrop": SettingDefinition(
        name="bCanPickupOtherGuildDeathPenaltyDrop",
        value_type=bool,
        description="Allow picking up death drops from other guilds.",
        default_value=False,
        category="Features",
    ),
    "bEnableNonLoginPenalty": SettingDefinition(
        name="bEnableNonLoginPenalty",
        value_type=bool,
        description="Enable penalties for not logging in.",
        default_value=True,
        category="Features",
    ),
    "bEnableFastTravel": SettingDefinition(
        name="bEnableFastTravel",
        value_type=bool,
        description="Enable fast travel.",
        default_value=True,
        category="Features",
    ),
    "bEnableFastTravelOnlyBaseCamp": SettingDefinition(
        name="bEnableFastTravelOnlyBaseCamp",
        value_type=bool,
        description="Restrict fast travel to between bases only.",
        default_value=False,
        category="Features",
    ),
    "bIsStartLocationSelectByMap": SettingDefinition(
        name="bIsStartLocationSelectByMap",
        value_type=bool,
        description="Allow players to choose their starting location.",
        default_value=False,
        category="Features",
    ),
    "bExistPlayerAfterLogout": SettingDefinition(
        name="bExistPlayerAfterLogout",
        value_type=bool,
        description="Players enter a sleeping state when logging out.",
        default_value=False,
        category="Features",
    ),
    "bEnableDefenseOtherGuildPlayer": SettingDefinition(
        name="bEnableDefenseOtherGuildPlayer",
        value_type=bool,
        description="Enable defense against other guild players.",
        default_value=False,
        category="Features",
    ),
    "bInvisibleOtherGuildBaseCampAreaFX": SettingDefinition(
        name="bInvisibleOtherGuildBaseCampAreaFX",
        value_type=bool,
        description="Show base area boundaries.",
        default_value=False,
        category="Features",
    ),
    "bBuildAreaLimit": SettingDefinition(
        name="bBuildAreaLimit",
        value_type=bool,
        description="Prevent building near fast-travel points.",
        default_value=False,
        category="Features",
    ),
    "bAutoResetGuildNoOnlinePlayers": SettingDefinition(
        name="bAutoResetGuildNoOnlinePlayers",
        value_type=bool,
        description="Auto-delete structures/Pals if no guild members log in.",
        default_value=False,
        category="Features",
    ),
    "AutoResetGuildTimeNoOnlinePlayers": SettingDefinition(
        name="AutoResetGuildTimeNoOnlinePlayers",
        value_type=float,
        min_value=1.0,
        max_value=8760.0,
        description="Offline hours before auto-reset triggers.",
        default_value=72.0,
        category="Features",
    ),
    "bEnableVoiceChat": SettingDefinition(
        name="bEnableVoiceChat",
        value_type=bool,
        description="Enable in-game voice chat.",
        default_value=False,
        category="Features",
    ),
    "VoiceChatMaxVolumeDistance": SettingDefinition(
        name="VoiceChatMaxVolumeDistance",
        value_type=float,
        min_value=0.0,
        max_value=50000.0,
        description="Distance at which voice chat volume does not attenuate.",
        default_value=3000.0,
        category="Features",
    ),
    "VoiceChatZeroVolumeDistance": SettingDefinition(
        name="VoiceChatZeroVolumeDistance",
        value_type=float,
        min_value=0.0,
        max_value=50000.0,
        description="Distance at which voice chat volume becomes zero.",
        default_value=15000.0,
        category="Features",
    ),
    "bAllowEnhanceStat_Health": SettingDefinition(
        name="bAllowEnhanceStat_Health",
        value_type=bool,
        description="Allow allocating stat points to HP.",
        default_value=True,
        category="Features",
    ),
    "bAllowEnhanceStat_Attack": SettingDefinition(
        name="bAllowEnhanceStat_Attack",
        value_type=bool,
        description="Allow allocating stat points to Attack.",
        default_value=True,
        category="Features",
    ),
    "bAllowEnhanceStat_Stamina": SettingDefinition(
        name="bAllowEnhanceStat_Stamina",
        value_type=bool,
        description="Allow allocating stat points to Stamina.",
        default_value=True,
        category="Features",
    ),
    "bAllowEnhanceStat_Weight": SettingDefinition(
        name="bAllowEnhanceStat_Weight",
        value_type=bool,
        description="Allow allocating stat points to Carry Weight.",
        default_value=True,
        category="Features",
    ),
    "bAllowEnhanceStat_WorkSpeed": SettingDefinition(
        name="bAllowEnhanceStat_WorkSpeed",
        value_type=bool,
        description="Allow allocating stat points to Work Speed.",
        default_value=True,
        category="Features",
    ),
    "bAllowGlobalPalboxExport": SettingDefinition(
        name="bAllowGlobalPalboxExport",
        value_type=bool,
        description="Allow saving to the Global Palbox.",
        default_value=True,
        category="Features",
    ),
    "bAllowGlobalPalboxImport": SettingDefinition(
        name="bAllowGlobalPalboxImport",
        value_type=bool,
        description="Allow loading from the Global Palbox.",
        default_value=False,
        category="Features",
    ),
    "EnablePredatorBossPal": SettingDefinition(
        name="EnablePredatorBossPal",
        value_type=bool,
        description="Enable predator boss Pal spawns.",
        default_value=True,
        category="Features",
    ),
    "bEnableBuildingPlayerUIdDisplay": SettingDefinition(
        name="bEnableBuildingPlayerUIdDisplay",
        value_type=bool,
        description="Display the creator's player ID on structures.",
        default_value=False,
        category="Server management",
    ),
    "BuildingNameDisplayCacheTTLSeconds": SettingDefinition(
        name="BuildingNameDisplayCacheTTLSeconds",
        value_type=int,
        min_value=0,
        max_value=3600,
        description="Cache TTL for building player name display (seconds).",
        default_value=60,
        category="Server management",
    ),
    # --- Features: Randomizer ---
    "RandomizerType": SettingDefinition(
        name="RandomizerType",
        value_type=str,
        allowed_values=["None", "Region", "All"],
        description="Pal spawn randomization: None, Region, or All.",
        default_value="None",
        category="Features",
        raw_string=True,
    ),
    "RandomizerSeed": SettingDefinition(
        name="RandomizerSeed",
        value_type=str,
        description="Seed value for Pal spawn randomization.",
        default_value="",
        category="Features",
    ),
    "bIsRandomizerPalLevelRandom": SettingDefinition(
        name="bIsRandomizerPalLevelRandom",
        value_type=bool,
        description="If true, wild Pal levels are fully random.",
        default_value=False,
        category="Features",
    ),
    # --- Performances ---
    "BaseCampMaxNum": SettingDefinition(
        name="BaseCampMaxNum",
        value_type=int,
        min_value=1,
        max_value=5000,
        description="Total number of bases across the server.",
        default_value=128,
        category="Performances",
    ),
    "BaseCampMaxNumInGuild": SettingDefinition(
        name="BaseCampMaxNumInGuild",
        value_type=int,
        min_value=1,
        max_value=10,
        description="Maximum bases per guild. Increasing raises load.",
        default_value=4,
        category="Performances",
    ),
    "BaseCampWorkerMaxNum": SettingDefinition(
        name="BaseCampWorkerMaxNum",
        value_type=int,
        min_value=1,
        max_value=50,
        description="Maximum Pals per base. Increasing raises load.",
        default_value=15,
        category="Performances",
    ),
    "DropItemMaxNum": SettingDefinition(
        name="DropItemMaxNum",
        value_type=int,
        min_value=0,
        max_value=50000,
        description="Maximum number of dropped items in world.",
        default_value=3000,
        category="Game balances",
    ),
    "PhysicsActiveDropItemMaxNum": SettingDefinition(
        name="PhysicsActiveDropItemMaxNum",
        value_type=int,
        min_value=-1,
        max_value=50000,
        description="Max dropped items with active physics (-1 = unlimited).",
        default_value=-1,
        category="Performances",
    ),
    "DropItemMaxNum_UNKO": SettingDefinition(
        name="DropItemMaxNum_UNKO",
        value_type=int,
        min_value=0,
        max_value=5000,
        description="Maximum number of UNKO dropped items.",
        default_value=100,
        category="Game balances",
    ),
    "DropItemAliveMaxHours": SettingDefinition(
        name="DropItemAliveMaxHours",
        value_type=float,
        min_value=0.0,
        max_value=24.0,
        description="Hours before dropped items despawn.",
        default_value=1.0,
        category="Game balances",
    ),
    "MaxBuildingLimitNum": SettingDefinition(
        name="MaxBuildingLimitNum",
        value_type=int,
        min_value=0,
        max_value=100000,
        description="Per-player building count cap (0 = unlimited).",
        default_value=0,
        category="Performances",
    ),
    "ServerReplicatePawnCullDistance": SettingDefinition(
        name="ServerReplicatePawnCullDistance",
        value_type=float,
        min_value=5000.0,
        max_value=15000.0,
        description="Pal sync distance from players (cm). 5000\u201315000.",
        default_value=15000.0,
        category="Performances",
    ),
    "ItemContainerForceMarkDirtyInterval": SettingDefinition(
        name="ItemContainerForceMarkDirtyInterval",
        value_type=float,
        min_value=0.1,
        max_value=60.0,
        description="Container UI re-sync interval (seconds).",
        default_value=1.0,
        category="Performances",
    ),
    "PlayerDataPalStorageUpdateCheckTickInterval": SettingDefinition(
        name="PlayerDataPalStorageUpdateCheckTickInterval",
        value_type=float,
        min_value=0.1,
        max_value=60.0,
        description="Pal storage update check interval (seconds).",
        default_value=1.0,
        category="Performances",
    ),
    "MaxGuildsPerFrame": SettingDefinition(
        name="MaxGuildsPerFrame",
        value_type=int,
        min_value=1,
        max_value=100,
        description="Max guilds processed per server frame.",
        default_value=10,
        category="Performances",
    ),
    "AutoTransferMasterCheckIntervalSeconds": SettingDefinition(
        name="AutoTransferMasterCheckIntervalSeconds",
        value_type=float,
        min_value=60.0,
        max_value=86400.0,
        description="Interval for auto guild master transfer checks (sec).",
        default_value=3600.0,
        category="Performances",
    ),
    "AutoTransferMasterThresholdDays": SettingDefinition(
        name="AutoTransferMasterThresholdDays",
        value_type=int,
        min_value=1,
        max_value=365,
        description="Days offline before guild master auto-transfers.",
        default_value=14,
        category="Performances",
    ),
    # --- Server management ---
    "ServerPlayerMaxNum": SettingDefinition(
        name="ServerPlayerMaxNum",
        value_type=int,
        min_value=1,
        max_value=32,
        description="Maximum number of players who can join the server.",
        default_value=32,
        category="Server management",
    ),
    "CoopPlayerMaxNum": SettingDefinition(
        name="CoopPlayerMaxNum",
        value_type=int,
        min_value=1,
        max_value=32,
        description="Maximum players in co-op session.",
        default_value=4,
        category="Server management",
    ),
    "ServerName": SettingDefinition(
        name="ServerName",
        value_type=str,
        description="Server name displayed in server browser.",
        default_value="Default Palworld Server",
        category="Server management",
    ),
    "ServerDescription": SettingDefinition(
        name="ServerDescription",
        value_type=str,
        description="Server description shown in server browser.",
        default_value="",
        category="Server management",
    ),
    "AdminPassword": SettingDefinition(
        name="AdminPassword",
        value_type=str,
        description="Password for obtaining admin privileges.",
        default_value="",
        category="Server management",
    ),
    "ServerPassword": SettingDefinition(
        name="ServerPassword",
        value_type=str,
        description="Password required to log in to the server.",
        default_value="",
        category="Server management",
    ),
    "PublicPort": SettingDefinition(
        name="PublicPort",
        value_type=int,
        min_value=1024,
        max_value=65535,
        description="External public port (does not change listening port).",
        default_value=8211,
        category="Server management",
    ),
    "PublicIP": SettingDefinition(
        name="PublicIP",
        value_type=str,
        description="Explicitly specify the external public IP.",
        default_value="",
        category="Server management",
    ),
    "RCONEnabled": SettingDefinition(
        name="RCONEnabled",
        value_type=bool,
        description="Enable RCON remote administration.",
        default_value=False,
        category="Server management",
    ),
    "RCONPort": SettingDefinition(
        name="RCONPort",
        value_type=int,
        min_value=1024,
        max_value=65535,
        description="Port number used for RCON.",
        default_value=25575,
        category="Server management",
    ),
    "Region": SettingDefinition(
        name="Region",
        value_type=str,
        description="Server region identifier.",
        default_value="",
        category="Server management",
    ),
    "bUseAuth": SettingDefinition(
        name="bUseAuth",
        value_type=bool,
        description="Enable authentication system.",
        default_value=True,
        category="Server management",
    ),
    "BanListURL": SettingDefinition(
        name="BanListURL",
        value_type=str,
        description="URL for the server ban list.",
        default_value="https://b.palworldgame.com/api/banlist.txt",
        category="Server management",
    ),
    "RESTAPIEnabled": SettingDefinition(
        name="RESTAPIEnabled",
        value_type=bool,
        description="Enable the REST API.",
        default_value=False,
        category="Server management",
    ),
    "RESTAPIPort": SettingDefinition(
        name="RESTAPIPort",
        value_type=int,
        min_value=1024,
        max_value=65535,
        description="Listening port for the REST API.",
        default_value=8212,
        category="Server management",
    ),
    "bShowPlayerList": SettingDefinition(
        name="bShowPlayerList",
        value_type=bool,
        description="Enable the player list on the ESC menu.",
        default_value=False,
        category="Features",
    ),
    "ChatPostLimitPerMinute": SettingDefinition(
        name="ChatPostLimitPerMinute",
        value_type=int,
        min_value=1,
        max_value=999,
        description="Maximum chat messages allowed per minute.",
        default_value=30,
        category="Server management",
    ),
    "CrossplayPlatforms": SettingDefinition(
        name="CrossplayPlatforms",
        value_type=str,
        description="Allowed platforms to connect: (Steam,Xbox,PS5,Mac).",
        default_value="(Steam,Xbox,PS5,Mac)",
        category="Server management",
        raw_string=True,
    ),
    "bAllowClientMod": SettingDefinition(
        name="bAllowClientMod",
        value_type=bool,
        description="Allow players with mods to join the server.",
        default_value=True,
        category="Server management",
    ),
    "LogFormatType": SettingDefinition(
        name="LogFormatType",
        value_type=str,
        allowed_values=["Text", "Json"],
        description="Log format: Text or Json.",
        default_value="Text",
        category="Server management",
        raw_string=True,
    ),
    "bIsShowJoinLeftMessage": SettingDefinition(
        name="bIsShowJoinLeftMessage",
        value_type=bool,
        description="Show in-game messages when players join/leave.",
        default_value=True,
        category="Server management",
    ),
    "bIsUseBackupSaveData": SettingDefinition(
        name="bIsUseBackupSaveData",
        value_type=bool,
        description="Enable world backups. Increases disk load.",
        default_value=True,
        category="Server management",
    ),
    "AutoSaveSpan": SettingDefinition(
        name="AutoSaveSpan",
        value_type=float,
        min_value=1.0,
        max_value=3600.0,
        description="Auto-save interval (seconds).",
        default_value=30.0,
        category="Server management",
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
            # String type: strip surrounding quotes if present
            if raw_value.startswith('"') and raw_value.endswith('"'):
                return raw_value[1:-1]
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
                if definition.raw_string:
                    return str(value)
                return f'"{value}"'

        return str(value)
