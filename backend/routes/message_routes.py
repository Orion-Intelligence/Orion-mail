from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from configs.app_dependency import get_current_user
from orion.api.interactive.message_manager.message_manager import message_manager
from orion.api.interactive.message_manager.models.message_param_model import DraftMessageRequest, MESSAGE_SEARCH_SCOPE, MessageBulkActionRequest, MessageLabelUpdateRequest, MessageMoveRequest, MessageTranslationRequest, ScheduleSendRequest, SenderReportRequest, SnoozeRequest
from orion.services.mongo_manager.shared_model.db_message_model import MESSAGE_FOLDER
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model

message_routes = APIRouter(prefix="/messages", tags=["Messages"])


@message_routes.post("/send")
async def send_user_message(receiver_address: Annotated[str, Form()], subject: Annotated[str, Form()], body: Annotated[str, Form()], files: Annotated[list[UploadFile] | None, File()] = None, cc_addresses: Annotated[list[str] | None, Form()] = None, in_reply_to_message_id: Annotated[str | None, Form()] = None, forward_message_id: Annotated[str | None, Form()] = None, forward_attachment_ids: Annotated[list[str] | None, Form()] = None, draft_id: Annotated[str | None, Form()] = None, bcc_addresses: Annotated[list[str] | None, Form()] = None, body_html: Annotated[str | None, Form()] = None, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().send_message(
        current_user=current_user,
        receiver_address=receiver_address,
        subject=subject,
        body=body,
        files=files or [],
        cc_addresses=cc_addresses,
        bcc_addresses=bcc_addresses,
        body_html=body_html,
        in_reply_to_message_id=in_reply_to_message_id,
        forward_message_id=forward_message_id,
        forward_attachment_ids=forward_attachment_ids,
        draft_id=draft_id,
    )


@message_routes.get("/drafts")
async def get_user_draft_messages(limit: Annotated[int | None, Query(ge=1, le=200)] = None, offset: Annotated[int, Query(ge=0)] = 0, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().get_draft_messages(current_user=current_user, limit=limit, offset=offset)


@message_routes.post("/drafts", status_code=status.HTTP_201_CREATED)
async def create_user_draft(draft_data: DraftMessageRequest, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().save_draft(current_user=current_user, receiver_address=draft_data.receiver_address, cc_addresses=draft_data.cc_addresses, bcc_addresses=draft_data.bcc_addresses, subject=draft_data.subject, body=draft_data.body, body_html=draft_data.body_html)


@message_routes.put("/drafts/{message_id}")
async def update_user_draft(message_id: str, draft_data: DraftMessageRequest, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().save_draft(current_user=current_user, receiver_address=draft_data.receiver_address, cc_addresses=draft_data.cc_addresses, bcc_addresses=draft_data.bcc_addresses, subject=draft_data.subject, body=draft_data.body, body_html=draft_data.body_html, draft_id=message_id)


@message_routes.get("/inbox")
async def get_user_inbox(limit: Annotated[int | None, Query(ge=1, le=200)] = None, offset: Annotated[int, Query(ge=0)] = 0, oldest_first: bool = False, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().get_inbox_messages(current_user=current_user, limit=limit, offset=offset, oldest_first=oldest_first)


@message_routes.get("/sent")
async def get_user_sent_messages(limit: Annotated[int | None, Query(ge=1, le=200)] = None, offset: Annotated[int, Query(ge=0)] = 0, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().get_sent_messages(current_user=current_user, limit=limit, offset=offset)


@message_routes.get("/archive")
async def get_user_archived_messages(limit: Annotated[int | None, Query(ge=1, le=200)] = None, offset: Annotated[int, Query(ge=0)] = 0, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().get_archived_messages(current_user=current_user, limit=limit, offset=offset)


@message_routes.get("/trash")
async def get_user_trash_messages(limit: Annotated[int | None, Query(ge=1, le=200)] = None, offset: Annotated[int, Query(ge=0)] = 0, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().get_trash_messages(current_user=current_user, limit=limit, offset=offset)


@message_routes.get("/spam")
async def get_user_spam_messages(limit: Annotated[int | None, Query(ge=1, le=200)] = None, offset: Annotated[int, Query(ge=0)] = 0, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().get_spam_messages(current_user=current_user, limit=limit, offset=offset)


@message_routes.get("/starred")
async def get_user_starred_messages(limit: Annotated[int | None, Query(ge=1, le=200)] = None, offset: Annotated[int, Query(ge=0)] = 0, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().get_starred_messages(current_user=current_user, limit=limit, offset=offset)


@message_routes.get("/important")
async def get_user_important_messages(limit: Annotated[int | None, Query(ge=1, le=200)] = None, offset: Annotated[int, Query(ge=0)] = 0, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().get_important_messages(current_user=current_user, limit=limit, offset=offset)


@message_routes.get("/all")
async def get_user_all_messages(limit: Annotated[int | None, Query(ge=1, le=200)] = None, offset: Annotated[int, Query(ge=0)] = 0, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().get_all_messages(current_user=current_user, limit=limit, offset=offset)


@message_routes.get("/snoozed")
async def get_user_snoozed_messages(limit: Annotated[int | None, Query(ge=1, le=200)] = None, offset: Annotated[int, Query(ge=0)] = 0, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().get_snoozed_messages(current_user=current_user, limit=limit, offset=offset)


@message_routes.get("/scheduled")
async def get_user_scheduled_messages(limit: Annotated[int | None, Query(ge=1, le=200)] = None, offset: Annotated[int, Query(ge=0)] = 0, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().get_scheduled_messages(current_user=current_user, limit=limit, offset=offset)


@message_routes.get("/usage")
async def get_user_mailbox_usage(current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().get_mailbox_usage(current_user=current_user)


@message_routes.get("/storage-status")
async def get_server_storage_status(_current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().server_storage_status()


@message_routes.get("/search")
async def search_user_messages(query: Annotated[str, Query(min_length=1, max_length=200)], scope: MESSAGE_SEARCH_SCOPE = MESSAGE_SEARCH_SCOPE.ALL, label_id: str | None = None, limit: Annotated[int | None, Query(ge=1, le=100)] = None, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().search_messages(current_user=current_user, query=query, scope=scope, label_id=label_id, limit=limit)


@message_routes.get("/folder-counts")
async def get_user_folder_counts(current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().get_folder_counts(current_user=current_user)


@message_routes.delete("/folder/{folder}")
async def empty_user_folder(folder: MESSAGE_FOLDER, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().empty_folder(current_user=current_user, folder=folder)


@message_routes.put("/folder/{folder}/read")
async def mark_user_folder_read(folder: MESSAGE_FOLDER, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().mark_folder_read(current_user=current_user, folder=folder)


@message_routes.put("/bulk")
async def bulk_update_user_messages(bulk_data: MessageBulkActionRequest, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().bulk_update_messages(current_user=current_user, message_ids=bulk_data.message_ids, action=bulk_data.action, destination=bulk_data.destination, label_ids=bulk_data.label_ids)


@message_routes.put("/{message_id}/labels")
async def set_user_message_labels(message_id: str, label_data: MessageLabelUpdateRequest, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().set_message_labels(current_user=current_user, message_id=message_id, label_ids=label_data.label_ids)


@message_routes.put("/{message_id}/move")
async def move_user_message(message_id: str, move_data: MessageMoveRequest, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().move_message(current_user=current_user, message_id=message_id, destination=move_data.destination)


@message_routes.put("/{message_id}/unread")
async def mark_user_message_unread(message_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().mark_message_unread(current_user=current_user, message_id=message_id)


@message_routes.put("/{message_id}/report")
async def report_message_sender(message_id: str, report_data: SenderReportRequest, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().report_sender(current_user=current_user, message_id=message_id, report_type=report_data.report_type)


@message_routes.put("/{message_id}/block-sender")
async def block_message_sender(message_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().block_sender(current_user=current_user, message_id=message_id)


@message_routes.delete("/{message_id}/block-sender")
async def unblock_message_sender(message_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().unblock_sender(current_user=current_user, message_id=message_id)


@message_routes.put("/{message_id}/snooze")
async def snooze_user_message(message_id: str, snooze_data: SnoozeRequest, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().snooze_message(current_user=current_user, message_id=message_id, snoozed_until=snooze_data.snoozed_until)


@message_routes.delete("/{message_id}/snooze")
async def unsnooze_user_message(message_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().unsnooze_message(current_user=current_user, message_id=message_id)


@message_routes.put("/{message_id}/schedule")
async def schedule_user_message(message_id: str, schedule_data: ScheduleSendRequest, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().schedule_message(current_user=current_user, message_id=message_id, scheduled_at=schedule_data.scheduled_at)


@message_routes.delete("/{message_id}/schedule")
async def cancel_user_scheduled_message(message_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().cancel_scheduled_message(current_user=current_user, message_id=message_id)


@message_routes.get("/{message_id}/thread")
async def get_user_message_thread(message_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().get_thread_messages(current_user=current_user, message_id=message_id)


@message_routes.get("/{message_id}/download")
async def download_user_message(message_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().download_message(current_user=current_user, message_id=message_id)


@message_routes.post("/{message_id}/translate")
async def translate_user_message(message_id: str, translation_data: MessageTranslationRequest, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().translate_message(current_user=current_user, message_id=message_id, target_language=translation_data.target_language)


@message_routes.put("/{message_id}/archive")
async def archive_user_message(message_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().archive_message(current_user=current_user, message_id=message_id)


@message_routes.put("/{message_id}/trash")
async def trash_user_message(message_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().move_to_trash(current_user=current_user, message_id=message_id)


@message_routes.put("/{message_id}/restore")
async def restore_user_message(message_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().restore_message(current_user=current_user, message_id=message_id)


@message_routes.delete("/{message_id}/permanent")
async def permanently_delete_user_message(message_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().permanently_delete_message(current_user=current_user, message_id=message_id)


@message_routes.get("/{message_id}")
async def get_user_message(message_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().get_message_by_id(current_user=current_user, message_id=message_id)


@message_routes.delete("/{message_id}")
async def delete_user_message(message_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await message_manager.get_instance().delete_message(current_user=current_user, message_id=message_id)
