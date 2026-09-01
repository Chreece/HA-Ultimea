"""Config flow for ULTIMEA Poseidon D80 Boom."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .const import (
    CONF_DISCONNECT_DELAY,
    CONF_FIRMWARE,
    CONF_KEEP_CONNECTED,
    CONF_MODEL,
    CONF_SERIAL,
    CONF_VOLUME_MAX,
    DEFAULT_DISCONNECT_DELAY,
    DEFAULT_KEEP_CONNECTED,
    DEFAULT_VOLUME_MAX,
    DISCOVERY_SERVICE_UUID,
    DOMAIN,
    SUPPORTED_MODEL,
    ULTIMEA_MANUFACTURER_ID,
)
from .device import (
    UltimeaConnectionError,
    UltimeaUnsupportedDeviceError,
    async_probe_device,
)


def _is_d80_candidate(info: bluetooth.BluetoothServiceInfoBleak) -> bool:
    """Return whether an advertisement is a plausible D80 Boom."""
    uuids = {uuid.lower() for uuid in info.service_uuids}
    return (
        ULTIMEA_MANUFACTURER_ID in info.manufacturer_data
        and DISCOVERY_SERVICE_UUID in uuids
    )


def _display_name(info: bluetooth.BluetoothServiceInfoBleak) -> str:
    """Return a human-friendly discovery name, never a raw BLE address."""
    name = (info.name or "").strip()
    address = info.address.upper()
    if not name or name.upper() == address:
        return SUPPORTED_MODEL
    # Some BlueZ paths expose the address as the device name when no cached
    # local name is present. Never surface that as the model/title in HA.
    compact = name.replace(":", "").replace("-", "").upper()
    if len(compact) == 12 and all(ch in "0123456789ABCDEF" for ch in compact):
        return SUPPORTED_MODEL
    if name.casefold().endswith(" ble"):
        name = name[:-4].rstrip()
    return name or SUPPORTED_MODEL


def _entry_for_address(hass, address: str):
    """Find an already configured entry for this Bluetooth address."""
    address = address.upper()
    for entry in hass.config_entries.async_entries(DOMAIN):
        configured = str(entry.data.get(CONF_ADDRESS, "")).upper()
        if configured == address:
            return entry
    return None


def _entry_for_serial(hass, serial: str | None):
    """Find an already configured entry for this soundbar serial."""
    if not serial:
        return None
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_SERIAL) == serial:
            return entry
    return None


class UltimeaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle ULTIMEA configuration."""

    VERSION = 1

    def __init__(self) -> None:
        self._address: str | None = None
        self._name: str = SUPPORTED_MODEL

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""
        if not _is_d80_candidate(discovery_info):
            return self.async_abort(reason="not_supported")

        self._address = discovery_info.address.upper()
        self._name = _display_name(discovery_info)

        # Existing entries created by v0.1.0/v0.1.1 may have their serial as
        # config-entry unique_id. Match the stored Bluetooth address before HA
        # creates a discovery card, otherwise the same D80 is shown twice.
        if _entry_for_address(self.hass, self._address) is not None:
            return self.async_abort(reason="already_configured")

        # Bluetooth address is the stable discovery key available without
        # connecting. The device serial remains the Device Registry identifier.
        await self.async_set_unique_id(self._address)
        self._abort_if_unique_id_configured(updates={CONF_ADDRESS: self._address})

        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm and verify a discovered soundbar."""
        assert self._address is not None
        errors: dict[str, str] = {}

        # Re-check in case another flow configured this device while this
        # discovery confirmation was open in the UI.
        if _entry_for_address(self.hass, self._address) is not None:
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            try:
                identity = await async_probe_device(
                    self.hass, self._address, self._name
                )
            except UltimeaConnectionError:
                errors["base"] = "cannot_connect"
            except UltimeaUnsupportedDeviceError:
                return self.async_abort(reason="not_supported")
            else:
                data = {
                    CONF_ADDRESS: self._address,
                    CONF_MODEL: identity.model,
                    CONF_SERIAL: identity.serial,
                    CONF_FIRMWARE: identity.firmware,
                }
                if _entry_for_serial(self.hass, identity.serial) is not None:
                    return self.async_abort(reason="already_configured")
                suffix = identity.serial[-4:] if identity.serial else self._address[-5:].replace(":", "")
                return self.async_create_entry(
                    title=f"{identity.model or SUPPORTED_MODEL} {suffix}",
                    data=data,
                )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._name},
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow manual setup or selection from the HA Bluetooth cache."""
        errors: dict[str, str] = {}
        discovered = {
            info.address.upper(): info
            for info in bluetooth.async_discovered_service_info(
                self.hass, connectable=True
            )
            if _is_d80_candidate(info)
            and _entry_for_address(self.hass, info.address) is None
        }

        if user_input is not None:
            address = str(user_input[CONF_ADDRESS]).strip().upper()
            info = discovered.get(address)
            self._address = address
            self._name = _display_name(info) if info else SUPPORTED_MODEL

            if _entry_for_address(self.hass, address) is not None:
                return self.async_abort(reason="already_configured")

            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured(updates={CONF_ADDRESS: address})

            try:
                identity = await async_probe_device(self.hass, address, self._name)
            except UltimeaConnectionError:
                errors["base"] = "cannot_connect"
            except UltimeaUnsupportedDeviceError:
                errors["base"] = "not_supported"
            else:
                data = {
                    CONF_ADDRESS: address,
                    CONF_MODEL: identity.model,
                    CONF_SERIAL: identity.serial,
                    CONF_FIRMWARE: identity.firmware,
                }
                if _entry_for_serial(self.hass, identity.serial) is not None:
                    return self.async_abort(reason="already_configured")
                suffix = identity.serial[-4:] if identity.serial else address[-5:].replace(":", "")
                return self.async_create_entry(
                    title=f"{identity.model or SUPPORTED_MODEL} {suffix}",
                    data=data,
                )

        if discovered:
            choices = {
                address: f"{_display_name(info)} ({address})"
                for address, info in discovered.items()
            }
            schema = vol.Schema({vol.Required(CONF_ADDRESS): vol.In(choices)})
        else:
            schema = vol.Schema({vol.Required(CONF_ADDRESS): str})

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return UltimeaOptionsFlow()


class UltimeaOptionsFlow(OptionsFlow):
    """ULTIMEA options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_KEEP_CONNECTED,
                        default=options.get(
                            CONF_KEEP_CONNECTED, DEFAULT_KEEP_CONNECTED
                        ),
                    ): bool,
                    vol.Required(
                        CONF_DISCONNECT_DELAY,
                        default=options.get(
                            CONF_DISCONNECT_DELAY, DEFAULT_DISCONNECT_DELAY
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=2, max=300)),
                    vol.Required(
                        CONF_VOLUME_MAX,
                        default=options.get(CONF_VOLUME_MAX, DEFAULT_VOLUME_MAX),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=255)),
                }
            ),
        )
