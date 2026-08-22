from fastapi import APIRouter, Depends

from configs.app_dependency import get_current_user
from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model

attachment_routes = APIRouter(prefix="/attachments", tags=["Attachments"])


@attachment_routes.get("/{attachment_id}/download")
async def download_attachment(attachment_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await attachment_manager.get_instance().download_attachment(attachment_id=attachment_id, current_user=current_user)
