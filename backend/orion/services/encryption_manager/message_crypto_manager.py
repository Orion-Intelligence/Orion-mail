import base64

from orion.services.encryption_manager.encryption_manager import encryption_manager
from orion.services.encryption_manager.key_manager import key_manager
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import db_message_model

ENCRYPTED_FIELDS = ("subject", "body", "body_html")


class message_crypto_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if message_crypto_manager.__instance is None:
            message_crypto_manager()
        return message_crypto_manager.__instance

    def __init__(self):
        if message_crypto_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        message_crypto_manager.__instance = self
        self._engine = mongo_controller.get_instance().get_engine()
        self._owner_cache: dict[str, str] = {}

    async def owner_auth_id(self, owner_mailbox_id) -> str | None:
        cached = self._owner_cache.get(str(owner_mailbox_id))
        if cached:
            return cached

        mailbox = await self._engine.find_one(db_mailbox_model, db_mailbox_model.id == owner_mailbox_id)
        if mailbox is None:
            return None

        auth_id = str(mailbox.user_id)
        self._owner_cache[str(owner_mailbox_id)] = auth_id
        return auth_id

    async def encrypt_message(self, message: db_message_model) -> db_message_model:
        if message.is_encrypted:
            return message

        auth_id = await self.owner_auth_id(message.owner_mailbox_id)
        if auth_id is None:
            return message

        record = await key_manager.get_instance().get_or_create_user_keys(auth_id)
        content_key = key_manager.generate_data_key()
        cipher = encryption_manager.create(content_key)

        for field_name in ENCRYPTED_FIELDS:
            value = getattr(message, field_name)
            if value:
                setattr(message, field_name, cipher.encrypt(value))

        message.sealed_key = base64.b64encode(key_manager.seal_data_key(record.public_key, content_key)).decode()
        message.is_encrypted = True
        return message

    async def decrypt_message(self, message: db_message_model) -> db_message_model:
        if not message.is_encrypted or not message.sealed_key:
            return message

        auth_id = await self.owner_auth_id(message.owner_mailbox_id)
        if auth_id is None:
            return message

        content_key = await key_manager.get_instance().unseal_data_key(auth_id, base64.b64decode(message.sealed_key))
        if content_key is None:
            return message

        cipher = encryption_manager.create(content_key)

        for field_name in ENCRYPTED_FIELDS:
            value = getattr(message, field_name)
            if value:
                setattr(message, field_name, cipher.decrypt(value))

        message.is_encrypted = False
        return message

    async def save_message(self, message: db_message_model) -> db_message_model:
        was_plaintext = not message.is_encrypted
        await self.encrypt_message(message)
        saved = await self._engine.save(message)
        if was_plaintext:
            await self.decrypt_message(saved)
        return saved

    async def decrypt_messages(self, messages: list[db_message_model]) -> list[db_message_model]:
        for message in messages:
            await self.decrypt_message(message)
        return messages

    async def content_cipher(self, message: db_message_model) -> encryption_manager | None:
        auth_id = await self.owner_auth_id(message.owner_mailbox_id)
        if auth_id is None:
            return None
        return encryption_manager.create(await key_manager.get_instance().get_data_key(auth_id))
