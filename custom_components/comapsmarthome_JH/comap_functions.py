import logging

from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def refresh_all_comap_entities(hass, unique_id):

    """Rafraîchit toutes les entités liées à un domaine spécifique."""
    # Récupérer le registre des entités
    entity_registry = async_get_entity_registry(hass)

    # Trouver toutes les entités liées à l'identifiant de l'appareil
    entities_to_refresh = [
        entry.entity_id for entry in entity_registry.entities.values()
        if (entry.platform == DOMAIN) & (entry.unique_id != unique_id)
    ]

    # Rafraîchir chaque entité
    for entity_id in entities_to_refresh:
        try:
            await hass.services.async_call(
                "homeassistant", "update_entity", {"entity_id": entity_id}
            )
        except:
            pass

async def refresh_main_entity (hass):
    unique_id = hass.data[DOMAIN]["main_sensor_id"]
    entity_registry = async_get_entity_registry(hass)
    entities_to_refresh = [
        entry.entity_id for entry in entity_registry.entities.values()
        if (entry.platform == DOMAIN) & (entry.unique_id == unique_id)
    ]
    for entity_id in entities_to_refresh:
        try:
            await hass.services.async_call(
                "homeassistant", "update_entity", {"entity_id": entity_id}
            )
        except:
            pass

def get_connected_object_zone_infos(object_sn, thermal_details):
    zones = thermal_details.get("zones")
    zone_id = None
    zone_title = None
    for zone in zones:
        zone_obj = zone.get("connected_objects")
        for obj_serial in zone_obj:
            if obj_serial == object_sn:
                zone_title = zone.get("title")
                zone_id = zone.get("id")
    return {
        "id": zone_id,
        "title": zone_title
    }