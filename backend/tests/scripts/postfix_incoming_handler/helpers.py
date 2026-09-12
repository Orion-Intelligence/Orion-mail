from __future__ import annotations

from email import message_from_bytes, policy
from email.message import EmailMessage, MIMEPart

import postfix_incoming_handler
from tests.scripts.postfix_incoming_handler.fakes import FakeConnection


def parse(raw: bytes) -> EmailMessage:
    return message_from_bytes(raw, policy=policy.default)


def build_plain_email() -> EmailMessage:
    message = EmailMessage()
    message["From"] = "Alice <alice@example.com>"
    message["To"] = "bob@example.com"
    message["Subject"] = "Hello"
    message.set_content("plain body")
    return message


def build_alternative_email() -> EmailMessage:
    message = EmailMessage()
    message["From"] = "alice@example.com"
    message.set_content("text body")
    message.add_alternative("<p>html body</p>", subtype="html")
    return message


def build_attachment_email() -> EmailMessage:
    message = EmailMessage()
    message["From"] = "alice@example.com"
    message.set_content("body text")
    message.add_attachment(b"binary-data", maintype="application", subtype="octet-stream", filename="report.bin")
    return message


def build_nested_email() -> EmailMessage:
    inner = EmailMessage()
    inner["From"] = "origin@example.com"
    inner["Message-ID"] = "<original@example.com>"
    inner["Subject"] = "Origin"
    inner.set_content("inner body")
    outer = EmailMessage()
    outer["From"] = "fwd@example.com"
    outer.set_content("see attached")
    outer.add_attachment(inner, filename="fwd.eml")
    return outer


def build_rfc822_part_without_list() -> MIMEPart:
    part = MIMEPart(policy=policy.default)
    part["Content-Type"] = "message/rfc822"
    part.set_payload("raw inner text here")
    return part


def build_bad_charset_part() -> EmailMessage:
    raw = b'Content-Type: text/plain; charset="x-nonexistent-cs"\r\nContent-Transfer-Encoding: 7bit\r\n\r\nhello fallback\r\n'
    return parse(raw)


def build_inline_related_email() -> EmailMessage:
    raw = b'MIME-Version: 1.0\r\nContent-Type: multipart/related; boundary="REL"\r\n\r\n--REL\r\nContent-Type: text/plain\r\n\r\nbody\r\n--REL\r\nContent-Type: image/png\r\nContent-ID: <logo@example.com>\r\n\r\nPNGDATA\r\n--REL--\r\n'
    return parse(raw)


def build_dsn_email() -> EmailMessage:
    raw = (
        b"From: MAILER-DAEMON@example.com\r\n"
        b"To: sender@example.com\r\n"
        b"Subject: Delivery Status Notification (Failure)\r\n"
        b"MIME-Version: 1.0\r\n"
        b'Content-Type: multipart/report; report-type=delivery-status; boundary="BOUND"\r\n\r\n'
        b"--BOUND\r\n"
        b"Content-Type: text/plain\r\n\r\n"
        b"Delivery failed.\r\n\r\n"
        b"--BOUND\r\n"
        b"Content-Type: message/delivery-status\r\n\r\n"
        b"Reporting-MTA: dns; example.com\r\n\r\n"
        b"Final-Recipient: rfc822; missing@example.com\r\n"
        b"Action: failed\r\n"
        b"Status: 5.1.1\r\n\r\n"
        b"--BOUND\r\n"
        b"Content-Type: message/rfc822\r\n\r\n"
        b"From: sender@example.com\r\n"
        b"To: missing@example.com\r\n"
        b"Message-ID: <original@example.com>\r\n"
        b"Subject: Original\r\n\r\n"
        b"Original body.\r\n"
        b"--BOUND--\r\n"
    )
    return parse(raw)


def build_dsn_headers_email() -> EmailMessage:
    raw = (
        b"MIME-Version: 1.0\r\n"
        b'Content-Type: multipart/report; report-type=delivery-status; boundary="B"\r\n\r\n'
        b"--B\r\n"
        b"Content-Type: message/delivery-status\r\n\r\n"
        b"Action: failed\r\n"
        b"Status: 5.1.1\r\n"
        b"Final-Recipient: rfc822; x@example.com\r\n\r\n"
        b"--B\r\n"
        b"Content-Type: text/rfc822-headers\r\n\r\n"
        b"From: sender@example.com\r\n"
        b"Message-ID: <orig2@example.com>\r\n"
        b"Subject: Original\r\n"
        b"--B--\r\n"
    )
    return parse(raw)


def install_fake_connection(monkeypatch, status: int = 200, body: bytes = b"ok", connection_class=FakeConnection):
    record: dict = {"instances": []}

    def make(scheme: str):
        def factory(host, port, timeout=None):
            connection = connection_class(host, port, timeout=timeout, status=status, body=body, scheme=scheme)
            record["instances"].append(connection)
            return connection
        return factory

    monkeypatch.setattr(postfix_incoming_handler.http.client, "HTTPConnection", make("http"))
    monkeypatch.setattr(postfix_incoming_handler.http.client, "HTTPSConnection", make("https"))
    return record
