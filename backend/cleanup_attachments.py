import asyncio

from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.management.managers.service_manager import service_manager
from orion.services.log_manager.log_controller import log


async def main() -> None:
    await service_manager.get_instance().init_services()
    try:
        log.g().i(f"attachment cleanup: {await attachment_manager.get_instance().cleanup_expired_attachments()}")
    finally:
        await service_manager.get_instance().close_services()


if __name__ == "__main__":
    asyncio.run(main())
