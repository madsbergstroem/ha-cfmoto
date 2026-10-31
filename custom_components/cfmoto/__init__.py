"""CFMoto cloud integration for Home Assistant."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CfMotoClient
from .const import (
    CONF_AREA,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    DEFAULT_AREA,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)
from .coordinator import CfMotoCoordinator
from .frontend import async_register_frontend

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CFMoto from a config entry."""
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    area = entry.data.get(CONF_AREA, DEFAULT_AREA)
    poll_interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)

    session = async_get_clientsession(hass)
    client = CfMotoClient(session, email, password, area)
    coordinator = CfMotoCoordinator(hass, client, poll_interval)
    coordinator.ble_lock = asyncio.Lock()  # serializes BLE command sessions

    await coordinator.async_config_entry_first_refresh()

    await async_register_frontend(hass)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(
        entry.add_update_listener(_async_update_options)
    )
    return True


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update the coordinator poll interval when options change."""
    coordinator: CfMotoCoordinator = hass.data[DOMAIN][entry.entry_id]
    poll_interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
    coordinator.update_interval = timedelta(seconds=poll_interval)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
