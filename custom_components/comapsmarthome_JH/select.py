from datetime import timedelta
import logging
from typing import Any
from bidict import bidict
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType


from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL
)

from . import ComapCoordinator, ComapClient

from .const import (
    DOMAIN,
)

SCAN_INTERVAL = timedelta(minutes=1)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    
    # Extraire la valeur de l'intervalle de scan depuis la configuration
    #scan_interval_minutes = config_type.get(CONF_SCAN_INTERVAL, 1)
    #scan_interval = timedelta(minutes=scan_interval_minutes)
    
    config = hass.data[DOMAIN][config_entry.entry_id]
    client = ComapClient(username=config[CONF_USERNAME], password=config[CONF_PASSWORD])
    
    req = await client.get_zones()
    zones = req.get("zones")

    zones_selects = [
        ZoneModeSelect(client, zone)
        for zone in zones
    ]

    central_select = CentralModeSelect(client, related_entities=zones_selects)

    selects = [central_select] + zones_selects

    async_add_entities(selects, update_before_add=True)


class CentralModeSelect(SelectEntity):
    """Representation of the central mode choice"""

    def __init__(self, client, related_entities):
        super().__init__()
        self._scan_interval = 1
        self.client = client
        self.housing = client.housing
        self._name = "Planning Comap"
        self.device_name = client.get_housings()[0].get("name")
        self._attr_unique_id = "central_mode"
        self._attr_options = []
        self._attr_current_option = None
        self.modes = {}
        self.related_entities = related_entities or []

    @property
    def scan_interval(self) -> timedelta:
        """Retourne l'intervalle de scan défini."""
        return self._scan_interval
    
    @property
    def icon(self) -> str:
        return "mdi:form-select"

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.client.housing

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            name=self.device_name,
            manufacturer="comap",
        )

    async def async_update(self):       
        schedules = await self.get_schedules()
        self._attr_options = self.list_schedules(schedules)
        self.modes = self.parse_schedules(schedules)
        self._attr_current_option = await self.get_active_schedule_name(schedules)

    async def async_select_option(self, option: str) -> None:
        schedule_id = self.modes.get(option)
        await self.setProgram(schedule_id)
        self._attr_current_option = option
        for entity in self.related_entities:
            await entity.async_update_ha_state(force_refresh=True)

    async def get_schedules(self):
        r = await self.client.get_schedules()
        return r

    def list_schedules(self, r) -> list:
        schedules = []
        for schedule in r:
            schedules.append(schedule["title"])
        return schedules

    def parse_schedules(self, r) -> dict[str, str]:
        schedules = {}
        for schedule in r:
            schedules.update({schedule["title"]: schedule["id"]})
        return schedules

    async def get_active_schedule_name(self,schedules) -> str:
        r = await self.client.get_active_program()
        id = r["zones"][0]["schedule_id"]
        for schedule in schedules:
            if (schedule["id"]) == id:
                return schedule["title"]    

    async def setProgram(self,schedule_id):
        housing_details = await self.client.get_zones()
        for zone in housing_details.get("zones"):
            await self.client.set_schedule(zone["id"],schedule_id)

class ZoneModeSelect(SelectEntity):
    """Representation of the central mode choice"""

    def __init__(self, client, zone):
        super().__init__()
        self._scan_interval = 1
        self.client = client
        self.housing = client.housing
        self._name = "Planning Comap zone " + zone.get("title")
        self.zone_id = zone.get("id")
        self._attr_unique_id = "zone_mode_" + zone.get("title")
        self.zone_name = zone.get("title")
        self._attr_options = []
        self._attr_current_option = None
        self.modes = {}
    
    @property
    def scan_interval(self) -> timedelta:
        """Retourne l'intervalle de scan défini."""
        return self._scan_interval

    @property
    def icon(self) -> str:
        return "mdi:form-select"

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.zone_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            name=self.zone_name,
            manufacturer="comap",
            serial_number = self.zone_id
        )

    async def async_update(self):       
        schedules = await self.get_schedules()
        self._attr_options = self.list_schedules(schedules)
        self.modes = self.parse_schedules(schedules)
        self._attr_current_option = await self.get_active_schedule_name(schedules,self.zone_id)

    async def async_select_option(self, option: str) -> None:
        schedule_id = self.modes.get(option)
        await self.setProgram(schedule_id,self.zone_id)
        self._attr_current_option = option

    async def get_schedules(self):
        r = await self.client.get_schedules()
        return r

    def list_schedules(self, r) -> list:
        schedules = []
        for schedule in r:
            schedules.append(schedule["title"])
        return schedules

    def parse_schedules(self, r) -> dict[str, str]:
        schedules = {}
        for schedule in r:
            schedules.update({schedule["title"]: schedule["id"]})
        return schedules

    async def get_active_schedule_name(self,schedules,zone_id) -> str:
        r = await self.client.get_active_program()
        zones = r["zones"]
        for zone in zones:
            if zone["id"] == zone_id:
                id = zone["schedule_id"]
        for schedule in schedules:
            if (schedule["id"]) == id:
                return schedule["title"]  

    async def setProgram(self,schedule_id, zone_id):
        await self.client.set_schedule(zone_id,schedule_id)          