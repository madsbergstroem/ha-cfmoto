"""Device tracker platform for CFMoto (GPS position)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CfMotoCoordinator
from .entity import CfMotoEntity


class CfMotoDeviceTracker(CfMotoEntity, TrackerEntity):
    """Tracks the vehicle's GPS position from the cloud."""

    @property
    def _geo(self) -> dict[str, Any]:
        return self.detail.get("geoLocation") or {}

    @property
    def latitude(self) -> float | None:
        value = self._geo.get("latitude")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def longitude(self) -> float | None:
        value = self._geo.get("longitude")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        altitude = self._geo.get("altitude")
        if altitude is not None:
            attrs["altitude"] = altitude
        report = self._geo.get("report") or {}
        report_ms = report.get("datetime")
        if report_ms is not None:
            try:
                attrs["last_report"] = datetime.fromtimestamp(
                    float(report_ms) / 1000, tz=timezone.utc
                )
            except (TypeError, ValueError):
                pass
        return attrs


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CfMotoCoordinator = hass.data[DOMAIN][entry.entry_id]
    vehicles = coordinator.data.get("vehicles", [])
    async_add_entities(
        CfMotoDeviceTracker(coordinator, vehicle, "location")
        for vehicle in vehicles
    )
