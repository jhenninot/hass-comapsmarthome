from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .comap import ComapClient
from .const import DOMAIN
from .comap_functions import refresh_main_entity
from . import ComapDataCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    
    config = hass.data[DOMAIN][config_entry.entry_id]
    client = ComapClient(username=config[CONF_USERNAME], password=config[CONF_PASSWORD])

    coordinator = ComapDataCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()

    zones = hass.data[DOMAIN]["thermal_details"].get("zones")

    temporary_instructions_switches = [
        ComapZoneTemporarySwitch(coordinator,client, zone)
        for zone in zones
    ]

    housing_switches = [ComapHousingOnOff(coordinator,client),ComapHousingHoliday(coordinator,client),ComapHousingAbsence(coordinator,client)]
    zones_switches = temporary_instructions_switches

    switches = housing_switches + zones_switches

    async_add_entities(switches, update_before_add=True)


class ComapHousingOnOff(CoordinatorEntity, SwitchEntity):
    def __init__(self, coordinator, client) -> None:
        super().__init__(coordinator)
        self.client = client
        self.housing_id = coordinator.data["housing"].get("id")
        self.housing_name = coordinator.data["housing"].get("name")
        self._name = self.housing_name
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._id = self.housing_id + "_on_off"
#fixes
    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.housing_id)
            },
            name=self.housing_name,
            manufacturer="comap",
        )

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._id
    

#variables
    @property
    def is_on(self):
        """If the sensor is currently on or off."""
        thermal_details = self.coordinator.data["thermal_details"]
        self._is_on = thermal_details["heating_system_state"] == "on"
        return self._is_on

#fonctions

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._is_on = True
        await self.client.turn_on()
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._is_on = True
        await self.client.turn_off()
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    
class ComapHousingHoliday(CoordinatorEntity, SwitchEntity):
    def __init__(self, coordinator, client) -> None:
        super().__init__(coordinator)
        self.client = client
        self.housing_id = coordinator.data["housing"].get("id")
        self.housing_name = coordinator.data["housing"].get("name")
        self._name = "Holiday " + coordinator.data["housing"].get("name")
        self._is_on = None
        self._attr_device_class = SwitchDeviceClass.SWITCH


    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.housing_id)
            },
            name=self.housing_name,
            manufacturer="comap",
        )

    @property

    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.housing_id + "_holiday"

    @property
    def is_on(self):
        """If the sensor is currently on or off."""
        thermal_details = self.coordinator.data["thermal_details"]
        events = thermal_details.get("events")
        if ('absence' in events):
            self._is_on = True
        else:
            self._is_on = False
       
    async def async_turn_on(self, **kwargs: Any) -> None:
        self._is_on = True
        await self.client.set_holiday()
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._is_on = False
        await self.client.delete_holiday()
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()
    
class ComapHousingAbsence(CoordinatorEntity, SwitchEntity):
    def __init__(self, coordinator, client) -> None:
        super().__init__(coordinator)
        self.client = client
        self.housing_id = coordinator.data["housing"].get("id")
        self.housing_name = coordinator.data["housing"].get("name")
        self._name = "Absence " + coordinator.data["housing"].get("name")
        self._is_on = None
        self._attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.housing_id)
            },
            name=self.housing_name,
            manufacturer="comap",
        )

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.housing_id + "_absence"

    @property
    def is_on(self):
        thermal_details = self.coordinator.data["thermal_details"]
        events = thermal_details.get("events")
        if ('time_shift' in events):
            return True
        else:
            return False
       
    async def async_turn_on(self, **kwargs: Any) -> None:
        self._is_on = True
        await self.client.set_absence()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._is_on = True
        await self.client.delete_absence()
        await self.coordinator.async_request_refresh()
    

class ComapZoneTemporarySwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, coordinator, client, zone) -> None:
        super().__init__(coordinator)
        self.client = client
        self.housing_id = coordinator.data["housing"].get("id")
        self.housing_name = coordinator.data["housing"].get("name")
        self._name = "Temporary " + self.housing_name + " " + zone.get("title")
        self._id = zone.get("id") + "_temporary"
        self.zone_name = zone.get("title")
        self.zone_id = zone.get("id")
        self._extra_state_attributes = {}
        self._is_on = False
        self._extra_state_attributes = {}

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.zone_id)
            },
            name=self.zone_name,
            manufacturer="comap",
            serial_number = self.zone_id
        )
    
    @property
    def icon(self) -> str:
        if self._is_on:
            return "mdi:timer-minus"
        return "mdi:timer-off"

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name
    
    @property
    def extra_state_attributes(self):
        return self._extra_state_attributes

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._id
    
    @property
    def extra_state_attributes(self):
        # Retourne un dictionnaire d'attributs supplémentaires
        return self.get_state_and_attr()["attrs"]
    
    @property
    def is_on(self):
        """If the sensor is currently on or off."""
        return self.get_state_and_attr()["is_on"]

    def get_state_and_attr (self):
        attrs = {}
        is_on = None
        thermal_details = self.coordinator.data["thermal_details"]
        zones = thermal_details.get("zones")
        events = {}
        for zone in zones:
            if zone.get("id") == self.zone_id:
                events = zone.get("events")
        attrs["temporary_instruction"] = events.get("temporary_instruction")
        if ('temporary_instruction' in events):
            temporary_instruction = events.get("temporary_instruction")
            is_on = True
            attrs["end_at"] = temporary_instruction.get("end_at")
            attrs["instruction"] = temporary_instruction.get("set_point").get("instruction")
        else:
            is_on = False
            attrs["end_at"] = None
            attrs["instruction"] = None
        return {
            "is_on": is_on,
            "attrs": attrs
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        return
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        response = await self.client.remove_temporary_instruction(self.zone_id)
        events = response.get("events")
        self._extra_state_attributes["temporary_instruction"] = events.get("temporary_instruction")
        if ('temporary_instruction' in events):
            self._is_on = True
        else:
            self._is_on = False
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()