from fastapi import APIRouter, Depends

from configs.app_dependency import get_current_user
from orion.api.interactive.disposable_mailbox_manager.disposable_mailbox_manager import disposable_mailbox_manager
from orion.api.interactive.disposable_mailbox_manager.models.disposable_mailbox_param_model import DeleteDisposableMailboxRequest, GenerateDisposableMailboxRequest, UpdateDisposableSignatureRequest
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


disposable_mailbox_routes = APIRouter(prefix="/sender-identities", tags=["Sender Identities"])


@disposable_mailbox_routes.get("")
async def list_sender_identities(current_user: db_user_model = Depends(get_current_user)):
    return await disposable_mailbox_manager.get_instance().list_sender_identities(current_user)


@disposable_mailbox_routes.post("/disposable")
async def generate_disposable_mailbox(data: GenerateDisposableMailboxRequest, current_user: db_user_model = Depends(get_current_user)):
    return await disposable_mailbox_manager.get_instance().generate_disposable_mailbox(current_user=current_user, identity_signature=data.identity_signature, pgp_key_id=data.pgp_key_id)


@disposable_mailbox_routes.delete("/disposable/{disposable_id}")
async def delete_disposable_mailbox(disposable_id: str, data: DeleteDisposableMailboxRequest, current_user: db_user_model = Depends(get_current_user)):
    return await disposable_mailbox_manager.get_instance().delete_disposable_mailbox(current_user=current_user, disposable_id=disposable_id, keep_pgp=data.keep_pgp)


@disposable_mailbox_routes.get("/saved-pgp")
async def list_saved_pgp_keys(current_user: db_user_model = Depends(get_current_user)):
    return await disposable_mailbox_manager.get_instance().list_saved_pgp_keys(current_user)


@disposable_mailbox_routes.delete("/saved-pgp/{pgp_key_id}")
async def delete_saved_pgp_key(pgp_key_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await disposable_mailbox_manager.get_instance().delete_saved_pgp_key(current_user, pgp_key_id)


@disposable_mailbox_routes.put("/disposable/{disposable_id}/signature")
async def update_disposable_signature(disposable_id: str, request: UpdateDisposableSignatureRequest, current_user: db_user_model = Depends(get_current_user)):
    return await disposable_mailbox_manager.get_instance().update_disposable_signature(current_user=current_user, disposable_id=disposable_id, identity_signature=request.identity_signature)
