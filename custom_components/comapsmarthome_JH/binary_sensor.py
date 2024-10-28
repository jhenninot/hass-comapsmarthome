from datetime import datetime, timedelta, timezone
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo

from . import ComapClient
from .const import DOMAIN
from.comap_functions import get_zone_thermal_details


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    config = hass.data[DOMAIN][config_entry.entry_id]
    client = ComapClient(username=config[CONF_USERNAME], password=config[CONF_PASSWORD])

    global HOUSING_DATA
    HOUSING_DATA = hass.data[DOMAIN]["housing"]

    global _HASS
    _HASS = hass

    zones = hass.data[DOMAIN]["thermal_details"].get("zones")

    entities = list()
    for zone in zones:
        if (
            "last_presence_detected" in zone.keys()
            and zone["last_presence_detected"] != None
        ):
            entities.append(
                ComapPresenceSensor(
                    zone_id=zone.get("id"), zone_name=zone.get("title"), client=client
                )
            )
    # entities: entities
    async_add_entities(entities)


class ComapPresenceSensor(BinarySensorEntity):
    def __init__(self, zone_id, zone_name, client):
        super().__init__()
        self.client = client
        self.zone_id = zone_id
        self.zone_name = zone_name
        self._attr_device_class = BinarySensorDeviceClass.OCCUPANCY
        self._name = zone_name + " presence"
        self._id = HOUSING_DATA.get("id") + "_" + zone_id + "_presence"
        self._is_on = None
        self.attrs = dict()

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

    @property
    def extra_state_attributes(self) -> dict:
        return self.attrs

    
    async def async_update(self):
        zone = get_zone_thermal_details(self.zone_id,_HASS.data[DOMAIN]["thermal_details"])
        last_presence_detected = zone.get("last_presence_detected")
        self._is_on = self.is_occupied(last_presence_detected)
        self.attrs.update(
            {
                "last_presence_detected": last_presence_detected,
            }
        )
        self.async_write_ha_state()

    @staticmethod
    def is_occupied(timestamp):
        now = datetime.now(timezone.utc)
        presence = datetime.fromisoformat(timestamp)
        two_minutes = timedelta(minutes=2)
        if now - presence < two_minutes:
            return True
        else:
            return False