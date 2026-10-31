"""Sensor platform for CFMoto."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CfMotoCoordinator
from .entity import CfMotoEntity


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _km_from_meters(value: Any) -> float | None:
    meters = _num(value)
    return round(meters / 1000, 1) if meters is not None else None


def _ms_datetime(value: Any) -> datetime | None:
    ms = _num(value)
    return (
        datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        if ms is not None
        else None
    )


@dataclass(frozen=True)
class CfMotoSensorDescription(SensorEntityDescription):
    """Description with a value extractor."""

    value: Callable[[dict[str, Any]], Any] = lambda d: None


SENSORS: tuple[CfMotoSensorDescription, ...] = (
    CfMotoSensorDescription(
        key="odometer",
        name="Odometer",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        icon="mdi:counter",
        value=lambda d: _km_from_meters(d.get("totalRideMile")),
    ),
    CfMotoSensorDescription(
        key="speed",
        name="Speed",
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        icon="mdi:speedometer",
        value=lambda d: _num(d.get("speed")),
    ),
    CfMotoSensorDescription(
        key="range",
        name="Range",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        icon="mdi:map-marker-distance",
        value=lambda d: _num(d.get("hmiRidableMile")),
    ),
    CfMotoSensorDescription(
        key="battery_voltage",
        name="Battery voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        icon="mdi:battery",
        value=lambda d: _num(d.get("fireVoltage")),
    ),
    CfMotoSensorDescription(
        key="fuel_level",
        name="Fuel level",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gas-station",
        value=lambda d: _num(d.get("remainingOil")),
    ),
    CfMotoSensorDescription(
        key="fuel_display",
        name="Fuel level display",
        icon="mdi:gas-station",
        value=lambda d: d.get("remainingOilDisplay"),
    ),
    CfMotoSensorDescription(
        key="average_speed",
        name="Average speed",
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        icon="mdi:speedometer",
        value=lambda d: _num(d.get("avgRideSpeed")),
    ),
    CfMotoSensorDescription(
        key="ride_mileage_month",
        name="Ride mileage this month",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        icon="mdi:counter",
        value=lambda d: _km_from_meters(d.get("rideMileageMonth")),
    ),
    CfMotoSensorDescription(
        key="riding_time_month",
        name="Riding time this month",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-outline",
        value=lambda d: _num(d.get("ridingTimeMonth")),
    ),
    CfMotoSensorDescription(
        key="gsm_signal",
        name="GSM signal",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:signal",
        value=lambda d: _num(d.get("gsmRxLev")),
    ),
    CfMotoSensorDescription(
        key="vehicle_state",
        name="Vehicle state",
        icon="mdi:motorbike",
        value=lambda d: _num(d.get("vehicleState")),
    ),
    CfMotoSensorDescription(
        key="device_state",
        name="Device state",
        icon="mdi:access-point",
        value=lambda d: d.get("deviceState"),
    ),
    CfMotoSensorDescription(
        key="last_update",
        name="Last update",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
        value=lambda d: _ms_datetime(d.get("dataLastUpdateTime")),
    ),
)


class CfMotoSensor(CfMotoEntity, SensorEntity):
    """A CFMoto telemetry sensor."""

    entity_description: CfMotoSensorDescription

    def __init__(
        self,
        coordinator: CfMotoCoordinator,
        vehicle: dict[str, Any],
        description: CfMotoSensorDescription,
    ) -> None:
        super().__init__(coordinator, vehicle, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.detail)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CfMotoCoordinator = hass.data[DOMAIN][entry.entry_id]
    vehicles = coordinator.data.get("vehicles", [])
    async_add_entities(
        CfMotoSensor(coordinator, vehicle, description)
        for vehicle in vehicles
        for description in SENSORS
    )
