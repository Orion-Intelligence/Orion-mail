import asyncio

from orion.management.managers.cronjob_manager import cronjob_manager
from orion.management.managers.service_manager import service_manager


async def main() -> None:
    await service_manager.get_instance().init_services()
    await cronjob_manager.get_instance().init_jobs()
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
