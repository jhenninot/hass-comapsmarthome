from datetime import timedelta
import logging
from typing import Any, Optional

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, PERCENTAGE
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
    COMAP_SENSOR_SCAN_INTERVAL
)

_LOGGER = logging.getLogger(__name__)

SENSOR_PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(COMAP_SENSOR_SCAN_INTERVAL): cv.Number,
    }
)

SCAN_INTERVAL = timedelta(minutes=1)

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

    # Extraire la valeur de l'intervalle de scan depuis la configuration
    scan_interval_minutes = config.get(COMAP_SENSOR_SCAN_INTERVAL, 1)
    scan_interval = timedelta(minutes=scan_interval_minutes)

    client = ComapClient(username=config[CONF_USERNAME], password=config[CONF_PASSWORD])

    global HOUSING_DATA
    HOUSING_DATA = hass.data[DOMAIN]["housing"]

    connected_objects = await client.get_housing_connected_objects()

    req = await client.get_zones()
    zones = req.get("zones")
    obj_zone_names = {}
    obj_zone_ids = {}
    for zone in zones:
        zone_obj = zone.get("connected_objects")
        for obj_serial in zone_obj:
            obj_zone_names[obj_serial] = zone.get("title")
            obj_zone_ids[obj_serial] = zone.get("id")

    batt_list = []
    for object in connected_objects:
        if ('voltage_percent' in object):
            batt_list.append(object)
    
    batt_sensors = [
        ComapBatterySensor(client, batt_sensor, obj_zone_names, obj_zone_ids, scan_interval)
        for batt_sensor in batt_list
    ]

    device_sensors = [
        ComapDeviceSensor(client, device_sensor, obj_zone_names, obj_zone_ids, scan_interval)
        for device_sensor in connected_objects
    ]


    housing_sensors = [ComapHousingSensor(client, scan_interval)]

    sensors = housing_sensors + device_sensors + batt_sensors

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
    def __init__(self, client, scan_interval):
        super().__init__()
        self._scan_interval = scan_interval
        self.client = client
        self.housing = HOUSING_DATA.get("id")
        self._name = "Infos " + HOUSING_DATA.get("name")
        self._state = None
        self._available = True
        self.attrs: dict[str, Any] = {}

    @property
    def scan_interval(self) -> timedelta:
        """Retourne l'intervalle de scan défini."""
        return self._scan_interval

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.housing + "_sensor"

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
                (DOMAIN, self.housing)
            },
            name=self.name,
            manufacturer="comap",
            serial_number = self.housing
        )

    async def async_update(self):
        housings = await self.client.async_get_housings()
        self._name = housings[0].get("name")
        self.attrs[ATTR_ADDRESS] = housings[0].get("address")
        self.attrs["thermal-details"] = await self.client.get_zones()
        thermal_details = await self.client.get_zones()
        self._state = thermal_details.get("services_available")
                   

class ComapBatterySensor(Entity):
    def __init__(self, client, batt_sensor, obj_zone_names, obj_zone_ids, scan_interval):
        super().__init__()
        """Initialize the battery sensor."""
        self._scan_interval = scan_interval
        self.client = client
        self._state = batt_sensor.get("voltage_percent")
        self.housing = HOUSING_DATA.get("id")
        self._unique_id = None
        self.sn = batt_sensor.get("serial_number")
        self.model = batt_sensor.get("model")
        self._batt = batt_sensor.get("voltage_percent")
        self.zone_name = ""
        if (self.sn in obj_zone_names):
            self.zone_name = obj_zone_names.get(self.sn)
        self._name = "Batterie " + self.model + " " + self.zone_name + " " + self.client.get_housings()[0].get("name")
        self.zone_id = self.housing
        if (self.sn in obj_zone_ids):
            self.zone_id = obj_zone_ids.get(self.sn)

    @property
    def scan_interval(self) -> timedelta:
        """Retourne l'intervalle de scan défini."""
        return self._scan_interval

    @property
    def name(self):
        return self._name
    
    @property
    def battery(self) -> str:
        return self._state
    
    @property
    def device_class(self) -> str:
        return "battery"

    @property
    def unique_id(self) -> str:
        return self.housing + "_" + self.zone_id + "_battery_" + self.model + "_"+ self.sn
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.zone_id)
            },
            name = self.zone_name + " " + HOUSING_DATA.get("name"),
            manufacturer = "comap",
            serial_number = self.zone_id
        )

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return PERCENTAGE

    async def async_update(self):
        batt = None
        objects = await self.client.get_housing_connected_objects()
        for object in objects:
            if object.get("serial_number") == self.sn:
                batt = object.get("voltage_percent")
        self._state = batt

class ComapDeviceSensor(Entity):
    def __init__(self, client, device_sensor, obj_zone_names, obj_zone_ids, scan_interval):
        super().__init__()
        self._scan_interval = scan_interval
        self.client = client
        self.housing = HOUSING_DATA.get("id")
        self._state = None
        self._available = True
        #self._attr_disabled_by = 'integration'
        self._unique_id = None
        self.sn = device_sensor.get("serial_number")
        self.model = device_sensor.get("model")
        self.attrs: dict[str, Any] = {}
        self.device_sensor = device_sensor
        self.zone_name = ""
        if (self.sn in obj_zone_names):
            self.zone_name = obj_zone_names.get(self.sn)
        self._name = self.model.capitalize() + " " + self.zone_name
        self.zone_id = self.housing
        if (self.sn in obj_zone_ids):
            self.zone_id = obj_zone_ids.get(self.sn)

    @property
    def scan_interval(self) -> timedelta:
        """Retourne l'intervalle de scan défini."""
        return self._scan_interval
    
    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        icons = {
            "gateway": "mdi:network",
            "heating_module": "mdi:access-point",
            "thermostat": "mdi:home-thermometer"
        }
        if (self.model in icons):
            return icons.get(self.model)
        
        return "mdi:help-rhombus"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.housing + "_" + self.zone_id + "_" + self.model + "_"+ self.sn

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
                (DOMAIN, self.zone_id)
            },
            name = self.zone_name + " " + self.client.get_housings()[0].get("name"),
            manufacturer = "comap",
            serial_number = self.zone_id
        )

    async def async_update(self):
        zones = await self.client.get_eligible_zones(self.sn)
        objects = await self.client.get_housing_connected_objects()
        for object in objects:
            if object.get("serial_number") == self.sn:
                self.attrs = object
                self._state = object.get("communication_status")
        self.attrs["Zones"] = zones