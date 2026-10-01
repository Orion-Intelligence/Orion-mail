import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class content_security_policy_middleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.csp_nonce = secrets.token_urlsafe(16)
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (f"default-src 'self'; " f"script-src 'self'; " f"style-src 'self' 'nonce-{request.state.csp_nonce}'; " f"img-src 'self' data: blob:; " f"font-src 'self'; " f"connect-src 'self' https://*.gofile.io; " f"frame-src 'self' blob:; " f"frame-ancestors 'none'; " f"base-uri 'self'; " f"form-action 'self'; " f"object-src 'none'; " f"upgrade-insecure-requests")
        return response
