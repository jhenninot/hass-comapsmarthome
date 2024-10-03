from homeassistant.const import  Platform

DOMAIN = "comapsmarthome"
ATTR_ADDRESS = "address"
ATTR_TEMPERATURE = "temperature"
ATTR_AVL_SCHDL = "available_schedules"
SERVICE_SET_AWAY = "set_away"
SERVICE_SET_HOME = "set_home"
SERVICE_SET_SCHEDULE = "set_schedule"
ATTR_SCHEDULE_NAME = "schedule_name"

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
]
