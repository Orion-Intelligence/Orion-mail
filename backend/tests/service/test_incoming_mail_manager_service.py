from __future__ import annotations

import pytest
from bson import ObjectId
from fastapi import HTTPException

from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.api.interactive.incoming_mail_manager.incoming_mail_manager import incoming_mail_manager
from orion.api.interactive.sender_safety_manager.sender_safety_manager import sender_safety_manager
from orion.services.encryption_manager.message_crypto_manager import message_crypto_manager
from orion.services.mongo_manager.shared_model.db_attachment_model import STORAGE_TYPE
from orion.services.mongo_manager.shared_model.db_disposable_mailbox_model import db_disposable_mailbox_model
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import DELIVERY_STATUS, MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model
from tests.fake_model.fakes import RecordingEngine


def make_manager(engine):
    manager = object.__new__(incoming_mail_manager)
    manager._engine = engine
    return manager


def make_mailbox():
    return db_mailbox_model(user_id=ObjectId(), mailbox_address="test1@mail.orionintelligence.org")


class FakeCrypto:
    def __init__(self):
        self.saved = []

    async def save_message(self, message):
        self.saved.append(message)
        return message


class FakeRawMessage:
    async def read(self):
        return b"raw-bytes"


def patch_crypto(monkeypatch):
    crypto = FakeCrypto()
    monkeypatch.setattr(message_crypto_manager, "get_instance", staticmethod(lambda: crypto))
    return crypto


def patch_sender_safety(monkeypatch, blocked: bool):
    class FakeSenderSafety:
        async def is_domain_blocked_for_user(self, _user_id, _sender):
            return blocked

    monkeypatch.setattr(sender_safety_manager, "get_instance", staticmethod(lambda: FakeSenderSafety()))


def test_normalize_addresses_dedupes_lowercases_and_skips_invalid():
    result = incoming_mail_manager.normalize_addresses(["User@Example.COM", "not-an-email", " user@example.com "])
    assert result == ["user@example.com"]


@pytest.mark.parametrize("value,expected", [(None, None), ("", None), ("plain text", None), ("<abc@host>", "<abc@host>"), ("prefix <id@host> suffix", "<id@host>")])
def test_normalize_message_id(value, expected):
    assert incoming_mail_manager.normalize_message_id(value) == expected


@pytest.mark.anyio
async def test_save_incoming_email_raises_when_mailbox_missing():
    engine = RecordingEngine(find_one={db_mailbox_model: None, db_disposable_mailbox_model: None})
    manager = make_manager(engine)
    with pytest.raises(HTTPException) as error:
        await manager.save_incoming_email("s@x.org", "missing@mail.orionintelligence.org", "subject", "body", [])
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_save_incoming_email_resolves_disposable_owner_then_raises_when_owner_gone():
    disposable = db_disposable_mailbox_model(user_id=ObjectId(), owner_mailbox_id=ObjectId(), mailbox_address="drop@mail.orionintelligence.org", pgp_key_id=ObjectId())
    engine = RecordingEngine(find_one={db_mailbox_model: [None, None], db_disposable_mailbox_model: disposable})
    manager = make_manager(engine)
    with pytest.raises(HTTPException) as error:
        await manager.save_incoming_email("s@x.org", "drop@mail.orionintelligence.org", "subject", "body", [])
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_save_incoming_email_skips_duplicate_message():
    mailbox = make_mailbox()
    duplicate = db_message_model(owner_mailbox_id=mailbox.id, sender_address="s@x.org", receiver_address=mailbox.mailbox_address, subject="s", body="b", direction=MESSAGE_DIRECTION.INCOMING, folder=MESSAGE_FOLDER.INBOX)
    engine = RecordingEngine(find_one={db_mailbox_model: mailbox, db_message_model: duplicate})
    manager = make_manager(engine)
    result = await manager.save_incoming_email("s@x.org", mailbox.mailbox_address, "subject", "body", [], message_id_header="<dup@host>")
    assert result == {"message": "Incoming email already stored"}


@pytest.mark.anyio
async def test_save_incoming_email_routes_blocked_sender_to_spam(monkeypatch):
    mailbox = make_mailbox()
    engine = RecordingEngine(find_one={db_mailbox_model: mailbox})
    manager = make_manager(engine)
    crypto = patch_crypto(monkeypatch)
    patch_sender_safety(monkeypatch, blocked=True)

    class FakeAttachments:
        async def save_incoming_attachments(self, message_id, files):
            return []

        async def save_raw_source(self, data, mailbox_id):
            return "raw.eml", True, len(data)

    monkeypatch.setattr(attachment_manager, "get_instance", staticmethod(lambda: FakeAttachments()))

    result = await manager.save_incoming_email("bad@spam.org", mailbox.mailbox_address, "subject", "body", [], raw_message=FakeRawMessage())

    assert result == {"message": "Incoming email saved successfully"}
    stored = crypto.saved[0]
    assert stored.folder == MESSAGE_FOLDER.SPAM
    assert stored.previous_folder == MESSAGE_FOLDER.INBOX
    assert stored.raw_source_filename == "raw.eml"


@pytest.mark.anyio
async def test_save_incoming_email_flags_scanner_spam_verdict(monkeypatch):
    mailbox = make_mailbox()
    engine = RecordingEngine(find_one={db_mailbox_model: mailbox})
    manager = make_manager(engine)
    crypto = patch_crypto(monkeypatch)
    patch_sender_safety(monkeypatch, blocked=False)

    class FakeAttachments:
        async def save_incoming_attachments(self, message_id, files):
            return []

    monkeypatch.setattr(attachment_manager, "get_instance", staticmethod(lambda: FakeAttachments()))

    await manager.save_incoming_email("clean@ok.org", mailbox.mailbox_address, "subject", "body", [], spam_verdict={"flag": "yes", "score": "9.5"})

    stored = crypto.saved[0]
    assert stored.folder == MESSAGE_FOLDER.SPAM
    assert stored.spam_score == 9.5


@pytest.mark.anyio
async def test_save_incoming_email_links_thread_and_stores_attachments(monkeypatch):
    mailbox = make_mailbox()
    parent = db_message_model(owner_mailbox_id=mailbox.id, sender_address="s@x.org", receiver_address=mailbox.mailbox_address, subject="p", body="p", direction=MESSAGE_DIRECTION.INCOMING, folder=MESSAGE_FOLDER.INBOX, message_id_header="<parent@host>")
    engine = RecordingEngine(find_one={db_mailbox_model: mailbox}, find={db_message_model: [parent]})
    manager = make_manager(engine)
    crypto = patch_crypto(monkeypatch)
    patch_sender_safety(monkeypatch, blocked=False)

    class FakeAttachments:
        async def save_incoming_attachments(self, message_id, files):
            return [{"original_filename": "f.txt", "stored_filename": "s.txt", "size": 3, "storage_type": STORAGE_TYPE.INCOMING}]

    monkeypatch.setattr(attachment_manager, "get_instance", staticmethod(lambda: FakeAttachments()))

    await manager.save_incoming_email("s@x.org", mailbox.mailbox_address, "subject", "body", [], in_reply_to="<parent@host>", references=["<ref1@host>", "<parent@host>", "invalid", "<ref1@host>"])

    stored = crypto.saved[-1]
    assert stored.thread_id == parent.id
    assert stored.in_reply_to == "<parent@host>"
    assert "<ref1@host>" in stored.references
    assert len(stored.attachments) == 1


@pytest.mark.anyio
async def test_save_incoming_email_cleans_up_on_attachment_failure(monkeypatch):
    mailbox = make_mailbox()
    engine = RecordingEngine(find_one={db_mailbox_model: mailbox})
    manager = make_manager(engine)
    patch_crypto(monkeypatch)
    patch_sender_safety(monkeypatch, blocked=False)

    purged = []

    class FakeAttachments:
        async def save_incoming_attachments(self, message_id, files):
            raise RuntimeError("disk full")

        async def delete_message_attachments(self, message_id):
            purged.append(message_id)

        async def delete_raw_source(self, filename):
            purged.append(filename)

    monkeypatch.setattr(attachment_manager, "get_instance", staticmethod(lambda: FakeAttachments()))

    with pytest.raises(RuntimeError):
        await manager.save_incoming_email("clean@ok.org", mailbox.mailbox_address, "subject", "body", [])

    assert len(engine.deleted) == 1


@pytest.mark.anyio
async def test_apply_delivery_report_ignores_missing_original_message_id():
    manager = make_manager(RecordingEngine())
    assert await manager.apply_delivery_report(make_mailbox(), {}) is None


@pytest.mark.anyio
async def test_apply_delivery_report_ignores_unknown_original():
    engine = RecordingEngine(find_one={db_message_model: None})
    manager = make_manager(engine)
    assert await manager.apply_delivery_report(make_mailbox(), {"original_message_id": "<id@host>"}) is None


@pytest.mark.anyio
async def test_apply_delivery_report_ignores_non_failure_action():
    mailbox = make_mailbox()
    original = db_message_model(owner_mailbox_id=mailbox.id, sender_address="me@x.org", receiver_address="them@y.org", subject="s", body="b", direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT, message_id_header="<id@host>")
    engine = RecordingEngine(find_one={db_message_model: original})
    manager = make_manager(engine)
    assert await manager.apply_delivery_report(mailbox, {"original_message_id": "<id@host>", "action": "delivered"}) is None


@pytest.mark.anyio
async def test_apply_delivery_report_marks_failure_as_bounced(monkeypatch):
    mailbox = make_mailbox()
    original = db_message_model(owner_mailbox_id=mailbox.id, sender_address="me@x.org", receiver_address="them@y.org", subject="s", body="b", direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT, message_id_header="<id@host>")
    engine = RecordingEngine(find_one={db_message_model: original})
    manager = make_manager(engine)
    patch_crypto(monkeypatch)

    result = await manager.apply_delivery_report(mailbox, {"original_message_id": "<id@host>", "action": "failed", "status": "5.1.1", "recipient": "them@y.org"})

    assert result == str(original.id)
    assert original.delivery_status == DELIVERY_STATUS.BOUNCED
    assert original.bounce_status == "5.1.1"
