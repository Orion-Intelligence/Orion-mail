from __future__ import annotations

from io import BytesIO

from bson import ObjectId
from fastapi import UploadFile
from starlette.datastructures import Headers

from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.api.server.config_manager.config_controller import config_controller
from orion.services.antivirus_manager.antivirus_manager import antivirus_manager
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model
from tests.model.fakes import build_encryption_stack
from tests.scripts.attachment_manager.fakes import FakeAntivirusManager, FakeConfigController

RAW_EML = b"From: a@mail.orionintelligence.org\r\nSubject: Secret\r\n\r\nConfidential body\r\n"
ONE_MB = 1024 * 1024


def build_stack():
    mailbox = db_mailbox_model(user_id=ObjectId(), mailbox_address="admin@mail.orionintelligence.org")
    message = db_message_model(owner_mailbox_id=mailbox.id, sender_address="a@x.org", receiver_address="b@x.org", subject="s", body="b", direction=MESSAGE_DIRECTION.INCOMING, folder=MESSAGE_FOLDER.INBOX)
    _crypto, engine = build_encryption_stack(mailbox=mailbox, message=message)

    manager = object.__new__(attachment_manager)
    manager._engine = engine
    return manager, engine, mailbox, message


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
