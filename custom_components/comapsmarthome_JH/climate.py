import logging
from typing import Any

from bidict import bidict
import voluptuous as vol

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.components.climate.const import (
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
)
from homeassistant.components.sensor import PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .comap import ComapClient
from .const import ATTR_SCHEDULE_NAME, DOMAIN, SERVICE_SET_SCHEDULE, ASSIST_COMPATIBILITY
from .comap_functions import refresh_main_entity

_LOGGER = logging.getLogger(__name__)

SENSOR_PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(ASSIST_COMPATIBILITY): cv.boolean
    }
)

PRESET_MODE_MAP = bidict(
    {
        "stop": "off",
        "frost_protection": PRESET_AWAY,
        "eco": PRESET_ECO,
        "comfort": PRESET_COMFORT,
        "comfort_minus1": "comfort -1",
        "comfort_minus2": "comfort -2",
    }
)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
):
    global _HASS
    _HASS = hass

    config = hass.data[DOMAIN][config_entry.entry_id]
    #assist_compatibility = config_entry.data.get(ASSIST_COMPATIBILITY)
    assist_compatibility = False
    await async_setup_platform(hass, config, async_add_entities, assist_compatibility)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    assist_compatibility: bool
) -> None:
    """Set up the comapsmarthome platform."""

    client = ComapClient(username=config[CONF_USERNAME], password=config[CONF_PASSWORD])

    housing_details = hass.data[DOMAIN]["thermal_details"]
    heating_system_state = housing_details.get("heating_system_state")

    for zone in housing_details.get("zones"):
        zone.update({"heating_system_state": heating_system_state})

    zones = [
        ComapZoneThermostat(client, zone, assist_compatibility)
        for zone in housing_details.get("zones")
    ]

    async_add_entities(zones, update_before_add=True)

    schedules = hass.data[DOMAIN]["schedules"]

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_SCHEDULE,
        {
            vol.Required(ATTR_SCHEDULE_NAME): vol.In(
                [schedule["id"] for schedule in schedules]
            )
        },
        "service_set_schedule",
    )

    return True


