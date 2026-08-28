import asyncio
import struct

from fastapi import HTTPException, status

from orion.constants.constant import CONSTANTS
from orion.services.log_manager.log_controller import log


class antivirus_manager:
    __instance = None
    CHUNK_SIZE = 65536

    @staticmethod
    def get_instance():
        if antivirus_manager.__instance is None:
            antivirus_manager()
        return antivirus_manager.__instance

    def __init__(self):
        if antivirus_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        antivirus_manager.__instance = self

    async def _scan(self, content: bytes) -> str:
        reader, writer = await asyncio.open_connection(CONSTANTS.S_CLAMAV_HOST, CONSTANTS.S_CLAMAV_PORT)
        try:
            writer.write(b"zINSTREAM\0")
            for offset in range(0, len(content), self.CHUNK_SIZE):
                chunk = content[offset:offset + self.CHUNK_SIZE]
                writer.write(struct.pack("!L", len(chunk)) + chunk)
            writer.write(struct.pack("!L", 0))
            await writer.drain()
            return (await reader.readuntil(b"\0")).decode(errors="replace").strip("\0 \n")
        finally:
            writer.close()
            await writer.wait_closed()

    async def assert_clean(self, content: bytes, _filename: str) -> None:
        try:
            response = await asyncio.wait_for(self._scan(content), timeout=CONSTANTS.S_CLAMAV_TIMEOUT_SECONDS)
        except Exception as error:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Attachment could not be virus scanned") from error

        if response.endswith("FOUND"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment was rejected because it contains malware")

        if not response.endswith("OK"):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Attachment could not be virus scanned")
