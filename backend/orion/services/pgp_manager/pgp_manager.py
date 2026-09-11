import asyncio
import contextlib
import shutil
import tempfile
from pathlib import Path

from fastapi import HTTPException, status

from orion.constants.constant import CONSTANTS
from orion.services.encryption_manager.key_manager import key_manager


class pgp_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if pgp_manager.__instance is None:
            pgp_manager()
        return pgp_manager.__instance

    def __init__(self):
        if pgp_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        pgp_manager.__instance = self

    @staticmethod
    @contextlib.contextmanager
    def _workspace(prefix: str):
        temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
        try:
            yield temp_dir
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def _run_gpg(self, args: list[str], input_data: bytes | None = None) -> bytes:
        process = await asyncio.create_subprocess_exec(  # nosec - no shell; static "gpg" binary with a fixed argument list  # nosemgrep
            "gpg",
            *args,
            stdin=asyncio.subprocess.PIPE if input_data is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate(input_data)
        if process.returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PGP operation failed",
            )
        return stdout

    async def generate_key_pair(self) -> tuple[str, str, str]:
        with self._workspace("orion-pgp-") as temp_dir:
            batch = f"""
Key-Type: RSA
Key-Length: {CONSTANTS.S_PGP_KEY_BITS}
Name-Real: Orion Mail Identity
Expire-Date: 0
%no-protection
%commit
""".strip().encode()

            await self._run_gpg(["--homedir", str(temp_dir), "--batch", "--generate-key"], batch)

            keys = await self._run_gpg(["--homedir", str(temp_dir), "--batch", "--with-colons", "--list-secret-keys"])
            fingerprint = ""

            for line in keys.decode().splitlines():
                parts = line.split(":")
                if parts[0] == "fpr":
                    fingerprint = parts[9]
                    break

            if not fingerprint:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="PGP key generation failed",
                )

            public_key = await self._run_gpg(["--homedir", str(temp_dir), "--armor", "--export", fingerprint])
            private_key = await self._run_gpg(["--homedir", str(temp_dir), "--armor", "--export-secret-keys", fingerprint])

            return public_key.decode(), private_key.decode(), fingerprint

    async def sign_bytes(self, raw_data: bytes, wrapped_private_key: str) -> str:
        with self._workspace("orion-sign-") as temp_dir:
            data_path = temp_dir / "message.txt"
            sig_path = temp_dir / "signature.asc"

            private_key = key_manager.get_instance().unwrap(wrapped_private_key)
            await self._run_gpg(["--homedir", str(temp_dir), "--batch", "--import"], private_key.encode())

            data_path.write_bytes(raw_data)

            await self._run_gpg([
                "--homedir", str(temp_dir),
                "--batch",
                "--yes",
                "--armor",
                "--detach-sign",
                "--digest-algo", "SHA256",
                "--output", str(sig_path),
                str(data_path),
            ])

            return sig_path.read_text()
