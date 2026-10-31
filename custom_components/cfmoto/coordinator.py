"""DataUpdateCoordinator for CFMoto."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CfMotoAuthError, CfMotoClient, CfMotoError
from .const import DEFAULT_POLL_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class CfMotoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the CFMoto cloud for vehicle telemetry."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: CfMotoClient,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self._client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            vehicles = await self._relogin_retry(self._client.get_vehicles)
        except CfMotoAuthError as exc:
            raise UpdateFailed(f"authentication failed: {exc}") from exc
        except CfMotoError as exc:
            raise UpdateFailed(f"vehicle list failed: {exc}") from exc

        details: dict[str, dict[str, Any]] = {}
        for vehicle in vehicles:
            vid = str(vehicle.get("vehicleId") or "")
            if not vid:
                continue
            try:
                details[vid] = await self._relogin_retry(
                    self._client.get_vehicle, vid
                )
            except CfMotoAuthError as exc:
                raise UpdateFailed(f"authentication failed: {exc}") from exc
            except CfMotoError as exc:
                _LOGGER.warning("vehicle %s detail failed: %s", vid, exc)
                details[vid] = {}

        return {"vehicles": vehicles, "details": details}

    async def _relogin_retry(self, fn, *args: Any) -> Any:
        """Run a call, re-login once on a stale token, and retry."""
        try:
            return await fn(*args)
        except CfMotoAuthError:
            raise
        except CfMotoError:
            _LOGGER.debug("API error, re-logging in and retrying")
            await self._client.login()
            return await fn(*args)
