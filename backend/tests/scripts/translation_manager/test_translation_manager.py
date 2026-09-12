from __future__ import annotations

import json

import httpx
import pytest

from orion.api.interactive.translation_manager import translation_manager as translation_module
from orion.api.interactive.translation_manager.translation_manager import translation_manager
from orion.constants.constant import CONSTANTS
from tests.scripts.translation_manager.fakes import FakeStreamResponse
from tests.scripts.translation_manager.helpers import build_manager, patch_httpx


def test_split_text_empty_returns_empty():
    assert translation_manager.split_text("") == []


def test_split_text_short_returns_single_chunk():
    assert translation_manager.split_text("hello world") == ["hello world"]


def test_split_text_splits_on_newline():
    text = "a" * 3000 + "\n" + "b" * 1000
    chunks = translation_manager.split_text(text)
    assert len(chunks) == 2
    assert chunks[0].endswith("\n")
    assert "".join(chunks) == text


def test_split_text_splits_on_space_when_no_newline():
    text = "a" * 3000 + " " + "b" * 1000
    chunks = translation_manager.split_text(text)
    assert len(chunks) == 2
    assert chunks[0].endswith(" ")


def test_split_text_hard_splits_without_any_separator():
    text = "a" * 4000
    chunks = translation_manager.split_text(text)
    assert len(chunks) == 2
    assert len(chunks[0]) == translation_manager._chunk_size


def test_translation_url_builds_https_query():
    url = translation_manager._translation_url("fr")
    assert url.startswith("https://")
    assert "tl=fr" in url


def test_translation_url_rejects_non_https(monkeypatch):
    monkeypatch.setattr(CONSTANTS, "S_TRANSLATION_API_URL", "http://translate.example.com/api")
    with pytest.raises(translation_module.HTTPException) as error:
        translation_manager._translation_url("fr")
    assert error.value.status_code == 503


def test_translation_url_rejects_missing_hostname(monkeypatch):
    monkeypatch.setattr(CONSTANTS, "S_TRANSLATION_API_URL", "https:///api")
    with pytest.raises(translation_module.HTTPException) as error:
        translation_manager._translation_url("fr")
    assert error.value.status_code == 503


def test_translation_url_rejects_embedded_credentials(monkeypatch):
    monkeypatch.setattr(CONSTANTS, "S_TRANSLATION_API_URL", "https://user:pass@translate.example.com/api")
    with pytest.raises(translation_module.HTTPException) as error:
        translation_manager._translation_url("fr")
    assert error.value.status_code == 503


def test_translation_url_rejects_fragment(monkeypatch):
    monkeypatch.setattr(CONSTANTS, "S_TRANSLATION_API_URL", "https://translate.example.com/api#frag")
    with pytest.raises(translation_module.HTTPException) as error:
        translation_manager._translation_url("fr")
    assert error.value.status_code == 503


def test_translate_chunk_sync_returns_text_and_language(monkeypatch):
    payload = [[["Hola", "Hello", None, None]], None, "en"]
    patch_httpx(monkeypatch, FakeStreamResponse(body=json.dumps(payload).encode()))
    assert translation_manager._translate_chunk_sync("Hello", "es") == ("Hola", "en")


def test_translate_chunk_sync_wraps_http_error(monkeypatch):
    patch_httpx(monkeypatch, FakeStreamResponse(raise_error=httpx.HTTPError("boom")))
    with pytest.raises(translation_module.HTTPException) as error:
        translation_manager._translate_chunk_sync("Hello", "es")
    assert error.value.status_code == 502


def test_translate_chunk_sync_wraps_invalid_json(monkeypatch):
    patch_httpx(monkeypatch, FakeStreamResponse(body=b"not-json"))
    with pytest.raises(translation_module.HTTPException) as error:
        translation_manager._translate_chunk_sync("Hello", "es")
    assert error.value.status_code == 502


def test_translate_chunk_sync_wraps_malformed_payload(monkeypatch):
    patch_httpx(monkeypatch, FakeStreamResponse(body=b"[]"))
    with pytest.raises(translation_module.HTTPException) as error:
        translation_manager._translate_chunk_sync("Hello", "es")
    assert error.value.status_code == 502


@pytest.mark.anyio
async def test_translate_text_empty_returns_empty_tuple():
    manager = build_manager()
    assert await manager.translate_text("", "fr") == ("", None)


@pytest.mark.anyio
async def test_translate_text_joins_chunk_results():
    manager = build_manager()
    manager._translate_chunk_sync = lambda chunk, language: ("X", "de")
    text = "a" * 4000
    translated, detected = await manager.translate_text(text, "de")
    assert translated == "XX"
    assert detected == "de"


@pytest.mark.anyio
async def test_translate_message_rejects_unsupported_language():
    manager = build_manager()
    with pytest.raises(translation_module.HTTPException) as error:
        await manager.translate_message("subject", "body", "xx")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_translate_message_normalizes_and_returns_translation():
    manager = build_manager()

    async def fake_translate_text(text, target_language):
        return f"{text}-{target_language}", "en"

    manager.translate_text = fake_translate_text
    result = await manager.translate_message("Hi", "There", "FR")
    assert result["target_language"] == "fr"
    assert result["target_language_name"] == "French"
    assert result["source_language"] == "en"
    assert result["translated_subject"] == "Hi-fr"
    assert result["translated_body"] == "There-fr"
