from __future__ import annotations

from orion.api.interactive.e2e_key_manager.e2e_key_manager import e2e_key_manager
from orion.api.interactive.e2e_key_manager.models.e2e_key_param_model import E2eKeyBundleRequest
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_pgp_key_model import PGP_KEY_TYPE, db_pgp_key_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model
from orion.services.orion_identity_manager.orion_identity_client import orion_identity_client
from orion.services.pgp_manager.pgp_manager import pgp_manager
from orion.services.encryption_manager.key_manager import key_manager
from tests.model.fakes import RecordingEngine
from tests.scripts.e2e_key_manager.fakes import FakeIdentityClient, FakeKeyWrapper, FakePgpInspector

USER = db_user_model(full_name="Test One", email="test1@orionintelligence.org", username="test1")
FINGERPRINT = "769657C7AD10E295782948E4CC29AACB6C898196"
OTHER_FINGERPRINT = "A" * 40
PUBLIC_KEY = "-----BEGIN PGP PUBLIC KEY BLOCK-----\n\npublic\n-----END PGP PUBLIC KEY BLOCK-----"
LOCKED_KEY = "-----BEGIN PGP PRIVATE KEY BLOCK-----\n\nlocked\n-----END PGP PRIVATE KEY BLOCK-----"
RECOVERY_KEY = "-----BEGIN PGP PRIVATE KEY BLOCK-----\n\nrecovery\n-----END PGP PRIVATE KEY BLOCK-----"
SALT = "c2FsdHNhbHRzYWx0c2FsdA=="
VERIFIER = "A" * 43 + "="
RECOVERY_VERIFIER = "B" * 43 + "="
WRONG_VERIFIER = "C" * 43 + "="
SESSION_TOKEN = "session-token"


def make_manager(engine):
    manager = object.__new__(e2e_key_manager)
    manager._engine = engine
    return manager


def make_mailbox(address="test1@mail.orionintelligence.org"):
    return db_mailbox_model(user_id=USER.id, mailbox_address=address)


def make_key(mailbox, fingerprint=FINGERPRINT):
    return db_pgp_key_model(user_id=mailbox.user_id, owner_mailbox_id=mailbox.id, key_type=PGP_KEY_TYPE.E2E, fingerprint=fingerprint, public_key=PUBLIC_KEY, wrapped_private_key=LOCKED_KEY, recovery_private_key=RECOVERY_KEY, kdf_salt=SALT, verifier_hash=key_manager.hash_secret(VERIFIER), recovery_verifier_hash=key_manager.hash_secret(RECOVERY_VERIFIER))


def engine_with_key(key_overrides=None):
    mailbox = make_mailbox()
    key = make_key(mailbox)
    for name, value in (key_overrides or {}).items():
        setattr(key, name, value)
    return RecordingEngine(find_one={db_mailbox_model: mailbox, db_pgp_key_model: key}), key


def make_bundle(**overrides):
    values = {"fingerprint": FINGERPRINT.lower(), "public_key": PUBLIC_KEY, "locked_private_key": LOCKED_KEY, "recovery_private_key": RECOVERY_KEY, "kdf_salt": SALT, "verifier": VERIFIER, "recovery_verifier": RECOVERY_VERIFIER}
    return E2eKeyBundleRequest(**{**values, **overrides})


def use_identity_client(monkeypatch, error=None):
    client = FakeIdentityClient(error)
    monkeypatch.setattr(orion_identity_client, "get_instance", staticmethod(lambda: client))
    return client


def use_inspector(monkeypatch, fingerprint=FINGERPRINT, locked=True):
    inspector = FakePgpInspector(fingerprint, locked)
    monkeypatch.setattr(pgp_manager, "get_instance", staticmethod(lambda: inspector))
    return inspector


def use_key_wrapper(monkeypatch):
    monkeypatch.setattr(key_manager, "get_instance", staticmethod(lambda: FakeKeyWrapper()))
