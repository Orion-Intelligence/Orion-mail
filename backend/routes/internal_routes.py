from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from configs.app_dependency import require_orion_client_secret
from orion.api.interactive.mailbox_manager.mailbox_manager import mailbox_manager
from orion.api.interactive.message_manager.message_manager import message_manager
from orion.api.interactive.mailbox_manager.models.mailbox_param_model import TenantMailboxCreateRequest, TakedownSendRequest

internal_routes = APIRouter(
    prefix="/api/internal",
    tags=["Internal API"],
    dependencies=[Depends(require_orion_client_secret)],
    include_in_schema=False,
)

@internal_routes.post("/tenants/mailbox")
async def create_tenant_mailbox(payload: TenantMailboxCreateRequest):
    return await mailbox_manager.get_instance().create_tenant_report_mailbox(
        tenant_id=payload.tenant_id,
        tenant_slug=payload.tenant_slug,
        tenant_name=payload.tenant_name,
    )


@internal_routes.post("/takedown/send")
async def send_takedown(payload: TakedownSendRequest):
    return await message_manager.get_instance().send_takedown_email(
        tenant_id=payload.tenant_id,
        to_email=payload.to_email,
        subject=payload.subject,
        target_domain=payload.target_domain,
        custom_message=payload.custom_message or "",
        html_content=payload.html_content or "",
        screenshot_base64=payload.screenshot_base64 or "",
        screenshot_filename=payload.screenshot_filename or "",
        html_filename=payload.html_filename or "",
        takedown_id=payload.takedown_id or "",
        body_html=payload.body_html or "",
        body_text=payload.body_text or "",
    )



@internal_routes.get("/takedown/unread-count")
async def get_unread_takedown_count(tenant_id: str = Query(...)):
    count = await message_manager.get_instance().get_unread_takedown_count(tenant_id=tenant_id)
    return {"unread_count": count}


@internal_routes.get("/tenants/{tenant_id}/mailbox-status")
async def get_tenant_mailbox_status(tenant_id: str):
    return await mailbox_manager.get_instance().get_tenant_mailbox_status(tenant_id=tenant_id)

