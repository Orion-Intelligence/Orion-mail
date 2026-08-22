from typing import Annotated

from fastapi import APIRouter, Depends, Query

from configs.app_dependency import get_current_user
from orion.api.interactive.address_book_manager.address_book_constants import ADDRESS_BOOK_LIMITS
from orion.api.interactive.address_book_manager.address_book_manager import address_book_manager
from orion.api.interactive.address_book_manager.models.address_book_response_model import AddressHintResponse
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model

address_book_routes = APIRouter(prefix="/address-book", tags=["Address book"])


@address_book_routes.get("/hints", response_model=list[AddressHintResponse])
async def get_address_hints(query: Annotated[str, Query(min_length=1, max_length=320)], current_user: db_user_model = Depends(get_current_user), limit: Annotated[int, Query(ge=1, le=ADDRESS_BOOK_LIMITS.MAX_HINTS)] = ADDRESS_BOOK_LIMITS.DEFAULT_HINTS):
    return await address_book_manager.get_instance().get_hints(current_user=current_user, query=query, limit=limit)
