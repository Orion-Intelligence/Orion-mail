import http.client
import os
import re
import sys
from email import message_from_bytes, policy
# noinspection PyProtectedMember
from email.message import EmailMessage, MIMEPart
from email.utils import getaddresses, parseaddr
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

INCOMING_MAIL_URL = os.getenv("ORION_MAIL_INCOMING_URL", "http://127.0.0.1:8000/incoming-mail/")
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
AUTH_RESULT_PATTERN = re.compile(r"\b(spf|dkim|dmarc)\s*=\s*([a-z]+)", re.IGNORECASE)
SPAM_SCORE_PATTERN = re.compile(r"\[\s*(-?\d+(?:\.\d+)?)\s*/\s*-?\d+(?:\.\d+)?\s*\]")
SPAM_FLAG_VALUES = ("yes", "true", "1")


def load_incoming_mail_token() -> str:
    token = os.getenv("ORION_MAIL_INCOMING_TOKEN", "")
    if token:
        return token
    try:
        content = ENV_FILE.read_text()
    except OSError:
        return ""
    for line in content.splitlines():
        if line.startswith("INCOMING_MAIL_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


INCOMING_MAIL_TOKEN = load_incoming_mail_token()


def sanitize_header_value(value: str) -> str:
    return value.replace("\r", "").replace("\n", "").replace('"', "'")


def decode_part_text(part: MIMEPart) -> str:
    try:
        return str(part.get_content())
    except (LookupError, UnicodeError, ValueError, TypeError, KeyError):
        return bytes(part.get_payload(decode=True) or b"").decode("utf-8", errors="replace")


def serialize_nested_message(part: MIMEPart) -> tuple[bytes, str]:
    payload = part.get_payload()
    inner = payload[0] if isinstance(payload, list) and payload else None

    if isinstance(inner, MIMEPart):
        data = inner.as_bytes()
    else:
        data = bytes(part.get_payload(decode=True) or b"")

    return data, "forwarded-message.eml"


def collect_message_parts(part: MIMEPart, bodies: dict, attachments: list[dict], reports: list[MIMEPart]) -> None:
    content_type = part.get_content_type()

    if content_type == "message/rfc822":
        data, filename = serialize_nested_message(part)
        attachments.append({"filename": filename, "content_type": "message/rfc822", "data": data, "content_id": ""})
        return

    if content_type == "message/delivery-status":
        reports.append(part)
        return

    if part.is_multipart():
        for child in part.iter_parts():
            collect_message_parts(child, bodies, attachments, reports)
        return

    filename = part.get_filename()
    disposition = part.get_content_disposition()
    content_id = str(part.get("Content-ID", "")).strip().strip("<>")

    if disposition == "attachment" or filename is not None or content_id:
        file_data = bytes(part.get_payload(decode=True) or b"")
        attachments.append({"filename": filename or "attachment", "content_type": part.get_content_type() or "application/octet-stream", "data": file_data, "content_id": content_id})
        return

    if content_type == "text/plain" and not bodies["text"]:
        bodies["text"] = decode_part_text(part)
    elif content_type == "text/html" and not bodies["html"]:
        bodies["html"] = decode_part_text(part)


def extract_authentication_results(email_message: EmailMessage) -> dict:
    verdicts = {"spf": "", "dkim": "", "dmarc": ""}
    for header_value in email_message.get_all("Authentication-Results", []):
        for method, result in AUTH_RESULT_PATTERN.findall(str(header_value)):
            key = method.lower()
            if key in verdicts and not verdicts[key]:
                verdicts[key] = result.lower()
    if not verdicts["spf"]:
        for header_value in email_message.get_all("Received-SPF", []):
            match = re.match(r"\s*([a-z]+)", str(header_value), re.IGNORECASE)
            if match:
                verdicts["spf"] = match.group(1).lower()
                break
    return verdicts


def extract_spam_verdict(email_message: EmailMessage) -> dict:
    verdict = {"score": "", "flag": ""}
    for header_value in email_message.get_all("X-Spamd-Result", []):
        match = SPAM_SCORE_PATTERN.search(str(header_value))
        if match:
            verdict["score"] = match.group(1)
            break
    if str(email_message.get("X-Spam", "")).strip().lower() in SPAM_FLAG_VALUES:
        verdict["flag"] = "yes"
    return verdict


def apply_delivery_report_field(report: dict, name: str, value) -> None:
    key = name.strip().lower()
    cleaned = str(value).strip()
    if key == "action" and not report["action"]:
        report["action"] = cleaned.lower()
    elif key == "status" and not report["status"]:
        report["status"] = cleaned
    elif key in ("final-recipient", "original-recipient") and not report["recipient"]:
        report["recipient"] = cleaned.split(";")[-1].strip().lower()


def extract_delivery_report(email_message: EmailMessage, reports: list[MIMEPart]) -> dict:
    if email_message.get_content_type() != "multipart/report" and not reports:
        return {}
    report = {"action": "", "status": "", "recipient": "", "original_message_id": ""}
    for part in reports:
        payload = part.get_payload()
        blocks = payload if isinstance(payload, list) else []
        for block in blocks:
            if not isinstance(block, MIMEPart):
                continue
            for name, value in block.items():
                apply_delivery_report_field(report, name, value)
        if not blocks:
            for line in str(payload).splitlines():
                name, separator, value = line.partition(":")
                if not separator:
                    continue
                apply_delivery_report_field(report, name, value)
    for part in email_message.walk():
        if part.get_content_type() in ("message/rfc822", "text/rfc822-headers"):
            payload = part.get_payload()
            inner = payload[0] if isinstance(payload, list) and payload else None
            candidate = str(inner.get("Message-ID", "")).strip() if isinstance(inner, MIMEPart) else ""
            if not candidate:
                match = re.search(r"Message-ID:\s*(<[^>]+>)", decode_part_text(part), re.IGNORECASE)
                candidate = match.group(1) if match else ""
            if candidate:
                report["original_message_id"] = candidate
                break
    return report if report["action"] or report["status"] or report["original_message_id"] else {}


def build_multipart_request(sender_address: str, receiver_address: str, subject: str, body: str, attachments: list[dict], raw_email: bytes, body_html: str = "", to_addresses: list[str] | None = None, cc_addresses: list[str] | None = None, reply_to_address: str = "", message_id_header: str = "", in_reply_to: str = "", references: list[str] | None = None, authentication: dict | None = None, delivery_report: dict | None = None, spam_verdict: dict | None = None) -> tuple[bytes, str]:
    boundary = f"----OrionMailBoundary{uuid4().hex}"
    body_parts: list[bytes] = []
    authentication = authentication or {}
    delivery_report = delivery_report or {}
    spam_verdict = spam_verdict or {}
    form_fields: list[tuple[str, str]] = [
        ("sender_address", sender_address),
        ("receiver_address", receiver_address),
        ("subject", subject),
        ("body", body),
        ("body_html", body_html),
        ("reply_to_address", reply_to_address),
        ("message_id_header", message_id_header),
        ("in_reply_to", in_reply_to),
        ("spf_result", authentication.get("spf", "")),
        ("dkim_result", authentication.get("dkim", "")),
        ("dmarc_result", authentication.get("dmarc", "")),
        ("report_action", delivery_report.get("action", "")),
        ("report_status", delivery_report.get("status", "")),
        ("report_recipient", delivery_report.get("recipient", "")),
        ("report_original_message_id", delivery_report.get("original_message_id", "")),
        ("spam_score", spam_verdict.get("score", "")),
        ("spam_flag", spam_verdict.get("flag", "")),
    ]
    form_fields.extend(("to_addresses", address) for address in to_addresses or [])
    form_fields.extend(("cc_addresses", address) for address in cc_addresses or [])
    form_fields.extend(("references", reference) for reference in references or [])

    for field_name, field_value in form_fields:
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'.encode())
        body_parts.append(str(field_value).encode("utf-8"))
        body_parts.append(b"\r\n")

    for attachment in attachments:
        filename = sanitize_header_value(attachment["filename"])
        content_type = attachment["content_type"]
        file_data = attachment["data"]
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'.encode("utf-8"))
        body_parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
        body_parts.append(file_data)
        body_parts.append(b"\r\n")
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(b'Content-Disposition: form-data; name="file_content_ids"\r\n\r\n')
        body_parts.append(sanitize_header_value(attachment.get("content_id", "")).encode("utf-8"))
        body_parts.append(b"\r\n")

    body_parts.append(f"--{boundary}\r\n".encode())
    body_parts.append(b'Content-Disposition: form-data; name="raw_message"; filename="message.eml"\r\n')
    body_parts.append(b"Content-Type: message/rfc822\r\n\r\n")
    body_parts.append(raw_email)
    body_parts.append(b"\r\n")

    body_parts.append(f"--{boundary}--\r\n".encode())
    request_body = b"".join(body_parts)
    content_type = f"multipart/form-data; boundary={boundary}"
    return request_body, content_type


def post_incoming_mail(request_body: bytes, content_type: str) -> tuple[int, bytes]:
    parsed = urlsplit(INCOMING_MAIL_URL)
    host = parsed.hostname
    if parsed.scheme not in ("http", "https") or not host:
        raise ValueError("ORION_MAIL_INCOMING_URL must be an http(s) URL")
    connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    connection = connection_class(host, parsed.port, timeout=60)
    try:
        path = (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")
        connection.request("POST", path, body=request_body, headers={"Content-Type": content_type, "Content-Length": str(len(request_body)), "X-Incoming-Mail-Token": INCOMING_MAIL_TOKEN})
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def main() -> int:
    if len(sys.argv) < 2:
        print("5.3.0 Missing envelope recipient", file=sys.stderr)
        return os.EX_DATAERR

    receiver_address = sys.argv[1].strip().lower()
    raw_email = sys.stdin.buffer.read()

    try:
        email_message: EmailMessage = message_from_bytes(raw_email, policy=policy.default)
    except Exception:
        print("5.6.0 Invalid email format", file=sys.stderr)
        return os.EX_DATAERR

    _, sender_address = parseaddr(str(email_message.get("From", "")))
    sender_address = sender_address.strip().lower()
    to_addresses = [address.strip().lower() for _, address in getaddresses(email_message.get_all("To", [])) if address.strip()]
    cc_addresses = [address.strip().lower() for _, address in getaddresses(email_message.get_all("Cc", [])) if address.strip()]
    _, reply_to_address = parseaddr(str(email_message.get("Reply-To", "")))
    reply_to_address = reply_to_address.strip().lower()
    message_id_header = str(email_message.get("Message-ID", "")).strip()
    in_reply_to = str(email_message.get("In-Reply-To", "")).strip()
    references = str(email_message.get("References", "")).split()
    subject = str(email_message.get("Subject", "")).strip()
    bodies = {"text": "", "html": ""}
    attachments: list[dict] = []
    reports: list[MIMEPart] = []

    collect_message_parts(email_message, bodies, attachments, reports)

    authentication = extract_authentication_results(email_message)
    delivery_report = extract_delivery_report(email_message, reports)
    spam_verdict = extract_spam_verdict(email_message)

    request_body, content_type = build_multipart_request(
        sender_address=sender_address,
        receiver_address=receiver_address,
        subject=subject,
        body=bodies["text"].strip(),
        body_html=bodies["html"].strip(),
        attachments=attachments,
        raw_email=raw_email,
        to_addresses=to_addresses,
        cc_addresses=cc_addresses,
        reply_to_address=reply_to_address,
        message_id_header=message_id_header,
        in_reply_to=in_reply_to,
        references=references,
        authentication=authentication,
        delivery_report=delivery_report,
        spam_verdict=spam_verdict,
    )
    try:
        status_code, _ = post_incoming_mail(request_body, content_type)
    except (http.client.HTTPException, TimeoutError, OSError, ValueError):
        print("4.3.0 Orion Mail incoming service unavailable", file=sys.stderr)
        return os.EX_TEMPFAIL

    if status_code in (200, 201, 409):
        return os.EX_OK

    if status_code == 413:
        print("5.3.4 Orion Mail rejected the message because the attachment size exceeds the configured limit.", file=sys.stderr)
        return os.EX_DATAERR

    if status_code == 404:
        print("5.1.1 Orion Mail recipient mailbox does not exist.", file=sys.stderr)
        return os.EX_NOUSER

    if status_code in (400, 422):
        print("5.6.0 Orion Mail rejected the message as malformed.", file=sys.stderr)
        return os.EX_DATAERR

    if status_code == 507:
        print("4.2.2 Orion Mail recipient mailbox is full.", file=sys.stderr)
        return os.EX_TEMPFAIL

    print(f"4.3.0 Orion Mail could not process the message. HTTP status: {status_code}", file=sys.stderr)
    return os.EX_TEMPFAIL


if __name__ == "__main__":
    raise SystemExit(main())
