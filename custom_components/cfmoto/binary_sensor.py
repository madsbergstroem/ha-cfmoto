"""Binary sensor platform for CFMoto."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CfMotoCoordinator
from .entity import CfMotoEntity


@dataclass(frozen=True)
class CfMotoBinarySensorDescription(BinarySensorEntityDescription):
    """Description with an on/off extractor."""

    value: Callable[[dict[str, Any]], bool | None] = lambda d: None


def _flag(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _eq_one(value: Any) -> bool | None:
    try:
        return int(value) == 1
    except (TypeError, ValueError):
        return None


BINARY_SENSORS: tuple[CfMotoBinarySensorDescription, ...] = (
    CfMotoBinarySensorDescription(
        key="tbox_online",
        name="T-Box online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value=lambda d: _flag(d.get("deviceState") == "ONLINE"),
    ),
    CfMotoBinarySensorDescription(
        key="vehicle_online",
        name="Vehicle online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value=lambda d: _flag(d.get("isOnline")),
    ),
    CfMotoBinarySensorDescription(
        key="tbox_active",
        name="T-Box active",
        value=lambda d: _flag(d.get("tboxIsActive")),
    ),
    CfMotoBinarySensorDescription(
        key="ignition",
        name="Ignition",
        device_class=BinarySensorDeviceClass.POWER,
        value=lambda d: _eq_one(d.get("kl")),
    ),
    CfMotoBinarySensorDescription(
        key="steering_lock",
        name="Steering lock",
        device_class=BinarySensorDeviceClass.LOCK,
        value=lambda d: _eq_one(d.get("headLockState")),
    ),
    CfMotoBinarySensorDescription(
        key="seat_lock",
        name="Seat lock",
        device_class=BinarySensorDeviceClass.LOCK,
        value=lambda d: _eq_one(d.get("seatLockState")),
    ),
    CfMotoBinarySensorDescription(
        key="fuel_lock",
        name="Fuel lock",
        device_class=BinarySensorDeviceClass.LOCK,
        value=lambda d: _eq_one(d.get("oilLockState")),
    ),
    CfMotoBinarySensorDescription(
        key="battery_lock",
        name="Battery lock",
        device_class=BinarySensorDeviceClass.LOCK,
        value=lambda d: _eq_one(d.get("batteryLockState")),
    ),
)


class CfMotoBinarySensor(CfMotoEntity, BinarySensorEntity):
    """A CFMoto binary sensor."""

    entity_description: CfMotoBinarySensorDescription

    def __init__(
        self,
        coordinator: CfMotoCoordinator,
        vehicle: dict[str, Any],
        description: CfMotoBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, vehicle, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value(self.detail)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CfMotoCoordinator = hass.data[DOMAIN][entry.entry_id]
    vehicles = coordinator.data.get("vehicles", [])
    async_add_entities(
        CfMotoBinarySensor(coordinator, vehicle, description)
        for vehicle in vehicles
        for description in BINARY_SENSORS
    )
