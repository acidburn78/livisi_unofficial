"""Code to handle a Livisi switches."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .livisi_device import LivisiDevice

from .const import (
    DOMAIN,
    LIVISI_STATE_CHANGE,
    LOGGER,
    SWITCH_DEVICE_TYPES,
    VARIABLE_DEVICE_TYPE,
)
from .coordinator import LivisiDataUpdateCoordinator
from .entity import LivisiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch device."""
    coordinator: LivisiDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    @callback
    def handle_coordinator_update() -> None:
        """Add switch."""
        shc_devices: list[LivisiDevice] = coordinator.data
        entities: list[SwitchEntity] = []
        for device in shc_devices:
            if device.id not in known_devices:
                switch = None
                if device.type in SWITCH_DEVICE_TYPES:
                    switch_type = device.tag_category
                    if switch_type != "TCLightId":
                        switch = LivisiSwitch(config_entry, coordinator, device)
                elif device.type == VARIABLE_DEVICE_TYPE:
                    switch = LivisiVariable(config_entry, coordinator, device)

                if switch is not None:
                    LOGGER.debug("Include device type: %s", device.type)
                    coordinator.devices.add(device.id)
                    known_devices.add(device.id)
                    entities.append(switch)

        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiSwitch(LivisiEntity, SwitchEntity):
    """Represents the Livisi Switch."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: LivisiDevice,
    ) -> None:
        """Initialize the Livisi switch."""
        super().__init__(config_entry, coordinator, device, "SwitchActuator")
        self._attr_name = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        success = await self.aio_livisi.async_set_state(
            self.capability_id, key="onState", value=True
        )
        if not success:
            self.update_reachability(False)
            raise HomeAssistantError(f"Failed to turn on {self._attr_name}")

        self._attr_is_on = True
        self.update_reachability(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        success = await self.aio_livisi.async_set_state(
            self.capability_id, key="onState", value=False
        )
        if not success:
            self.update_reachability(False)
            raise HomeAssistantError(f"Failed to turn off {self._attr_name}")

        self._attr_is_on = False
        self.update_reachability(True)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        response = await self.coordinator.aiolivisi.async_get_device_state(
            self.capability_id, "onState"
        )
        if response is None:
            self._attr_is_on = False
            self.update_reachability(False)
        else:
            self._attr_is_on = response
            self.update_reachability(True)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self.capability_id}",
                self.update_states,
            )
        )

    @callback
    def update_states(self, state: bool) -> None:
        """Update the state of the switch device."""
        self._attr_is_on = state
        self.async_write_ha_state()


class LivisiVariable(LivisiEntity, SwitchEntity):
    """Represents a Livisi boolean variable."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: LivisiDevice,
    ) -> None:
        """Initialize the Livisi switch."""
        super().__init__(config_entry, coordinator, device, "BooleanStateActuator")
        self._attr_name = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        success = await self.aio_livisi.async_set_state(
            self.capability_id, key="value", value=True
        )

        if not success:
            self.update_reachability(False)
            raise HomeAssistantError(f"Failed to set {self._attr_name}")

        self._attr_is_on = True
        self.update_reachability(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        success = await self.aio_livisi.async_set_state(
            self.capability_id, key="value", value=False
        )

        if not success:
            self.update_reachability(False)
            raise HomeAssistantError(f"Failed to unset {self._attr_name}")

        self._attr_is_on = False
        self.update_reachability(True)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        response = await self.coordinator.aiolivisi.async_get_device_state(
            self.capability_id, "value"
        )
        if response is None:
            self.update_reachability(False)
        else:
            self.update_reachability(True)
            self.update_states(response)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self.capability_id}",
                self.update_states,
            )
        )

    @callback
    def update_states(self, state: bool) -> None:
        """Update the state of the switch device."""
        self._attr_is_on = state
        self.update_reachability(True)
        self.async_write_ha_state()
