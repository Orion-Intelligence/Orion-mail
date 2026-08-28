import re
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import uuid4

from bson import ObjectId
from bson.errors import InvalidId
from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException, UploadFile, status
from fastapi.responses import Response
from odmantic.query import QueryExpression, and_, desc, eq, in_, match, ne, or_
from starlette.datastructures import Headers

from orion.api.interactive.address_book_manager.address_book_manager import address_book_manager
from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.api.interactive.incoming_mail_manager.incoming_mail_manager import incoming_mail_manager
from orion.api.interactive.message_manager.message_enums import MESSAGE_LIMITS
from orion.api.interactive.message_manager.models.message_param_model import BULK_MESSAGE_ACTION, MESSAGE_SEARCH_SCOPE
from orion.api.interactive.sender_safety_manager.sender_safety_manager import sender_safety_manager
from orion.api.interactive.translation_manager.translation_manager import translation_manager
from orion.constants.constant import CONSTANTS
from orion.services.encryption_manager.message_crypto_manager import message_crypto_manager
from orion.services.log_manager.log_controller import log
from orion.services.mail_manager.mail_manager import mail_manager
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_domain_safety_model import REPORT_TYPE
from orion.services.mongo_manager.shared_model.db_label_model import db_label_model
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import DELIVERY_STATUS, MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_attachment, db_message_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


