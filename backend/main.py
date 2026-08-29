from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from orion.management.managers.service_manager import service_manager
from orion.middleware.middleware_setup import setup_middlewares
from orion.services.mongo_manager.mongo_controller import mongo_controller
from routes.address_book_routes import address_book_routes
from routes.attachment_routes import attachment_routes
from routes.auth_routes import auth_routes
from routes.config_routes import config_routes
from routes.incoming_mail_routes import incoming_mail_routes
from routes.label_routes import label_routes
from routes.mailbox_routes import mailbox_routes
from routes.message_routes import message_routes


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await service_manager.get_instance().init_services()
    yield
    await service_manager.get_instance().close_services()


app = FastAPI(title="Orion Mail API", version="1.0.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
setup_middlewares(app)


@app.get("/")
async def root():
    return {"message": "Orion Mail API is running"}


@app.get("/health")
async def health():
    try:
        await mongo_controller.get_instance().link_connection()
    except PyMongoError:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "database": "disconnected"})
    return {"status": "healthy", "database": "connected"}


app.include_router(auth_routes)
app.include_router(mailbox_routes)
app.include_router(address_book_routes)
app.include_router(message_routes)
app.include_router(label_routes)
app.include_router(incoming_mail_routes)
app.include_router(attachment_routes)
app.include_router(config_routes)
