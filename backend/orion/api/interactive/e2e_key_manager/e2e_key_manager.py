import base64
import contextlib
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from odmantic.exceptions import DuplicateKeyError
from odmantic.query import and_, eq, in_

from orion.api.interactive.e2e_key_manager.e2e_key_enums import E2E_ARMOR, E2E_KEY_LIMITS, E2E_UNLOCK_KIND
from orion.api.interactive.e2e_key_manager.models.e2e_key_param_model import E2eKeyBundleRequest, E2eKeyUnlockRequest
from orion.services.encryption_manager.key_manager import key_manager
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_pgp_key_model import PGP_KEY_STATUS, PGP_KEY_TYPE, db_pgp_key_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model
from orion.services.orion_identity_manager.orion_identity_client import orion_identity_client
from orion.services.pgp_manager.pgp_manager import pgp_manager


class e2e_key_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if e2e_key_manager.__instance is None:
            e2e_key_manager()
        return e2e_key_manager.__instance

    def __init__(self):
        if e2e_key_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        e2e_key_manager.__instance = self
        self._engine = mongo_controller.get_instance().get_engine()

    @staticmethod
    def is_e2e_body(body: str) -> bool:
        return body.startswith(E2E_ARMOR.MESSAGE_HEADER) and E2E_ARMOR.MESSAGE_MARKER in body and body.rstrip().endswith(E2E_ARMOR.MESSAGE_FOOTER)

    async def get_owner_mailbox(self, current_user: db_user_model) -> db_mailbox_model:
        mailbox = await self._engine.find_one(db_mailbox_model, and_(eq(db_mailbox_model.user_id, current_user.id), eq(db_mailbox_model.is_active, True)))
        if mailbox is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
        return mailbox

    async def get_mailbox_key(self, mailbox: db_mailbox_model) -> db_pgp_key_model | None:
        return await self._engine.find_one(db_pgp_key_model, and_(eq(db_pgp_key_model.owner_mailbox_id, mailbox.id), eq(db_pgp_key_model.key_type, PGP_KEY_TYPE.E2E)))

    @staticmethod
    def serialize_state(mailbox: db_mailbox_model, key: db_pgp_key_model | None) -> dict:
        if key is None:
            return {"configured": False, "mailbox_address": mailbox.mailbox_address}
        return {"configured": True, "mailbox_address": mailbox.mailbox_address, "fingerprint": key.fingerprint, "public_key": key.public_key, "kdf_salt": key.kdf_salt, "created_at": key.created_at, "updated_at": key.updated_at}

    @staticmethod
    async def assert_valid_bundle(bundle: E2eKeyBundleRequest, fingerprint: str) -> None:
        if not bundle.public_key.lstrip().startswith(E2E_ARMOR.PUBLIC_KEY_HEADER):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Public key is not an armored PGP public key")

        private_keys = [private_key for private_key in (bundle.locked_private_key, bundle.recovery_private_key) if private_key is not None]
        for private_key in private_keys:
            if not private_key.lstrip().startswith(E2E_ARMOR.PRIVATE_KEY_HEADER):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Private key is not an armored PGP private key")

        for armored_key in (bundle.public_key, *private_keys):
            if await pgp_manager.get_instance().key_fingerprint(armored_key) != fingerprint:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Key material does not match the fingerprint")

        for private_key in private_keys:
            if not await pgp_manager.get_instance().private_key_is_locked(private_key):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Private key must be locked with a passphrase before upload")

    @staticmethod
    def assert_not_blocked(key: db_pgp_key_model) -> None:
        blocked_until = key.unlock_blocked_until
        if blocked_until is not None and blocked_until.replace(tzinfo=UTC) > datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Too many wrong attempts. Try again in {E2E_KEY_LIMITS.UNLOCK_BLOCK_MINUTES} minutes.")

    async def record_attempt(self, key: db_pgp_key_model, succeeded: bool) -> None:
        if succeeded and not key.failed_unlocks and key.unlock_blocked_until is None:
            return
        key.failed_unlocks = 0 if succeeded else key.failed_unlocks + 1
        key.unlock_blocked_until = None
        if key.failed_unlocks >= E2E_KEY_LIMITS.MAX_FAILED_UNLOCKS:
            key.failed_unlocks = 0
            key.unlock_blocked_until = datetime.now(UTC) + timedelta(minutes=E2E_KEY_LIMITS.UNLOCK_BLOCK_MINUTES)
        await self._engine.save(key)

    async def check_verifier(self, key: db_pgp_key_model, verifier: str, kinds: tuple[E2E_UNLOCK_KIND, ...]) -> E2E_UNLOCK_KIND:
        self.assert_not_blocked(key)
        stored = {E2E_UNLOCK_KIND.PASSPHRASE: key.verifier_hash, E2E_UNLOCK_KIND.RECOVERY: key.recovery_verifier_hash}
        matched = next((kind for kind in kinds if key_manager.secret_matches(verifier, stored[kind])), None)
        await self.record_attempt(key, matched is not None)
        if matched is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="That passphrase or recovery code is not correct")
        return matched

    async def get_key_state(self, current_user: db_user_model) -> dict:
        mailbox = await self.get_owner_mailbox(current_user)
        return self.serialize_state(mailbox, await self.get_mailbox_key(mailbox))

    async def unlock_key(self, current_user: db_user_model, request: E2eKeyUnlockRequest) -> dict:
        mailbox = await self.get_owner_mailbox(current_user)
        key = await self.get_mailbox_key(mailbox)
        if key is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="End-to-end key not found")

        kind = await self.check_verifier(key, request.verifier, (request.kind,))
        return {**self.serialize_state(mailbox, key), "kind": kind, "private_key": key.recovery_private_key if kind == E2E_UNLOCK_KIND.RECOVERY else key.wrapped_private_key}

    async def save_key_bundle(self, current_user: db_user_model, bundle: E2eKeyBundleRequest, session_token: str | None = None) -> dict:
        mailbox = await self.get_owner_mailbox(current_user)
        fingerprint = bundle.fingerprint.upper()
        key = await self.get_mailbox_key(mailbox)

        if key is not None and key.fingerprint != fingerprint:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An end-to-end key already exists for this mailbox")
        if (bundle.recovery_private_key is None) != (bundle.recovery_verifier is None) or (key is None and bundle.recovery_verifier is None):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A recovery copy of the key is required")
        if key is not None:
            if not bundle.proof:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your current passphrase or recovery code is required")
            await self.check_verifier(key, bundle.proof, (E2E_UNLOCK_KIND.PASSPHRASE, E2E_UNLOCK_KIND.RECOVERY))
            if bundle.recovery_verifier is None and bundle.kdf_salt != key.kdf_salt:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The key salt cannot change without a new recovery copy")

        await self.assert_valid_bundle(bundle, fingerprint)

        if session_token:
            await orion_identity_client.get_instance().set_mail_passphrase(session_token, bundle.verifier)
        if key is None:
            key = db_pgp_key_model(user_id=current_user.id, owner_mailbox_id=mailbox.id, key_type=PGP_KEY_TYPE.E2E, status=PGP_KEY_STATUS.ACTIVE, fingerprint=fingerprint, public_key=bundle.public_key, wrapped_private_key=bundle.locked_private_key)

        key.public_key = bundle.public_key
        key.wrapped_private_key = bundle.locked_private_key
        key.kdf_salt = bundle.kdf_salt
        key.verifier_hash = key_manager.hash_secret(bundle.verifier)
        if bundle.recovery_private_key is not None and bundle.recovery_verifier is not None:
            key.recovery_private_key = bundle.recovery_private_key
            key.recovery_verifier_hash = key_manager.hash_secret(bundle.recovery_verifier)
        key.failed_unlocks = 0
        key.unlock_blocked_until = None
        key.updated_at = datetime.now(UTC)

        try:
            key = await self._engine.save(key)
        except DuplicateKeyError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This key is already registered") from error
        return self.serialize_state(mailbox, key)

    async def delete_key_bundle(self, current_user: db_user_model, session_token: str | None = None) -> dict:
        mailbox = await self.get_owner_mailbox(current_user)
        key = await self.get_mailbox_key(mailbox)
        if key is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="End-to-end key not found")
        await self._engine.delete(key)
        if session_token:
            with contextlib.suppress(HTTPException):
                await orion_identity_client.get_instance().set_mail_passphrase(session_token, None)
        return {"message": "End-to-end key removed"}

    @staticmethod
    def session_binding(session_id: str) -> str:
        return hashlib.sha256(session_id.encode("utf-8")).hexdigest()

    async def tab_secret(self, current_user: db_user_model, session_id: str | None) -> dict:
        key = await self.get_mailbox_key(await self.get_owner_mailbox(current_user))
        if key is None or not session_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="End-to-end key not found")

        now = datetime.now(UTC)
        binding = self.session_binding(session_id)
        expires_at = key.tab_secret_expires_at
        if key.tab_secret and key.tab_secret_binding == binding and expires_at is not None and expires_at.replace(tzinfo=UTC) > now:
            return {"secret": key_manager.get_instance().unwrap(key.tab_secret)}

        secret = base64.b64encode(secrets.token_bytes(32)).decode()
        key.tab_secret = key_manager.get_instance().wrap(secret)
        key.tab_secret_binding = binding
        key.tab_secret_expires_at = now + timedelta(hours=E2E_KEY_LIMITS.TAB_SECRET_HOURS)
        await self._engine.save(key)
        return {"secret": secret}

    async def lookup_public_keys(self, addresses: list[str]) -> dict:
        normalized = list(dict.fromkeys(address.strip().lower() for address in addresses if address.strip()))
        if not normalized:
            return {"keys": []}

        mailboxes = await self._engine.find(db_mailbox_model, and_(in_(db_mailbox_model.mailbox_address, normalized), eq(db_mailbox_model.is_active, True)))
        address_by_mailbox = {mailbox.id: mailbox.mailbox_address for mailbox in mailboxes}
        if not address_by_mailbox:
            return {"keys": []}

        keys = await self._engine.find(db_pgp_key_model, and_(in_(db_pgp_key_model.owner_mailbox_id, list(address_by_mailbox)), eq(db_pgp_key_model.key_type, PGP_KEY_TYPE.E2E)))
        return {"keys": [{"address": address_by_mailbox[key.owner_mailbox_id], "fingerprint": key.fingerprint, "public_key": key.public_key} for key in keys]}