class message_manager:
    __instance = None
    VISIBLE_FOLDERS = [MESSAGE_FOLDER.INBOX, MESSAGE_FOLDER.SENT, MESSAGE_FOLDER.ARCHIVE]
    REMOVED_FOLDERS = {MESSAGE_FOLDER.SPAM, MESSAGE_FOLDER.TRASH}
    RESTORABLE_FOLDERS = {MESSAGE_FOLDER.ARCHIVE, MESSAGE_FOLDER.SPAM, MESSAGE_FOLDER.TRASH}
    PURGEABLE_FOLDERS = {MESSAGE_FOLDER.DRAFTS, MESSAGE_FOLDER.SPAM, MESSAGE_FOLDER.TRASH}
    SEARCH_QUERY_MAX_LENGTH = 200
    SEARCH_RESULT_LIMIT_MAX = 100
    SEARCH_FIELDS = (
        db_message_model.sender_address,
        db_message_model.receiver_address,
        db_message_model.to_addresses,
        db_message_model.cc_addresses,
        db_message_model.subject,
        db_message_model.body,
    )

    @staticmethod
    def get_instance():
        if message_manager.__instance is None:
            message_manager()
        return message_manager.__instance

    def __init__(self):
        if message_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        message_manager.__instance = self
        self._engine = mongo_controller.get_instance().get_engine()

    async def get_active_user_mailbox(self, current_user: db_user_model) -> db_mailbox_model:
        mailbox = await self._engine.find_one(db_mailbox_model, and_(eq(db_mailbox_model.user_id, current_user.id), eq(db_mailbox_model.is_active, True)))

        if mailbox is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")

        return mailbox

    async def get_owned_message(self, mailbox: db_mailbox_model, message_id: str) -> db_message_model:
        try:
            object_id = ObjectId(message_id)
        except InvalidId as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid message ID") from error

        message = await self._engine.find_one(db_message_model, and_(eq(db_message_model.id, object_id), eq(db_message_model.owner_mailbox_id, mailbox.id)))
        if message is not None:
            await message_crypto_manager.get_instance().decrypt_message(message)

        if message is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

        return message

    @staticmethod
    async def mark_delivery_failed(message: db_message_model) -> None:
        message.delivery_status = DELIVERY_STATUS.FAILED
        message.updated_at = datetime.now(UTC)
        await message_crypto_manager.get_instance().save_message(message)

    async def partition_recipient_addresses(self, recipient_addresses: list[str]) -> tuple[list[str], list[str]]:
        mailboxes = await self._engine.find(db_mailbox_model, and_(in_(db_mailbox_model.mailbox_address, recipient_addresses), eq(db_mailbox_model.is_active, True)))
        internal_addresses = {mailbox.mailbox_address for mailbox in mailboxes}
        missing_local_addresses = [address for address in recipient_addresses if address.rpartition("@")[2] == CONSTANTS.S_MAIL_DOMAIN.lower() and address not in internal_addresses]

        if missing_local_addresses:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more local recipient mailboxes were not found")

        return (
            [address for address in recipient_addresses if address in internal_addresses],
            [address for address in recipient_addresses if address not in internal_addresses],
        )

    @staticmethod
    def validate_subject_and_body(normalized_subject: str, body: str) -> None:
        if "\r" in normalized_subject or "\n" in normalized_subject:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject cannot contain line breaks")

        if len(normalized_subject) > MESSAGE_LIMITS.SUBJECT_MAX_LENGTH:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Subject cannot exceed {MESSAGE_LIMITS.SUBJECT_MAX_LENGTH} characters")

        if len(body) > MESSAGE_LIMITS.BODY_MAX_LENGTH:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message body is too long")

    async def serialized_message_page(self, query: QueryExpression, sort, limit: int | None, offset: int) -> list[dict]:
        messages = await self._engine.find(db_message_model, query, sort=sort, skip=max(offset, 0), limit=limit)
        await message_crypto_manager.get_instance().decrypt_messages(messages)
        return [{**self.serialize_message(item), **self.message_state(item)} for item in messages]

    @staticmethod
    def internal_attachment_uploads(attachments: list[dict]) -> list[UploadFile]:
        uploads: list[UploadFile] = []
        for attachment in attachments:
            file_path = mail_manager.get_instance().get_attachment_file_path(attachment["storage_type"], attachment["stored_filename"])
            if not file_path.is_file():
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Attachment file not found")
            uploads.append(UploadFile(file=BytesIO(file_path.read_bytes()), size=attachment["size"], filename=attachment["original_filename"], headers=Headers({"content-type": attachment["content_type"]})))
        return uploads

    async def deliver_internal_email(self, recipient_address: str, sender_address: str, to_addresses: list[str], cc_addresses: list[str], subject: str, body: str, attachments: list[dict], raw_source: bytes, message_id_header: str | None, in_reply_to: str | None, references: list[str], body_html: str | None = None) -> None:
        uploads = self.internal_attachment_uploads(attachments)
        raw_upload = UploadFile(file=BytesIO(raw_source), size=len(raw_source), filename="message.eml", headers=Headers({"content-type": "message/rfc822"}))
        try:
            await incoming_mail_manager.get_instance().save_incoming_email(
                sender_address=sender_address,
                receiver_address=recipient_address,
                subject=subject,
                body=body,
                files=uploads,
                raw_message=raw_upload,
                to_addresses=to_addresses,
                cc_addresses=cc_addresses,
                message_id_header=message_id_header,
                in_reply_to=in_reply_to,
                references=references,
                body_html=body_html,
            )
        finally:
            for upload in uploads:
                await upload.close()
            await raw_upload.close()

    @staticmethod
    def serialize_message(message: db_message_model) -> dict:
        return {
            "id": str(message.id),
            "sender_address": message.sender_address,
            "receiver_address": message.receiver_address,
            "to_addresses": [address for address in (message.to_addresses or [message.receiver_address]) if address],
            "cc_addresses": message.cc_addresses,
            "bcc_addresses": message.bcc_addresses,
            "reply_to_address": message.reply_to_address,
            "subject": message.subject,
            "body": message.body,
            "body_html": message.body_html,
            "attachments": [attachment.model_dump() for attachment in message.attachments],
            "label_ids": [str(label_id) for label_id in message.label_ids],
            "direction": message.direction,
            "folder": message.folder,
            "is_starred": message.is_starred,
            "is_important": message.is_important,
            "snoozed_until": message.snoozed_until,
            "scheduled_at": message.scheduled_at,
            "failed_recipients": message.failed_recipients,
            "bounce_status": message.bounce_status,
            "bounce_recipient": message.bounce_recipient,
            "authentication": {"spf": message.spf_result, "dkim": message.dkim_result, "dmarc": message.dmarc_result},
            "thread_id": str(message.thread_id) if message.thread_id else str(message.id),
            "has_original_source": bool(message.raw_source_filename),
            "created_at": message.created_at,
        }

    @staticmethod
    def allowed_destinations(message: db_message_model) -> set[MESSAGE_FOLDER]:
        if message.folder == MESSAGE_FOLDER.DRAFTS:
            return set()
        return {MESSAGE_FOLDER.INBOX, MESSAGE_FOLDER.ARCHIVE, MESSAGE_FOLDER.SPAM, MESSAGE_FOLDER.TRASH} if message.direction == MESSAGE_DIRECTION.INCOMING else {MESSAGE_FOLDER.SENT, MESSAGE_FOLDER.TRASH}

    def relocate_message(self, message: db_message_model, destination: MESSAGE_FOLDER) -> None:
        if destination in self.REMOVED_FOLDERS and message.folder not in self.REMOVED_FOLDERS:
            message.previous_folder = message.folder
        elif destination not in self.REMOVED_FOLDERS:
            message.previous_folder = None
        message.folder = destination
        message.updated_at = datetime.now(UTC)

    def restore_target(self, message: db_message_model) -> MESSAGE_FOLDER:
        fallback_folder = MESSAGE_FOLDER.INBOX if message.direction == MESSAGE_DIRECTION.INCOMING else MESSAGE_FOLDER.SENT
        restore_folder = fallback_folder if message.folder == MESSAGE_FOLDER.ARCHIVE else message.previous_folder or fallback_folder
        return fallback_folder if restore_folder in self.REMOVED_FOLDERS else restore_folder

    @staticmethod
    def message_state(message: db_message_model) -> dict:
        return {"is_read": message.is_read} if message.direction == MESSAGE_DIRECTION.INCOMING else {"delivery_status": message.delivery_status}

    async def message_response(self, current_user: db_user_model, message: db_message_model) -> dict:
        response = {**self.serialize_message(message), **self.message_state(message)}
        if message.direction == MESSAGE_DIRECTION.INCOMING:
            response["safety"] = await sender_safety_manager.get_instance().get_domain_state(current_user, message.sender_address)
        return response

    async def get_folder_messages(self, current_user: db_user_model, folder: MESSAGE_FOLDER, limit: int | None = None, offset: int = 0, oldest_first: bool = False) -> list[dict]:
        mailbox = await self.get_active_user_mailbox(current_user)
        conditions = [eq(db_message_model.owner_mailbox_id, mailbox.id), eq(db_message_model.folder, folder)]
        if folder == MESSAGE_FOLDER.INBOX:
            conditions.append(or_(eq(db_message_model.snoozed_until, None), db_message_model.snoozed_until <= datetime.now(UTC)))
        if folder == MESSAGE_FOLDER.DRAFTS:
            conditions.append(eq(db_message_model.scheduled_at, None))
        query = and_(*conditions)
        order = db_message_model.created_at if oldest_first else desc(db_message_model.created_at)
        messages = await self._engine.find(db_message_model, query, sort=order, skip=max(offset, 0), limit=limit)
        await message_crypto_manager.get_instance().decrypt_messages(messages)
        return [{**self.serialize_message(message), **self.message_state(message)} for message in messages]

    async def set_message_labels(self, current_user: db_user_model, message_id: str, label_ids: list[str]) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)
        object_ids: list[ObjectId] = []

        for label_id in label_ids:
            try:
                object_id = ObjectId(label_id)
            except InvalidId as error:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid label ID") from error
            if object_id not in object_ids:
                object_ids.append(object_id)

        if object_ids:
            owned_label_count = await self._engine.get_collection(db_label_model).count_documents({"_id": {"$in": object_ids}, "user_id": current_user.id})
            if owned_label_count != len(object_ids):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more labels are invalid")

        message.label_ids = object_ids
        message.updated_at = datetime.now(UTC)
        await message_crypto_manager.get_instance().save_message(message)
        return {**self.serialize_message(message), **self.message_state(message)}

    @staticmethod
    def normalize_recipient_addresses(addresses: list[str], field_name: str) -> list[str]:
        normalized: list[str] = []
        for address in addresses:
            try:
                value = validate_email(address.strip(), check_deliverability=False).normalized.lower()
            except EmailNotValidError as error:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} contains an invalid email address") from error
            if value not in normalized:
                normalized.append(value)
        return normalized

    async def save_draft(self, current_user: db_user_model, receiver_address: str, cc_addresses: list[str], bcc_addresses: list[str], subject: str, body: str, draft_id: str | None = None, body_html: str | None = None) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        normalized_subject = subject.strip()

        self.validate_subject_and_body(normalized_subject, body)

        normalized_receiver_address = receiver_address.strip().lower()
        normalized_cc_addresses = list(dict.fromkeys(address.strip().lower() for address in cc_addresses if address.strip()))
        normalized_bcc_addresses = list(dict.fromkeys(address.strip().lower() for address in bcc_addresses if address.strip()))

        if draft_id:
            message = await self.get_owned_message(mailbox, draft_id)
            if message.folder != MESSAGE_FOLDER.DRAFTS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is not a draft")
        else:
            message = db_message_model(owner_mailbox_id=mailbox.id, sender_address=mailbox.mailbox_address, receiver_address="", subject="", body="", direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.DRAFTS, delivery_status=DELIVERY_STATUS.QUEUED)
            message.message_id_header = f"<{uuid4().hex}@{CONSTANTS.S_MAIL_DOMAIN}>"
            message.thread_id = message.id

        message.receiver_address = normalized_receiver_address
        message.to_addresses = [normalized_receiver_address] if normalized_receiver_address else []
        message.cc_addresses = normalized_cc_addresses
        message.bcc_addresses = normalized_bcc_addresses
        message.subject = normalized_subject
        message.body = body
        message.body_html = (body_html or "").strip() or None
        message.updated_at = datetime.now(UTC)
        await message_crypto_manager.get_instance().save_message(message)
        return {**self.serialize_message(message), **self.message_state(message)}

    async def send_message(self, current_user: db_user_model, receiver_address: str, subject: str, body: str, files: list[UploadFile], cc_addresses: list[str] | None = None, bcc_addresses: list[str] | None = None, in_reply_to_message_id: str | None = None, forward_message_id: str | None = None, forward_attachment_ids: list[str] | None = None, draft_id: str | None = None, body_html: str | None = None) -> dict:
        sender_mailbox = await self.get_active_user_mailbox(current_user)
        normalized_receiver_address = receiver_address.strip().lower()
        normalized_subject = subject.strip()
        normalized_body = body.strip()

        if not normalized_receiver_address:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Receiver address cannot be empty")

        if not normalized_subject:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject cannot be empty")

        if not normalized_body:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message body cannot be empty")

        self.validate_subject_and_body(normalized_subject, normalized_body)

        try:
            normalized_receiver_address = validate_email(normalized_receiver_address, check_deliverability=False).normalized.lower()
        except EmailNotValidError as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Receiver address is not a valid email address") from error

        normalized_cc_addresses = [address for address in self.normalize_recipient_addresses(cc_addresses or [], "Cc") if address != normalized_receiver_address]
        normalized_bcc_addresses = [address for address in self.normalize_recipient_addresses(bcc_addresses or [], "Bcc") if address != normalized_receiver_address and address not in normalized_cc_addresses]
        recipient_addresses = [normalized_receiver_address, *normalized_cc_addresses, *normalized_bcc_addresses]

        if len(recipient_addresses) > MESSAGE_LIMITS.MAX_RECIPIENTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"A message cannot have more than {MESSAGE_LIMITS.MAX_RECIPIENTS} recipients")

        await self.enforce_send_quota(sender_mailbox)
        await self.enforce_storage_quota(sender_mailbox)
        internal_recipient_addresses, external_recipient_addresses = await self.partition_recipient_addresses(recipient_addresses)
        reply_parent = await self.get_owned_message(sender_mailbox, in_reply_to_message_id) if in_reply_to_message_id else None
        forward_source = await self.get_owned_message(sender_mailbox, forward_message_id) if forward_message_id else None
        if forward_attachment_ids and forward_source is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A source message is required to forward attachments")
        if reply_parent and forward_source:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A message cannot be a reply and a forward at the same time")
        draft = await self.get_owned_message(sender_mailbox, draft_id) if draft_id else None
        if draft is not None and draft.folder != MESSAGE_FOLDER.DRAFTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is not a draft")

        parent_header = reply_parent.message_id_header if reply_parent else None
        references = []
        if reply_parent:
            references = [*reply_parent.references]
            if parent_header and parent_header not in references:
                references.append(parent_header)
            references = references[-MESSAGE_LIMITS.MAX_THREAD_REFERENCES:]

        message = db_message_model(
            owner_mailbox_id=sender_mailbox.id,
            sender_address=sender_mailbox.mailbox_address,
            receiver_address=normalized_receiver_address,
            to_addresses=[normalized_receiver_address],
            cc_addresses=normalized_cc_addresses,
            bcc_addresses=normalized_bcc_addresses,
            subject=normalized_subject,
            body=normalized_body,
            body_html=(body_html or "").strip() or None,
            direction=MESSAGE_DIRECTION.OUTGOING,
            folder=MESSAGE_FOLDER.SENT,
            delivery_status=DELIVERY_STATUS.QUEUED,
            in_reply_to=parent_header,
            references=references,
            thread_id=(reply_parent.thread_id or reply_parent.id) if reply_parent else None,
            forwarded_from_message_id=forward_source.id if forward_source else None,
        )
        message.message_id_header = f"<{uuid4().hex}@{CONSTANTS.S_MAIL_DOMAIN}>"
        message.thread_id = message.thread_id or message.id
        message = await message_crypto_manager.get_instance().save_message(message)

        try:
            saved_attachments = await attachment_manager.get_instance().save_outgoing_attachments(message_id=message.id, files=files)
            forwarded_attachments = await attachment_manager.get_instance().clone_outgoing_attachments(
                source_message_id=forward_source.id,
                target_message_id=message.id,
                attachment_ids=forward_attachment_ids or [],
                existing_attachments=saved_attachments,
            ) if forward_source else []
            all_attachments = [*saved_attachments, *forwarded_attachments]
            message.attachments = [db_message_attachment(**attachment) for attachment in all_attachments]
            message.updated_at = datetime.now(UTC)
            await message_crypto_manager.get_instance().save_message(message)

            email_message = mail_manager.get_instance().build_email_message(
                sender_address=sender_mailbox.mailbox_address,
                receiver_addresses=[normalized_receiver_address],
                cc_addresses=normalized_cc_addresses,
                subject=normalized_subject,
                body=normalized_body,
                body_html=message.body_html,
                attachments=all_attachments,
                message_id_header=message.message_id_header,
                in_reply_to=message.in_reply_to,
                references=message.references,
            )
            raw_source = mail_manager.get_instance().serialize_email_message(email_message)
            raw_source_filename, raw_source_encrypted, raw_source_size = await attachment_manager.get_instance().save_raw_source(raw_source, message.owner_mailbox_id)
            message.raw_source_filename = raw_source_filename
            message.raw_source_encrypted = raw_source_encrypted
            message.raw_source_size = raw_source_size
            message.updated_at = datetime.now(UTC)
            await message_crypto_manager.get_instance().save_message(message)
            for recipient_address in internal_recipient_addresses:
                await self.deliver_internal_email(
                    recipient_address=recipient_address,
                    sender_address=sender_mailbox.mailbox_address,
                    to_addresses=[normalized_receiver_address],
                    cc_addresses=normalized_cc_addresses,
                    subject=normalized_subject,
                    body=normalized_body,
                    body_html=message.body_html,
                    attachments=all_attachments,
                    raw_source=raw_source,
                    message_id_header=message.message_id_header,
                    in_reply_to=message.in_reply_to,
                    references=message.references,
                )
            failed_recipients = await mail_manager.get_instance().send_email_source(raw_source=raw_source, sender_address=sender_mailbox.mailbox_address, recipient_addresses=external_recipient_addresses) if external_recipient_addresses else {}
            message.failed_recipients = sorted(failed_recipients)
            message.delivery_status = DELIVERY_STATUS.PARTIAL if failed_recipients else DELIVERY_STATUS.SENT
            message.updated_at = datetime.now(UTC)
            await message_crypto_manager.get_instance().save_message(message)
        except HTTPException:
            await self.mark_delivery_failed(message)
            raise
        except Exception as error:
            await self.mark_delivery_failed(message)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Email delivery failed") from error

        try:
            await address_book_manager.get_instance().record_recipients(mailbox=sender_mailbox, recipient_addresses=recipient_addresses)
        except Exception:
            pass

        if draft is not None:
            await self._engine.delete(draft)

        return {
            **self.serialize_message(message),
            **self.message_state(message),
            "message": "Email queued successfully",
        }

    async def get_thread_messages(self, current_user: db_user_model, message_id: str) -> list[dict]:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)
        thread_id = message.thread_id or message.id
        query = and_(eq(db_message_model.owner_mailbox_id, mailbox.id), eq(db_message_model.thread_id, thread_id), in_(db_message_model.folder, self.VISIBLE_FOLDERS))
        messages = await self._engine.find(db_message_model, query, sort=db_message_model.created_at)
        await message_crypto_manager.get_instance().decrypt_messages(messages)
        return [{**self.serialize_message(item), **self.message_state(item)} for item in messages]

    async def mailbox_storage_used(self, mailbox: db_mailbox_model) -> int:
        pipeline = [
            {"$match": {"owner_mailbox_id": mailbox.id}},
            {"$group": {"_id": None, "attachment_bytes": {"$sum": {"$sum": "$attachments.size"}}, "raw_bytes": {"$sum": "$raw_source_size"}}},
        ]
        rows = await self._engine.get_collection(db_message_model).aggregate(pipeline).to_list(length=1)
        if not rows:
            return 0
        return int(rows[0].get("attachment_bytes", 0) or 0) + int(rows[0].get("raw_bytes", 0) or 0)

    async def get_mailbox_usage(self, current_user: db_user_model) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        used_bytes = await self.mailbox_storage_used(mailbox)
        return {"used_bytes": used_bytes, "quota_bytes": MESSAGE_LIMITS.MAILBOX_QUOTA_BYTES, "used_percent": round(used_bytes * 100 / MESSAGE_LIMITS.MAILBOX_QUOTA_BYTES, 2)}

    async def enforce_storage_quota(self, mailbox: db_mailbox_model) -> None:
        if await self.mailbox_storage_used(mailbox) >= MESSAGE_LIMITS.MAILBOX_QUOTA_BYTES:
            raise HTTPException(status_code=status.HTTP_507_INSUFFICIENT_STORAGE, detail="Mailbox storage quota exceeded. Delete messages or attachments to free space.")

    async def snooze_message(self, current_user: db_user_model, message_id: str, snoozed_until: datetime) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)
        if message.direction != MESSAGE_DIRECTION.INCOMING:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only received messages can be snoozed")

        wake_time = snoozed_until if snoozed_until.tzinfo else snoozed_until.replace(tzinfo=UTC)
        if wake_time <= datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Snooze time must be in the future")

        message.snoozed_until = wake_time
        message.folder = MESSAGE_FOLDER.INBOX
        message.updated_at = datetime.now(UTC)
        await message_crypto_manager.get_instance().save_message(message)
        return {**self.serialize_message(message), **self.message_state(message)}

    async def clear_message_timestamp(self, current_user: db_user_model, message_id: str, field_name: str) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)
        setattr(message, field_name, None)
        message.updated_at = datetime.now(UTC)
        await message_crypto_manager.get_instance().save_message(message)
        return {**self.serialize_message(message), **self.message_state(message)}

    async def unsnooze_message(self, current_user: db_user_model, message_id: str) -> dict:
        return await self.clear_message_timestamp(current_user, message_id, "snoozed_until")

    async def get_snoozed_messages(self, current_user: db_user_model, limit: int | None = None, offset: int = 0) -> list[dict]:
        mailbox = await self.get_active_user_mailbox(current_user)
        query = and_(eq(db_message_model.owner_mailbox_id, mailbox.id), db_message_model.snoozed_until > datetime.now(UTC))
        return await self.serialized_message_page(query, db_message_model.snoozed_until, limit, offset)

    async def get_scheduled_messages(self, current_user: db_user_model, limit: int | None = None, offset: int = 0) -> list[dict]:
        mailbox = await self.get_active_user_mailbox(current_user)
        query = and_(eq(db_message_model.owner_mailbox_id, mailbox.id), eq(db_message_model.folder, MESSAGE_FOLDER.DRAFTS), ne(db_message_model.scheduled_at, None))
        return await self.serialized_message_page(query, db_message_model.scheduled_at, limit, offset)

    async def schedule_message(self, current_user: db_user_model, message_id: str, scheduled_at: datetime) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)
        if message.folder != MESSAGE_FOLDER.DRAFTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only drafts can be scheduled")

        send_time = scheduled_at if scheduled_at.tzinfo else scheduled_at.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        if send_time <= now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Scheduled time must be in the future")
        if send_time > now + timedelta(days=MESSAGE_LIMITS.MAX_SCHEDULE_DAYS):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"A message cannot be scheduled more than {MESSAGE_LIMITS.MAX_SCHEDULE_DAYS} days ahead")
        if not message.receiver_address:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Add a recipient before scheduling")

        message.scheduled_at = send_time
        message.updated_at = now
        await message_crypto_manager.get_instance().save_message(message)
        return {**self.serialize_message(message), **self.message_state(message)}

    async def cancel_scheduled_message(self, current_user: db_user_model, message_id: str) -> dict:
        return await self.clear_message_timestamp(current_user, message_id, "scheduled_at")

    async def wake_snoozed_messages(self) -> dict:
        result = await self._engine.get_collection(db_message_model).update_many({"snoozed_until": {"$ne": None, "$lte": datetime.now(UTC)}}, {"$set": {"snoozed_until": None, "updated_at": datetime.now(UTC)}})
        return {"woken": result.modified_count}

    async def dispatch_scheduled_messages(self) -> dict:
        now = datetime.now(UTC)
        due = await self._engine.find(db_message_model, and_(eq(db_message_model.folder, MESSAGE_FOLDER.DRAFTS), ne(db_message_model.scheduled_at, None), db_message_model.scheduled_at <= now), limit=50)
        await message_crypto_manager.get_instance().decrypt_messages(due)
        sent = 0
        failed = 0
        for draft in due:
            mailbox: db_mailbox_model | None = await self._engine.find_one(db_mailbox_model, eq(db_mailbox_model.id, draft.owner_mailbox_id))
            owner: db_user_model | None = await self._engine.find_one(db_user_model, eq(db_user_model.id, mailbox.user_id)) if mailbox else None
            if owner is None:
                draft.scheduled_at = None
                await message_crypto_manager.get_instance().save_message(draft)
                continue
            try:
                await self.send_message(current_user=owner, receiver_address=draft.receiver_address, subject=draft.subject, body=draft.body, files=[], cc_addresses=list(draft.cc_addresses), bcc_addresses=list(draft.bcc_addresses), body_html=draft.body_html, draft_id=str(draft.id))
                sent += 1
            except Exception as error:
                failed += 1
                draft.scheduled_at = None
                draft.updated_at = datetime.now(UTC)
                await message_crypto_manager.get_instance().save_message(draft)
        return {"sent": sent, "failed": failed}

    async def enforce_send_quota(self, mailbox: db_mailbox_model) -> None:
        window_start = datetime.now(UTC) - timedelta(seconds=MESSAGE_LIMITS.SEND_WINDOW_SECONDS)
        recent_sends = await self._engine.get_collection(db_message_model).count_documents({"owner_mailbox_id": mailbox.id, "direction": MESSAGE_DIRECTION.OUTGOING.value, "folder": MESSAGE_FOLDER.SENT.value, "created_at": {"$gte": window_start}})
        if recent_sends >= MESSAGE_LIMITS.MAX_SENDS_PER_WINDOW:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Send limit reached. A mailbox can send at most {MESSAGE_LIMITS.MAX_SENDS_PER_WINDOW} messages per hour.", headers={"Retry-After": str(MESSAGE_LIMITS.SEND_WINDOW_SECONDS)})

    async def get_inbox_messages(self, current_user: db_user_model, limit: int | None = None, offset: int = 0, oldest_first: bool = False) -> list[dict]:
        return await self.get_folder_messages(current_user, MESSAGE_FOLDER.INBOX, limit, offset, oldest_first)

    async def get_sent_messages(self, current_user: db_user_model, limit: int | None = None, offset: int = 0) -> list[dict]:
        return await self.get_folder_messages(current_user, MESSAGE_FOLDER.SENT, limit, offset)

    async def get_archived_messages(self, current_user: db_user_model, limit: int | None = None, offset: int = 0) -> list[dict]:
        return await self.get_folder_messages(current_user, MESSAGE_FOLDER.ARCHIVE, limit, offset)

    async def get_trash_messages(self, current_user: db_user_model, limit: int | None = None, offset: int = 0) -> list[dict]:
        return await self.get_folder_messages(current_user, MESSAGE_FOLDER.TRASH, limit, offset)

    async def get_draft_messages(self, current_user: db_user_model, limit: int | None = None, offset: int = 0) -> list[dict]:
        return await self.get_folder_messages(current_user, MESSAGE_FOLDER.DRAFTS, limit, offset)

    async def get_spam_messages(self, current_user: db_user_model, limit: int | None = None, offset: int = 0) -> list[dict]:
        return await self.get_folder_messages(current_user, MESSAGE_FOLDER.SPAM, limit, offset)

    async def get_matching_messages(self, current_user: db_user_model, *conditions: QueryExpression, limit: int | None = None, offset: int = 0) -> list[dict]:
        mailbox = await self.get_active_user_mailbox(current_user)
        query = and_(eq(db_message_model.owner_mailbox_id, mailbox.id), in_(db_message_model.folder, self.VISIBLE_FOLDERS), *conditions)
        messages = await self._engine.find(db_message_model, query, sort=desc(db_message_model.created_at), skip=max(offset, 0), limit=limit)
        await message_crypto_manager.get_instance().decrypt_messages(messages)
        return [{**self.serialize_message(message), **self.message_state(message)} for message in messages]

    async def get_starred_messages(self, current_user: db_user_model, limit: int | None = None, offset: int = 0) -> list[dict]:
        return await self.get_matching_messages(current_user, eq(db_message_model.is_starred, True), limit=limit, offset=offset)

    async def get_important_messages(self, current_user: db_user_model, limit: int | None = None, offset: int = 0) -> list[dict]:
        return await self.get_matching_messages(current_user, eq(db_message_model.is_important, True), limit=limit, offset=offset)

    async def get_all_messages(self, current_user: db_user_model, limit: int | None = None, offset: int = 0) -> list[dict]:
        return await self.get_matching_messages(current_user, limit=limit, offset=offset)

    async def empty_folder(self, current_user: db_user_model, folder: MESSAGE_FOLDER) -> dict:
        if folder not in self.PURGEABLE_FOLDERS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only Drafts, Spam or Trash can be emptied")
        mailbox = await self.get_active_user_mailbox(current_user)
        messages = await self._engine.find(db_message_model, and_(eq(db_message_model.owner_mailbox_id, mailbox.id), eq(db_message_model.folder, folder)))
        for message in messages:
            await attachment_manager.get_instance().delete_message_attachments(message.id)
            await attachment_manager.get_instance().delete_raw_source(message.raw_source_filename)
            await self._engine.delete(message)
        return {"folder": folder.value, "deleted": len(messages)}

    async def mark_folder_read(self, current_user: db_user_model, folder: MESSAGE_FOLDER) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        result = await self._engine.get_collection(db_message_model).update_many({"owner_mailbox_id": mailbox.id, "folder": folder.value, "direction": MESSAGE_DIRECTION.INCOMING.value, "is_read": False}, {"$set": {"is_read": True, "updated_at": datetime.now(UTC)}})
        return {"folder": folder.value, "updated": result.modified_count}

    async def search_messages(self, current_user: db_user_model, query: str, scope: MESSAGE_SEARCH_SCOPE, label_id: str | None = None, limit: int | None = None) -> list[dict]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Search query cannot be empty")
        if len(normalized_query) > self.SEARCH_QUERY_MAX_LENGTH:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Search query cannot exceed {self.SEARCH_QUERY_MAX_LENGTH} characters")
        if limit is not None and not 1 <= limit <= self.SEARCH_RESULT_LIMIT_MAX:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Search limit must be between 1 and {self.SEARCH_RESULT_LIMIT_MAX}")

        mailbox = await self.get_active_user_mailbox(current_user)
        conditions: list[QueryExpression] = [eq(db_message_model.owner_mailbox_id, mailbox.id)]

        if scope.value in {folder.value for folder in MESSAGE_FOLDER}:
            conditions.append(eq(db_message_model.folder, MESSAGE_FOLDER(scope.value)))
        elif scope == MESSAGE_SEARCH_SCOPE.STARRED:
            conditions.append(eq(db_message_model.is_starred, True))
        elif scope == MESSAGE_SEARCH_SCOPE.IMPORTANT:
            conditions.append(eq(db_message_model.is_important, True))
        elif scope == MESSAGE_SEARCH_SCOPE.LABEL:
            if label_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A label is required for label search")
            try:
                label_object_id = ObjectId(label_id)
            except InvalidId as error:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid label ID") from error
            label = await self._engine.find_one(db_label_model, and_(eq(db_label_model.id, label_object_id), eq(db_label_model.user_id, current_user.id)))
            if label is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")
            conditions.append(eq(db_message_model.label_ids, label_object_id))

        for term in normalized_query.split():
            term_pattern = re.compile(re.escape(term), re.IGNORECASE)
            conditions.append(or_(*(match(field, term_pattern) for field in self.SEARCH_FIELDS)))

        messages = await self._engine.find(db_message_model, and_(*conditions), sort=desc(db_message_model.created_at), limit=limit)
        await message_crypto_manager.get_instance().decrypt_messages(messages)
        return [{**self.serialize_message(message), **self.message_state(message)} for message in messages]

    async def get_folder_counts(self, current_user: db_user_model) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        unread_condition = {"$cond": [{"$and": [{"$eq": ["$direction", MESSAGE_DIRECTION.INCOMING.value]}, {"$eq": ["$is_read", False]}]}, 1, 0]}
        pipeline = [
            {"$match": {"owner_mailbox_id": mailbox.id}},
            {"$group": {"_id": "$folder", "count": {"$sum": 1}, "unread": {"$sum": unread_condition}}},
        ]
        rows = await self._engine.get_collection(db_message_model).aggregate(pipeline).to_list(length=None)
        counts = {folder.value: 0 for folder in MESSAGE_FOLDER}
        unread = {folder.value: 0 for folder in MESSAGE_FOLDER}
        for row in rows:
            if row.get("_id") in counts:
                counts[row["_id"]] = row["count"]
                unread[row["_id"]] = row["unread"]
        return {**counts, "unread": unread}

    async def get_message_by_id(self, current_user: db_user_model, message_id: str) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)

        if message.direction == MESSAGE_DIRECTION.INCOMING and not message.is_read:
            message.is_read = True
            message.updated_at = datetime.now(UTC)
            await message_crypto_manager.get_instance().save_message(message)

        return await self.message_response(current_user, message)

    async def mark_message_unread(self, current_user: db_user_model, message_id: str) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)
        if message.direction != MESSAGE_DIRECTION.INCOMING:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only incoming messages can be marked unread")

        message.is_read = False
        message.updated_at = datetime.now(UTC)
        await message_crypto_manager.get_instance().save_message(message)
        return await self.message_response(current_user, message)

    async def move_message(self, current_user: db_user_model, message_id: str, destination: MESSAGE_FOLDER) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)
        if destination not in self.allowed_destinations(message):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be moved to that folder")

        self.relocate_message(message, destination)
        await message_crypto_manager.get_instance().save_message(message)
        return await self.message_response(current_user, message)

    async def report_sender(self, current_user: db_user_model, message_id: str, report_type: REPORT_TYPE) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)
        if message.direction != MESSAGE_DIRECTION.INCOMING:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only incoming senders can be reported")

        try:
            report = await sender_safety_manager.get_instance().report_domain(current_user, message, report_type)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

        if message.folder != MESSAGE_FOLDER.SPAM:
            self.relocate_message(message, MESSAGE_FOLDER.SPAM)
            await message_crypto_manager.get_instance().save_message(message)

        return {**await self.message_response(current_user, message), "report": report}

    async def block_sender(self, current_user: db_user_model, message_id: str) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)
        if message.direction != MESSAGE_DIRECTION.INCOMING:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only incoming senders can be blocked")

        try:
            block = await sender_safety_manager.get_instance().block_domain(current_user, message)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

        if message.folder != MESSAGE_FOLDER.SPAM:
            self.relocate_message(message, MESSAGE_FOLDER.SPAM)
            await message_crypto_manager.get_instance().save_message(message)

        return {**await self.message_response(current_user, message), "block": block}

    async def unblock_sender(self, current_user: db_user_model, message_id: str) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)
        if message.direction != MESSAGE_DIRECTION.INCOMING:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only incoming senders can be unblocked")

        try:
            block = await sender_safety_manager.get_instance().unblock_domain(current_user, message.sender_address)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
        return {**await self.message_response(current_user, message), "block": block}

    async def archive_message(self, current_user: db_user_model, message_id: str) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)

        if message.folder == MESSAGE_FOLDER.ARCHIVE:
            return {**self.serialize_message(message), **self.message_state(message)}
        if message.folder != MESSAGE_FOLDER.INBOX:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only Inbox messages can be archived")

        message.previous_folder = MESSAGE_FOLDER.INBOX
        message.folder = MESSAGE_FOLDER.ARCHIVE
        message.updated_at = datetime.now(UTC)
        await message_crypto_manager.get_instance().save_message(message)
        return {**self.serialize_message(message), **self.message_state(message)}

    async def move_to_trash(self, current_user: db_user_model, message_id: str) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)

        if message.folder != MESSAGE_FOLDER.TRASH:
            self.relocate_message(message, MESSAGE_FOLDER.TRASH)
            await message_crypto_manager.get_instance().save_message(message)

        return {**self.serialize_message(message), **self.message_state(message)}

    async def restore_message(self, current_user: db_user_model, message_id: str) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)

        if message.folder not in self.RESTORABLE_FOLDERS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is not archived, in Spam or in Trash")

        message.folder = self.restore_target(message)
        message.previous_folder = None
        message.updated_at = datetime.now(UTC)
        await message_crypto_manager.get_instance().save_message(message)
        return {**self.serialize_message(message), **self.message_state(message)}

    async def bulk_update_messages(self, current_user: db_user_model, message_ids: list[str], action: BULK_MESSAGE_ACTION, destination: MESSAGE_FOLDER | None = None, label_ids: list[str] | None = None) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        object_ids: list[ObjectId] = []
        for message_id in message_ids:
            try:
                object_id = ObjectId(message_id)
            except InvalidId as error:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more message IDs are invalid") from error
            if object_id not in object_ids:
                object_ids.append(object_id)

        messages = await self._engine.find(db_message_model, and_(eq(db_message_model.owner_mailbox_id, mailbox.id), in_(db_message_model.id, object_ids)))
        await message_crypto_manager.get_instance().decrypt_messages(messages)
        if len(messages) != len(object_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more messages were not found")

        label_object_ids: list[ObjectId] = []
        if action == BULK_MESSAGE_ACTION.ADD_LABELS:
            for label_id in label_ids or []:
                try:
                    label_object_id = ObjectId(label_id)
                except InvalidId as error:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more label IDs are invalid") from error
                if label_object_id not in label_object_ids:
                    label_object_ids.append(label_object_id)
            if not label_object_ids:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose at least one label")
            owned_label_count = await self._engine.get_collection(db_label_model).count_documents({"_id": {"$in": label_object_ids}, "user_id": current_user.id})
            if owned_label_count != len(label_object_ids):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more labels are invalid")

        now = datetime.now(UTC)
        for message in messages:
            if action == BULK_MESSAGE_ACTION.ARCHIVE and (message.direction != MESSAGE_DIRECTION.INCOMING or message.folder != MESSAGE_FOLDER.INBOX):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only Inbox messages can be archived")
            if action in {BULK_MESSAGE_ACTION.MARK_READ, BULK_MESSAGE_ACTION.MARK_UNREAD, BULK_MESSAGE_ACTION.REPORT_SPAM, BULK_MESSAGE_ACTION.REPORT_PHISHING} and message.direction != MESSAGE_DIRECTION.INCOMING:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This action only applies to incoming messages")
            if action == BULK_MESSAGE_ACTION.RESTORE and message.folder not in self.RESTORABLE_FOLDERS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only archived, Spam or Trash messages can be restored")
            if action == BULK_MESSAGE_ACTION.PERMANENT_DELETE and message.folder not in self.PURGEABLE_FOLDERS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only messages in Drafts, Spam or Trash can be permanently deleted")
            if action == BULK_MESSAGE_ACTION.MOVE:
                if destination is None:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A destination folder is required")
                if destination not in self.allowed_destinations(message):
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more messages cannot be moved to that folder")

        processed_ids: list[str] = []
        deleted_ids: list[str] = []
        for message in messages:
            if action == BULK_MESSAGE_ACTION.PERMANENT_DELETE:
                await attachment_manager.get_instance().delete_message_attachments(message.id)
                await attachment_manager.get_instance().delete_raw_source(message.raw_source_filename)
                await self._engine.delete(message)
                deleted_ids.append(str(message.id))
                processed_ids.append(str(message.id))
                continue

            if action == BULK_MESSAGE_ACTION.ARCHIVE:
                message.previous_folder = MESSAGE_FOLDER.INBOX
                message.folder = MESSAGE_FOLDER.ARCHIVE
            elif action == BULK_MESSAGE_ACTION.TRASH:
                if message.folder != MESSAGE_FOLDER.TRASH:
                    self.relocate_message(message, MESSAGE_FOLDER.TRASH)
            elif action == BULK_MESSAGE_ACTION.RESTORE:
                message.folder = self.restore_target(message)
                message.previous_folder = None
            elif action == BULK_MESSAGE_ACTION.MARK_READ:
                message.is_read = True
            elif action == BULK_MESSAGE_ACTION.MARK_UNREAD:
                message.is_read = False
            elif action == BULK_MESSAGE_ACTION.STAR:
                message.is_starred = True
            elif action == BULK_MESSAGE_ACTION.UNSTAR:
                message.is_starred = False
            elif action == BULK_MESSAGE_ACTION.MARK_IMPORTANT:
                message.is_important = True
            elif action == BULK_MESSAGE_ACTION.MARK_NOT_IMPORTANT:
                message.is_important = False
            elif action == BULK_MESSAGE_ACTION.MOVE:
                if destination is None:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose a destination folder")
                self.relocate_message(message, destination)
            elif action == BULK_MESSAGE_ACTION.ADD_LABELS:
                message.label_ids = list(dict.fromkeys([*message.label_ids, *label_object_ids]))
            elif action in {BULK_MESSAGE_ACTION.REPORT_SPAM, BULK_MESSAGE_ACTION.REPORT_PHISHING}:
                report_type = REPORT_TYPE.SPAM if action == BULK_MESSAGE_ACTION.REPORT_SPAM else REPORT_TYPE.PHISHING
                await sender_safety_manager.get_instance().report_domain(current_user, message, report_type)
                if message.folder != MESSAGE_FOLDER.SPAM:
                    self.relocate_message(message, MESSAGE_FOLDER.SPAM)

            message.updated_at = now
            await message_crypto_manager.get_instance().save_message(message)
            processed_ids.append(str(message.id))

        return {
            "action": action.value,
            "processed_ids": processed_ids,
            "deleted_ids": deleted_ids,
            "messages": [{**self.serialize_message(message), **self.message_state(message)} for message in messages if str(message.id) not in deleted_ids],
        }

    @staticmethod
    def get_original_source_path(message: db_message_model):
        if not message.raw_source_filename:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original source is unavailable for messages stored before source retention was enabled",
            )
        try:
            source_path = attachment_manager.get_instance().get_raw_source_path(message.raw_source_filename)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Stored message source is invalid") from error
        if not source_path.is_file():
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Original message source is no longer available")
        return source_path

    @staticmethod
    def message_download_filename(message: db_message_model) -> str:
        return "message.eml"

    async def get_message_source(self, current_user: db_user_model, message_id: str) -> Response:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)
        return Response(
            content=await attachment_manager.get_instance().read_raw_source(message, self.get_original_source_path(message)),
            media_type="text/plain",
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

    async def download_message(self, current_user: db_user_model, message_id: str) -> Response:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)
        return Response(
            content=await attachment_manager.get_instance().read_raw_source(message, self.get_original_source_path(message)),
            media_type="message/rfc822",
            headers={
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": f'attachment; filename="{self.message_download_filename(message)}"',
            },
        )

    async def translate_message(self, current_user: db_user_model, message_id: str, target_language: str) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)
        translation = await translation_manager.get_instance().translate_message(message.subject, message.body, target_language)
        return {"message_id": str(message.id), **translation}

    async def permanently_delete_message(self, current_user: db_user_model, message_id: str) -> dict:
        mailbox = await self.get_active_user_mailbox(current_user)
        message = await self.get_owned_message(mailbox, message_id)
        if message.folder not in self.PURGEABLE_FOLDERS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Move the message to Trash before deleting it permanently")

        await attachment_manager.get_instance().delete_message_attachments(message.id)
        await attachment_manager.get_instance().delete_raw_source(message.raw_source_filename)
        await self._engine.delete(message)
        return {"message": "Message and attachments deleted permanently"}

    async def delete_message(self, current_user: db_user_model, message_id: str) -> dict:
        await self.move_to_trash(current_user, message_id)
        return {"message": "Message moved to Trash"}
