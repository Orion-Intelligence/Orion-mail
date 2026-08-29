from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.api.server.config_manager.config_controller import config_controller
from orion.services.antivirus_manager.antivirus_manager import antivirus_manager

ONE_MB = 1024 * 1024


class FakeConfigController:
    async def get_config_int(self, _key):
        return 1


class FakeAntivirusManager:
    def __init__(self):
        self.scanned = []

    async def assert_clean(self, content, filename):
        self.scanned.append(filename)


def build_upload(name, size):
    payload = b"x" * size
    return UploadFile(file=BytesIO(payload), size=size, filename=name, headers=Headers({"content-type": "application/octet-stream"}))


def build_manager(tmp_path, monkeypatch):
    manager = object.__new__(attachment_manager)
    scanner = FakeAntivirusManager()
    monkeypatch.setattr(config_controller, "get_instance", staticmethod(lambda: FakeConfigController()))
    monkeypatch.setattr(antivirus_manager, "get_instance", staticmethod(lambda: scanner))
    monkeypatch.setattr(attachment_manager, "staging_directory", staticmethod(lambda: tmp_path))
    return manager, scanner


@pytest.mark.anyio
async def test_staging_writes_plaintext_and_records_no_database_row(tmp_path, monkeypatch):
    manager, _scanner = build_manager(tmp_path, monkeypatch)

    staged = await manager.stage_outgoing_attachments([build_upload("report.pdf", 2048)])

    assert len(staged) == 1
    assert staged[0]["original_filename"] == "report.pdf"
    assert "id" not in staged[0]
    stored = tmp_path / staged[0]["stored_filename"]
    assert stored.read_bytes() == b"x" * 2048


@pytest.mark.anyio
async def test_staging_rejects_a_file_over_the_limit_by_name(tmp_path, monkeypatch):
    manager, scanner = build_manager(tmp_path, monkeypatch)

    with pytest.raises(HTTPException) as error:
        await manager.stage_outgoing_attachments([build_upload("huge.zip", ONE_MB + 1)])

    assert error.value.status_code == 413
    assert "huge.zip" in error.value.detail
    assert scanner.scanned == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_staging_rejects_a_cumulative_overrun_and_leaves_no_files(tmp_path, monkeypatch):
    manager, _scanner = build_manager(tmp_path, monkeypatch)

    with pytest.raises(HTTPException) as error:
        await manager.stage_outgoing_attachments([build_upload("a.bin", 700 * 1024), build_upload("b.bin", 700 * 1024)])

    assert error.value.status_code == 413
    assert "Total attachment size" in error.value.detail
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_discard_removes_every_staged_file(tmp_path, monkeypatch):
    manager, _scanner = build_manager(tmp_path, monkeypatch)

    staged = await manager.stage_outgoing_attachments([build_upload("a.bin", 16), build_upload("b.bin", 16)])
    assert len(list(tmp_path.iterdir())) == 2

    manager.discard_staged_attachments(staged)

    assert list(tmp_path.iterdir()) == []
