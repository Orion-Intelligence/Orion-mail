from __future__ import annotations

import pytest
from io import BytesIO
from bson import ObjectId
from fastapi import HTTPException, UploadFile
from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.api.interactive.message_manager.message_enums import MESSAGE_LIMITS
from orion.services.mongo_manager.shared_model.db_attachment_model import STORAGE_TYPE
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model
from tests.model.fakes import build_encryption_stack
from starlette.datastructures import Headers
from orion.api.server.config_manager.config_controller import config_controller
from orion.services.antivirus_manager.antivirus_manager import antivirus_manager


def test_sanitize_strips_path_traversal():
    assert attachment_manager.sanitize_original_filename("../../etc/passwd") == "passwd"


def test_sanitize_defaults_when_missing():
    assert attachment_manager.sanitize_original_filename(None) == "attachment"


def test_sanitize_removes_control_characters():
    assert attachment_manager.sanitize_original_filename("re\x00port\n.txt") == "report.txt"


def test_sanitize_replaces_backslashes():
    assert attachment_manager.sanitize_original_filename("folder\\file.txt") == "folder_file.txt"


def test_sanitize_truncates_to_max_length():
    long_name = "a" * 500 + ".txt"
    assert len(attachment_manager.sanitize_original_filename(long_name)) <= MESSAGE_LIMITS.FILENAME_MAX_LENGTH


def test_generate_keeps_safe_lowercased_suffix():
    assert attachment_manager.generate_stored_filename("Report.PDF").endswith(".pdf")


def test_generate_drops_unsafe_suffix():
    stored = attachment_manager.generate_stored_filename("archive.gz!")
    assert "." not in stored


def test_get_attachment_path_rejects_traversal(tmp_path):
    with pytest.raises(ValueError):
        attachment_manager.get_attachment_path(tmp_path, "../escape.txt")


def test_get_attachment_path_allows_plain_filename(tmp_path):
    path = attachment_manager.get_attachment_path(tmp_path, "file.txt")
    assert path.name == "file.txt"


def test_get_storage_directory_rejects_invalid_type():
    with pytest.raises(ValueError):
        attachment_manager.get_storage_directory("not-a-real-type")


@pytest.mark.anyio
async def test_save_attachments_rejects_too_many_files():
    manager = object.__new__(attachment_manager)
    files = [
        UploadFile(filename=f"file{i}.txt", file=BytesIO(b"x"))
        for i in range(MESSAGE_LIMITS.MAX_ATTACHMENTS + 1)
    ]
    with pytest.raises(HTTPException) as error:
        await manager.save_attachments(ObjectId(), files, STORAGE_TYPE.INCOMING, "key", "err", "err")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_save_attachments_returns_empty_for_no_files():
    manager = object.__new__(attachment_manager)
    assert await manager.save_attachments(ObjectId(), [], STORAGE_TYPE.INCOMING, "key", "err", "err") == []


RAW_EML = b"From: a@mail.orionintelligence.org\r\nSubject: Secret\r\n\r\nConfidential body\r\n"


def build_stack():
    mailbox = db_mailbox_model(user_id=ObjectId(), mailbox_address="admin@mail.orionintelligence.org")
    message = db_message_model(owner_mailbox_id=mailbox.id, sender_address="a@x.org", receiver_address="b@x.org", subject="s", body="b", direction=MESSAGE_DIRECTION.INCOMING, folder=MESSAGE_FOLDER.INBOX)
    _crypto, engine = build_encryption_stack(mailbox=mailbox, message=message)

    manager = object.__new__(attachment_manager)
    manager._engine = engine
    return manager, engine, mailbox, message


@pytest.mark.anyio
async def test_owner_cipher_round_trips_file_bytes():
    manager, _engine, mailbox, _message = build_stack()

    cipher = await manager.owner_cipher(mailbox.id)
    assert cipher is not None
    sealed = cipher.encrypt_bytes(RAW_EML)

    assert RAW_EML not in sealed
    assert b"Confidential" not in sealed
    assert cipher.decrypt_bytes(sealed) == RAW_EML


@pytest.mark.anyio
async def test_message_cipher_matches_the_owning_mailbox_key():
    manager, _engine, mailbox, message = build_stack()

    by_message = await manager.message_cipher(message.id)
    by_mailbox = await manager.owner_cipher(mailbox.id)
    assert by_message is not None and by_mailbox is not None

    assert by_mailbox.decrypt_bytes(by_message.encrypt_bytes(RAW_EML)) == RAW_EML


