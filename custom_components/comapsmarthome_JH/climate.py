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
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from . import ComapDataCoordinator
from .comap import ComapClient
from .const import ATTR_SCHEDULE_NAME, DOMAIN, SERVICE_SET_SCHEDULE, ASSIST_COMPATIBILITY
from .comap_functions import refresh_main_entity

_LOGGER = logging.getLogger(__name__)

SENSOR_PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL): cv.Number,
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

    coordinator = ComapDataCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()

    housing_details = coordinator.data["thermal_details"]
    heating_system_state = housing_details.get("heating_system_state")

    for zone in housing_details.get("zones"):
        zone.update({"heating_system_state": heating_system_state})

    climates = [
        ComapZoneThermostat(coordinator, client, zone, assist_compatibility)
        for zone in housing_details.get("zones")
    ]

    async_add_entities(climates, update_before_add=True)

    schedules = coordinator.data["schedules"]

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

class ComapZonePilot (CoordinatorEntity, ClimateEntity):
    _attr_target_temperature_step = 0.5
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
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

    def __init__(self, coordinator, client, zone, assist_compatibility):
        self.hass = _HASS
        self._assist_compatibility = assist_compatibility
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        if not assist_compatibility:
            self._attr_hvac_modes.append(HVACMode.AUTO)
        self.client = client
        self.zone_id = zone.get("id")
        self.zone_name = coordinator.data["housing"]["name"] + " zone " + zone.get("title")
        self._name = "Thermostat " + coordinator.data["housing"]["name"] + " zone " + zone.get("title")
        self._preset_mode = self.map_preset_mode(
            zone.get("set_point").get("instruction")
        )
        self._attr_supported_features = ClimateEntityFeature.PRESET_MODE
        self._enable_turn_on_off_backwards_compatibility = False
        self._hvac_mode: HVACMode = self.map_hvac_mode(zone)
        self._hvac_action: HVACAction = self.map_hvac_action(zone)
        self.attrs: dict[str, Any] = {}
        self.added = False

# service
    async def service_set_schedule(self, **kwargs: Any):
        """Set schedule by id for the zone"""
        r = await self.client.set_schedule(self.zone_id, kwargs.get(ATTR_SCHEDULE_NAME))
        # Update the data
        await self.coordinator.async_request_refresh()
        return r

#fixes
        
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
    
# updates

    @property
    def current_temperature(self) -> float:
        return self.get_zone_data().get("temperature")

    @property
    def current_humidity(self) -> int:
        self.get_zone_data().get("humidity")

    @property
    def hvac_mode(self) -> HVACMode:
        return self.map_hvac_mode(self.get_zone_data())
    
    @property
    def hvac_action(self) -> HVACAction:
        return self.map_hvac_action(self.get_zone_data())

    @property
    def preset_mode(self) -> str | None:
        zone_data = self.get_zone_data() 
        self._preset_mode = self.map_preset_mode(
                zone_data.get("set_point").get("instruction")
            )
        return self._preset_mode
    
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self.attrs
    
#commandes du thermostat

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

#fonctions internes
    
    def get_zone_data (self):
        zone_data = None
        thermal_details = self.coordinator.data["thermal_details"]
        heating_system_state = thermal_details.get("heating_system_state")
        for zone in thermal_details["zones"]:
            if zone.get("id") == self.zone_id:
                zone_data = zone
        if zone_data is None:
            _LOGGER.error("Error during refresh : no information found for " + self.name)
            return
        zone_data.update({"heating_system_state": heating_system_state})
        return zone_data
        
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
    

class ComapZoneThermostat(CoordinatorEntity, ClimateEntity):
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

    def __init__(self, coordinator, client, zone, assist_compatibility):
        
        super().__init__(coordinator)

        self._assist_compatibility = assist_compatibility
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        if not assist_compatibility:
            self._attr_hvac_modes.append(HVACMode.AUTO)
        self.client = client
        self.zone_id = zone.get("id")
        self.zone_name = coordinator.data["housing"]["name"] + " zone " + zone.get("title")
        self._name = "Thermostat " + coordinator.data["housing"]["name"] + " zone " + zone.get("title")
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
                self._attr_target_temperature = self.get_target_temperature(zone.get("set_point_type"), zone.get("set_point").get("instruction"))

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

#fixes
        
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
    

# updates

    @property
    def current_temperature(self) -> float:
        zone_data = self.get_zone_data(self.coordinator, self.zone_id)
        return zone_data.get("temperature")

    @property
    def current_humidity(self) -> int:
        zone_data = self.get_zone_data(self.coordinator, self.zone_id)
        return zone_data.get("humidity")

    @property
    def hvac_mode(self) -> HVACMode:
        zone_data = self.get_zone_data(self.coordinator, self.zone_id)
        return self.map_hvac_mode(zone_data)
    
    @property
    def hvac_action(self) -> HVACAction:
        zone_data = self.get_zone_data(self.coordinator, self.zone_id)
        return self.map_hvac_action(zone_data)

    @property
    def preset_mode(self) -> str | None:
        return self._preset_mode
    
    @property
    def target_temperature(self):
        zone_data = self.get_zone_data(self.coordinator, self.zone_id)
        instruction = zone_data.get("set_point").get("instruction")
        set_point_type = zone_data.get("set_point_type")
        return self.get_target_temperature(set_point_type, instruction)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        zone_data = self.get_zone_data(self.coordinator, self.zone_id)
        next_timeslot = zone_data["next_timeslot"]
        return {
            "next_timeslot": next_timeslot["begin_at"],
            "next_instruction": next_timeslot["set_point"]["instruction"]

        }
    
#commandes du thermostat

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.client.set_temporary_instruction(
            self.zone_id, self.map_comap_mode(preset_mode)
        )
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_reset_temporary (self):
        await self.client.remove_temporary_instruction(self.zone_id)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

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
        elif (hvac_mode == HVACMode.HEAT) & (self.zone_type == "thermostat"):
            await self.client.set_temporary_instruction(self.zone_id, 20)
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs) -> None:
        await self.client.set_temporary_instruction(self.zone_id, kwargs["temperature"])
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()


#fonctions internes
        
    def get_zone_data (self, coordinator, zone_id):
        zone_data = None
        thermal_details = coordinator.data["thermal_details"]
        heating_system_state = thermal_details.get("heating_system_state")
        for zone in thermal_details["zones"]:
            if zone.get("id") == zone_id:
                zone_data = zone
        if zone_data is None:
            _LOGGER.error("Error during refresh : no information found for " + self.name)
            return
        zone_data.update({"heating_system_state": heating_system_state})
        return zone_data

        
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

    def get_target_temperature(self, set_point_type, instruction):
        if set_point_type == "custom_temperature":
            return instruction
        elif set_point_type == "defined_temperature":
            try:
                temperatures = self.coordinator.data["temperatures"]
                if instruction in temperatures:
                    return temperatures[instruction]
                elif instruction in temperatures["connected"]:
                    return temperatures["connected"][instruction]
                elif instruction in temperatures["smart"]:
                    return temperatures["smart"][instruction]
                else:
                    return 0
            except:
                return 0

# service
    async def service_set_schedule(self, **kwargs: Any):
        """Set schedule by id for the zone"""
        r = await self.client.set_schedule(self.zone_id, kwargs.get(ATTR_SCHEDULE_NAME))
        # Update the data
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()
        return r