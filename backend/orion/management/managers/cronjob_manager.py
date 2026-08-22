import asyncio

from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.api.interactive.message_manager.message_manager import message_manager
from orion.constants.constant import CONSTANTS
from orion.services.log_manager.log_controller import log


class cronjob_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if cronjob_manager.__instance is None:
            cronjob_manager()
        return cronjob_manager.__instance

    def __init__(self):
        if cronjob_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        cronjob_manager.__instance = self

    @staticmethod
    async def attachment_cleanup_loop() -> None:
        while True:
            try:
                result = await attachment_manager.get_instance().cleanup_expired_attachments()
                log.g().i(f"[cronjobs] attachment cleanup: {result}")
            except Exception as error:
                log.g().e(f"[cronjobs] attachment cleanup failed: {error}")
            await asyncio.sleep(CONSTANTS.S_ATTACHMENT_CLEANUP_INTERVAL_SECONDS)

    @staticmethod
    async def scheduled_delivery_loop() -> None:
        while True:
            try:
                dispatched = await message_manager.get_instance().dispatch_scheduled_messages()
                woken = await message_manager.get_instance().wake_snoozed_messages()
                if dispatched["sent"] or dispatched["failed"] or woken["woken"]:
                    log.g().i(f"[cronjobs] scheduled delivery: {dispatched}, snooze wake: {woken}")
            except Exception as error:
                log.g().e(f"[cronjobs] scheduled delivery failed: {error}")
            await asyncio.sleep(CONSTANTS.S_SCHEDULED_DELIVERY_INTERVAL_SECONDS)

    @staticmethod
    async def init_jobs() -> None:
        asyncio.create_task(cronjob_manager.attachment_cleanup_loop())
        asyncio.create_task(cronjob_manager.scheduled_delivery_loop())