@pytest.mark.anyio
async def test_read_raw_source_decrypts_only_when_flagged(tmp_path):
    manager, _engine, mailbox, message = build_stack()
    cipher = await manager.owner_cipher(mailbox.id)
    assert cipher is not None

    sealed_path = tmp_path / "sealed.eml"
    sealed_path.write_bytes(cipher.encrypt_bytes(RAW_EML))
    message.raw_source_encrypted = True
    assert await manager.read_raw_source(message, sealed_path) == RAW_EML

    legacy_path = tmp_path / "legacy.eml"
    legacy_path.write_bytes(RAW_EML)
    message.raw_source_encrypted = False
    assert await manager.read_raw_source(message, legacy_path) == RAW_EML


@pytest.mark.anyio
async def test_a_different_users_key_cannot_read_the_file():
    manager, engine, mailbox, _message = build_stack()
    owner_cipher = await manager.owner_cipher(mailbox.id)
    assert owner_cipher is not None
    sealed = owner_cipher.encrypt_bytes(RAW_EML)

    engine.mailbox = db_mailbox_model(user_id=ObjectId(), mailbox_address="other@mail.orionintelligence.org")
    other_cipher = await manager.owner_cipher(engine.mailbox.id)
    assert other_cipher is not None

    with pytest.raises(Exception):
        other_cipher.decrypt_bytes(sealed)


ONE_MB = 1024 * 1024


class FakeConfigController:
    async def get_config_int(self, _key):
        return 1


class FakeAntivirusManager:
    def __init__(self):
        self.scanned = []

    async def assert_clean(self, content, filename):
        self.scanned.append(filename)


def build_upload(name, size):
    payload = b"x" * size
    return UploadFile(file=BytesIO(payload), size=size, filename=name, headers=Headers({"content-type": "application/octet-stream"}))


def build_manager(tmp_path, monkeypatch):
    manager = object.__new__(attachment_manager)
    scanner = FakeAntivirusManager()
    monkeypatch.setattr(config_controller, "get_instance", staticmethod(lambda: FakeConfigController()))
    monkeypatch.setattr(antivirus_manager, "get_instance", staticmethod(lambda: scanner))
    monkeypatch.setattr(attachment_manager, "staging_directory", staticmethod(lambda: tmp_path))
    return manager, scanner


@pytest.mark.anyio
async def test_staging_writes_plaintext_and_records_no_database_row(tmp_path, monkeypatch):
    manager, _scanner = build_manager(tmp_path, monkeypatch)

    staged = await manager.stage_outgoing_attachments([build_upload("report.pdf", 2048)])

    assert len(staged) == 1
    assert staged[0]["original_filename"] == "report.pdf"
    assert "id" not in staged[0]
    stored = tmp_path / staged[0]["stored_filename"]
    assert stored.read_bytes() == b"x" * 2048


@pytest.mark.anyio
async def test_staging_rejects_a_file_over_the_limit_by_name(tmp_path, monkeypatch):
    manager, scanner = build_manager(tmp_path, monkeypatch)

    with pytest.raises(HTTPException) as error:
        await manager.stage_outgoing_attachments([build_upload("huge.zip", ONE_MB + 1)])

    assert error.value.status_code == 413
    assert "huge.zip" in error.value.detail
    assert scanner.scanned == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_staging_rejects_a_cumulative_overrun_and_leaves_no_files(tmp_path, monkeypatch):
    manager, _scanner = build_manager(tmp_path, monkeypatch)

    with pytest.raises(HTTPException) as error:
        await manager.stage_outgoing_attachments([build_upload("a.bin", 700 * 1024), build_upload("b.bin", 700 * 1024)])

    assert error.value.status_code == 413
    assert "Total attachment size" in error.value.detail
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_discard_removes_every_staged_file(tmp_path, monkeypatch):
    manager, _scanner = build_manager(tmp_path, monkeypatch)

    staged = await manager.stage_outgoing_attachments([build_upload("a.bin", 16), build_upload("b.bin", 16)])
    assert len(list(tmp_path.iterdir())) == 2

    manager.discard_staged_attachments(staged)

    assert list(tmp_path.iterdir()) == []
