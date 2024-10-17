from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .comap import ComapClient
from .const import DOMAIN
from .comap_functions import refresh_main_entity

SCAN_INTERVAL = timedelta(minutes=60)
_HASS = HomeAssistant

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    
    config = hass.data[DOMAIN][config_entry.entry_id]
    client = ComapClient(username=config[CONF_USERNAME], password=config[CONF_PASSWORD])

    global _HASS
    _HASS = hass

    zones = hass.data[DOMAIN]["thermal_details"].get("zones")

    temporary_instructions_switches = [
        ComapZoneTemporarySwitch(client, zone)
        for zone in zones
    ]

    housing_switches = [ComapHousingOnOff(client),ComapHousingHoliday(client),ComapHousingAbsence(client)]
    zones_switches = temporary_instructions_switches

    switches = housing_switches + zones_switches

    async_add_entities(switches, update_before_add=True)


class ComapHousingOnOff(SwitchEntity):
    def __init__(self, client) -> None:
        super().__init__()
        self.client = client
        self.housing = _HASS.data[DOMAIN]["housing"].get("id")
        self._name = _HASS.data[DOMAIN]["housing"].get("name")
        self._is_on = None
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self.hass = _HASS
        self._id = self.housing + "_on_off"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, _HASS.data[DOMAIN]["housing"].get("id"))
            },
            name=_HASS.data[DOMAIN]["housing"].get("name"),
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

    @property
    def is_on(self):
        """If the sensor is currently on or off."""
        return self._is_on
    
    async def async_update(self):
        zones = _HASS.data[DOMAIN]["thermal_details"]
        self._is_on = zones["heating_system_state"] == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        ret = await self.client.turn_on()
        await refresh_main_entity(_HASS)
        return ret

    async def async_turn_off(self, **kwargs: Any) -> None:
        ret =  await self.client.turn_off()
        await refresh_main_entity(_HASS)
        return ret
    
class ComapHousingHoliday(SwitchEntity):
    def __init__(self, client) -> None:
        super().__init__()
        self.client = client
        self.housing = _HASS.data[DOMAIN]["housing"].get("id")
        self._name = "Holiday " + _HASS.data[DOMAIN]["housing"].get("name")
        self._is_on = None
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._extra_state_attributes = {}
        self.hass = _HASS

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, _HASS.data[DOMAIN]["housing"].get("id"))
            },
            name=_HASS.data[DOMAIN]["housing"].get("name"),
            manufacturer="comap",
        )

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.housing + "_holiday"

    @property
    def is_on(self):
        """If the sensor is currently on or off."""
        return self._is_on
    
    @property
    def extra_state_attributes(self):
        return self._extra_state_attributes

    async def async_update(self):
        thermal_details = _HASS.data[DOMAIN]["thermal_details"]
        events = thermal_details.get("events")
        if ('absence' in events):
            self._is_on = True
        else:
            self._is_on = False
        self._extra_state_attributes = events.get("absence")
       
    async def async_turn_on(self, **kwargs: Any) -> None:
        self._is_on = True
        await self.client.set_holiday()
        await refresh_main_entity(_HASS)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._is_on = False
        await self.client.delete_holiday()
        await refresh_main_entity(_HASS)
    
class ComapHousingAbsence(SwitchEntity):
    def __init__(self, client) -> None:
        super().__init__()
        self.client = client
        self.housing = _HASS.data[DOMAIN]["housing"].get("id")
        self._name = "Absence " + _HASS.data[DOMAIN]["housing"].get("name")
        self._is_on = None
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._extra_state_attributes = {}
        self.hass = _HASS

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, _HASS.data[DOMAIN]["housing"].get("id"))
            },
            name=_HASS.data[DOMAIN]["housing"].get("name"),
            manufacturer="comap",
        )

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.housing + "_absence"

    @property
    def is_on(self):
        """If the sensor is currently on or off."""
        return self._is_on
    
    @property
    def extra_state_attributes(self):
        return self._extra_state_attributes

    async def async_update(self):
        thermal_details = _HASS.data[DOMAIN]["thermal_details"]
        events = thermal_details.get("events")
        if ('time_shift' in events):
            self._is_on = True
        else:
            self._is_on = False
        self._extra_state_attributes = events.get("time_shift")
       
    async def async_turn_on(self, **kwargs: Any) -> None:
        self._is_on = True
        await self.client.set_absence()
        await refresh_main_entity(_HASS)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._is_on = True
        await self.client.delete_absence()
        await refresh_main_entity(_HASS)
    

class ComapZoneTemporarySwitch(SwitchEntity):
    def __init__(self, client, zone) -> None:
        super().__init__()
        self.client = client
        self.housing = _HASS.data[DOMAIN]["housing"].get("id")
        self._name = "Temporary " + _HASS.data[DOMAIN]["housing"].get("name") + " " + zone.get("title")
        self._id = zone.get("id") + "_temporary"
        self.zone_name = zone.get("title")
        self.zone_id = zone.get("id")
        self._extra_state_attributes = {}
        self._is_on = False
        self._extra_state_attributes = {}
        self.hass = _HASS

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
        return self._extra_state_attributes
    
    @property
    def is_on(self):
        """If the sensor is currently on or off."""
        return self._is_on

    async def async_update(self):
        self._extra_state_attributes = {}
        thermal_details = _HASS.data[DOMAIN]["thermal_details"]
        zones = thermal_details.get("zones")
        events = {}
        for zone in zones:
            if zone.get("id") == self.zone_id:
                events = zone.get("events")
        self._extra_state_attributes["temporary_instruction"] = events.get("temporary_instruction")
        if ('temporary_instruction' in events):
            temporary_instruction = events.get("temporary_instruction")
            self._is_on = True
            self._extra_state_attributes["end_at"] = temporary_instruction.get("end_at")
            self._extra_state_attributes["instruction"] = temporary_instruction.get("set_point").get("instruction")
        else:
            self._is_on = False
            self._extra_state_attributes["end_at"] = None
            self._extra_state_attributes["instruction"] = None

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
        await refresh_main_entity(_HASS)