"""ComapSmartHome custom component."""

from asyncio import timeout
from datetime import timedelta
import logging

from homeassistant import config_entries, core
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .comap_functions import setComapValues

from .comap import ComapClientException, ComapClient
from .const import DOMAIN

from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    
    
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data


    config = hass.data[DOMAIN][entry.entry_id]
    client = ComapClient(username=config[CONF_USERNAME], password=config[CONF_PASSWORD])

    
    await setComapValues(hass,client)

    # Forward the setup to the sensor platform.
    await hass.config_entries.async_forward_entry_setups(
        entry, ["sensor"]
    )
    await hass.config_entries.async_forward_entry_setups(
        entry, ["binary_sensor", "switch", "select", "climate"]
    )

    return True