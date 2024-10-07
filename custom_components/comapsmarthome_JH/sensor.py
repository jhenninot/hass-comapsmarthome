from datetime import timedelta
import logging
from typing import Any, Optional

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .comap import ComapClient
from .const import (
    ATTR_ADDRESS,
    ATTR_AVL_SCHDL,
    DOMAIN,
    SERVICE_SET_AWAY,
    SERVICE_SET_HOME,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)

SENSOR_PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL): cv.Number,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
):
    config = hass.data[DOMAIN][config_entry.entry_id]
    await async_setup_platform(hass, config, async_add_entities)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
) -> None:


    connected_objects = await client.get_housing_connected_objects()
    obj_list = []
    for object in connected_objects:
        if ('voltage_percent' in object):
            obj_list.append(object)
    
    sensors = [
        ComapBatterySensor(client,batt_sensor)
        for batt_sensor in obj_list
    ]

    client = ComapClient(username=config[CONF_USERNAME], password=config[CONF_PASSWORD])

    housing_sensor = ComapHousingSensor(client)

    sensors.append(housing_sensor)

    async_add_entities(sensors, update_before_add=True)

    async def set_away(call):
        """Set home away."""
        await client.leave_home()

    async def set_home(call):
        """Set home."""
        await client.return_home()

    hass.services.async_register(DOMAIN, SERVICE_SET_AWAY, set_away)
    hass.services.async_register(DOMAIN, SERVICE_SET_HOME, set_home)

    return True


class ComapHousingSensor(Entity):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.housing = client.housing
        self._name = client.get_housings()[0].get("name")
        self._state = None
        self._available = True
        self.attrs: dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.client.housing

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def state(self) -> Optional[str]:
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.attrs

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            name=self.name,
            manufacturer="comap",
        )

    async def async_update(self):
        housings = await self.hass.async_add_executor_job(self.client.get_housings)
        self._name = housings[0].get("name")
        self.attrs[ATTR_ADDRESS] = housings[0].get("address")
        r = await self.get_schedules()
        self.attrs[ATTR_AVL_SCHDL] = self.parse_schedules(r)
        prg_name = await self.get_active_schedule_name(r)
        self.attrs["TEST"] = await self.client.get_housing_connected_objects()
        self._state = prg_name

    async def get_schedules(self):
        r = await self.client.get_schedules()
        return r

    def parse_schedules(self, r) -> dict[str, str]:
        schedules = {}
        for schedule in r:
            schedules.update({schedule["id"]: schedule["title"]})
        return schedules
        
    async def get_active_program(self):
        r = await self.client.get_active_program()
        return r
        
    async def get_active_schedule_name(self,schedules):
        r = await self.client.get_active_program()
        id = r["zones"][0]["schedule_id"]
        for schedule in schedules:
            if (schedule["id"]) == id:
                return schedule["title"]
            

class ComapBatterySensor(Entity):
    def __init__(self, client, batt_sensor):
        super().__init__()
        """Initialize the battery sensor."""
        self.client = client
        self._state = batt_sensor.get("voltage_percent")
        self.housing = client.housing
        self._unique_id = "comap_batt_" + batt_sensor.get("serial_number")
        self.sn = batt_sensor.get("serial_number")
        self._batt = batt_sensor.get("voltage_percent")

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Comap Test Battery" + self.sn
    
    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return "comap_battery_" + self.sn
    @property
    def state(self):
        """Return the state of the sensor."""
        # Remplacez par la logique qui récupère l'état actuel de la batterie
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return PERCENTAGE

    async def async_update(self):
        """Fetch new state data for the sensor."""
        # Mettre à jour l'état ici en appelant votre client Comap pour récupérer la batterie
        self._state = self._batt