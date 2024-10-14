from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from . import ComapClient, ComapCoordinator
from .const import DOMAIN

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    config = hass.data[DOMAIN][config_entry.entry_id]
    client = ComapClient(username=config[CONF_USERNAME], password=config[CONF_PASSWORD])
    global HOUSING_DATA
    HOUSING_DATA = hass.data[DOMAIN]["housing"]
    req = await client.get_zones()
    zones = req.get("zones")

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
        self.housing = HOUSING_DATA.get("id")
        self._name = HOUSING_DATA.get("name")
        self._is_on = None
        self._attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, HOUSING_DATA.get("id"))
            },
            name=HOUSING_DATA.get("name"),
            manufacturer="comap",
        )

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.housing + "_on_off"

    @property
    def is_on(self):
        """If the sensor is currently on or off."""
        return self._is_on
    
    async def async_update(self):
        zones = await self.client.get_zones()
        self._is_on = zones["heating_system_state"] == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        return await self.client.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        return await self.client.turn_off()
    
class ComapHousingHoliday(SwitchEntity):
    def __init__(self, client) -> None:
        super().__init__()
        self.client = client
        self.housing = HOUSING_DATA.get("id")
        self._name = "Holiday " + HOUSING_DATA.get("name")
        self._is_on = None
        self._attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, HOUSING_DATA.get("id"))
            },
            name=HOUSING_DATA.get("name"),
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

    async def async_update(self):
        zones = await self.client.get_zones()
        events = zones.get("events")
        if ('absence' in events):
            self._is_on = True
        else:
            self._is_on = False
       
    async def async_turn_on(self, **kwargs: Any) -> None:
        return await self.client.set_holiday()

    async def async_turn_off(self, **kwargs: Any) -> None:
        return await self.client.delete_holiday()
    
class ComapHousingAbsence(SwitchEntity):
    def __init__(self, client) -> None:
        super().__init__()
        self.client = client
        self.housing = HOUSING_DATA.get("id")
        self._name = "Absence " + HOUSING_DATA.get("name")
        self._is_on = None
        self._attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, HOUSING_DATA.get("id"))
            },
            name=HOUSING_DATA.get("name"),
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

    async def async_update(self):
        zones = await self.client.get_zones()
        events = zones.get("events")
        if ('time_shift' in events):
            self._is_on = True
        else:
            self._is_on = False
       
    async def async_turn_on(self, **kwargs: Any) -> None:
        return await self.client.set_absence()

    async def async_turn_off(self, **kwargs: Any) -> None:
        return await self.client.delete_absence()
    

class ComapZoneTemporarySwitch(SwitchEntity):
    def __init__(self, client, zone) -> None:
        super().__init__()
        self.client = client
        self.housing = HOUSING_DATA.get("id")
        self._name = "Temporary " + HOUSING_DATA.get("name") + " " + zone.get("title")
        self._id = zone.get("id") + "_temporary"
        self.zone_name = zone.get("title")
        self.zone_id = zone.get("id")
        self._extra_state_attributes = {}
        self._is_on = False

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
        req = await self.client.get_zones()
        zones = req.get("zones")
        events = {}
        for zone in zones:
            if zone.get("id") == self.zone_id:
                events = zone.get("events")
        self._extra_state_attributes["temporary_instruction"] = events.get("temporary_instruction")
        if ('temporary_instruction' in events):
            self._is_on = True
        else:
            self._is_on = False
       
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