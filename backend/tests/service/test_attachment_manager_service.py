from __future__ import annotations

from io import BytesIO

import pytest
from bson import ObjectId
from fastapi import HTTPException, UploadFile

from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.api.interactive.message_manager.message_enums import MESSAGE_LIMITS
from orion.services.mongo_manager.shared_model.db_attachment_model import STORAGE_TYPE


def test_sanitize_strips_path_traversal():
    assert attachment_manager.sanitize_original_filename("../../etc/passwd") == "passwd"


def test_sanitize_defaults_when_missing():
    assert attachment_manager.sanitize_original_filename(None) == "attachment"


def test_sanitize_removes_control_characters():
    assert attachment_manager.sanitize_original_filename("re\x00port\n.txt") == "report.txt"


def test_sanitize_replaces_backslashes():
    assert attachment_manager.sanitize_original_filename("folder\\file.txt") == "folder_file.txt"


def test_sanitize_truncates_to_max_length():
    long_name = "a" * 500 + ".txt"
    assert len(attachment_manager.sanitize_original_filename(long_name)) <= MESSAGE_LIMITS.FILENAME_MAX_LENGTH


def test_generate_keeps_safe_lowercased_suffix():
    assert attachment_manager.generate_stored_filename("Report.PDF").endswith(".pdf")


def test_generate_drops_unsafe_suffix():
    stored = attachment_manager.generate_stored_filename("archive.gz!")
    assert "." not in stored


def test_get_attachment_path_rejects_traversal(tmp_path):
    with pytest.raises(ValueError):
        attachment_manager.get_attachment_path(tmp_path, "../escape.txt")


def test_get_attachment_path_allows_plain_filename(tmp_path):
    path = attachment_manager.get_attachment_path(tmp_path, "file.txt")
    assert path.name == "file.txt"


def test_get_storage_directory_rejects_invalid_type():
    with pytest.raises(ValueError):
        attachment_manager.get_storage_directory("not-a-real-type")


@pytest.mark.anyio
async def test_save_attachments_rejects_too_many_files():
    manager = object.__new__(attachment_manager)
    files = [
        UploadFile(filename=f"file{i}.txt", file=BytesIO(b"x"))
        for i in range(MESSAGE_LIMITS.MAX_ATTACHMENTS + 1)
    ]
    with pytest.raises(HTTPException) as error:
        await manager.save_attachments(ObjectId(), files, STORAGE_TYPE.INCOMING, "key", "err", "err")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_save_attachments_returns_empty_for_no_files():
    manager = object.__new__(attachment_manager)
    assert await manager.save_attachments(ObjectId(), [], STORAGE_TYPE.INCOMING, "key", "err", "err") == []
