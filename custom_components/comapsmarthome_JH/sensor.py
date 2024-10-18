from datetime import timedelta, datetime
from zoneinfo import ZoneInfo

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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .comap_functions import refresh_all_comap_entities, get_connected_object_zone_infos, get_now

from . import ComapDataCoordinator

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
    
    #
    coordinator = ComapDataCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()

    client = ComapClient(username=config[CONF_USERNAME], password=config[CONF_PASSWORD])
    
    themal_details = coordinator.data["thermal_details"]
    connected_objects = coordinator.data["connected_objects"]

    zones = themal_details.get("zones")
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
        ComapBatterySensor(coordinator, batt_sensor)
        for batt_sensor in batt_list
    ]

    device_sensors = [
        ComapDeviceSensor(coordinator, device_sensor)
        for device_sensor in connected_objects
    ]


    housing_sensors = [ComapHousingSensor(coordinator)]

    sensors = housing_sensors + device_sensors + batt_sensors

    async_add_entities(sensors, update_before_add = True)

    async def set_away(call):
        """Set home away."""
        await client.leave_home()

    async def set_home(call):
        """Set home."""
        await client.return_home()

    hass.services.async_register(DOMAIN, SERVICE_SET_AWAY, set_away)
    hass.services.async_register(DOMAIN, SERVICE_SET_HOME, set_home)

    return True


class ComapHousingSensor(CoordinatorEntity, Entity):

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.housing_id = coordinator.data["housing"]["id"]
        self._name = None
        self._id = self.housing_id + "_sensor"

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return "Infos " + self.coordinator.data["housing"]["name"]

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.coordinator.data["housing"]["id"] + "_sensor"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.housing_id)
            },
            name=self.name,
            manufacturer="comap",
            serial_number = self.housing_id
        )
    
    @property
    def state(self) -> Optional[str]:
        return self.coordinator.data["thermal_details"]["services_available"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "automatic_update_time": self.coordinator.data["automatic_update_time"],
            ATTR_ADDRESS:  self.coordinator.data["housing"]["address"]
        }            

class ComapBatterySensor(CoordinatorEntity, Entity):
    def __init__(self, coordinator, batt_sensor):
        super().__init__(coordinator)
        self.housing_id = coordinator.data["housing"]["id"]
        self.housing_name = coordinator.data["housing"]["name"]
        self.sn = batt_sensor.get("serial_number")
        self.model = batt_sensor.get("model")
        obj_zone_infos = get_connected_object_zone_infos(self.sn, coordinator.data["thermal_details"])
        self.zone_name = obj_zone_infos.get("title")
        if self.zone_name is None:
            self.zone_name = ""
        self._name = "Batterie " + self.model + " " + self.zone_name + " " + self.housing_name
        self.zone_id = obj_zone_infos.get("id")
        if self.zone_id is None:
            self.zone_id = self.housing_id
        self._unique_id = self.housing_id + "_" + self.zone_id + "_battery_" + self.model + "_"+ self.sn

    @property
    def name(self):
        return self._name
    
    @property
    def device_class(self) -> str:
        return "battery"

    @property
    def unique_id(self) -> str:
        return self._unique_id
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.zone_id)
            },
            name = self.zone_name + " " + self.housing_name,
            manufacturer = "comap",
            serial_number = self.zone_id
        )
    
    @property
    def unit_of_measurement(self):
        return PERCENTAGE
    
    @property
    def battery(self) -> str:
        return self.get_batt_level()
    
    @property
    def state(self):
        return self.get_batt_level()
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "automatic_update_time": self.coordinator.data["automatic_update_time"],
        }

    def get_batt_level(self):
        batt_level = None
        for object in self.coordinator.data["connected_objects"]:
            if object.get("serial_number") == self.sn:
                batt_level = object.get("voltage_percent")
        return batt_level


class ComapDeviceSensor(CoordinatorEntity,Entity):

    def __init__(self, coordinator, device_sensor):
        super().__init__(coordinator)
        self.housing_id = coordinator.data["housing"]["id"]
        self.housing_name = coordinator.data["housing"]["name"]
        self.sn = device_sensor.get("serial_number")
        self.model = device_sensor.get("model")

        obj_zone_infos = get_connected_object_zone_infos(self.sn, coordinator.data["thermal_details"])
        self.zone_name = obj_zone_infos.get("title")
        if self.zone_name is None:
            self.zone_name = ""
        self._name = self.model.capitalize() + " " + self.zone_name
        self.zone_id = obj_zone_infos.get("id")
        if self.zone_id is None:
            self.zone_id = self.housing_id
        self._unique_id = self.housing_id + "_" + self.zone_id + "_" + self.model + "_"+ self.sn
    
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
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.zone_id)
            },
            name = self.zone_name + " " + self.housing_name,
            manufacturer = "comap",
            serial_number = self.zone_id
        )
    
    @property
    def state(self) -> Optional[str]:
        data = self.get_state_and_attrs()
        return data["state"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.get_state_and_attrs()
        return data["attrs"]

    def get_state_and_attrs(self):
        state = None
        attrs = {
            "automatic_update_time": self.coordinator.data["automatic_update_time"]
        }
        for object in self.coordinator.data["connected_objects"]:
            if object.get("serial_number") == self.sn:
                state = object.get("communication_status")
                attrs.update(object)
        return {
            "state": state,
            "attrs": attrs
        }


