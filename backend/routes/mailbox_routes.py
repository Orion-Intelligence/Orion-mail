from fastapi import APIRouter, Depends

from configs.app_dependency import get_current_user
from orion.api.interactive.mailbox_manager.mailbox_manager import mailbox_manager
from orion.api.interactive.message_manager.models.message_param_model import MailboxSettingsRequest
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model

mailbox_routes = APIRouter(prefix="/mailboxes", tags=["Mailboxes"])


@mailbox_routes.post("")
async def create_user_mailbox(current_user: db_user_model = Depends(get_current_user)):
    return await mailbox_manager.get_instance().create_mailbox(current_user=current_user)


@mailbox_routes.get("/me")
async def get_my_mailbox(current_user: db_user_model = Depends(get_current_user)):
    return await mailbox_manager.get_instance().get_user_mailbox(current_user=current_user)


@mailbox_routes.delete("/me")
async def delete_my_mailbox(current_user: db_user_model = Depends(get_current_user)):
    return await mailbox_manager.get_instance().delete_mailbox(current_user=current_user)


@mailbox_routes.put("/me/settings")
async def update_my_mailbox_settings(settings_data: MailboxSettingsRequest, current_user: db_user_model = Depends(get_current_user)):
    return await mailbox_manager.get_instance().update_mailbox_settings(current_user=current_user, signature=settings_data.signature)
