from __future__ import annotations

from urllib.parse import quote

import httpx

from fastapi import HTTPException, status


class gofile_client:
    UPLOAD_URL = "https://upload.gofile.io/uploadfile"
    DELETE_URL = "https://api.gofile.io/contents"

    TIMEOUT = httpx.Timeout(
        connect=20.0,
        read=300.0,
        write=300.0,
        pool=20.0,
    )

    @staticmethod
    def _server_hostname(server: str) -> str:
        server = server.strip()

        if server.startswith("https://"):
            return server.removeprefix("https://").rstrip("/")

        if server.endswith(".gofile.io"):
            return server

        return f"{server}.gofile.io"

    @classmethod
    async def upload(cls, content: bytes, filename: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=cls.TIMEOUT) as client:

                response = await client.post(cls.UPLOAD_URL,
                    files={
                        "file": (
                            filename,
                            content,
                            "application/octet-stream",
                        )
                    },
                )

            response.raise_for_status()

            payload = response.json()

        except (httpx.HTTPError, ValueError) as error:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="External file storage upload failed") from error

        if payload.get("status") != "ok":
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="External file storage rejected the upload")

        data = payload.get("data") or {}

        content_id = data.get("id")
        parent_folder = data.get("parentFolder")
        download_page = data.get("downloadPage")
        guest_token = data.get("guestToken")
        provider_name = data.get("name") or filename
        servers = data.get("servers") or []

        if (
            not content_id
            or not parent_folder
            or not download_page
            or not guest_token
            or not servers
        ):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="External file storage returned incomplete upload information")

        hostname = cls._server_hostname(str(servers[0]))

        encoded_id = quote(str(content_id), safe="")
        encoded_name = quote(str(provider_name), safe="")

        direct_url = (
            f"https://{hostname}/download/web/"
            f"{encoded_id}/{encoded_name}"
        )

        return {
            "content_id": str(content_id),
            "parent_folder": str(parent_folder),
            "download_page": str(download_page),
            "guest_token": str(guest_token),
            "filename": str(provider_name),
            "direct_url": direct_url,
        }

    @classmethod
    async def download(cls, direct_url: str, guest_token: str, expected_size: int) -> bytes:
        headers = {"Cookie": f"accountToken={guest_token}"}

        try:
            async with httpx.AsyncClient(timeout=cls.TIMEOUT, follow_redirects=True) as client:

                response = await client.get(direct_url, headers=headers)

            response.raise_for_status()

        except httpx.HTTPError as error:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Encrypted file could not be retrieved from storage") from error

        content = response.content

        content_type = response.headers.get(
            "content-type",
            "",
        ).lower()

        if "text/html" in content_type:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="External storage did not return the encrypted file")

        if expected_size > 0 and len(content) != expected_size:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Encrypted file size does not match stored metadata")

        return content

    @classmethod
    async def delete(cls, content_id: str, guest_token: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=cls.TIMEOUT) as client:

                response = await client.request(
                    "DELETE",
                    cls.DELETE_URL,
                    headers={
                        "Authorization": f"Bearer {guest_token}",
                    },
                    json={
                        "contentsId": content_id,
                    },
                )

            if response.status_code >= 500:
                response.raise_for_status()

        except httpx.HTTPError:
            return
