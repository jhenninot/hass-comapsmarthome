from datetime import timedelta
import logging
from typing import Any
from bidict import bidict
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry


from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
)

from . import ComapCoordinator, ComapClient
from .comap_functions import refresh_main_entity

from .const import (
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=60)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    
    config = hass.data[DOMAIN][config_entry.entry_id]
    client = ComapClient(username=config[CONF_USERNAME], password=config[CONF_PASSWORD])

    global _HASS
    _HASS = hass
    
    req = hass.data[DOMAIN]["thermal_details"]
    zones = req.get("zones")

    zones_selects = [
        ZoneScheduleSelect(client, zone)
        for zone in zones
    ]


    central_program = ProgramSelect(client)

    selects = zones_selects + [central_program]

    async_add_entities(selects, update_before_add=True)


class ZoneScheduleSelect(SelectEntity):

    def __init__(self, client, zone):
        super().__init__()
        self.client = client
        self.housing = _HASS.data[DOMAIN]["housing"].get("id")
        self._name = "Planning " + _HASS.data[DOMAIN]["housing"].get("name") + " zone " + zone.get("title")
        self.zone_id = zone.get("id")
        self._attr_unique_id = "zone_mode_" + zone.get("id")
        self.zone_name = zone.get("title")
        self._attr_options = []
        self._attr_current_option = None
        self.modes = {}
        self._available = True
    
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
        return self.zone_id + "_schedule"
    
    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

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

    async def async_update(self):       
        schedules = _HASS.data[DOMAIN]["schedules"]
        self._attr_options = self.list_schedules(schedules)
        self.modes = self.parse_schedules(schedules)
        self._attr_current_option = await self.get_active_schedule_name(schedules,self.zone_id)

    async def async_select_option(self, option: str) -> None:
        schedule_id = self.modes.get(option)
        await self.setProgram(schedule_id,self.zone_id)
        self._attr_current_option = option
        await refresh_main_entity(_HASS)

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
        r = _HASS.data[DOMAIN]["active_program"]
        zones = r["zones"]
        for zone in zones:
            if zone["id"] == zone_id:
                id = zone["schedule_id"]
        for schedule in schedules:
            if (schedule["id"]) == id:
                return schedule["title"]  

    async def setProgram(self,schedule_id, zone_id):
        await self.client.set_schedule(zone_id,schedule_id)

class ProgramSelect(SelectEntity):

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.housing = _HASS.data[DOMAIN]["housing"].get("id")
        self._name = "Programme " + _HASS.data[DOMAIN]["housing"].get("name")
        self.device_name = _HASS.data[DOMAIN]["housing"].get("name")
        self._unique_id = self.housing + "program"
        self._attr_options = []
        self._attr_current_option = None
        self.modes = {}
        self.hass = _HASS
    
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
        return self._unique_id

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

    async def async_update(self):       
        programs = await self.get_programs()
        self._attr_options = self.list_programs(programs)
        self.modes = self.parse_programs(programs)
        self._attr_current_option = self.get_active_program_name(programs)

    async def async_select_option(self, option: str) -> None:
        program_id = self.modes.get(option)
        await self.setProgram(program_id)
        self._attr_current_option = option
        await refresh_main_entity(_HASS)
    
    async def get_programs(self):
        req = _HASS.data[DOMAIN]["programs"]
        return req.get("programs")

    def list_programs(self, prglist) -> list:
        programs = []
        for program in prglist:
            programs.append(program["title"])
        return programs

    def parse_programs(self, prglist) -> dict[str, str]:
        programs = {}
        for schedule in prglist:
            programs.update({schedule["title"]: schedule["id"]})
        return programs

    def get_active_program_name(self,prglist) -> str:
        active_program = None
        for program in prglist:
            if program["is_activated"]:
                    active_program = program["title"] 
        return active_program   

    async def setProgram(self,program_id):
        await self.client.set_program(program_id)