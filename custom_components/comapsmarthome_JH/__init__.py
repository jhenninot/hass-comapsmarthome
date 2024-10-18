"""ComapSmartHome custom component."""

from asyncio import timeout
from datetime import timedelta
import logging

from homeassistant import config_entries, core
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .comap import ComapClientException, ComapClient
from .const import DOMAIN, COMAP_SENSOR_SCAN_INTERVAL
from .comap_functions import get_now

from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant, 
    entry: config_entries.ConfigEntry
) -> bool:
    
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})

    hass.data[DOMAIN][entry.entry_id] = entry.data

    config = hass.data[DOMAIN][entry.entry_id]
    scan_interval_minutes = config.get(COMAP_SENSOR_SCAN_INTERVAL, 1)

    client = ComapClient(username=config[CONF_USERNAME], password=config[CONF_PASSWORD])

    global HASS, COMAP_CLIENT, SCAN_INTERVAL
    HASS = hass
    COMAP_CLIENT = client
    SCAN_INTERVAL = timedelta(minutes=scan_interval_minutes)
    
    hass.data[DOMAIN]["housing"] = await client.async_gethousing_data()
    hass.data[DOMAIN]["thermal_details"] = await client.get_thermal_details()
    hass.data[DOMAIN]["connected_objects"] = await client.get_housing_connected_objects()
    hass.data[DOMAIN]["schedules"] = await client.get_schedules()

    # Forward the setup to the sensor platform.
    await hass.config_entries.async_forward_entry_setups(
        entry, ["sensor"]
    )
    await hass.config_entries.async_forward_entry_setups(
        entry, ["switch", "select", "climate"]

        #"binary_sensor" a été mis de côté pour le moment
    )
    return True

class ComapDataCoordinator (DataUpdateCoordinator):
    def __init__(self,hass):
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="ComapSmartHome",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval = SCAN_INTERVAL,
        )
        self.client = COMAP_CLIENT

    async def _async_update_data(self) -> dict:
        _LOGGER.warning("Updating state for %s", self.name)
        try:
            thermal_details = await self.client.get_thermal_details()
            for zone in thermal_details["zones"]:
                zone["heating_system_state"] = thermal_details["heating_system_state"]

            housing = await self.client.async_gethousing_data()
            connected_objects = await self.client.get_housing_connected_objects()
            schedules = await self.client.get_schedules()
            temperatures = await self.client.get_custom_temperatures()

            data = {
                "housing": housing,
                "thermal_details": thermal_details,
                "connected_objects": connected_objects,
                "schedules": schedules,
                "automatic_update_time": get_now(),
                "temperatures": temperatures
            }

            _LOGGER.warning(data["thermal_details"])

            return data
            
        except ComapClientException as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed from err
    