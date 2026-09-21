from __future__ import annotations

from odmantic import ObjectId

from orion.services.mongo_manager.shared_model.db_messenger_message_model import db_messenger_message_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model

E2E_BODY = "-----BEGIN PGP MESSAGE-----\nComment: Orion Mail E2E v1\n\nwcBMA\n-----END PGP MESSAGE-----"
LEGACY_BODY = "-----BEGIN PGP MESSAGE-----\n\nwcBMA\n-----END PGP MESSAGE-----"
SENDER = db_user_model(full_name="Test One", email="test1@orionintelligence.org", username="test1")
RECEIVER = db_user_model(full_name="Test Two", email="test2@orionintelligence.org", username="test2")
OUTSIDER = db_user_model(full_name="Test Three", email="test3@orionintelligence.org", username="test3")


def make_message(body: str) -> db_messenger_message_model:
    return db_messenger_message_model(conversation_id=ObjectId(), sender_user_id=SENDER.id, receiver_user_id=RECEIVER.id, sender_mailbox_id=ObjectId(), receiver_mailbox_id=ObjectId(), encrypted_for_sender=body, encrypted_for_receiver=body, sender_key_fingerprint="A" * 40, receiver_key_fingerprint="B" * 40)
