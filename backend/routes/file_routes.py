from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import Response

from configs.app_dependency import get_current_user
from orion.api.interactive.file_manager.file_manager import file_manager
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model



file_routes = APIRouter(prefix="/api/files", tags=["Files"])


@file_routes.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
async def upload_shared_file(
    encrypted_file: Annotated[UploadFile, File()],
    original_filename: Annotated[str, Form()],
    original_size: Annotated[int, Form()],
    content_type: Annotated[str, Form()],
    iv: Annotated[str, Form()],
    current_user: db_user_model = Depends(get_current_user),
):
    return await file_manager.get_instance().upload_file(
        current_user=current_user,
        encrypted_file=encrypted_file,
        original_filename=original_filename,
        original_size=original_size,
        content_type=content_type,
        iv=iv,
    )


@file_routes.get("")
async def get_shared_files(current_user: db_user_model = Depends(get_current_user)):
    return await file_manager.get_instance().get_my_files(current_user=current_user)


@file_routes.get("/public/{public_id}")
async def get_public_file_metadata(public_id: str):
    return (
        await file_manager
        .get_instance()
        .get_public_metadata(public_id)
    )


@file_routes.get("/public/{public_id}/content")
async def get_public_file_content(public_id: str):
    content = (
        await file_manager
        .get_instance()
        .get_ciphertext(public_id)
    )

    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@file_routes.delete("/{file_id}")
async def delete_shared_file(file_id: str, current_user: db_user_model = Depends(get_current_user)):
    return await file_manager.get_instance().delete_file(current_user=current_user, file_id=file_id)