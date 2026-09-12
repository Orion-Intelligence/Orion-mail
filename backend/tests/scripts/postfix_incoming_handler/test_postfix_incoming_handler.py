from __future__ import annotations

import io
import os
import types

import pytest

import postfix_incoming_handler
from postfix_incoming_handler import (
    apply_delivery_report_field,
    build_multipart_request,
    collect_message_parts,
    decode_part_text,
    extract_authentication_results,
    extract_delivery_report,
    extract_spam_verdict,
    load_incoming_mail_token,
    main,
    post_incoming_mail,
    sanitize_header_value,
    serialize_nested_message,
)
from tests.scripts.postfix_incoming_handler.fakes import FailingResponseConnection
from tests.scripts.postfix_incoming_handler.helpers import (
    build_alternative_email,
    build_attachment_email,
    build_bad_charset_part,
    build_dsn_email,
    build_dsn_headers_email,
    build_inline_related_email,
    build_nested_email,
    build_plain_email,
    build_rfc822_part_without_list,
    install_fake_connection,
    parse,
)


def test_load_token_prefers_environment(monkeypatch):
    monkeypatch.setenv("ORION_MAIL_INCOMING_TOKEN", "env-token")
    assert load_incoming_mail_token() == "env-token"


def test_load_token_reads_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("ORION_MAIL_INCOMING_TOKEN", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text('OTHER=1\nINCOMING_MAIL_TOKEN="file-token"\n')
    monkeypatch.setattr(postfix_incoming_handler, "ENV_FILE", env_file)
    assert load_incoming_mail_token() == "file-token"


def test_load_token_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.delenv("ORION_MAIL_INCOMING_TOKEN", raising=False)
    monkeypatch.setattr(postfix_incoming_handler, "ENV_FILE", tmp_path / "absent.env")
    assert load_incoming_mail_token() == ""


def test_load_token_file_without_line_returns_empty(monkeypatch, tmp_path):
    monkeypatch.delenv("ORION_MAIL_INCOMING_TOKEN", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("NOTHING=here\n")
    monkeypatch.setattr(postfix_incoming_handler, "ENV_FILE", env_file)
    assert load_incoming_mail_token() == ""


def test_sanitize_header_value_strips_crlf_and_quotes():
    assert sanitize_header_value('na\r\nme"x"') == "name'x'"


def test_decode_part_text_happy_path():
    part = next(build_plain_email().walk())
    assert "plain body" in decode_part_text(part)


def test_decode_part_text_falls_back_on_bad_charset():
    assert decode_part_text(build_bad_charset_part()).strip() == "hello fallback"


def test_serialize_nested_message_uses_inner_bytes():
    outer = build_nested_email()
    rfc822 = next(part for part in outer.walk() if part.get_content_type() == "message/rfc822")
    data, filename = serialize_nested_message(rfc822)
    assert filename == "forwarded-message.eml"
    assert b"original@example.com" in data


def test_serialize_nested_message_without_inner_list():
    data, filename = serialize_nested_message(build_rfc822_part_without_list())
    assert filename == "forwarded-message.eml"
    assert data == b"raw inner text here"


def collect(message):
    bodies = {"text": "", "html": ""}
    attachments: list[dict] = []
    reports: list = []
    collect_message_parts(message, bodies, attachments, reports)
    return bodies, attachments, reports


def test_collect_gathers_text_and_html():
    bodies, attachments, reports = collect(build_alternative_email())
    assert "text body" in bodies["text"]
    assert "html body" in bodies["html"]
    assert attachments == []
    assert reports == []


def test_collect_gathers_attachment():
    bodies, attachments, _ = collect(build_attachment_email())
    assert "body text" in bodies["text"]
    assert len(attachments) == 1
    assert attachments[0]["filename"] == "report.bin"
    assert attachments[0]["data"] == b"binary-data"


def test_collect_gathers_nested_message_as_attachment():
    _, attachments, _ = collect(build_nested_email())
    rfc822 = [item for item in attachments if item["content_type"] == "message/rfc822"]
    assert len(rfc822) == 1
    assert rfc822[0]["filename"] == "forwarded-message.eml"


def test_collect_gathers_inline_content_id():
    _, attachments, _ = collect(build_inline_related_email())
    assert len(attachments) == 1
    assert attachments[0]["content_id"] == "logo@example.com"
    assert attachments[0]["filename"] == "attachment"


def test_collect_gathers_delivery_status_reports():
    _, attachments, reports = collect(build_dsn_email())
    assert len(reports) == 1
    assert reports[0].get_content_type() == "message/delivery-status"
    assert any(item["content_type"] == "message/rfc822" for item in attachments)


def test_extract_authentication_results_from_header():
    message = parse(b"Authentication-Results: mx.example.com; spf=pass; dkim=fail; dmarc=pass\r\n\r\nbody\r\n")
    assert extract_authentication_results(message) == {"spf": "pass", "dkim": "fail", "dmarc": "pass"}


def test_extract_authentication_results_received_spf_fallback():
    message = parse(b"Received-SPF: Pass (mailfrom)\r\n\r\nbody\r\n")
    assert extract_authentication_results(message)["spf"] == "pass"


def test_extract_authentication_results_defaults_empty():
    assert extract_authentication_results(build_plain_email()) == {"spf": "", "dkim": "", "dmarc": ""}


def test_extract_spam_verdict_reads_score_and_flag():
    message = parse(b"X-Spamd-Result: default: False [ 3.5 / 15.0 ]\r\nX-Spam: Yes\r\n\r\nbody\r\n")
    verdict = extract_spam_verdict(message)
    assert verdict == {"score": "3.5", "flag": "yes"}


def test_extract_spam_verdict_defaults_empty():
    assert extract_spam_verdict(build_plain_email()) == {"score": "", "flag": ""}


def test_apply_delivery_report_field_sets_and_keeps_first():
    report = {"action": "", "status": "", "recipient": "", "original_message_id": ""}
    apply_delivery_report_field(report, "Action", "Failed")
    apply_delivery_report_field(report, "Action", "delayed")
    apply_delivery_report_field(report, "Status", "5.1.1")
    apply_delivery_report_field(report, "Final-Recipient", "rfc822; USER@Example.com")
    apply_delivery_report_field(report, "Unknown", "ignored")
    assert report == {"action": "failed", "status": "5.1.1", "recipient": "user@example.com", "original_message_id": ""}


def test_extract_delivery_report_returns_empty_when_not_report():
    assert extract_delivery_report(build_plain_email(), []) == {}


def test_extract_delivery_report_from_dsn():
    _, _, reports = collect(build_dsn_email())
    report = extract_delivery_report(build_dsn_email(), reports)
    assert report["action"] == "failed"
    assert report["status"] == "5.1.1"
    assert report["recipient"] == "missing@example.com"
    assert report["original_message_id"] == "<original@example.com>"


def test_extract_delivery_report_headers_regex_fallback():
    message = build_dsn_headers_email()
    _, _, reports = collect(message)
    report = extract_delivery_report(message, reports)
    assert report["action"] == "failed"
    assert report["original_message_id"] == "<orig2@example.com>"


def test_extract_delivery_report_string_payload_branch():
    part = build_rfc822_part_without_list()
    part.replace_header("Content-Type", "message/delivery-status")
    part.set_payload("no-separator-line\r\nAction: Failed\r\nStatus: 4.4.1\r\nFinal-Recipient: rfc822; late@example.com\r\n")
    report = extract_delivery_report(build_plain_email(), [part])
    assert report["action"] == "failed"
    assert report["status"] == "4.4.1"
    assert report["recipient"] == "late@example.com"


def test_extract_delivery_report_skips_non_mimepart_blocks():
    fake_report = types.SimpleNamespace(get_payload=lambda: ["not-a-mime-part"])
    assert extract_delivery_report(build_plain_email(), [fake_report]) == {}


def test_build_multipart_request_contains_fields_and_attachment():
    attachments = [{"filename": 'bad"\r\nname.txt', "content_type": "text/plain", "data": b"filedata", "content_id": "cid1"}]
    body, content_type = build_multipart_request(
        sender_address="sender@example.com",
        receiver_address="rcpt@example.com",
        subject="Subject",
        body="text body",
        attachments=attachments,
        raw_email=b"RAWEMAILBYTES",
        body_html="<p>html</p>",
        to_addresses=["to1@example.com"],
        cc_addresses=["cc1@example.com"],
        reply_to_address="reply@example.com",
        message_id_header="<mid@example.com>",
        in_reply_to="<parent@example.com>",
        references=["<ref1@example.com>"],
        authentication={"spf": "pass", "dkim": "pass", "dmarc": "pass"},
        delivery_report={"action": "failed", "status": "5.1.1", "recipient": "x@example.com", "original_message_id": "<o@x>"},
        spam_verdict={"score": "1.2", "flag": "yes"},
    )
    assert content_type.startswith("multipart/form-data; boundary=----OrionMailBoundary")
    assert b'name="sender_address"' in body
    assert b"sender@example.com" in body
    assert b'name="to_addresses"' in body
    assert b'name="cc_addresses"' in body
    assert b'name="references"' in body
    assert b'name="spf_result"' in body
    assert b'name="files"; filename="bad\'name.txt"' in body
    assert b"filedata" in body
    assert b'name="file_content_ids"' in body
    assert b'name="raw_message"; filename="message.eml"' in body
    assert b"RAWEMAILBYTES" in body


def test_build_multipart_request_defaults_optional_dicts():
    body, _ = build_multipart_request("s@x.com", "r@x.com", "sub", "body", [], b"raw")
    assert b'name="spf_result"' in body
    assert b'name="raw_message"' in body


def test_post_incoming_mail_uses_http_connection(monkeypatch):
    monkeypatch.setattr(postfix_incoming_handler, "INCOMING_MAIL_URL", "http://mail.example.com:8000/incoming-mail/?q=1")
    monkeypatch.setattr(postfix_incoming_handler, "INCOMING_MAIL_TOKEN", "tok")
    record = install_fake_connection(monkeypatch, status=201, body=b"created")
    status_code, body = post_incoming_mail(b"payload", "multipart/form-data; boundary=x")
    assert (status_code, body) == (201, b"created")
    connection = record["instances"][0]
    assert connection.scheme == "http"
    assert connection.host == "mail.example.com"
    assert connection.port == 8000
    assert connection.closed is True
    request = connection.requests[0]
    assert request["method"] == "POST"
    assert request["path"] == "/incoming-mail/?q=1"
    assert request["headers"]["X-Incoming-Mail-Token"] == "tok"
    assert request["headers"]["Content-Length"] == str(len(b"payload"))


def test_post_incoming_mail_uses_https_connection(monkeypatch):
    monkeypatch.setattr(postfix_incoming_handler, "INCOMING_MAIL_URL", "https://mail.example.com/incoming-mail/")
    record = install_fake_connection(monkeypatch, status=200, body=b"ok")
    status_code, _ = post_incoming_mail(b"payload", "ct")
    assert status_code == 200
    assert record["instances"][0].scheme == "https"


def test_post_incoming_mail_closes_on_error(monkeypatch):
    monkeypatch.setattr(postfix_incoming_handler, "INCOMING_MAIL_URL", "http://mail.example.com/incoming-mail/")
    record = install_fake_connection(monkeypatch, connection_class=FailingResponseConnection)
    with pytest.raises(OSError):
        post_incoming_mail(b"payload", "ct")
    assert record["instances"][0].closed is True


@pytest.mark.parametrize("url", ["ftp://mail.example.com/x", "http:///no-host", "not-a-url"])
def test_post_incoming_mail_rejects_bad_url(monkeypatch, url):
    monkeypatch.setattr(postfix_incoming_handler, "INCOMING_MAIL_URL", url)
    with pytest.raises(ValueError):
        post_incoming_mail(b"payload", "ct")


def set_stdin(monkeypatch, raw: bytes):
    monkeypatch.setattr(postfix_incoming_handler.sys, "stdin", types.SimpleNamespace(buffer=io.BytesIO(raw)))


def test_main_missing_recipient_returns_dataerr(monkeypatch):
    monkeypatch.setattr(postfix_incoming_handler.sys, "argv", ["postfix_incoming_handler.py"])
    assert main() == os.EX_DATAERR


def test_main_invalid_email_returns_dataerr(monkeypatch):
    monkeypatch.setattr(postfix_incoming_handler.sys, "argv", ["prog", "rcpt@example.com"])
    set_stdin(monkeypatch, b"raw")

    def boom(*_args, **_kwargs):
        raise ValueError("bad")

    monkeypatch.setattr(postfix_incoming_handler, "message_from_bytes", boom)
    assert main() == os.EX_DATAERR


def test_main_success_posts_and_returns_ok(monkeypatch):
    monkeypatch.setattr(postfix_incoming_handler.sys, "argv", ["prog", "RcPt@Example.com"])
    set_stdin(monkeypatch, build_plain_email().as_bytes())
    captured: dict = {}

    def fake_post(request_body, content_type):
        captured["content_type"] = content_type
        captured["body"] = request_body
        return 200, b""

    monkeypatch.setattr(postfix_incoming_handler, "post_incoming_mail", fake_post)
    assert main() == os.EX_OK
    assert captured["content_type"].startswith("multipart/form-data")
    assert b"rcpt@example.com" in captured["body"]
    assert b"alice@example.com" in captured["body"]


def test_main_failure_branch_returns_tempfail(monkeypatch):
    monkeypatch.setattr(postfix_incoming_handler.sys, "argv", ["prog", "rcpt@example.com"])
    set_stdin(monkeypatch, build_plain_email().as_bytes())

    def failing_post(*_args, **_kwargs):
        raise OSError("service down")

    monkeypatch.setattr(postfix_incoming_handler, "post_incoming_mail", failing_post)
    assert main() == os.EX_TEMPFAIL


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (200, os.EX_OK),
        (201, os.EX_OK),
        (409, os.EX_OK),
        (413, os.EX_DATAERR),
        (404, os.EX_NOUSER),
        (400, os.EX_DATAERR),
        (422, os.EX_DATAERR),
        (507, os.EX_TEMPFAIL),
        (500, os.EX_TEMPFAIL),
    ],
)
def test_main_maps_status_codes(monkeypatch, status_code, expected):
    monkeypatch.setattr(postfix_incoming_handler.sys, "argv", ["prog", "rcpt@example.com"])
    set_stdin(monkeypatch, build_plain_email().as_bytes())
    monkeypatch.setattr(postfix_incoming_handler, "post_incoming_mail", lambda body, content_type: (status_code, b""))
    assert main() == expected
