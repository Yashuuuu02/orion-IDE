from orion.schemas.settings import ProviderConfig

class LiteLLMConfigBuilder:
    """
    Dynamically generates litellm_config.yaml content from ProviderConfig list.
    Called by LiteLLMManager.configure() every time providers change.
    Never writes to disk — returns config dict that litellm.Router accepts directly.
    """

    def build(self, providers: list[ProviderConfig]) -> dict:
        """
        Returns a dict matching litellm Router config format:
        {
            "model_list": [ ... ],
            "router_settings": {
                "drop_params": True
            }
        }
        Only include enabled providers (provider.enabled == True).
        If no providers enabled: return {"model_list": [], "router_settings": {"drop_params": True}}
        """
        model_list = []
        for provider in providers:
            if not provider.enabled:
                continue

            model_list.append({
                "model_name": "planning",
                "litellm_params": {
                    "model": provider.model_planning,
                    "api_key": provider.api_key,
                    "base_url": provider.base_url or None
                }
            })
            model_list.append({
                "model_name": "fast",
                "litellm_params": {
                    "model": provider.model_fast,
                    "api_key": provider.api_key,
                    "base_url": provider.base_url or None
                }
            })

        return {
            "model_list": model_list,
            "router_settings": {
                "drop_params": True
            }
        }

config_builder = LiteLLMConfigBuilder()
