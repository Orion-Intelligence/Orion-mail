from fastapi import APIRouter, Depends, Query

from configs.app_dependency import get_current_user
from orion.api.interactive.messenger_manager.messenger_manager import messenger_manager
from orion.api.interactive.messenger_manager.models.messenger_param_model import MessengerSendRequest
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


messenger_routes = APIRouter(prefix="/messenger-api", tags=["Messenger"])


@messenger_routes.get("/users")
async def list_messenger_users(query: str = Query(default="", max_length=100), limit: int = Query(default=100, ge=1, le=200), offset: int = Query(default=0, ge=0), current_user: db_user_model = Depends(get_current_user)):
    return await messenger_manager.get_instance().list_users(
        current_user=current_user,
        query=query,
        limit=limit,
        offset=offset,
    )


@messenger_routes.get("/conversations")
async def list_messenger_conversations(current_user: db_user_model = Depends(get_current_user)):
    return await messenger_manager.get_instance().list_conversations(current_user)


@messenger_routes.get("/conversations/{other_user_id}/messages")
async def get_messenger_messages(other_user_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await messenger_manager.get_instance().get_messages(current_user=current_user, other_user_id=other_user_id)


@messenger_routes.post("/messages")
async def send_messenger_message(request: MessengerSendRequest, current_user: db_user_model = Depends(get_current_user)):
    return await messenger_manager.get_instance().send_message(current_user=current_user, request=request)
