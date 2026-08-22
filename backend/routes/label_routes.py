from fastapi import APIRouter, Depends, status

from configs.app_dependency import get_current_user
from orion.api.interactive.label_manager.label_manager import label_manager
from orion.api.interactive.label_manager.models.label_param_model import LabelCreateRequest, LabelUpdateRequest
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model

label_routes = APIRouter(prefix="/labels", tags=["Labels"])


@label_routes.get("")
async def get_user_labels(current_user: db_user_model = Depends(get_current_user)):
    return await label_manager.get_instance().get_labels(current_user=current_user)


@label_routes.post("", status_code=status.HTTP_201_CREATED)
async def create_user_label(label_data: LabelCreateRequest, current_user: db_user_model = Depends(get_current_user)):
    return await label_manager.get_instance().create_label(current_user=current_user, label_data=label_data)


@label_routes.patch("/{label_id}")
async def update_user_label(label_id: str, label_data: LabelUpdateRequest, current_user: db_user_model = Depends(get_current_user)):
    return await label_manager.get_instance().update_label(current_user=current_user, label_id=label_id, label_data=label_data)


@label_routes.delete("/{label_id}")
async def delete_user_label(label_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await label_manager.get_instance().delete_label(current_user=current_user, label_id=label_id)


@label_routes.get("/{label_id}/messages")
async def get_user_label_messages(label_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await label_manager.get_instance().get_label_messages(current_user=current_user, label_id=label_id)
