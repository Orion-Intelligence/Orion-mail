import re
from datetime import UTC, datetime

from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException, UploadFile, status
from odmantic.query import and_, eq, in_

from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.api.interactive.message_manager.message_enums import MESSAGE_LIMITS
from orion.api.interactive.sender_safety_manager.sender_safety_manager import sender_safety_manager
from orion.constants.constant import CONSTANTS
from orion.services.encryption_manager.message_crypto_manager import message_crypto_manager
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import DELIVERY_STATUS, MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_attachment, db_message_model


class incoming_mail_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if incoming_mail_manager.__instance is None:
            incoming_mail_manager()
        return incoming_mail_manager.__instance

    def __init__(self):
        if incoming_mail_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        incoming_mail_manager.__instance = self
        self._engine = mongo_controller.get_instance().get_engine()

    @staticmethod
    def normalize_addresses(addresses: list[str]) -> list[str]:
        normalized: list[str] = []
        for address in addresses:
            try:
                value = validate_email(address.strip(), check_deliverability=False).normalized.lower()
            except EmailNotValidError:
                continue
            if value not in normalized:
                normalized.append(value)
        return normalized

    @staticmethod
    def normalize_message_id(value: str | None) -> str | None:
        if not value:
            return None
        match = re.search(r"<[^<>\s\r\n]{1,990}>", value)
        return match.group(0) if match else None

    async def save_incoming_email(self, sender_address: str, receiver_address: str, subject: str, body: str, files: list[UploadFile], raw_message: UploadFile | None = None, to_addresses: list[str] | None = None, cc_addresses: list[str] | None = None, reply_to_address: str | None = None, message_id_header: str | None = None, in_reply_to: str | None = None, references: list[str] | None = None, body_html: str | None = None, file_content_ids: list[str] | None = None, authentication: dict | None = None, delivery_report: dict | None = None) -> dict:
        mailbox = await self._engine.find_one(db_mailbox_model, and_(eq(db_mailbox_model.mailbox_address, receiver_address.lower()), eq(db_mailbox_model.is_active, True)))

        if mailbox is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiver mailbox not found")

        normalized_sender_address = sender_address.strip().lower()
        normalized_receiver_address = receiver_address.strip().lower()
        normalized_to_addresses = self.normalize_addresses(to_addresses or []) or [normalized_receiver_address]
        normalized_cc_addresses = [address for address in self.normalize_addresses(cc_addresses or []) if address not in normalized_to_addresses]
        normalized_reply_to_addresses = self.normalize_addresses([reply_to_address]) if reply_to_address else []
        normalized_reply_to = normalized_reply_to_addresses[0] if normalized_reply_to_addresses else None
        normalized_message_id = self.normalize_message_id(message_id_header)

        if normalized_message_id:
            duplicate = await self._engine.find_one(db_message_model, and_(eq(db_message_model.owner_mailbox_id, mailbox.id), eq(db_message_model.message_id_header, normalized_message_id), eq(db_message_model.direction, MESSAGE_DIRECTION.INCOMING)))
            if duplicate is not None:
                return {"id": str(duplicate.id), "attachments": [], "message": "Incoming email already stored"}
        normalized_in_reply_to = self.normalize_message_id(in_reply_to)
        normalized_references = []
        for reference in references or []:
            normalized_reference = self.normalize_message_id(reference)
            if normalized_reference and normalized_reference not in normalized_references:
                normalized_references.append(normalized_reference)
        normalized_references = normalized_references[-MESSAGE_LIMITS.MAX_THREAD_REFERENCES:]

        thread_parent: db_message_model | None = None
        thread_candidates = [candidate for candidate in [normalized_in_reply_to, *reversed(normalized_references)] if candidate]
        if thread_candidates:
            matching_messages = await self._engine.find(db_message_model, and_(eq(db_message_model.owner_mailbox_id, mailbox.id), in_(db_message_model.message_id_header, thread_candidates)))
            matching_by_header = {message.message_id_header: message for message in matching_messages}
            thread_parent = next((matching_by_header[candidate] for candidate in thread_candidates if candidate in matching_by_header), None)

        sender_is_blocked = await sender_safety_manager.get_instance().is_domain_blocked_for_user(mailbox.user_id, normalized_sender_address)
        initial_folder = MESSAGE_FOLDER.SPAM if sender_is_blocked else MESSAGE_FOLDER.INBOX
        previous_folder = MESSAGE_FOLDER.INBOX if sender_is_blocked else None
        message = db_message_model(
            owner_mailbox_id=mailbox.id,
            sender_address=normalized_sender_address,
            receiver_address=normalized_receiver_address,
            to_addresses=normalized_to_addresses,
            cc_addresses=normalized_cc_addresses,
            reply_to_address=normalized_reply_to,
            subject=subject.strip(),
            body=body.strip(),
            direction=MESSAGE_DIRECTION.INCOMING,
            folder=initial_folder,
            previous_folder=previous_folder,
            is_read=False,
            delivery_status=DELIVERY_STATUS.RECEIVED,
            body_html=(body_html or "").strip() or None,
            spf_result=(authentication or {}).get("spf") or None,
            dkim_result=(authentication or {}).get("dkim") or None,
            dmarc_result=(authentication or {}).get("dmarc") or None,
            message_id_header=normalized_message_id,
            in_reply_to=normalized_in_reply_to,
            references=normalized_references,
            thread_id=(thread_parent.thread_id or thread_parent.id) if thread_parent else None,
        )
        message.message_id_header = message.message_id_header or f"<{message.id}@{CONSTANTS.S_MAIL_DOMAIN}>"
        message.thread_id = message.thread_id or message.id
        message = await message_crypto_manager.get_instance().save_message(message)

        try:
            saved_attachments = await attachment_manager.get_instance().save_incoming_attachments(message_id=message.id, files=files)
            content_ids = file_content_ids or []
            for index, saved_attachment in enumerate(saved_attachments):
                saved_attachment["content_id"] = (content_ids[index].strip() if index < len(content_ids) else "") or None
            message.attachments = [db_message_attachment(**attachment) for attachment in saved_attachments]
            if raw_message is not None:
                raw_source_filename, raw_source_encrypted, raw_source_size = await attachment_manager.get_instance().save_raw_source(await raw_message.read(), message.owner_mailbox_id)
                message.raw_source_filename = raw_source_filename
                message.raw_source_encrypted = raw_source_encrypted
                message.raw_source_size = raw_source_size
            message.updated_at = datetime.now(UTC)
            await message_crypto_manager.get_instance().save_message(message)
        except Exception:
            await attachment_manager.get_instance().delete_message_attachments(message.id)
            await attachment_manager.get_instance().delete_raw_source(message.raw_source_filename)
            await self._engine.delete(message)
            raise

        bounced_message_id = await self.apply_delivery_report(mailbox, delivery_report or {})
        return {"id": str(message.id), "attachments": saved_attachments, "bounced_message_id": bounced_message_id, "message": "Incoming email saved successfully"}

    async def apply_delivery_report(self, mailbox: db_mailbox_model, delivery_report: dict) -> str | None:
        original_message_id = self.normalize_message_id(delivery_report.get("original_message_id"))
        if not original_message_id:
            return None

        original = await self._engine.find_one(db_message_model, and_(eq(db_message_model.owner_mailbox_id, mailbox.id), eq(db_message_model.message_id_header, original_message_id), eq(db_message_model.direction, MESSAGE_DIRECTION.OUTGOING)))
        if original is None:
            return None

        action = (delivery_report.get("action") or "").lower()
        if action and action not in ("failed", "delayed"):
            return None

        original.delivery_status = DELIVERY_STATUS.BOUNCED if action == "failed" else original.delivery_status
        original.bounce_status = delivery_report.get("status") or None
        original.bounce_recipient = delivery_report.get("recipient") or None
        original.updated_at = datetime.now(UTC)
        await message_crypto_manager.get_instance().save_message(original)
        return str(original.id)
