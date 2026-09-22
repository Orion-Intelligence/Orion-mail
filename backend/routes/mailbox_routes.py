from fastapi import APIRouter, Depends, Request

from configs.app_dependency import get_current_user, login_session_id
from configs.auth_cookie import session_token_from_request
from orion.api.interactive.e2e_key_manager.e2e_key_manager import e2e_key_manager
from orion.api.interactive.e2e_key_manager.models.e2e_key_param_model import E2eKeyBundleRequest, E2eKeyLookupRequest, E2eKeyUnlockRequest
from orion.api.interactive.mailbox_manager.mailbox_manager import mailbox_manager
from orion.api.interactive.message_manager.models.message_param_model import MailboxSettingsRequest
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model

mailbox_routes = APIRouter(prefix="/api/mailboxes", tags=["Mailboxes"])


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


@mailbox_routes.get("/me/e2e-key")
async def get_my_e2e_key(current_user: db_user_model = Depends(get_current_user)):
    return await e2e_key_manager.get_instance().get_key_state(current_user=current_user)


@mailbox_routes.post("/me/e2e-key/unlock")
async def unlock_my_e2e_key(unlock: E2eKeyUnlockRequest, current_user: db_user_model = Depends(get_current_user)):
    return await e2e_key_manager.get_instance().unlock_key(current_user=current_user, request=unlock)


@mailbox_routes.post("/me/e2e-key/session")
async def get_my_e2e_tab_secret(request: Request, current_user: db_user_model = Depends(get_current_user)):
    return await e2e_key_manager.get_instance().tab_secret(current_user=current_user, session_id=login_session_id(request))


@mailbox_routes.put("/me/e2e-key")
async def save_my_e2e_key(request: Request, bundle: E2eKeyBundleRequest, current_user: db_user_model = Depends(get_current_user)):
    return await e2e_key_manager.get_instance().save_key_bundle(current_user=current_user, bundle=bundle, session_token=session_token_from_request(request))


@mailbox_routes.delete("/me/e2e-key")
async def delete_my_e2e_key(request: Request, current_user: db_user_model = Depends(get_current_user)):
    return await e2e_key_manager.get_instance().delete_key_bundle(current_user=current_user, session_token=session_token_from_request(request))


@mailbox_routes.post("/e2e-keys/lookup")
async def lookup_e2e_keys(lookup: E2eKeyLookupRequest, _current_user: db_user_model = Depends(get_current_user)):
    return await e2e_key_manager.get_instance().lookup_public_keys(addresses=lookup.addresses)
