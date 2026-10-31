"""Packaged dashboard assets for the CFMoto integration.

Serves one fixed directory so the Lovelace card can be loaded from
``/cfmoto-static/cfmoto-vehicle-card.js`` without touching ``config/www``.
No dashboard or resource changes are made automatically.
"""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

CARD_URL = "/cfmoto-static/cfmoto-vehicle-card.js"
STATIC_PATH = "/cfmoto-static"
DATA_FRONTEND = f"{__package__}_frontend"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register the card directory once per Home Assistant instance."""
    if hass.data.get(DATA_FRONTEND):
        return
    http = getattr(hass, "http", None)
    if http is None:
        return
    await http.async_register_static_paths(
        [StaticPathConfig(STATIC_PATH, str(Path(__file__).parent / "frontend"), False)]
    )
    hass.data[DATA_FRONTEND] = True
