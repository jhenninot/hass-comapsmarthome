"""Config flow to configure Comap smart home."""
import logging

from .comap import ComapClient, ComapClientException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_SCAN_INTERVAL

from .const import DOMAIN


DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Required(CONF_SCAN_INTERVAL, default=1): int
})

_LOGGER = logging.getLogger(__name__)


class ComapFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a ComapSmartHome config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            try:
                self._async_abort_entries_match(
                    {CONF_USERNAME: user_input[CONF_USERNAME]}
                )
                client = ComapClient(username=user_input[CONF_USERNAME],password=user_input[CONF_PASSWORD])

            except ComapClientException:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=DOMAIN, data=user_input)
            
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Define the flow to handle options."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for the Comap Smart Home integration."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options form."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle the options form."""
        if user_input is not None:
            # Sauvegarder la nouvelle valeur de seuil
            return self.async_create_entry(title="Délai de rafraichissement des infos", data=user_input)

        # Obtenir la valeur actuelle ou utiliser la valeur par défaut
        current_interval_value = self.config_entry.options.get(CONF_SCAN_INTERVAL, 1)

        data_schema = vol.Schema({
            vol.Required(CONF_SCAN_INTERVAL, default=current_interval_value): vol.Range(min=1, max=30, msg="Value must be between 1 and 30"),
        })

        return self.async_show_form(step_id="user", data_schema=data_schema)