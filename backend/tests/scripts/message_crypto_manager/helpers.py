from __future__ import annotations

from bson import ObjectId

from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model
from tests.model.fakes import build_encryption_stack

PLAIN_SUBJECT = "Quarterly report"
PLAIN_BODY = "The figures are attached. Treat as confidential."
PLAIN_HTML = "<p>The figures are attached.</p>"


def build_stack():
    mailbox = db_mailbox_model(user_id=ObjectId(), mailbox_address="admin@mail.orionintelligence.org")
    crypto, engine = build_encryption_stack(mailbox=mailbox)
    return crypto, engine, mailbox


def build_message(mailbox):
    return db_message_model(owner_mailbox_id=mailbox.id, sender_address="a@mail.orionintelligence.org", receiver_address="b@mail.orionintelligence.org", subject=PLAIN_SUBJECT, body=PLAIN_BODY, body_html=PLAIN_HTML, direction=MESSAGE_DIRECTION.INCOMING, folder=MESSAGE_FOLDER.INBOX)
