from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from orion.constants.constant import CONSTANTS
from orion.services.orion_identity_manager.orion_brand_client import get_tenant_brand

interface = APIRouter()

BASE_DIR = Path(__file__).resolve().parent
ANGULAR_BUILD_DIR = (BASE_DIR / "workspace" / "build").resolve()
CSP_NONCE_PLACEHOLDER = "__CSP_NONCE__"
SPLASH_LOGO_PLACEHOLDER = "<!--__SPLASH_LOGO__-->"


def _tenant_orion_origin(request: Request) -> str:
    host = (request.headers.get("host") or "").split(":")[0].strip().lower()
    base_domain = CONSTANTS.S_MAIL_BASE_DOMAIN
    if base_domain.startswith("mail.") and CONSTANTS.S_MAIL_TENANT_HOST_PATTERN.fullmatch(host):
        return f"https://{host.split('.', 1)[0]}.{base_domain[len('mail.'):]}"
    return CONSTANTS.S_ORION_INTELLIGENCE_PUBLIC_URL


def _splash_logo_html(brand: dict[str, str]) -> str:
    light = brand.get("logo_light") or ""
    dark = brand.get("logo_dark") or ""
    if not light and not dark:
        return ""
    return (
        f'<img class="app-splash-logo app-splash-logo-light" src="{light or dark}" alt="" />'
        f'<img class="app-splash-logo app-splash-logo-dark" src="{dark or light}" alt="" />'
    )


async def _frontend_index_response(request: Request) -> HTMLResponse:
    index_path = ANGULAR_BUILD_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")

    html = index_path.read_text(encoding="utf-8")
    nonce = getattr(request.state, "csp_nonce", "")
    html = html.replace(CSP_NONCE_PLACEHOLDER, nonce)
    if not nonce:
        html = html.replace(' ngCspNonce=""', "").replace(' ngcspnonce=""', "").replace(' nonce=""', "")
    brand = await get_tenant_brand(_tenant_orion_origin(request))
    html = html.replace(SPLASH_LOGO_PLACEHOLDER, _splash_logo_html(brand))
    return HTMLResponse(html)


@interface.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(request: Request, full_path: str):
    user_path = Path(full_path)
    if user_path.is_absolute() or ".." in user_path.parts:
        raise HTTPException(status_code=404, detail="Frontend not found")

    safe_relative_path = Path(*[part for part in user_path.parts if part not in ("", ".")])
    requested_path = (ANGULAR_BUILD_DIR / safe_relative_path).resolve()
    if requested_path == ANGULAR_BUILD_DIR / "index.html":
        return await _frontend_index_response(request)
    if requested_path.is_relative_to(ANGULAR_BUILD_DIR) and requested_path.exists() and requested_path.is_file():
        return FileResponse(requested_path)

    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="API route not found")

    return await _frontend_index_response(request)
