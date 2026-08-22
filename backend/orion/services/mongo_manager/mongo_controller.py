import motor.motor_asyncio
from odmantic import AIOEngine

from orion.services.mongo_manager.mongo_enums import MONGO_CONNECTIONS
from orion.services.mongo_manager.shared_model.db_address_book_entry_model import db_address_book_entry_model
from orion.services.mongo_manager.shared_model.db_attachment_model import db_attachment_model
from orion.services.mongo_manager.shared_model.db_domain_safety_model import db_domain_report_model, db_domain_reputation_model, db_sender_block_model
from orion.services.mongo_manager.shared_model.db_label_model import db_label_model
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import db_message_model
from orion.services.mongo_manager.shared_model.db_system_config_model import db_system_config_model
from orion.services.mongo_manager.shared_model.db_user_key_model import db_user_key_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


class mongo_controller:
    __instance = None

    @staticmethod
    def get_instance():
        if mongo_controller.__instance is None:
            mongo_controller()
        return mongo_controller.__instance

    def __init__(self):
        if mongo_controller.__instance is not None:
            raise Exception("This class is a singleton!")
        mongo_controller.__instance = self
        self.__client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_CONNECTIONS.S_MONGO_URL)
        self.__engine = AIOEngine(client=self.__client, database=MONGO_CONNECTIONS.S_MONGO_DATABASE_NAME)

    def get_engine(self) -> AIOEngine:
        return self.__engine

    async def link_connection(self) -> None:
        await self.__client.admin.command("ping")

    async def ensure_indexes(self) -> None:
        user_collection = self.__engine.get_collection(db_user_model)
        await user_collection.update_many({"password_hash": {"$exists": True}}, {"$unset": {"password_hash": ""}})  # nosec B105
        await user_collection.create_index("email", unique=True)
        await user_collection.create_index("orion_user_id", unique=True, sparse=True)
        await self.__engine.get_collection(db_user_key_model).create_index("auth_id", unique=True)
        await self.__engine.get_collection(db_mailbox_model).create_index("mailbox_address", unique=True)
        await self.__engine.get_collection(db_mailbox_model).create_index("user_id", unique=True)
        await self.__engine.get_collection(db_address_book_entry_model).create_index([("owner_mailbox_id", 1), ("email_address", 1)], unique=True)
        await self.__engine.get_collection(db_address_book_entry_model).create_index([("owner_mailbox_id", 1), ("last_used_at", -1)])
        await self.__engine.get_collection(db_system_config_model).create_index("key", unique=True)
        await self.__engine.get_collection(db_label_model).create_index([("user_id", 1), ("normalized_name", 1)], unique=True)
        await self.__engine.get_collection(db_domain_report_model).create_index([("reporter_user_id", 1), ("sender_domain", 1)], unique=True)
        await self.__engine.get_collection(db_domain_report_model).create_index([("sender_domain", 1), ("report_type", 1)])
        await self.__engine.get_collection(db_domain_reputation_model).create_index("sender_domain", unique=True)
        await self.__engine.get_collection(db_sender_block_model).create_index([("user_id", 1), ("sender_domain", 1)], unique=True)
        await self.__engine.get_collection(db_sender_block_model).create_index("sender_domain")
        await self.__engine.get_collection(db_message_model).create_index([("owner_mailbox_id", 1), ("folder", 1), ("created_at", -1)])
        await self.__engine.get_collection(db_message_model).create_index([("owner_mailbox_id", 1), ("label_ids", 1), ("created_at", -1)])
        await self.__engine.get_collection(db_message_model).create_index([("owner_mailbox_id", 1), ("message_id_header", 1)], sparse=True)
        await self.__engine.get_collection(db_message_model).create_index([("owner_mailbox_id", 1), ("thread_id", 1), ("created_at", 1)], sparse=True)
        await self.__engine.get_collection(db_attachment_model).create_index("message_id")
        await self.__engine.get_collection(db_attachment_model).create_index([("status", 1), ("expires_at", 1)])

    async def close_connection(self) -> None:
        self.__client.close()