class ComapZoneThermostat(ClimateEntity):
    _attr_target_temperature_step = 0.5
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    #_attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF, HVACMode.AUTO]
    _attr_preset_modes = [
        "off",
        PRESET_AWAY,
        "comfort -1",
        "comfort -2",
        PRESET_ECO,
        PRESET_COMFORT,
    ]
    _attr_hvac_mode: HVACMode | None
    _attr_hvac_action: HVACAction | None

    def __init__(self, client, zone, assist_compatibility):
        self.hass = _HASS
        super().__init__()
        self._assist_compatibility = assist_compatibility
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        if not assist_compatibility:
            self._attr_hvac_modes.append(HVACMode.AUTO)
        self.client = client
        self.zone_id = zone.get("id")
        self.zone_name = _HASS.data[DOMAIN]["housing"].get("name") + " zone " + zone.get("title")
        self._name = "Thermostat " + _HASS.data[DOMAIN]["housing"].get("name") + " zone " + zone.get("title")
        self._available = True
        self.set_point_type = zone.get("set_point_type")
        if (self.set_point_type == "custom_temperature") | (
            self.set_point_type == "defined_temperature"
        ):
            self.zone_type = "thermostat"
            self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
            self._current_temperature = zone.get("temperature")
            self._current_humidity = zone.get("humidity")
            if self.set_point_type == "custom_temperature":
                self._attr_target_temperature = zone.get("set_point").get("instruction")
            else:
                self.update_target_temperature(zone.get("set_point").get("instruction"))

        if self.set_point_type == "pilot_wire":
            self.zone_type = "pilot_wire"
            self._preset_mode = self.map_preset_mode(
                zone.get("set_point").get("instruction")
            )
            self._attr_supported_features = ClimateEntityFeature.PRESET_MODE
        self._enable_turn_on_off_backwards_compatibility = False
        self._hvac_mode: HVACMode = self.map_hvac_mode(zone)
        self._hvac_action: HVACAction = self.map_hvac_action(zone)
        self.attrs: dict[str, Any] = {}
        self.added = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.zone_id)
            },
            name = self.zone_name,
            manufacturer = "comap",
            serial_number = self.zone_id
        )

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.zone_id

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def current_temperature(self) -> float:
        return self._current_temperature

    @property
    def current_humidity(self) -> int:
        return self._current_humidity

    @property
    def hvac_mode(self) -> HVACMode:
        return self._hvac_mode
    
    @property
    def hvac_action(self) -> HVACAction:
        return self._hvac_action

    @property
    def preset_mode(self) -> str | None:
        return self._preset_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self.attrs

    async def async_added_to_hass(self) -> None:
        self.added = True
        return await super().async_added_to_hass()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.client.set_temporary_instruction(
            self.zone_id, self.map_comap_mode(preset_mode)
        )
        await self.async_update()

    async def async_reset_temporary (self):
        await self.client.remove_temporary_instruction(self.zone_id)
        await self.async_update()

    async def async_set_hvac_mode(self, hvac_mode: str) -> bool:
        """Set new hvac mode."""

        if (hvac_mode == HVACMode.AUTO):
            await self.async_reset_temporary()
        elif (hvac_mode == HVACMode.OFF) & (self.zone_type == "pilot_wire"):
            await self.async_set_preset_mode("off")
        elif (hvac_mode == HVACMode.HEAT) & (self.zone_type == "pilot_wire"):
            await self.async_set_preset_mode(PRESET_COMFORT)
        elif (hvac_mode == HVACMode.OFF) & (self.zone_type == "thermostat"):
            await self.client.set_temporary_instruction(self.zone_id, 7)
            await self.async_update()
        elif (hvac_mode == HVACMode.HEAT) & (self.zone_type == "thermostat"):
            await self.client.set_temporary_instruction(self.zone_id, 20)
            await self.async_update()
        await refresh_main_entity(_HASS)

    async def async_set_temperature(self, **kwargs) -> None:
        await self.client.set_temporary_instruction(self.zone_id, kwargs["temperature"])
        await self.async_update()
        await refresh_main_entity(_HASS)

    async def async_update(self):
        zone_data = None
        thermal_details = _HASS.data[DOMAIN]["thermal_details"]
        zones = thermal_details.get("zones")
        for zone in zones:
            if zone.get("id") == self.zone_id:
                zone_data = zone
        if zone_data is None:
            _LOGGER.error("Error during refresh : no information found for " + self.name)
            return
        heating_system_state = thermal_details.get("heating_system_state")
        zone_data.update({"heating_system_state": heating_system_state})
        self.attributes_update(zone_data)
        if self.added == True:
            self.async_write_ha_state()

    def attributes_update(self, zone_data):
        self._current_temperature = zone_data.get("temperature")
        self._current_humidity = zone_data.get("humidity")
        self._hvac_mode = self.map_hvac_mode(zone_data)
        self._hvac_action = self.map_hvac_action(zone_data)
        self.set_point_type = zone_data.get("set_point_type")
        if self.zone_type == "thermostat":
            self.update_target_temperature(
                zone_data.get("set_point").get("instruction")
            )
        elif self.zone_type == "pilot_wire":
            self._preset_mode = self.map_preset_mode(
                zone_data.get("set_point").get("instruction")
            )
        next_timeslot = zone_data["next_timeslot"]
        self.attrs["next_timeslot"] = next_timeslot["begin_at"]
        self.attrs["next_instruction"] = next_timeslot["set_point"]["instruction"]

    def map_hvac_mode(self, zone_data):
        heating_system_state = zone_data.get("heating_system_state")
        type = zone_data.get("set_point_type")
        temporary_instruction = zone_data.get("events").get("temporary_instruction")
        if temporary_instruction is None:
            hvac_mode_map = {"off": HVACMode.OFF, "on": HVACMode.AUTO}
            if self._assist_compatibility is True:
               hvac_mode_map = {"off": HVACMode.OFF, "on": HVACMode.HEAT} 
            if (heating_system_state is None):
                return HVACMode.OFF
            else:
                if type == "pilot_wire":
                    return hvac_mode_map.get(heating_system_state)
                else:
                    return hvac_mode_map.get(heating_system_state)
        else:
            return HVACMode.HEAT
        
    def map_hvac_action(self, zone_data):
        heating_status = zone_data.get("heating_status")
        heating_system_state = zone_data.get("heating_system_state")
        if heating_system_state == "off":
            return HVACAction.OFF
        hvac_action_map = {"cooling": HVACAction.IDLE, "heating": HVACAction.HEATING}
        if heating_status is None:
            return HVACAction.IDLE
        else:
            return hvac_action_map.get(heating_status)

    def map_preset_mode(self, comap_mode):
        return PRESET_MODE_MAP.get(comap_mode)

    def map_comap_mode(self, ha_mode):
        return PRESET_MODE_MAP.inverse[ha_mode]

    def update_target_temperature(self, instruction):
        if self.set_point_type == "custom_temperature":
            self._attr_target_temperature = instruction
        elif self.set_point_type == "defined_temperature":
            try:
                temperatures = _HASS.data[DOMAIN]["temperatures"]
                if instruction in temperatures:
                    self._attr_target_temperature = temperatures[instruction]
                elif instruction in temperatures["connected"]:
                    self._attr_target_temperature = temperatures["connected"][
                        instruction
                    ]
                elif instruction in temperatures["smart"]:
                    self._attr_target_temperature = temperatures["smart"][instruction]
                else:
                    self._attr_target_temperature = 0
            except:
                self._attr_target_temperature = 0

    async def service_set_schedule(self, **kwargs: Any):
        """Set schedule by id for the zone"""
        r = await self.client.set_schedule(self.zone_id, kwargs.get(ATTR_SCHEDULE_NAME))
        await refresh_main_entity(_HASS)
        return r