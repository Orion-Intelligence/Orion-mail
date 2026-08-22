from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

import aiosmtplib
from fastapi import HTTPException, status

from orion.constants.constant import CONSTANTS


class mail_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if mail_manager.__instance is None:
            mail_manager()
        return mail_manager.__instance

    def __init__(self):
        if mail_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        mail_manager.__instance = self

    @staticmethod
    def get_attachment_file_path(storage_type: str, stored_filename: str) -> Path:
        return CONSTANTS.S_ATTACHMENT_DIR / storage_type / stored_filename

    @staticmethod
    def build_email_message(sender_address: str, receiver_addresses: list[str], subject: str, body: str, attachments: list[dict] | None = None, cc_addresses: list[str] | None = None, message_id_header: str | None = None, in_reply_to: str | None = None, references: list[str] | None = None, body_html: str | None = None) -> EmailMessage:
        email_message = EmailMessage()
        email_message["From"] = sender_address
        email_message["To"] = ", ".join(receiver_addresses)
        if cc_addresses:
            email_message["Cc"] = ", ".join(cc_addresses)
        email_message["Subject"] = subject
        email_message["Date"] = format_datetime(datetime.now(UTC))
        if message_id_header:
            email_message["Message-ID"] = message_id_header
        if in_reply_to:
            email_message["In-Reply-To"] = in_reply_to
        if references:
            email_message["References"] = " ".join(references)
        email_message.set_content(body)
        if body_html:
            email_message.add_alternative(body_html, subtype="html")

        for attachment in attachments or []:
            stored_filename = attachment["stored_filename"]
            original_filename = attachment["original_filename"]
            storage_type = attachment["storage_type"]
            content_type = attachment.get("content_type", "application/octet-stream")
            file_path = mail_manager.get_attachment_file_path(storage_type, stored_filename)
            if not file_path.exists():
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Attachment file not found: {original_filename}")
            if "/" in content_type:
                maintype, subtype = content_type.split("/", 1)
            else:
                maintype, subtype = "application", "octet-stream"
            email_message.add_attachment(file_path.read_bytes(), maintype=maintype, subtype=subtype, filename=original_filename)

        return email_message

    @staticmethod
    def serialize_email_message(email_message: EmailMessage) -> bytes:
        return email_message.as_bytes(policy=policy.SMTP)

    @staticmethod
    async def send_email_source(raw_source: bytes, sender_address: str, recipient_addresses: list[str]) -> dict[str, str]:
        try:
            errors, _ = await aiosmtplib.send(raw_source, sender=sender_address, recipients=recipient_addresses, hostname=CONSTANTS.S_SMTP_HOST, port=CONSTANTS.S_SMTP_PORT, username=CONSTANTS.S_SMTP_USERNAME, password=CONSTANTS.S_SMTP_PASSWORD, start_tls=CONSTANTS.S_SMTP_START_TLS, timeout=30)
            return {address: str(reason) for address, reason in (errors or {}).items()}
        except aiosmtplib.SMTPException as error:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Email delivery failed: {str(error)}")
        except TimeoutError:
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="SMTP server connection timed out")
        except OSError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="SMTP server is unavailable")
