from typing import Any, Callable, cast

from fastapi import FastAPI
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from orion.constants.constant import CONSTANTS
from orion.middleware.middlewares.security_headers_middleware import security_headers_middleware


def middleware(cls: Any, **options: Any) -> Middleware:
    return cast(Callable[..., Middleware], Middleware)(cls, **options)


def build_middlewares() -> list[Middleware]:
    return [middleware(CORSMiddleware, allow_origins=CONSTANTS.S_CORS_ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "X-Requested-With"]), middleware(TrustedHostMiddleware, allowed_hosts=CONSTANTS.S_ALLOWED_HOSTS), middleware(security_headers_middleware)]


def setup_middlewares(app: FastAPI) -> None:
    for entry in build_middlewares():
        app.user_middleware.append(entry)
    app.middleware_stack = None
