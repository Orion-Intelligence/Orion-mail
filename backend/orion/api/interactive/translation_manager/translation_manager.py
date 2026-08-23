import asyncio
import json
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
from fastapi import HTTPException, status

from orion.constants.constant import CONSTANTS


SUPPORTED_LANGUAGES = {
    "ar": "Arabic",
    "de": "German",
    "en": "English",
    "es": "Spanish",
    "fa": "Persian",
    "fr": "French",
    "hi": "Hindi",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "nl": "Dutch",
    "pl": "Polish",
    "pt": "Portuguese",
    "ru": "Russian",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "vi": "Vietnamese",
    "zh-CN": "Chinese (Simplified)",
}


class translation_manager:
    __instance = None
    _chunk_size = 3500
    _max_parallel_requests = 4
    _max_response_bytes = 2 * 1024 * 1024

    @staticmethod
    def get_instance():
        if translation_manager.__instance is None:
            translation_manager()
        return translation_manager.__instance

    def __init__(self):
        if translation_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        translation_manager.__instance = self
        self._request_semaphore = asyncio.Semaphore(self._max_parallel_requests)

    @classmethod
    def split_text(cls, text: str) -> list[str]:
        if not text:
            return []

        chunks: list[str] = []
        remaining = text
        while remaining:
            if len(remaining) <= cls._chunk_size:
                chunks.append(remaining)
                break

            split_at = remaining.rfind("\n", 0, cls._chunk_size + 1)
            if split_at < cls._chunk_size // 2:
                split_at = remaining.rfind(" ", 0, cls._chunk_size + 1)
            if split_at < cls._chunk_size // 2:
                split_at = cls._chunk_size
            else:
                split_at += 1
            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:]
        return chunks

    @staticmethod
    def _translation_url(target_language: str) -> str:
        configured_url = CONSTANTS.S_TRANSLATION_API_URL
        parsed = urlsplit(configured_url)
        if (
            parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Translation service is not configured")
        query = urlencode({"client": "gtx", "sl": "auto", "tl": target_language, "dt": "t"})
        return urlunsplit(("https", parsed.netloc, parsed.path, query, ""))

    @staticmethod
    def _translate_chunk_sync(text: str, target_language: str) -> tuple[str, str | None]:
        url = translation_manager._translation_url(target_language)
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "User-Agent": "Orion-Mail/1.0"}
        try:
            with httpx.Client(timeout=CONSTANTS.S_TRANSLATION_TIMEOUT_SECONDS, trust_env=False) as client:
                with client.stream("POST", url, content=urlencode({"q": text}).encode("utf-8"), headers=headers) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) >= translation_manager._max_response_bytes:
                            break
            payload = json.loads(bytes(body[: translation_manager._max_response_bytes]).decode("utf-8"))
        except (httpx.HTTPError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Translation service is unavailable") from error

        try:
            translated = "".join(segment[0] or "" for segment in payload[0])
            detected_language = payload[2] if isinstance(payload[2], str) else None
        except (IndexError, TypeError) as error:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Translation service returned an invalid response") from error
        return translated, detected_language

    async def translate_text(self, text: str, target_language: str) -> tuple[str, str | None]:
        chunks = self.split_text(text)
        if not chunks:
            return "", None

        async def translate_chunk(chunk: str) -> tuple[str, str | None]:
            async with self._request_semaphore:
                return await asyncio.to_thread(self._translate_chunk_sync, chunk, target_language)

        translated_chunks = await asyncio.gather(*(translate_chunk(chunk) for chunk in chunks))
        detected_language = next((language for _, language in translated_chunks if language), None)
        return "".join(translation for translation, _ in translated_chunks), detected_language

    async def translate_message(self, subject: str, body: str, target_language: str) -> dict:
        normalized_target = next((code for code in SUPPORTED_LANGUAGES if code.lower() == target_language.lower()), None)
        if normalized_target is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported translation language")

        translated_subject, translated_body = await asyncio.gather(
            self.translate_text(subject, normalized_target),
            self.translate_text(body, normalized_target),
        )
        detected_language = translated_body[1] or translated_subject[1]
        return {
            "translated_subject": translated_subject[0],
            "translated_body": translated_body[0],
            "source_language": detected_language,
            "target_language": normalized_target,
            "target_language_name": SUPPORTED_LANGUAGES[normalized_target],
        }
