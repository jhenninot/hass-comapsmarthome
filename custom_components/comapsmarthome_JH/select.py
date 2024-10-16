from datetime import timedelta
import logging
from typing import Any
from bidict import bidict
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from .const import COMAP_SCHEDULE_SCAN_INTERVAL
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry


from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
)

from . import ComapCoordinator, ComapClient

from .const import (
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_HASS = HomeAssistant
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

    # Extraire la valeur de l'intervalle de scan depuis la configuration
    scan_interval_minutes = config.get(COMAP_SCHEDULE_SCAN_INTERVAL, 1)
    scan_interval = timedelta(minutes=scan_interval_minutes)
    
    req = await client.get_zones()
    zones = req.get("zones")

    zones_selects = [
        ZoneModeSelect(client, scan_interval, zone)
        for zone in zones
    ]

    central_select = CentralModeSelect(client, scan_interval, related_entities=zones_selects)

    central_program = ProgramSelect(client,scan_interval)

    selects = [central_select] + zones_selects + [central_program]

    async_add_entities(selects, update_before_add=True)


class CentralModeSelect(SelectEntity):
    """Representation of the central mode choice"""

    def __init__(self, client, scan_interval, related_entities):
        super().__init__()
        self._scan_interval = scan_interval
        self.client = client
        self.housing = HOUSING_DATA.get("id")
        self._name = "Planning global " + HOUSING_DATA.get("name")
        self.device_name = HOUSING_DATA.get("name")
        self._attr_unique_id = "central_mode"
        self._attr_options = []
        self._attr_current_option = None
        self.modes = {}
        self._available = True
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
        return self.housing + "_schedule"
    
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
                (DOMAIN, HOUSING_DATA.get("id"))
            },
            name=HOUSING_DATA.get("name"),
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

    def __init__(self, client, scan_interval, zone):
        super().__init__()
        self._scan_interval = scan_interval
        self.client = client
        self.housing = HOUSING_DATA.get("id")
        self._name = "Planning " + HOUSING_DATA.get("name") + " zone " + zone.get("title")
        self.zone_id = zone.get("id")
        self._attr_unique_id = "zone_mode_" + zone.get("id")
        self.zone_name = zone.get("title")
        self._attr_options = []
        self._attr_current_option = None
        self.modes = {}
        self._available = True
    
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

class ProgramSelect(SelectEntity):

    def __init__(self, client, scan_interval):
        super().__init__()
        self._scan_interval = scan_interval
        self.client = client
        self.housing = HOUSING_DATA.get("id")
        self._name = "Programme " + HOUSING_DATA.get("name")
        self.device_name = HOUSING_DATA.get("name")
        self._unique_id = self.housing + "program"
        self._attr_options = []
        self._attr_current_option = None
        self.modes = {}
        self.hass = _HASS

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
        return self._unique_id

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

    async def async_update(self):       
        programs = await self.get_programs()
        self._attr_options = self.list_programs(programs)
        self.modes = self.parse_programs(programs)
        self._attr_current_option = self.get_active_program_name(programs)

    async def async_select_option(self, option: str) -> None:
        program_id = self.modes.get(option)
        await self.setProgram(program_id)
        self._attr_current_option = option
        await self.refresh_all_entities_for_device()
    
    async def get_programs(self):
        req = await self.client.get_programs()
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

    async def refresh_all_entities_for_device(self):
        """Rafraîchit toutes les entités liées à un appareil spécifique."""
        # Récupérer le registre des entités
        entity_registry = async_get_entity_registry(self.hass)

        # Trouver toutes les entités liées à l'identifiant de l'appareil
        entities_to_refresh = [
            entry.entity_id for entry in entity_registry.entities.values()
            if entry.platform == DOMAIN
        ]

        # Rafraîchir chaque entité
        for entity_id in entities_to_refresh:
            await self.hass.services.async_call(
               "homeassistant", "update_entity", {"entity_id": entity_id}
            )