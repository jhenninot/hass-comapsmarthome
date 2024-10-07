from homeassistant.components.sensor import SensorEntity
from homeassistant.const import TEMP_CELSIUS

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setup the sensor platform."""
    sensors = [
        CustomSensor("Sensor 1", "25.6"),
    ]
    async_add_entities(sensors)

class CustomSensor(SensorEntity):
    def __init__(self, name, state):
        self._name = name
        self._state = state

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS