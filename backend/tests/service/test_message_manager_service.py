from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from fastapi import HTTPException
from fastapi.responses import Response

from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.api.interactive.message_manager.message_manager import message_manager
from orion.api.interactive.message_manager.message_enums import MESSAGE_LIMITS
from orion.api.interactive.message_manager.models.message_param_model import BULK_MESSAGE_ACTION, MESSAGE_SEARCH_SCOPE
from orion.api.interactive.sender_safety_manager.sender_safety_manager import sender_safety_manager
from orion.api.interactive.translation_manager.translation_manager import translation_manager
from orion.constants.constant import CONSTANTS
from orion.services.encryption_manager import message_crypto_manager as crypto_module
from orion.services.mail_manager.mail_manager import mail_manager
from orion.services.mongo_manager.shared_model.db_disposable_mailbox_model import db_disposable_mailbox_model
from orion.services.mongo_manager.shared_model.db_domain_safety_model import REPORT_TYPE
from orion.services.mongo_manager.shared_model.db_label_model import db_label_model
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import DELIVERY_STATUS, MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model
from orion.services.mongo_manager.shared_model.db_pgp_key_model import PGP_KEY_STATUS, PGP_KEY_TYPE, db_pgp_key_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model
from orion.services.spam_manager.spam_manager import spam_manager
from tests.fake_model.fakes import RecordingEngine

USER = db_user_model(full_name="Test One", email="test1@orionintelligence.org", username="test1")


class FakeCrypto:
    async def save_message(self, message):
        return message

    async def decrypt_message(self, message):
        return message

    async def decrypt_messages(self, messages):
        return messages


class FakeSafety:
    def __init__(self, domain_state=None, report=None, block=None, unblock=None, report_error=None, block_error=None, unblock_error=None):
        self._domain_state = domain_state if domain_state is not None else {"reported_as": None, "globally_blocked": False, "sender_blocked": False}
        self._report = report if report is not None else {"report_type": "spam"}
        self._block = block if block is not None else {"sender_blocked": True}
        self._unblock = unblock if unblock is not None else {"sender_blocked": False}
        self._report_error = report_error
        self._block_error = block_error
        self._unblock_error = unblock_error

    async def get_domain_state(self, _user, _sender):
        return self._domain_state

    async def report_domain(self, _user, _message, _report_type):
        if self._report_error is not None:
            raise self._report_error
        return self._report

    async def block_domain(self, _user, _message):
        if self._block_error is not None:
            raise self._block_error
        return self._block

    async def unblock_domain(self, _user, _sender):
        if self._unblock_error is not None:
            raise self._unblock_error
        return self._unblock


class FakePath:
    def __init__(self, is_file=True):
        self._is_file = is_file

    def is_file(self):
        return self._is_file


class FakeAttachments:
    def __init__(self, path=None, raw=b"raw-source", raise_path=False, raise_read=False):
        self._path = path if path is not None else FakePath(is_file=True)
        self._raw = raw
        self._raise_path = raise_path
        self._raise_read = raise_read
        self.deleted_attachments: list = []
        self.deleted_sources: list = []

    def get_raw_source_path(self, _filename):
        if self._raise_path:
            raise ValueError("bad path")
        return self._path

    async def read_raw_source(self, _message, _path):
        if self._raise_read:
            raise RuntimeError("read failed")
        return self._raw

    async def delete_message_attachments(self, message_id):
        self.deleted_attachments.append(message_id)

    async def delete_raw_source(self, filename):
        self.deleted_sources.append(filename)


class FakeSpam:
    def __init__(self):
        self.spam: list = []
        self.ham: list = []

    async def learn_spam(self, raw):
        self.spam.append(raw)

    async def learn_ham(self, raw):
        self.ham.append(raw)


class FakeAggCursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, length=None):
        return self._rows


class FakeAggCollection:
    def __init__(self, rows):
        self._rows = rows

    def aggregate(self, _pipeline):
        return FakeAggCursor(self._rows)


class FakeAggEngine:
    def __init__(self, rows):
        self._rows = rows

    def get_collection(self, _model):
        return FakeAggCollection(self._rows)


class FakeUpdateCollection:
    def __init__(self, modified):
        self.modified = modified
        self.update_many_calls: list = []

    async def update_many(self, filter_query, update):
        self.update_many_calls.append((filter_query, update))
        return type("R", (), {"modified_count": self.modified})()


class FakeUpdateEngine:
    def __init__(self, modified):
        self.collection = FakeUpdateCollection(modified)

    def get_collection(self, _model):
        return self.collection


def default_mailbox(signature=""):
    return db_mailbox_model(user_id=ObjectId(), mailbox_address="test1@mail.orionintelligence.org", signature=signature)


def make_message(**overrides):
    defaults = dict(
        owner_mailbox_id=ObjectId(),
        sender_address="sender@example.org",
        receiver_address="test1@mail.orionintelligence.org",
        subject="Subject",
        body="Body",
        direction=MESSAGE_DIRECTION.INCOMING,
        folder=MESSAGE_FOLDER.INBOX,
    )
    defaults.update(overrides)
    return db_message_model(**defaults)


def make_pgp_key(owner_mailbox_id=None):
    return db_pgp_key_model(user_id=USER.id, owner_mailbox_id=owner_mailbox_id or ObjectId(), key_type=PGP_KEY_TYPE.ORIGINAL, status=PGP_KEY_STATUS.ACTIVE, fingerprint=ObjectId().binary.hex(), public_key="PUB", wrapped_private_key="WRAP")


def make_manager(message=None, mailbox=None, engine=None):
    manager = object.__new__(message_manager)
    box = mailbox if mailbox is not None else default_mailbox()

    async def fake_mailbox(_user):
        return box

    async def fake_owned(_mailbox, _message_id):
        return message

    manager.get_active_user_mailbox = fake_mailbox
    manager.get_owned_message = fake_owned
    manager._engine = engine if engine is not None else RecordingEngine()
    return manager


@pytest.fixture(autouse=True)
def fake_crypto(monkeypatch):
    monkeypatch.setattr(crypto_module.message_crypto_manager, "get_instance", staticmethod(lambda: FakeCrypto()))


def patch_safety(monkeypatch, safety):
    monkeypatch.setattr(sender_safety_manager, "get_instance", staticmethod(lambda: safety))


def patch_attachments(monkeypatch, attachments):
    monkeypatch.setattr(attachment_manager, "get_instance", staticmethod(lambda: attachments))


def patch_spam(monkeypatch, spam):
    monkeypatch.setattr(spam_manager, "get_instance", staticmethod(lambda: spam))


@pytest.mark.anyio
async def test_get_owned_message_rejects_invalid_id():
    manager = object.__new__(message_manager)
    manager._engine = RecordingEngine()
    with pytest.raises(HTTPException) as error:
        await manager.get_owned_message(default_mailbox(), "not-an-object-id")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_get_owned_message_not_found():
    manager = object.__new__(message_manager)
    manager._engine = RecordingEngine(find_one={db_message_model: None})
    with pytest.raises(HTTPException) as error:
        await manager.get_owned_message(default_mailbox(), str(ObjectId()))
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_get_owned_message_returns_and_decrypts():
    message = make_message()
    manager = object.__new__(message_manager)
    manager._engine = RecordingEngine(find_one={db_message_model: message})
    assert await manager.get_owned_message(default_mailbox(), str(ObjectId())) is message


@pytest.mark.anyio
async def test_incoming_message_for_rejects_outgoing():
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT)
    manager = make_manager(message)
    with pytest.raises(HTTPException) as error:
        await manager.incoming_message_for(USER, "id", "test action")
    assert error.value.status_code == 400


def test_validate_subject_and_body_rejects_line_break():
    with pytest.raises(HTTPException) as error:
        message_manager.validate_subject_and_body("line\nbreak", "body")
    assert error.value.status_code == 400


def test_validate_subject_and_body_rejects_carriage_return():
    with pytest.raises(HTTPException) as error:
        message_manager.validate_subject_and_body("line\rbreak", "body")
    assert error.value.status_code == 400


def test_validate_subject_and_body_rejects_long_subject():
    with pytest.raises(HTTPException) as error:
        message_manager.validate_subject_and_body("x" * (MESSAGE_LIMITS.SUBJECT_MAX_LENGTH + 1), "body")
    assert error.value.status_code == 400


def test_validate_subject_and_body_rejects_long_body():
    with pytest.raises(HTTPException) as error:
        message_manager.validate_subject_and_body("subject", "x" * (MESSAGE_LIMITS.BODY_MAX_LENGTH + 1))
    assert error.value.status_code == 400


def test_validate_subject_and_body_accepts_valid():
    assert message_manager.validate_subject_and_body("subject", "body") is None


def test_normalize_recipient_addresses_rejects_invalid():
    with pytest.raises(HTTPException) as error:
        message_manager.normalize_recipient_addresses(["not-an-email"], "Cc")
    assert error.value.status_code == 400


def test_normalize_recipient_addresses_dedupes_and_lowercases():
    result = message_manager.normalize_recipient_addresses([" User@Example.COM ", "user@example.com"], "Cc")
    assert result == ["user@example.com"]


def test_allowed_destinations_empty_for_drafts():
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.DRAFTS)
    assert message_manager.allowed_destinations(message) == set()


def test_allowed_destinations_incoming():
    message = make_message()
    assert message_manager.allowed_destinations(message) == {MESSAGE_FOLDER.INBOX, MESSAGE_FOLDER.ARCHIVE, MESSAGE_FOLDER.SPAM, MESSAGE_FOLDER.TRASH}


def test_allowed_destinations_outgoing():
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT)
    assert message_manager.allowed_destinations(message) == {MESSAGE_FOLDER.SENT, MESSAGE_FOLDER.TRASH}


def test_relocate_message_records_previous_folder():
    manager = object.__new__(message_manager)
    message = make_message(folder=MESSAGE_FOLDER.INBOX)
    manager.relocate_message(message, MESSAGE_FOLDER.TRASH)
    assert message.folder == MESSAGE_FOLDER.TRASH
    assert message.previous_folder == MESSAGE_FOLDER.INBOX


def test_relocate_message_clears_previous_when_not_removed():
    manager = object.__new__(message_manager)
    message = make_message(folder=MESSAGE_FOLDER.TRASH, previous_folder=MESSAGE_FOLDER.INBOX)
    manager.relocate_message(message, MESSAGE_FOLDER.ARCHIVE)
    assert message.folder == MESSAGE_FOLDER.ARCHIVE
    assert message.previous_folder is None


def test_restore_target_archive_incoming_returns_inbox():
    manager = object.__new__(message_manager)
    message = make_message(folder=MESSAGE_FOLDER.ARCHIVE)
    assert manager.restore_target(message) == MESSAGE_FOLDER.INBOX


def test_restore_target_archive_outgoing_returns_sent():
    manager = object.__new__(message_manager)
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.ARCHIVE)
    assert manager.restore_target(message) == MESSAGE_FOLDER.SENT


def test_restore_target_uses_previous_folder():
    manager = object.__new__(message_manager)
    message = make_message(folder=MESSAGE_FOLDER.TRASH, previous_folder=MESSAGE_FOLDER.ARCHIVE)
    assert manager.restore_target(message) == MESSAGE_FOLDER.ARCHIVE


def test_restore_target_falls_back_when_previous_removed():
    manager = object.__new__(message_manager)
    message = make_message(folder=MESSAGE_FOLDER.TRASH, previous_folder=MESSAGE_FOLDER.SPAM)
    assert manager.restore_target(message) == MESSAGE_FOLDER.INBOX


def test_message_state_incoming_reports_read():
    assert message_manager.message_state(make_message()) == {"is_read": False}


def test_message_state_outgoing_reports_delivery_status():
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT)
    assert "delivery_status" in message_manager.message_state(message)


def test_message_download_filename():
    assert message_manager.message_download_filename(make_message()) == "message.eml"


def test_build_identity_signature_block_contains_parts():
    block = message_manager.build_identity_signature_block("Alice", "SIGNATURE")
    assert "Signed Identity Text:" in block
    assert "Alice" in block
    assert "SIGNATURE" in block


def test_build_identity_signature_block_html_escapes():
    block = message_manager.build_identity_signature_block_html("<b>Alice</b>", "<sig>")
    assert "&lt;b&gt;Alice&lt;/b&gt;" in block
    assert "&lt;sig&gt;" in block


def test_resolve_identity_signature_text_original_uses_mailbox_signature():
    result = message_manager.resolve_identity_signature_text(current_user=USER, sender_mailbox=default_mailbox(signature="My Signature"), sender_identity_type="original", disposable=None)
    assert result == "My Signature"


def test_resolve_identity_signature_text_original_falls_back_to_username():
    result = message_manager.resolve_identity_signature_text(current_user=USER, sender_mailbox=default_mailbox(), sender_identity_type="original", disposable=None)
    assert result == "test1"


def test_resolve_identity_signature_text_disposable_requires_disposable():
    with pytest.raises(HTTPException) as error:
        message_manager.resolve_identity_signature_text(current_user=USER, sender_mailbox=default_mailbox(), sender_identity_type="disposable", disposable=None)
    assert error.value.status_code == 400


def test_resolve_identity_signature_text_disposable_requires_signature():
    disposable = db_disposable_mailbox_model(user_id=USER.id, owner_mailbox_id=ObjectId(), mailbox_address="drop@mail.orionintelligence.org", pgp_key_id=ObjectId(), identity_signature="")
    with pytest.raises(HTTPException) as error:
        message_manager.resolve_identity_signature_text(current_user=USER, sender_mailbox=default_mailbox(), sender_identity_type="disposable", disposable=disposable)
    assert error.value.status_code == 400


def test_resolve_identity_signature_text_disposable_returns_signature():
    disposable = db_disposable_mailbox_model(user_id=USER.id, owner_mailbox_id=ObjectId(), mailbox_address="drop@mail.orionintelligence.org", pgp_key_id=ObjectId(), identity_signature="Drop Identity")
    result = message_manager.resolve_identity_signature_text(current_user=USER, sender_mailbox=default_mailbox(), sender_identity_type="disposable", disposable=disposable)
    assert result == "Drop Identity"


def test_get_original_source_path_missing_filename():
    message = make_message(raw_source_filename=None)
    with pytest.raises(HTTPException) as error:
        message_manager.get_original_source_path(message)
    assert error.value.status_code == 404


def test_get_original_source_path_invalid_path(monkeypatch):
    patch_attachments(monkeypatch, FakeAttachments(raise_path=True))
    message = make_message(raw_source_filename="raw.eml")
    with pytest.raises(HTTPException) as error:
        message_manager.get_original_source_path(message)
    assert error.value.status_code == 500


def test_get_original_source_path_gone(monkeypatch):
    patch_attachments(monkeypatch, FakeAttachments(path=FakePath(is_file=False)))
    message = make_message(raw_source_filename="raw.eml")
    with pytest.raises(HTTPException) as error:
        message_manager.get_original_source_path(message)
    assert error.value.status_code == 410


def test_get_original_source_path_returns_existing(monkeypatch):
    path = FakePath(is_file=True)
    patch_attachments(monkeypatch, FakeAttachments(path=path))
    message = make_message(raw_source_filename="raw.eml")
    assert message_manager.get_original_source_path(message) is path


@pytest.mark.anyio
async def test_internal_attachment_uploads_raises_when_file_missing(monkeypatch):
    class FakeMail:
        def get_attachment_file_path(self, _storage_type, _stored_filename):
            return FakePath(is_file=False)

    monkeypatch.setattr(mail_manager, "get_instance", staticmethod(lambda: FakeMail()))
    manager = object.__new__(message_manager)
    with pytest.raises(HTTPException) as error:
        manager.internal_attachment_uploads([{"storage_type": "incoming", "stored_filename": "s", "size": 3, "original_filename": "o", "content_type": "text/plain"}])
    assert error.value.status_code == 500


@pytest.mark.anyio
async def test_move_to_spam_if_needed_returns_false_when_already_spam():
    manager = object.__new__(message_manager)
    message = make_message(folder=MESSAGE_FOLDER.SPAM)
    assert await manager.move_to_spam_if_needed(message) is False


@pytest.mark.anyio
async def test_move_to_spam_if_needed_relocates():
    manager = object.__new__(message_manager)
    message = make_message(folder=MESSAGE_FOLDER.INBOX)
    assert await manager.move_to_spam_if_needed(message) is True
    assert message.folder == MESSAGE_FOLDER.SPAM


@pytest.mark.anyio
async def test_mark_delivery_failed_moves_sent_to_inbox():
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT)
    await message_manager.mark_delivery_failed(message)
    assert message.delivery_status == DELIVERY_STATUS.FAILED
    assert message.folder == MESSAGE_FOLDER.INBOX
    assert message.previous_folder == MESSAGE_FOLDER.SENT


@pytest.mark.anyio
async def test_mark_delivery_failed_keeps_non_sent_folder():
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.DRAFTS)
    await message_manager.mark_delivery_failed(message)
    assert message.delivery_status == DELIVERY_STATUS.FAILED
    assert message.folder == MESSAGE_FOLDER.DRAFTS


@pytest.mark.anyio
async def test_learn_message_class_skips_outgoing(monkeypatch):
    spam = FakeSpam()
    patch_spam(monkeypatch, spam)
    manager = object.__new__(message_manager)
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT, raw_source_filename="raw.eml")
    await manager.learn_message_class(message, True)
    assert spam.spam == []


@pytest.mark.anyio
async def test_learn_message_class_skips_without_source(monkeypatch):
    spam = FakeSpam()
    patch_spam(monkeypatch, spam)
    manager = object.__new__(message_manager)
    await manager.learn_message_class(make_message(raw_source_filename=None), True)
    assert spam.spam == []


@pytest.mark.anyio
async def test_learn_message_class_handles_invalid_source_path(monkeypatch):
    spam = FakeSpam()
    patch_spam(monkeypatch, spam)
    patch_attachments(monkeypatch, FakeAttachments(raise_path=True))
    manager = object.__new__(message_manager)
    await manager.learn_message_class(make_message(raw_source_filename="raw.eml"), True)
    assert spam.spam == []


@pytest.mark.anyio
async def test_learn_message_class_skips_when_file_missing(monkeypatch):
    spam = FakeSpam()
    patch_spam(monkeypatch, spam)
    patch_attachments(monkeypatch, FakeAttachments(path=FakePath(is_file=False)))
    manager = object.__new__(message_manager)
    await manager.learn_message_class(make_message(raw_source_filename="raw.eml"), True)
    assert spam.spam == []


@pytest.mark.anyio
async def test_learn_message_class_swallows_read_error(monkeypatch):
    spam = FakeSpam()
    patch_spam(monkeypatch, spam)
    patch_attachments(monkeypatch, FakeAttachments(raise_read=True))
    manager = object.__new__(message_manager)
    await manager.learn_message_class(make_message(raw_source_filename="raw.eml"), True)
    assert spam.spam == []


@pytest.mark.anyio
async def test_learn_message_class_learns_spam(monkeypatch):
    spam = FakeSpam()
    patch_spam(monkeypatch, spam)
    patch_attachments(monkeypatch, FakeAttachments(raw=b"spam-source"))
    manager = object.__new__(message_manager)
    await manager.learn_message_class(make_message(raw_source_filename="raw.eml"), True)
    assert spam.spam == [b"spam-source"]


@pytest.mark.anyio
async def test_learn_message_class_learns_ham(monkeypatch):
    spam = FakeSpam()
    patch_spam(monkeypatch, spam)
    patch_attachments(monkeypatch, FakeAttachments(raw=b"ham-source"))
    manager = object.__new__(message_manager)
    await manager.learn_message_class(make_message(raw_source_filename="raw.eml"), False)
    assert spam.ham == [b"ham-source"]


@pytest.mark.anyio
async def test_partition_recipient_addresses_rejects_missing_local():
    manager = make_manager(engine=RecordingEngine(find={db_mailbox_model: [], db_disposable_mailbox_model: []}))
    local = f"nobody@{CONSTANTS.S_MAIL_DOMAIN.lower()}"
    with pytest.raises(HTTPException) as error:
        await manager.partition_recipient_addresses([local])
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_partition_recipient_addresses_splits_internal_and_external():
    mailbox = default_mailbox()
    manager = make_manager(engine=RecordingEngine(find={db_mailbox_model: [mailbox], db_disposable_mailbox_model: []}))
    internal, external = await manager.partition_recipient_addresses([mailbox.mailbox_address, "outside@example.org"])
    assert internal == [mailbox.mailbox_address]
    assert external == ["outside@example.org"]


@pytest.mark.anyio
async def test_set_message_labels_rejects_invalid_label_id():
    manager = make_manager(make_message())
    with pytest.raises(HTTPException) as error:
        await manager.set_message_labels(USER, "id", ["not-an-object-id"])
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_set_message_labels_rejects_unowned_labels():
    manager = make_manager(make_message(), engine=RecordingEngine(counts={db_label_model: 0}))
    with pytest.raises(HTTPException) as error:
        await manager.set_message_labels(USER, "id", [str(ObjectId())])
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_set_message_labels_sets_owned_labels():
    label_id = ObjectId()
    message = make_message()
    manager = make_manager(message, engine=RecordingEngine(counts={db_label_model: 1}))
    result = await manager.set_message_labels(USER, "id", [str(label_id)])
    assert result["label_ids"] == [str(label_id)]


@pytest.mark.anyio
async def test_save_draft_rejects_non_draft():
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT)
    manager = make_manager(message)
    with pytest.raises(HTTPException) as error:
        await manager.save_draft(USER, "r@example.org", [], [], "subject", "body", draft_id="id")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_save_draft_rejects_subject_line_break():
    manager = make_manager(engine=RecordingEngine())
    with pytest.raises(HTTPException) as error:
        await manager.save_draft(USER, "r@example.org", [], [], "line\nbreak", "body")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_save_draft_creates_new_draft():
    manager = make_manager(engine=RecordingEngine())
    result = await manager.save_draft(USER, " R@Example.ORG ", [" cc@example.org "], [], " Hello ", "Body")
    assert result["receiver_address"] == "r@example.org"
    assert result["cc_addresses"] == ["cc@example.org"]
    assert result["subject"] == "Hello"
    assert result["folder"] == MESSAGE_FOLDER.DRAFTS


@pytest.mark.anyio
async def test_save_draft_updates_existing_draft():
    draft = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.DRAFTS)
    manager = make_manager(draft)
    result = await manager.save_draft(USER, "new@example.org", [], [], "Updated", "Body", draft_id="id")
    assert result["receiver_address"] == "new@example.org"
    assert result["subject"] == "Updated"


@pytest.mark.anyio
async def test_send_message_rejects_invalid_identity_type():
    manager = make_manager()
    with pytest.raises(HTTPException) as error:
        await manager.send_message(USER, "r@example.org", "subject", "body", [], sender_identity_type="unknown")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_send_message_disposable_requires_id():
    manager = make_manager()
    with pytest.raises(HTTPException) as error:
        await manager.send_message(USER, "r@example.org", "subject", "body", [], sender_identity_type="disposable")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_send_message_disposable_rejects_invalid_id():
    manager = make_manager()
    with pytest.raises(HTTPException) as error:
        await manager.send_message(USER, "r@example.org", "subject", "body", [], sender_identity_type="disposable", disposable_mailbox_id="bad-id")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_send_message_disposable_not_found():
    manager = make_manager(engine=RecordingEngine(find_one={db_disposable_mailbox_model: None}))
    with pytest.raises(HTTPException) as error:
        await manager.send_message(USER, "r@example.org", "subject", "body", [], sender_identity_type="disposable", disposable_mailbox_id=str(ObjectId()))
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_send_message_raises_when_pgp_key_lookup_fails():
    key = make_pgp_key()
    manager = make_manager(engine=RecordingEngine(find_one={db_pgp_key_model: [key, None]}))
    with pytest.raises(HTTPException) as error:
        await manager.send_message(USER, "r@example.org", "subject", "body", [])
    assert error.value.status_code == 500


@pytest.mark.anyio
async def test_send_message_rejects_empty_receiver():
    key = make_pgp_key()
    manager = make_manager(engine=RecordingEngine(find_one={db_pgp_key_model: key}))
    with pytest.raises(HTTPException) as error:
        await manager.send_message(USER, "   ", "subject", "body", [])
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_send_message_rejects_empty_subject():
    key = make_pgp_key()
    manager = make_manager(engine=RecordingEngine(find_one={db_pgp_key_model: key}))
    with pytest.raises(HTTPException) as error:
        await manager.send_message(USER, "r@example.org", "   ", "body", [])
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_send_message_rejects_empty_body():
    key = make_pgp_key()
    manager = make_manager(engine=RecordingEngine(find_one={db_pgp_key_model: key}))
    with pytest.raises(HTTPException) as error:
        await manager.send_message(USER, "r@example.org", "subject", "   ", [])
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_send_message_rejects_invalid_receiver_email():
    key = make_pgp_key()
    manager = make_manager(engine=RecordingEngine(find_one={db_pgp_key_model: key}))
    with pytest.raises(HTTPException) as error:
        await manager.send_message(USER, "not-an-email", "subject", "body", [])
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_send_message_rejects_too_many_recipients():
    key = make_pgp_key()
    manager = make_manager(engine=RecordingEngine(find_one={db_pgp_key_model: key}))
    cc = [f"user{index}@example.org" for index in range(MESSAGE_LIMITS.MAX_RECIPIENTS)]
    with pytest.raises(HTTPException) as error:
        await manager.send_message(USER, "r@example.org", "subject", "body", [], cc_addresses=cc)
    assert error.value.status_code == 400


def prepare_deep_send_manager(key, owned_message):
    manager = make_manager(engine=RecordingEngine(find_one={db_pgp_key_model: key}))

    async def no_op_quota(_mailbox):
        return None

    async def fake_partition(addresses):
        return ([], list(addresses))

    async def fake_owned(_mailbox, _message_id):
        return owned_message

    manager.enforce_send_quota = no_op_quota
    manager.enforce_storage_quota = no_op_quota
    manager.partition_recipient_addresses = fake_partition
    manager.get_owned_message = fake_owned
    return manager


@pytest.mark.anyio
async def test_send_message_rejects_reply_and_forward_together():
    manager = prepare_deep_send_manager(make_pgp_key(), make_message())
    with pytest.raises(HTTPException) as error:
        await manager.send_message(USER, "r@example.org", "subject", "body", [], in_reply_to_message_id="a", forward_message_id="b")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_send_message_rejects_forward_attachments_without_source():
    manager = prepare_deep_send_manager(make_pgp_key(), make_message())
    with pytest.raises(HTTPException) as error:
        await manager.send_message(USER, "r@example.org", "subject", "body", [], forward_attachment_ids=["att"])
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_send_message_rejects_non_draft_draft_id():
    manager = prepare_deep_send_manager(make_pgp_key(), make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT))
    with pytest.raises(HTTPException) as error:
        await manager.send_message(USER, "r@example.org", "subject", "body", [], draft_id="d")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_unsnooze_message_clears_snoozed_until():
    message = make_message(snoozed_until=datetime.now(UTC) + timedelta(hours=1))
    manager = make_manager(message)
    result = await manager.unsnooze_message(USER, "id")
    assert result["snoozed_until"] is None


@pytest.mark.anyio
async def test_cancel_scheduled_message_clears_scheduled_at():
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.DRAFTS, scheduled_at=datetime.now(UTC) + timedelta(hours=1))
    manager = make_manager(message)
    result = await manager.cancel_scheduled_message(USER, "id")
    assert result["scheduled_at"] is None


@pytest.mark.anyio
async def test_enforce_send_quota_raises_when_limit_reached():
    manager = object.__new__(message_manager)
    manager._engine = RecordingEngine(counts={db_message_model: MESSAGE_LIMITS.MAX_SENDS_PER_WINDOW})
    with pytest.raises(HTTPException) as error:
        await manager.enforce_send_quota(default_mailbox())
    assert error.value.status_code == 429


@pytest.mark.anyio
async def test_enforce_send_quota_allows_under_limit():
    manager = object.__new__(message_manager)
    manager._engine = RecordingEngine(counts={db_message_model: 0})
    assert await manager.enforce_send_quota(default_mailbox()) is None


@pytest.mark.anyio
async def test_enforce_storage_quota_raises_when_exceeded():
    manager = object.__new__(message_manager)
    manager._engine = FakeAggEngine([{"attachment_bytes": MESSAGE_LIMITS.MAILBOX_QUOTA_BYTES, "raw_bytes": 0}])
    with pytest.raises(HTTPException) as error:
        await manager.enforce_storage_quota(default_mailbox())
    assert error.value.status_code == 507


@pytest.mark.anyio
async def test_enforce_storage_quota_allows_under_limit():
    manager = object.__new__(message_manager)
    manager._engine = FakeAggEngine([{"attachment_bytes": 10, "raw_bytes": 5}])
    assert await manager.enforce_storage_quota(default_mailbox()) is None


@pytest.mark.anyio
async def test_storage_bytes_for_sums_attachment_and_raw():
    manager = object.__new__(message_manager)
    manager._engine = FakeAggEngine([{"attachment_bytes": 100, "raw_bytes": 50}])
    assert await manager.mailbox_storage_used(default_mailbox()) == 150


@pytest.mark.anyio
async def test_storage_bytes_for_returns_zero_when_no_rows():
    manager = object.__new__(message_manager)
    manager._engine = FakeAggEngine([])
    assert await manager.server_storage_used() == 0


@pytest.mark.anyio
async def test_server_storage_status_flags_exceeded():
    manager = object.__new__(message_manager)
    manager._engine = FakeAggEngine([{"attachment_bytes": CONSTANTS.S_SERVER_STORAGE_QUOTA_BYTES, "raw_bytes": 0}])
    status_result = await manager.server_storage_status()
    assert status_result["storage_exceeded"] is True


@pytest.mark.anyio
async def test_get_mailbox_usage_computes_percent():
    manager = make_manager(engine=FakeAggEngine([{"attachment_bytes": MESSAGE_LIMITS.MAILBOX_QUOTA_BYTES // 2, "raw_bytes": 0}]))
    usage = await manager.get_mailbox_usage(USER)
    assert usage["quota_bytes"] == MESSAGE_LIMITS.MAILBOX_QUOTA_BYTES
    assert usage["used_percent"] == 50.0


@pytest.mark.anyio
async def test_empty_folder_rejects_non_purgeable():
    manager = make_manager()
    with pytest.raises(HTTPException) as error:
        await manager.empty_folder(USER, MESSAGE_FOLDER.INBOX)
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_empty_folder_deletes_messages(monkeypatch):
    message = make_message(folder=MESSAGE_FOLDER.TRASH, raw_source_filename="raw.eml")
    engine = RecordingEngine(find={db_message_model: [message]})
    manager = make_manager(engine=engine)
    attachments = FakeAttachments()
    patch_attachments(monkeypatch, attachments)
    result = await manager.empty_folder(USER, MESSAGE_FOLDER.TRASH)
    assert result == {"folder": "trash", "deleted": 1}
    assert message in engine.deleted
    assert message.id in attachments.deleted_attachments


@pytest.mark.anyio
async def test_mark_folder_read_updates_documents():
    manager = make_manager(engine=FakeUpdateEngine(modified=3))
    result = await manager.mark_folder_read(USER, MESSAGE_FOLDER.INBOX)
    assert result == {"folder": "inbox", "updated": 3}


@pytest.mark.anyio
async def test_wake_snoozed_messages_returns_woken_count():
    manager = object.__new__(message_manager)
    manager._engine = FakeUpdateEngine(modified=5)
    result = await manager.wake_snoozed_messages()
    assert result == {"woken": 5}


@pytest.mark.anyio
async def test_search_rejects_empty_query():
    manager = make_manager()
    with pytest.raises(HTTPException) as error:
        await manager.search_messages(USER, "   ", MESSAGE_SEARCH_SCOPE.ALL)
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_search_rejects_too_long_query():
    manager = make_manager()
    with pytest.raises(HTTPException) as error:
        await manager.search_messages(USER, "x" * (message_manager.SEARCH_QUERY_MAX_LENGTH + 1), MESSAGE_SEARCH_SCOPE.ALL)
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_search_rejects_bad_limit():
    manager = make_manager()
    with pytest.raises(HTTPException) as error:
        await manager.search_messages(USER, "hello", MESSAGE_SEARCH_SCOPE.ALL, limit=0)
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_search_label_scope_requires_label():
    manager = make_manager()
    with pytest.raises(HTTPException) as error:
        await manager.search_messages(USER, "hello", MESSAGE_SEARCH_SCOPE.LABEL)
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_search_label_scope_rejects_invalid_label_id():
    manager = make_manager()
    with pytest.raises(HTTPException) as error:
        await manager.search_messages(USER, "hello", MESSAGE_SEARCH_SCOPE.LABEL, label_id="bad-id")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_search_label_scope_label_not_found():
    manager = make_manager(engine=RecordingEngine(find_one={db_label_model: None}))
    with pytest.raises(HTTPException) as error:
        await manager.search_messages(USER, "hello", MESSAGE_SEARCH_SCOPE.LABEL, label_id=str(ObjectId()))
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_search_returns_matches():
    message = make_message()
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    result = await manager.search_messages(USER, "sender", MESSAGE_SEARCH_SCOPE.ALL)
    assert len(result) == 1
    assert result[0]["id"] == str(message.id)


@pytest.mark.anyio
async def test_get_folder_counts_maps_rows():
    manager = make_manager(engine=FakeAggEngine([{"_id": "inbox", "count": 3, "unread": 2}]))
    counts = await manager.get_folder_counts(USER)
    assert counts["inbox"] == 3
    assert counts["unread"]["inbox"] == 2


@pytest.mark.anyio
async def test_get_folder_messages_inbox_serializes():
    message = make_message()
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    result = await manager.get_inbox_messages(USER)
    assert result[0]["id"] == str(message.id)


@pytest.mark.anyio
async def test_get_folder_messages_drafts_serializes():
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.DRAFTS)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    result = await manager.get_draft_messages(USER)
    assert result[0]["folder"] == MESSAGE_FOLDER.DRAFTS


@pytest.mark.anyio
async def test_get_starred_messages_serializes():
    message = make_message(is_starred=True)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    result = await manager.get_starred_messages(USER)
    assert result[0]["is_starred"] is True


@pytest.mark.anyio
async def test_get_thread_messages_serializes():
    message = make_message()
    manager = make_manager(message=message, engine=RecordingEngine(find={db_message_model: [message]}))
    result = await manager.get_thread_messages(USER, "id")
    assert result[0]["id"] == str(message.id)


@pytest.mark.anyio
async def test_get_message_by_id_marks_incoming_read(monkeypatch):
    message = make_message(is_read=False)
    manager = make_manager(message)
    patch_safety(monkeypatch, FakeSafety())
    result = await manager.get_message_by_id(USER, "id")
    assert message.is_read is True
    assert "safety" in result


@pytest.mark.anyio
async def test_mark_message_unread_rejects_outgoing():
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT)
    manager = make_manager(message)
    with pytest.raises(HTTPException) as error:
        await manager.mark_message_unread(USER, "id")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_mark_message_unread_sets_unread(monkeypatch):
    message = make_message(is_read=True)
    manager = make_manager(message)
    patch_safety(monkeypatch, FakeSafety())
    result = await manager.mark_message_unread(USER, "id")
    assert message.is_read is False
    assert result["is_read"] is False


@pytest.mark.anyio
async def test_move_message_rejects_disallowed_destination():
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.DRAFTS)
    manager = make_manager(message)
    with pytest.raises(HTTPException) as error:
        await manager.move_message(USER, "id", MESSAGE_FOLDER.INBOX)
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_move_message_to_spam_relocates(monkeypatch):
    message = make_message(folder=MESSAGE_FOLDER.INBOX)
    manager = make_manager(message)
    patch_safety(monkeypatch, FakeSafety())
    result = await manager.move_message(USER, "id", MESSAGE_FOLDER.SPAM)
    assert message.folder == MESSAGE_FOLDER.SPAM
    assert result["folder"] == MESSAGE_FOLDER.SPAM


@pytest.mark.anyio
async def test_report_sender_rejects_outgoing():
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT)
    manager = make_manager(message)
    with pytest.raises(HTTPException) as error:
        await manager.report_sender(USER, "id", REPORT_TYPE.SPAM)
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_report_sender_wraps_value_error(monkeypatch):
    message = make_message()
    manager = make_manager(message)
    patch_safety(monkeypatch, FakeSafety(report_error=ValueError("cannot report")))
    with pytest.raises(HTTPException) as error:
        await manager.report_sender(USER, "id", REPORT_TYPE.SPAM)
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_report_sender_moves_to_spam(monkeypatch):
    message = make_message(folder=MESSAGE_FOLDER.INBOX)
    manager = make_manager(message)
    patch_safety(monkeypatch, FakeSafety())
    result = await manager.report_sender(USER, "id", REPORT_TYPE.SPAM)
    assert message.folder == MESSAGE_FOLDER.SPAM
    assert "report" in result


@pytest.mark.anyio
async def test_block_sender_wraps_value_error(monkeypatch):
    message = make_message()
    manager = make_manager(message)
    patch_safety(monkeypatch, FakeSafety(block_error=ValueError("cannot block")))
    with pytest.raises(HTTPException) as error:
        await manager.block_sender(USER, "id")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_block_sender_moves_to_spam(monkeypatch):
    message = make_message(folder=MESSAGE_FOLDER.INBOX)
    manager = make_manager(message)
    patch_safety(monkeypatch, FakeSafety())
    result = await manager.block_sender(USER, "id")
    assert message.folder == MESSAGE_FOLDER.SPAM
    assert "block" in result


@pytest.mark.anyio
async def test_unblock_sender_wraps_value_error(monkeypatch):
    message = make_message()
    manager = make_manager(message)
    patch_safety(monkeypatch, FakeSafety(unblock_error=ValueError("cannot unblock")))
    with pytest.raises(HTTPException) as error:
        await manager.unblock_sender(USER, "id")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_unblock_sender_returns_block_state(monkeypatch):
    message = make_message()
    manager = make_manager(message)
    patch_safety(monkeypatch, FakeSafety())
    result = await manager.unblock_sender(USER, "id")
    assert result["block"]["sender_blocked"] is False


@pytest.mark.anyio
async def test_archive_message_already_archived_returns_unchanged():
    message = make_message(folder=MESSAGE_FOLDER.ARCHIVE)
    manager = make_manager(message)
    result = await manager.archive_message(USER, "id")
    assert result["folder"] == MESSAGE_FOLDER.ARCHIVE


@pytest.mark.anyio
async def test_archive_message_rejects_non_inbox():
    message = make_message(folder=MESSAGE_FOLDER.SENT, direction=MESSAGE_DIRECTION.OUTGOING)
    manager = make_manager(message)
    with pytest.raises(HTTPException) as error:
        await manager.archive_message(USER, "id")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_archive_message_moves_inbox_to_archive():
    message = make_message(folder=MESSAGE_FOLDER.INBOX)
    manager = make_manager(message)
    result = await manager.archive_message(USER, "id")
    assert message.folder == MESSAGE_FOLDER.ARCHIVE
    assert result["folder"] == MESSAGE_FOLDER.ARCHIVE


@pytest.mark.anyio
async def test_move_to_trash_relocates():
    message = make_message(folder=MESSAGE_FOLDER.INBOX)
    manager = make_manager(message)
    await manager.move_to_trash(USER, "id")
    assert message.folder == MESSAGE_FOLDER.TRASH


@pytest.mark.anyio
async def test_move_to_trash_noop_when_already_trash():
    message = make_message(folder=MESSAGE_FOLDER.TRASH)
    manager = make_manager(message)
    result = await manager.move_to_trash(USER, "id")
    assert result["folder"] == MESSAGE_FOLDER.TRASH


@pytest.mark.anyio
async def test_restore_message_rejects_non_restorable():
    message = make_message(folder=MESSAGE_FOLDER.INBOX)
    manager = make_manager(message)
    with pytest.raises(HTTPException) as error:
        await manager.restore_message(USER, "id")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_restore_message_from_trash():
    message = make_message(folder=MESSAGE_FOLDER.TRASH, previous_folder=MESSAGE_FOLDER.ARCHIVE)
    manager = make_manager(message)
    result = await manager.restore_message(USER, "id")
    assert result["folder"] == MESSAGE_FOLDER.ARCHIVE


@pytest.mark.anyio
async def test_restore_message_from_spam_learns_ham(monkeypatch):
    message = make_message(folder=MESSAGE_FOLDER.SPAM, raw_source_filename=None)
    manager = make_manager(message)
    result = await manager.restore_message(USER, "id")
    assert result["folder"] == MESSAGE_FOLDER.INBOX


@pytest.mark.anyio
async def test_permanently_delete_rejects_non_purgeable():
    message = make_message(folder=MESSAGE_FOLDER.INBOX)
    manager = make_manager(message)
    with pytest.raises(HTTPException) as error:
        await manager.permanently_delete_message(USER, "id")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_permanently_delete_removes_message(monkeypatch):
    message = make_message(folder=MESSAGE_FOLDER.TRASH, raw_source_filename="raw.eml")
    engine = RecordingEngine()
    manager = make_manager(message, engine=engine)
    attachments = FakeAttachments()
    patch_attachments(monkeypatch, attachments)
    result = await manager.permanently_delete_message(USER, "id")
    assert result == {"message": "Message and attachments deleted permanently"}
    assert message in engine.deleted


@pytest.mark.anyio
async def test_delete_message_moves_to_trash():
    message = make_message(folder=MESSAGE_FOLDER.INBOX)
    manager = make_manager(message)
    result = await manager.delete_message(USER, "id")
    assert result == {"message": "Message moved to Trash"}
    assert message.folder == MESSAGE_FOLDER.TRASH


@pytest.mark.anyio
async def test_translate_message_returns_translation(monkeypatch):
    message = make_message()
    manager = make_manager(message)

    class FakeTranslation:
        async def translate_message(self, _subject, _body, _target):
            return {"translated_subject": "Hola", "translated_body": "Mundo"}

    monkeypatch.setattr(translation_manager, "get_instance", staticmethod(lambda: FakeTranslation()))
    result = await manager.translate_message(USER, "id", "es")
    assert result["translated_subject"] == "Hola"
    assert result["message_id"] == str(message.id)


@pytest.mark.anyio
async def test_get_message_source_returns_response(monkeypatch):
    message = make_message(raw_source_filename="raw.eml")
    manager = make_manager(message)
    patch_attachments(monkeypatch, FakeAttachments(raw=b"SOURCE"))
    response = await manager.get_message_source(USER, "id")
    assert isinstance(response, Response)
    assert response.body == b"SOURCE"


@pytest.mark.anyio
async def test_download_message_sets_attachment_disposition(monkeypatch):
    message = make_message(raw_source_filename="raw.eml")
    manager = make_manager(message)
    patch_attachments(monkeypatch, FakeAttachments(raw=b"SOURCE"))
    response = await manager.download_message(USER, "id")
    assert response.headers["Content-Disposition"] == 'attachment; filename="message.eml"'


@pytest.mark.anyio
async def test_bulk_rejects_invalid_message_id():
    manager = make_manager()
    with pytest.raises(HTTPException) as error:
        await manager.bulk_update_messages(USER, ["bad-id"], BULK_MESSAGE_ACTION.STAR)
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_bulk_not_found_when_count_mismatch():
    message = make_message()
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    with pytest.raises(HTTPException) as error:
        await manager.bulk_update_messages(USER, [str(ObjectId()), str(ObjectId())], BULK_MESSAGE_ACTION.STAR)
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_bulk_add_labels_requires_labels():
    message = make_message()
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    with pytest.raises(HTTPException) as error:
        await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.ADD_LABELS, label_ids=[])
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_bulk_add_labels_rejects_invalid_label_id():
    message = make_message()
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    with pytest.raises(HTTPException) as error:
        await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.ADD_LABELS, label_ids=["bad-id"])
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_bulk_add_labels_rejects_unowned():
    message = make_message()
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}, counts={db_label_model: 0}))
    with pytest.raises(HTTPException) as error:
        await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.ADD_LABELS, label_ids=[str(ObjectId())])
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_bulk_archive_rejects_non_inbox():
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    with pytest.raises(HTTPException) as error:
        await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.ARCHIVE)
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_bulk_mark_read_rejects_outgoing():
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    with pytest.raises(HTTPException) as error:
        await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.MARK_READ)
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_bulk_restore_rejects_non_restorable():
    message = make_message(folder=MESSAGE_FOLDER.INBOX)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    with pytest.raises(HTTPException) as error:
        await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.RESTORE)
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_bulk_permanent_delete_rejects_non_purgeable():
    message = make_message(folder=MESSAGE_FOLDER.INBOX)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    with pytest.raises(HTTPException) as error:
        await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.PERMANENT_DELETE)
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_bulk_move_requires_destination():
    message = make_message()
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    with pytest.raises(HTTPException) as error:
        await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.MOVE, destination=None)
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_bulk_move_rejects_disallowed_destination():
    message = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.DRAFTS)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    with pytest.raises(HTTPException) as error:
        await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.MOVE, destination=MESSAGE_FOLDER.INBOX)
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_bulk_star_marks_starred():
    message = make_message(is_starred=False)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    result = await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.STAR)
    assert message.is_starred is True
    assert str(message.id) in result["processed_ids"]


@pytest.mark.anyio
async def test_bulk_permanent_delete_removes(monkeypatch):
    message = make_message(folder=MESSAGE_FOLDER.TRASH, raw_source_filename="raw.eml")
    engine = RecordingEngine(find={db_message_model: [message]})
    manager = make_manager(engine=engine)
    patch_attachments(monkeypatch, FakeAttachments())
    result = await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.PERMANENT_DELETE)
    assert str(message.id) in result["deleted_ids"]
    assert message in engine.deleted


@pytest.mark.anyio
async def test_bulk_add_labels_applies_labels():
    label_id = ObjectId()
    message = make_message()
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}, counts={db_label_model: 1}))
    await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.ADD_LABELS, label_ids=[str(label_id)])
    assert label_id in message.label_ids


@pytest.mark.anyio
async def test_bulk_move_relocates():
    message = make_message(folder=MESSAGE_FOLDER.INBOX)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.MOVE, destination=MESSAGE_FOLDER.ARCHIVE)
    assert message.folder == MESSAGE_FOLDER.ARCHIVE


@pytest.mark.anyio
async def test_bulk_report_spam_moves_to_spam(monkeypatch):
    message = make_message(folder=MESSAGE_FOLDER.INBOX, raw_source_filename=None)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    patch_safety(monkeypatch, FakeSafety())
    await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.REPORT_SPAM)
    assert message.folder == MESSAGE_FOLDER.SPAM


@pytest.mark.anyio
async def test_move_message_from_spam_learns_ham(monkeypatch):
    message = make_message(folder=MESSAGE_FOLDER.SPAM, raw_source_filename=None)
    manager = make_manager(message)
    patch_safety(monkeypatch, FakeSafety())
    result = await manager.move_message(USER, "id", MESSAGE_FOLDER.INBOX)
    assert message.folder == MESSAGE_FOLDER.INBOX
    assert result["folder"] == MESSAGE_FOLDER.INBOX


@pytest.mark.anyio
async def test_search_inbox_scope_filters_folder():
    message = make_message()
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    result = await manager.search_messages(USER, "sender", MESSAGE_SEARCH_SCOPE.INBOX)
    assert result[0]["id"] == str(message.id)


@pytest.mark.anyio
async def test_search_starred_scope():
    message = make_message(is_starred=True)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    result = await manager.search_messages(USER, "sender", MESSAGE_SEARCH_SCOPE.STARRED)
    assert result[0]["is_starred"] is True


@pytest.mark.anyio
async def test_search_important_scope():
    message = make_message(is_important=True)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    result = await manager.search_messages(USER, "sender", MESSAGE_SEARCH_SCOPE.IMPORTANT)
    assert result[0]["is_important"] is True


@pytest.mark.anyio
async def test_bulk_archive_moves_inbox():
    message = make_message(folder=MESSAGE_FOLDER.INBOX)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.ARCHIVE)
    assert message.folder == MESSAGE_FOLDER.ARCHIVE
    assert message.previous_folder == MESSAGE_FOLDER.INBOX


@pytest.mark.anyio
async def test_bulk_restore_from_spam_learns_ham():
    message = make_message(folder=MESSAGE_FOLDER.SPAM, raw_source_filename=None)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.RESTORE)
    assert message.folder == MESSAGE_FOLDER.INBOX


@pytest.mark.anyio
async def test_bulk_trash_relocates():
    message = make_message(folder=MESSAGE_FOLDER.INBOX)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.TRASH)
    assert message.folder == MESSAGE_FOLDER.TRASH


@pytest.mark.anyio
async def test_bulk_restore_restores():
    message = make_message(folder=MESSAGE_FOLDER.TRASH, previous_folder=MESSAGE_FOLDER.ARCHIVE)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.RESTORE)
    assert message.folder == MESSAGE_FOLDER.ARCHIVE


@pytest.mark.anyio
async def test_bulk_mark_read_sets_read():
    message = make_message(is_read=False)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.MARK_READ)
    assert message.is_read is True


@pytest.mark.anyio
async def test_bulk_mark_unread_sets_unread():
    message = make_message(is_read=True)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.MARK_UNREAD)
    assert message.is_read is False


@pytest.mark.anyio
async def test_bulk_unstar_clears_star():
    message = make_message(is_starred=True)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.UNSTAR)
    assert message.is_starred is False


@pytest.mark.anyio
async def test_bulk_mark_important_sets_important():
    message = make_message(is_important=False)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.MARK_IMPORTANT)
    assert message.is_important is True


@pytest.mark.anyio
async def test_bulk_mark_not_important_clears_important():
    message = make_message(is_important=True)
    manager = make_manager(engine=RecordingEngine(find={db_message_model: [message]}))
    await manager.bulk_update_messages(USER, [str(message.id)], BULK_MESSAGE_ACTION.MARK_NOT_IMPORTANT)
    assert message.is_important is False


@pytest.mark.anyio
async def test_dispatch_scheduled_messages_skips_when_owner_missing():
    draft = make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.DRAFTS, scheduled_at=datetime.now(UTC) - timedelta(hours=1))
    engine = RecordingEngine(find={db_message_model: [draft]}, find_one={db_mailbox_model: None})
    manager = object.__new__(message_manager)
    manager._engine = engine
    result = await manager.dispatch_scheduled_messages()
    assert result == {"sent": 0, "failed": 0}
    assert draft.scheduled_at is None


@pytest.mark.anyio
async def test_dispatch_scheduled_messages_sends_due_draft():
    mailbox = default_mailbox()
    draft = make_message(owner_mailbox_id=mailbox.id, direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.DRAFTS, receiver_address="r@example.org", scheduled_at=datetime.now(UTC) - timedelta(hours=1))
    engine = RecordingEngine(find={db_message_model: [draft]}, find_one={db_mailbox_model: mailbox, db_user_model: USER})
    manager = object.__new__(message_manager)
    manager._engine = engine

    async def fake_send(**_kwargs):
        return {}

    manager.send_message = fake_send
    result = await manager.dispatch_scheduled_messages()
    assert result == {"sent": 1, "failed": 0}


@pytest.mark.anyio
async def test_dispatch_scheduled_messages_marks_failure():
    mailbox = default_mailbox()
    draft = make_message(owner_mailbox_id=mailbox.id, direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.DRAFTS, receiver_address="r@example.org", scheduled_at=datetime.now(UTC) - timedelta(hours=1))
    engine = RecordingEngine(find={db_message_model: [draft]}, find_one={db_mailbox_model: mailbox, db_user_model: USER})
    manager = object.__new__(message_manager)
    manager._engine = engine

    async def fake_send(**_kwargs):
        raise RuntimeError("boom")

    manager.send_message = fake_send
    result = await manager.dispatch_scheduled_messages()
    assert result == {"sent": 0, "failed": 1}
    assert draft.scheduled_at is None
