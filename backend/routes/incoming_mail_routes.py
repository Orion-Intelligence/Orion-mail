from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import EmailStr

from configs.app_dependency import require_incoming_mail_token
from orion.api.interactive.incoming_mail_manager.incoming_mail_manager import incoming_mail_manager

incoming_mail_routes = APIRouter(prefix="/incoming-mail", tags=["Incoming Mail"], dependencies=[Depends(require_incoming_mail_token)], include_in_schema=False)


@incoming_mail_routes.post("/")
async def receive_incoming_email(sender_address: Annotated[EmailStr, Form()], receiver_address: Annotated[EmailStr, Form()], subject: Annotated[str, Form()], body: Annotated[str, Form()], files: Annotated[list[UploadFile] | None, File()] = None, raw_message: Annotated[UploadFile | None, File()] = None, to_addresses: Annotated[list[str] | None, Form()] = None, cc_addresses: Annotated[list[str] | None, Form()] = None, reply_to_address: Annotated[str | None, Form()] = None, message_id_header: Annotated[str | None, Form()] = None, in_reply_to: Annotated[str | None, Form()] = None, references: Annotated[list[str] | None, Form()] = None, body_html: Annotated[str | None, Form()] = None, spf_result: Annotated[str | None, Form()] = None, dkim_result: Annotated[str | None, Form()] = None, dmarc_result: Annotated[str | None, Form()] = None, report_action: Annotated[str | None, Form()] = None, report_status: Annotated[str | None, Form()] = None, report_recipient: Annotated[str | None, Form()] = None, report_original_message_id: Annotated[str | None, Form()] = None):
    return await incoming_mail_manager.get_instance().save_incoming_email(
        sender_address=str(sender_address),
        receiver_address=str(receiver_address),
        subject=subject,
        body=body,
        files=files or [],
        raw_message=raw_message,
        to_addresses=to_addresses or [],
        cc_addresses=cc_addresses or [],
        reply_to_address=reply_to_address,
        message_id_header=message_id_header,
        in_reply_to=in_reply_to,
        references=references or [],
        body_html=body_html,
        authentication={"spf": spf_result or "", "dkim": dkim_result or "", "dmarc": dmarc_result or ""},
        delivery_report={"action": report_action or "", "status": report_status or "", "recipient": report_recipient or "", "original_message_id": report_original_message_id or ""},
    )
