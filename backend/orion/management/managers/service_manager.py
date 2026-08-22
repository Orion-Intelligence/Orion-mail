from orion.api.interactive.mailbox_manager.mailbox_manager import mailbox_manager
from orion.api.server.config_manager.config_controller import config_controller
from orion.constants.constant import CONSTANTS
from orion.services.log_manager.log_controller import log
from orion.services.mongo_manager.mongo_controller import mongo_controller


class service_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if service_manager.__instance is None:
            service_manager()
        return service_manager.__instance

    def __init__(self):
        if service_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        service_manager.__instance = self

    @staticmethod
    def validate_configuration() -> None:
        if len(CONSTANTS.S_ORION_MAIL_SSO_CLIENT_SECRET) < 32:
            raise RuntimeError(
                "ORION_MAIL_SSO_CLIENT_SECRET must be at least 32 characters"
            )
        if not CONSTANTS.S_ENCRYPTION_KEY:
            raise RuntimeError(
                "ENCRYPTION_KEY must be set to a Fernet key"
            )
        if not CONSTANTS.S_INCOMING_MAIL_TOKEN:
            log.g().e("INCOMING_MAIL_TOKEN is not set; the Postfix ingest endpoint will reject all mail")

    async def init_services(self) -> None:
        self.validate_configuration()
        await mongo_controller.get_instance().link_connection()
        await mongo_controller.get_instance().ensure_indexes()
        await config_controller.get_instance().initialize()
        if CONSTANTS.S_SEED_LOCAL_TEST_MAILBOXES:
            created_count = await mailbox_manager.get_instance().seed_local_test_mailboxes()
            if created_count:
                log.g().i(f"Created {created_count} local test mailboxes")

    @staticmethod
    async def close_services() -> None:
        await mongo_controller.get_instance().close_connection()
