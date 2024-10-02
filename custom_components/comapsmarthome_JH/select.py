from datetime import timedelta
import logging
from typing import Any
from bidict import bidict
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.device_registry import DeviceInfo


from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
)

from . import ComapCoordinator, ComapClient

from .const import (
    DOMAIN,
)

SCAN_INTERVAL = timedelta(minutes=5)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    config = hass.data[DOMAIN][config_entry.entry_id]
    client = ComapClient(username=config[CONF_USERNAME], password=config[CONF_PASSWORD])
    async_add_entities([CentralModeSelect(client)], update_before_add=True)


class CentralModeSelect(SelectEntity):
    """Representation of the central mode choice"""

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.housing = client.housing
        self._name = "Programme"
        self._attr_unique_id = "central_mode"
        self._attr_options = []
        self._attr_current_option = None
        self.modes = {}

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
            name=self._name,
            manufacturer="comap",
        )



    async def async_update(self):
        housings = await self.hass.async_add_executor_job(self.client.get_housings)
        
        schedules = await self.get_schedules()
        self._attr_options = self.list_schedules(schedules)
        self.modes = self.parse_schedules(schedules)
        self._attr_current_option = await self.get_active_schedule_name(schedules)

    async def async_select_option(self, option: str) -> None:
        schedule_id = self.modes.get(option)
        await self.setProgram(schedule_id)
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
    
            