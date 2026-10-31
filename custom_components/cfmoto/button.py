"""Button platform: BLE control commands for the CFMoto T-Box.

Every press opens a fresh BLE session: connect -> auth -> command -> ACK ->
disconnect. Results land in the entity attributes and the HA log. No command
runs without an explicit press.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ble import BleError, run_command
from .const import CONF_ENABLE_BLE, DOMAIN
from .coordinator import CfMotoCoordinator
from .entity import CfMotoEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CfMotoButtonDescription(ButtonEntityDescription):
    """Description with the BLE command kind."""

    kind: str = ""


BUTTONS: tuple[CfMotoButtonDescription, ...] = (
    CfMotoButtonDescription(key="power_on", name="Power on", icon="mdi:power", kind="power_on"),
    CfMotoButtonDescription(key="power_off", name="Power off", icon="mdi:power-off", kind="power_off"),
    CfMotoButtonDescription(key="unlock", name="Unlock", icon="mdi:lock-open-variant-outline", kind="unlock"),
    CfMotoButtonDescription(key="lock", name="Lock", icon="mdi:lock-outline", kind="lock"),
    CfMotoButtonDescription(key="horn", name="Horn", icon="mdi:bullhorn-outline", kind="horn"),
    CfMotoButtonDescription(key="flash", name="Flash lights", icon="mdi:alarm-light-outline", kind="flash"),
    CfMotoButtonDescription(key="ble_test", name="BLE test", icon="mdi:bluetooth-connect", kind="test"),
)


class CfMotoButton(CfMotoEntity, ButtonEntity):
    """A BLE command button for one vehicle."""

    entity_description: CfMotoButtonDescription

    def __init__(
        self,
        coordinator: CfMotoCoordinator,
        vehicle: dict[str, Any],
        description: CfMotoButtonDescription,
    ) -> None:
        super().__init__(coordinator, vehicle, description.key)
        self.entity_description = description
        self._attr_extra_state_attributes = {}

    @property
    def _ble_lock(self) -> asyncio.Lock:
        return self.coordinator.ble_lock

    @property
    def available(self) -> bool:
        mac = self.detail.get("btMac")
        return bool(mac) and super().available

    async def async_press(self) -> None:
        detail = self.detail
        mac = detail.get("btMac")
        enc = detail.get("encryptInfo") or {}
        encrypt_value = enc.get("encryptValue")
        key = enc.get("key")
        if not mac or not encrypt_value or not key:
            raise HomeAssistantError(
                "BLE-Daten fehlen: btMac/encryptInfo nicht in den Cloud-Daten"
            )

        async with self._ble_lock:
            try:
                result = await run_command(
                    self.hass,
                    str(mac),
                    encrypt_value,
                    key,
                    self.entity_description.kind,
                    logger=_LOGGER,
                )
            except BleError as exc:
                self._attr_extra_state_attributes = {"last_error": str(exc)}
                self.async_write_ha_state()
                raise HomeAssistantError(str(exc)) from exc
            except Exception as exc:  # noqa: BLE001
                self._attr_extra_state_attributes = {"last_error": f"{type(exc).__name__}: {exc}"}
                self.async_write_ha_state()
                raise HomeAssistantError(f"BLE-Fehler: {exc}") from exc

        self._attr_extra_state_attributes = {"last_result": result}
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if not entry.options.get(CONF_ENABLE_BLE, True):
        _LOGGER.info("BLE-Steuerung in den Options deaktiviert — keine Buttons")
        return
    coordinator: CfMotoCoordinator = hass.data[DOMAIN][entry.entry_id]
    vehicles = coordinator.data.get("vehicles", [])
    async_add_entities(
        CfMotoButton(coordinator, vehicle, description)
        for vehicle in vehicles
        for description in BUTTONS
    )
