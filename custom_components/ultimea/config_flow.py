"""Config flow for app-capable ULTIMEA Bluetooth soundbars."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .const import (
    CONF_ABILITY_FLAGS,
    CONF_CAPABILITIES,
    CONF_DISCONNECT_DELAY,
    CONF_FIRMWARE,
    CONF_KEEP_CONNECTED,
    CONF_HEARTBEAT_INTERVAL,
    CONF_MODEL,
    CONF_PROFILE,
    CONF_PROTOCOL_VERSION,
    CONF_SERIAL,
    CONF_STANDBY_OPTIONS,
    CONF_TRANSPORT,
    CONF_VOLUME_MAX,
    DEFAULT_DISCONNECT_DELAY,
    DEFAULT_DISCOVERY_NAME,
    DEFAULT_KEEP_CONNECTED,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_VOLUME_MAX,
    DISCOVERY_SERVICE_UUID,
    DOMAIN,
    ULTIMEA_MANUFACTURER_ID,
)
from .device import (
    UltimeaConnectionError,
    UltimeaUnsupportedDeviceError,
    async_probe_device,
)

_FAMILY_PREFIXES = ("poseidon", "apollo", "nova", "aura", "solo", "skywave")


def _is_ultimea_candidate(info: bluetooth.BluetoothServiceInfoBleak) -> bool:
    """Return whether an advertisement is worth a safe protocol probe."""
    if ULTIMEA_MANUFACTURER_ID in info.manufacturer_data:
        return True
    uuids = {uuid.lower() for uuid in info.service_uuids}
    name = (info.name or "").strip().casefold()
    return DISCOVERY_SERVICE_UUID in uuids and name.startswith(_FAMILY_PREFIXES)


def _display_name(info: bluetooth.BluetoothServiceInfoBleak | None) -> str:
    """Return a human-friendly discovery name, never a raw BLE address."""
    if info is None:
        return DEFAULT_DISCOVERY_NAME
    name = (info.name or "").strip()
    address = info.address.upper()
    if not name or name.upper() == address:
        return DEFAULT_DISCOVERY_NAME
    compact = name.replace(":", "").replace("-", "").upper()
    if len(compact) == 12 and all(ch in "0123456789ABCDEF" for ch in compact):
        return DEFAULT_DISCOVERY_NAME
    if name.casefold().endswith(" ble"):
        name = name[:-4].rstrip()
    return name or DEFAULT_DISCOVERY_NAME


def _entry_for_address(hass, address: str):
    address = address.upper()
    for entry in hass.config_entries.async_entries(DOMAIN):
        if str(entry.data.get(CONF_ADDRESS, "")).upper() == address:
            return entry
    return None


def _entry_for_serial(hass, serial: str | None):
    if not serial:
        return None
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_SERIAL) == serial:
            return entry
    return None


def _probe_data(address: str, identity, capabilities) -> dict[str, Any]:
    return {
        CONF_ADDRESS: address,
        CONF_MODEL: identity.model,
        CONF_SERIAL: identity.serial,
        CONF_FIRMWARE: identity.firmware,
        CONF_PROTOCOL_VERSION: identity.protocol_version,
        CONF_PROFILE: identity.profile,
        CONF_CAPABILITIES: sorted(feature.value for feature in capabilities.features),
        CONF_ABILITY_FLAGS: list(capabilities.raw_ability_flags),
        CONF_STANDBY_OPTIONS: list(capabilities.standby_options),
        CONF_TRANSPORT: capabilities.transport,
    }


class UltimeaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle ULTIMEA configuration."""

    VERSION = 1

    def __init__(self) -> None:
        self._address: str | None = None
        self._name: str = DEFAULT_DISCOVERY_NAME

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""
        if not _is_ultimea_candidate(discovery_info):
            return self.async_abort(reason="not_supported")

        self._address = discovery_info.address.upper()
        self._name = _display_name(discovery_info)
        if _entry_for_address(self.hass, self._address) is not None:
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(self._address)
        self._abort_if_unique_id_configured(updates={CONF_ADDRESS: self._address})
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm and capability-probe a discovered soundbar."""
        assert self._address is not None
        errors: dict[str, str] = {}
        if _entry_for_address(self.hass, self._address) is not None:
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            try:
                identity, capabilities = await async_probe_device(
                    self.hass, self._address, self._name
                )
            except UltimeaConnectionError:
                errors["base"] = "cannot_connect"
            except UltimeaUnsupportedDeviceError:
                return self.async_abort(reason="not_supported")
            else:
                if _entry_for_serial(self.hass, identity.serial) is not None:
                    return self.async_abort(reason="already_configured")
                suffix = (
                    identity.serial[-4:]
                    if identity.serial
                    else self._address[-5:].replace(":", "")
                )
                return self.async_create_entry(
                    title=f"{identity.model or self._name} {suffix}",
                    data=_probe_data(self._address, identity, capabilities),
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
            if _is_ultimea_candidate(info)
            and _entry_for_address(self.hass, info.address) is None
        }

        if user_input is not None:
            address = str(user_input[CONF_ADDRESS]).strip().upper()
            info = discovered.get(address)
            self._address = address
            self._name = _display_name(info)
            if _entry_for_address(self.hass, address) is not None:
                return self.async_abort(reason="already_configured")

            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured(updates={CONF_ADDRESS: address})
            try:
                identity, capabilities = await async_probe_device(
                    self.hass, address, self._name
                )
            except UltimeaConnectionError:
                errors["base"] = "cannot_connect"
            except UltimeaUnsupportedDeviceError:
                errors["base"] = "not_supported"
            else:
                if _entry_for_serial(self.hass, identity.serial) is not None:
                    return self.async_abort(reason="already_configured")
                suffix = (
                    identity.serial[-4:]
                    if identity.serial
                    else address[-5:].replace(":", "")
                )
                return self.async_create_entry(
                    title=f"{identity.model or self._name} {suffix}",
                    data=_probe_data(address, identity, capabilities),
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
                        default=options.get(CONF_KEEP_CONNECTED, DEFAULT_KEEP_CONNECTED),
                    ): bool,
                    vol.Required(
                        CONF_DISCONNECT_DELAY,
                        default=options.get(CONF_DISCONNECT_DELAY, DEFAULT_DISCONNECT_DELAY),
                    ): vol.All(vol.Coerce(int), vol.Range(min=2, max=300)),
                    vol.Required(
                        CONF_VOLUME_MAX,
                        default=options.get(CONF_VOLUME_MAX, DEFAULT_VOLUME_MAX),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=255)),
                    vol.Required(
                        CONF_HEARTBEAT_INTERVAL,
                        default=options.get(CONF_HEARTBEAT_INTERVAL, DEFAULT_HEARTBEAT_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                }
            ),
        )
