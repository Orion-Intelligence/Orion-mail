from __future__ import annotations

import base64
import time
from urllib.parse import urlsplit

import httpx

from orion.constants.constant import CONSTANTS

_BRAND_CACHE_TTL_SECONDS = 300
_MAX_LOGO_BYTES = 256 * 1024
_brand_cache: dict[str, tuple[float, dict[str, str]]] = {}


def _empty_brand() -> dict[str, str]:
    return {"name": "", "logo_light": "", "logo_dark": "", "favicon": ""}


async def _fetch_logo(client: httpx.AsyncClient, resource_path: str, host: str) -> str:
    path = (resource_path or "").strip()
    if not path.startswith("/"):
        return ""
    try:
        response = await client.get(
            f"{CONSTANTS.S_ORION_INTELLIGENCE_INTERNAL_URL}{path}",
            headers={"Host": host},
        )
    except httpx.RequestError:
        return ""
    if response.status_code >= 400:
        return ""
    content = response.content
    if not content or len(content) > _MAX_LOGO_BYTES:
        return ""
    content_type = (response.headers.get("content-type") or "image/png").split(";")[0].strip()
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


async def get_tenant_brand(orion_origin: str) -> dict[str, str]:
    origin = (orion_origin or "").strip().rstrip("/")
    if not origin:
        return _empty_brand()

    now = time.monotonic()
    cached = _brand_cache.get(origin)
    if cached and now - cached[0] < _BRAND_CACHE_TTL_SECONDS:
        return cached[1]

    host = urlsplit(origin).netloc
    if not host:
        return _empty_brand()

    try:
        async with httpx.AsyncClient(
            timeout=CONSTANTS.S_ORION_SSO_TIMEOUT_SECONDS,
            trust_env=False,
        ) as client:
            response = await client.get(
                f"{CONSTANTS.S_ORION_INTELLIGENCE_INTERNAL_URL}/api/public",
                headers={"Host": host},
            )
            if response.status_code >= 400:
                return _empty_brand()
            settings = (response.json() or {}).get("settings") or {}
            brand = {
                "name": str(settings.get("app_name") or ""),
                "logo_light": await _fetch_logo(client, str(settings.get("logo_wide_light") or ""), host),
                "logo_dark": await _fetch_logo(client, str(settings.get("logo_wide_dark") or ""), host),
                "favicon": await _fetch_logo(client, "/api/s/static/favicon", host),
            }
    except (httpx.RequestError, ValueError):
        return _empty_brand()

    _brand_cache[origin] = (now, brand)
    return brand
