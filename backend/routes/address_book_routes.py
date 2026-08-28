from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from configs.app_dependency import get_current_user
from orion.api.interactive.address_book_manager.address_book_constants import ADDRESS_BOOK_LIMITS
from orion.api.interactive.address_book_manager.address_book_manager import address_book_manager
from orion.api.interactive.address_book_manager.models.address_book_response_model import AddressHintResponse
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


address_book_routes = APIRouter(prefix="/address-book", tags=["Address book"])


class AddressHintRequest(BaseModel):
    query: str = Field(min_length=1, max_length=320)
    limit: int = Field(default=ADDRESS_BOOK_LIMITS.DEFAULT_HINTS, ge=1, le=ADDRESS_BOOK_LIMITS.MAX_HINTS)


@address_book_routes.post("/hints", response_model=list[AddressHintResponse])
async def get_address_hints(hint_data: AddressHintRequest, current_user: db_user_model = Depends(get_current_user)):
    return await address_book_manager.get_instance().get_hints(current_user=current_user, query=hint_data.query, limit=hint_data.limit)