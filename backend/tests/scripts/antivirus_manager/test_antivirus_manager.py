from __future__ import annotations

import pytest
from fastapi import HTTPException, status

from orion.services.antivirus_manager.antivirus_manager import antivirus_manager


@pytest.fixture
def manager():
    return antivirus_manager.get_instance()


@pytest.mark.anyio
async def test_assert_clean_passes_when_clamav_reports_ok(manager, monkeypatch):
    async def fake_scan(_content):
        return "stream: OK"

    monkeypatch.setattr(manager, "_scan", fake_scan)
    await manager.assert_clean(b"harmless attachment bytes", "notes.txt")


@pytest.mark.anyio
async def test_assert_clean_rejects_malware_when_clamav_reports_found(manager, monkeypatch):
    async def fake_scan(_content):
        return "stream: Eicar-Test-Signature FOUND"

    monkeypatch.setattr(manager, "_scan", fake_scan)
    with pytest.raises(HTTPException) as error:
        await manager.assert_clean(b"malware payload", "virus.exe")
    assert error.value.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.anyio
async def test_assert_clean_is_unavailable_when_scan_response_is_unexpected(manager, monkeypatch):
    async def fake_scan(_content):
        return "stream: ERROR could not scan"

    monkeypatch.setattr(manager, "_scan", fake_scan)
    with pytest.raises(HTTPException) as error:
        await manager.assert_clean(b"bytes", "file.bin")
    assert error.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.anyio
async def test_assert_clean_is_unavailable_when_the_scanner_is_unreachable(manager, monkeypatch):
    async def fake_scan(_content):
        raise ConnectionRefusedError("clamav is down")

    monkeypatch.setattr(manager, "_scan", fake_scan)
    with pytest.raises(HTTPException) as error:
        await manager.assert_clean(b"bytes", "file.bin")
    assert error.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
