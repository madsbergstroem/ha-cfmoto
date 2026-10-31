"""Shared entity base for CFMoto entities."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CfMotoCoordinator


class CfMotoEntity(CoordinatorEntity[CfMotoCoordinator]):
    """Base entity bound to one vehicle's telemetry."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CfMotoCoordinator,
        vehicle: dict[str, Any],
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._vehicle = vehicle
        self._vid = str(vehicle.get("vehicleId") or "")
        self._key = key
        self._attr_unique_id = f"{self._vid}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._vid)},
            "name": vehicle.get("vehicleName") or vehicle.get("vin") or self._vid,
            "manufacturer": "CFMoto",
            "model": vehicle.get("vehicleType"),
        }

    @property
    def detail(self) -> dict[str, Any]:
        """The current telemetry detail for this vehicle."""
        return self.coordinator.data["details"].get(self._vid, {})
