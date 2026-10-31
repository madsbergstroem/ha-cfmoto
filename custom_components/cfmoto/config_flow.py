"""Config flow for CFMoto."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CfMotoAuthError, CfMotoClient, CfMotoError
from .const import CONF_AREA, CONF_EMAIL, CONF_PASSWORD, DEFAULT_AREA, DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_AREA, default=DEFAULT_AREA): str,
    }
)


class CfMotoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CFMoto."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry = None

    async def _validate(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        session = async_get_clientsession(self.hass)
        client = CfMotoClient(
            session,
            data[CONF_EMAIL],
            data[CONF_PASSWORD],
            data.get(CONF_AREA, DEFAULT_AREA),
        )
        await client.login()
        return await client.get_vehicles()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                vehicles = await self._validate(user_input)
            except CfMotoAuthError:
                errors["base"] = "invalid_auth"
            except CfMotoError:
                errors["base"] = "cannot_connect"
            else:
                if not vehicles:
                    errors["base"] = "no_vehicles"
                elif self._reauth_entry:
                    data = dict(self._reauth_entry.data)
                    data.update(
                        {
                            CONF_EMAIL: user_input[CONF_EMAIL],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_AREA: user_input.get(CONF_AREA, DEFAULT_AREA),
                        }
                    )
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry, data=data
                    )
                    await self.hass.config_entries.async_reload(
                        self._reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")
                else:
                    await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=user_input[CONF_EMAIL], data=user_input
                    )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user(user_input)
