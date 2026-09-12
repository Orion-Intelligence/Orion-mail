from __future__ import annotations

from bson import ObjectId

from orion.api.interactive.disposable_mailbox_manager.disposable_mailbox_manager import disposable_mailbox_manager
from orion.services.mongo_manager.shared_model.db_disposable_mailbox_model import db_disposable_mailbox_model
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_pgp_key_model import PGP_KEY_STATUS, PGP_KEY_TYPE, db_pgp_key_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model

USER = db_user_model(full_name="Test One", email="test1@orionintelligence.org", username="test1")


def make_manager(engine):
    manager = object.__new__(disposable_mailbox_manager)
    manager._engine = engine
    return manager


def make_mailbox():
    return db_mailbox_model(user_id=USER.id, mailbox_address="test1@mail.orionintelligence.org")


def make_pgp_key(key_type=PGP_KEY_TYPE.DISPOSABLE, status=PGP_KEY_STATUS.ACTIVE, owner_mailbox_id=None):
    return db_pgp_key_model(user_id=USER.id, owner_mailbox_id=owner_mailbox_id or ObjectId(), key_type=key_type, status=status, fingerprint=ObjectId().binary.hex(), public_key="PUB", wrapped_private_key="WRAP")


def make_disposable(pgp_key_id, owner_mailbox_id):
    return db_disposable_mailbox_model(user_id=USER.id, owner_mailbox_id=owner_mailbox_id, mailbox_address="abc@mail.orionintelligence.org", pgp_key_id=pgp_key_id)
