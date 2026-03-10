from fastapi import APIRouter
from orion.core.config import settings
from orion.schemas.settings import ProviderConfig
from orion.llm.manager import llm_manager

router = APIRouter()

@router.get("/settings")
async def get_settings():
    setting_dict = settings.model_dump()
    # Mask api key values
    if "api_keys" in setting_dict:
        for k in setting_dict["api_keys"]:
            setting_dict["api_keys"][k] = "********"
    if "OPENAI_API_KEY" in setting_dict and setting_dict["OPENAI_API_KEY"]:
        setting_dict["OPENAI_API_KEY"] = "********"
    return setting_dict

@router.post("/settings/provider")
async def add_provider(provider: ProviderConfig):
    # Retrieve current configured providers from llm_manager or just override/add
    # Simplified configure call for test
    llm_manager.configure([provider])
    return {"status": "configured"}

@router.delete("/settings/provider/{provider_name}")
async def delete_provider(provider_name: str):
    # Removes provider from llm_manager
    # In a real app we'd filter the list, for this stub we clear it if matching or just clear
    llm_manager.configure([])
    return {"status": "deleted"}
