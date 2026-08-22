from fastapi import APIRouter, Depends

from configs.app_dependency import get_current_user
from orion.api.server.config_manager.config_controller import config_controller
from orion.api.server.config_manager.models.config_param_model import SystemConfigUpdateRequest
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model

config_routes = APIRouter(prefix="/system-config", tags=["System configuration"])


@config_routes.get("")
async def get_system_config(_current_user: db_user_model = Depends(get_current_user)):
    return await config_controller.get_instance().get_settings()


@config_routes.put("")
async def update_system_config(config_data: SystemConfigUpdateRequest, _current_user: db_user_model = Depends(get_current_user)):
    return await config_controller.get_instance().update_settings(config_data.model_dump())
