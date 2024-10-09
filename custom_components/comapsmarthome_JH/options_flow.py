import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN

class MyComponentOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for MyComponent."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options for the custom component."""
        if user_input is not None:
            # Mettre à jour les options avec les nouvelles valeurs
            return self.async_create_entry(title="", data=user_input)

        # Récupérer la valeur actuelle de l'intervalle de rafraîchissement
        options = self.config_entry.options
        current_interval = options.get("refresh_interval", 60)  # Valeur par défaut de 60s

        # Créer un formulaire pour entrer le délai de rafraîchissement
        data_schema = vol.Schema({
            vol.Required("refresh_interval", default=current_interval): int
        })

        return self.async_show_form(step_id="init", data_schema=data_schema)