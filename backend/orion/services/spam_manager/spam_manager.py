import httpx

from orion.constants.constant import CONSTANTS
from orion.services.log_manager.log_controller import log


class spam_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if spam_manager.__instance is None:
            spam_manager()
        return spam_manager.__instance

    def __init__(self):
        if spam_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        spam_manager.__instance = self

    async def _learn(self, path: str, raw_source: bytes) -> bool:
        if not raw_source or not CONSTANTS.S_RSPAMD_CONTROLLER_URL or not CONSTANTS.S_RSPAMD_CONTROLLER_PASSWORD:
            return False

        try:
            async with httpx.AsyncClient(timeout=CONSTANTS.S_RSPAMD_TIMEOUT_SECONDS, trust_env=False) as client:
                response = await client.post(f"{CONSTANTS.S_RSPAMD_CONTROLLER_URL}{path}", content=raw_source, headers={"Password": CONSTANTS.S_RSPAMD_CONTROLLER_PASSWORD, "Content-Type": "message/rfc822"})
        except httpx.RequestError as error:
            log.g().e(f"rspamd learning request failed: {log.safe_error(error)}")
            return False

        if response.status_code >= 400:
            log.g().i(f"rspamd declined the learning request with status {response.status_code}")
            return False

        return True

    async def learn_spam(self, raw_source: bytes) -> bool:
        return await self._learn("/learnspam", raw_source)

    async def learn_ham(self, raw_source: bytes) -> bool:
        return await self._learn("/learnham", raw_source)
