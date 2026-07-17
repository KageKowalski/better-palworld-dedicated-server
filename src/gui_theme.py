"""Theme_Engine for the Palworld Server Wrapper GUI.

Single source of truth for all visual constants (colors, fonts, spacing) and
helper functions used by CustomTkinter widget classes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import customtkinter

# === Colors (Palworld Palette) ===
COLOR_BASE_BG: str = "#0b1626"          # Dark Navy — window & base background
COLOR_CARD_BG: str = "#1a2a3f"          # Card background (lighter than base)
COLOR_PRIMARY: str = "#1b66df"          # Vibrant Blue — buttons, focus borders
COLOR_ACCENT: str = "#ffd400"           # Bright Yellow — running state, pending, headers
COLOR_ALERT: str = "#f73f00"            # Deep Orange/Red — errors
COLOR_TEXT: str = "#ffffff"             # White — primary text
COLOR_TEXT_SECONDARY: str = "#b0b8c4"   # Muted text for descriptions
COLOR_DISABLED: str = "#4a4a4a"         # Gray — disabled buttons
COLOR_SUCCESS: str = "#2ecc71"          # Green — success notifications
COLOR_INPUT_BG: str = "#253a54"         # Text area / input background

# === Font Families ===
FONT_FAMILY_PRIMARY: tuple[str, ...] = ("Segoe UI", "Inter", "sans-serif")
FONT_FAMILY_MONO: tuple[str, ...] = ("Consolas", "Courier New", "monospace")

# === Font Sizes (pixels) ===
FONT_SIZE_HEADING: int = 16
FONT_SIZE_SUBHEADING: int = 13
FONT_SIZE_BODY: int = 12
FONT_SIZE_SMALL: int = 10

# === Font Tuples (family, size[, weight]) ===
FONT_HEADING: tuple[str, int, str] = (FONT_FAMILY_PRIMARY[0], FONT_SIZE_HEADING, "bold")
FONT_SUBHEADING: tuple[str, int, str] = (FONT_FAMILY_PRIMARY[0], FONT_SIZE_SUBHEADING, "bold")
FONT_BODY: tuple[str, int] = (FONT_FAMILY_PRIMARY[0], FONT_SIZE_BODY)
FONT_SMALL: tuple[str, int] = (FONT_FAMILY_PRIMARY[0], FONT_SIZE_SMALL)
FONT_MONO: tuple[str, int] = (FONT_FAMILY_MONO[0], FONT_SIZE_BODY)

# === Spacing / Layout ===
CARD_CORNER_RADIUS: int = 12
CARD_INNER_PADDING: int = 15
CARD_OUTER_MARGIN: int = 10            # padx/pady between card and parent
WIDGET_INNER_SPACING: int = 5          # padx/pady between widgets inside a card
BUTTON_CORNER_RADIUS: int = 8
NESTED_CARD_CORNER_RADIUS: int = 8     # For SettingRow cards


# === Helper Functions ===


def resolve_font_family() -> str:
    """Return the first available font family from the priority list.

    Iterates through FONT_FAMILY_PRIMARY and returns the first font that
    is available on the current system. Falls back to "TkDefaultFont" if
    none of the preferred fonts are installed.

    Returns:
        The resolved font family name string.
    """
    import tkinter.font as tkfont

    available = tkfont.families()
    for candidate in FONT_FAMILY_PRIMARY:
        if candidate in available:
            return candidate
    return "TkDefaultFont"


def create_card_frame(parent, **kwargs) -> "customtkinter.CTkFrame":
    """Create a consistently-styled Card_Frame container.

    Applies the standard card background color and corner radius from the
    theme constants. Any keyword arguments override the defaults.

    Args:
        parent: The parent widget for the new frame.
        **kwargs: Additional keyword arguments passed to CTkFrame.

    Returns:
        A configured CTkFrame instance.
    """
    import customtkinter

    defaults = {
        "fg_color": COLOR_CARD_BG,
        "corner_radius": CARD_CORNER_RADIUS,
    }
    defaults.update(kwargs)
    return customtkinter.CTkFrame(parent, **defaults)
