import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from configs.app_dependency import allowed_origins
from orion.api.interactive.mailbox_manager.models.mailbox_param_model import (
    MailboxCreateRequest,
)
from orion.constants.constant import CONSTANTS
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model
from routes.auth_routes import allowed_mail_origin, safe_return_to


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "/inbox"),
        ("/message/123?view=full#ignored", "/message/123?view=full"),
        ("https://attacker.example/path", "/inbox"),
        ("//attacker.example/path", "/inbox"),
        ("/\\attacker.example", "/inbox"),
        ("/\\/attacker.example", "/inbox"),
        ("\\\\attacker.example", "/inbox"),
        ("/inbox\r\nSet-Cookie: injected=1", "/inbox"),
        ("javascript:alert(1)", "/inbox"),
        ("", "/inbox"),
        ("/inbox", "/inbox"),
    ],
)
def test_safe_return_to_stays_on_mail(value, expected):
    assert safe_return_to(value) == expected


# noinspection HttpUrlsUsage
def test_mail_origin_requires_exact_allowlist(monkeypatch):
    monkeypatch.setattr(CONSTANTS, "S_ORION_MAIL_PUBLIC_URLS", ["http://mail.localhost:4200"])

    assert allowed_mail_origin("http://mail.localhost:4200/") == "http://mail.localhost:4200"
    with pytest.raises(HTTPException) as error:
        allowed_mail_origin("http://mail.localhost:4200.attacker.example")

    assert error.value.status_code == 400


def test_declared_mail_origins_are_csrf_origins(monkeypatch):
    monkeypatch.setattr(CONSTANTS, "S_ORION_MAIL_PUBLIC_URLS", ["http://mail.localhost:4200"])

    assert "http://mail.localhost:4200" in allowed_origins()


def test_mailbox_username_is_normalized_and_validated():
    assert MailboxCreateRequest(username="  abdul.mannan ").username == "abdul.mannan"
    with pytest.raises(ValidationError):
        MailboxCreateRequest(username="Abdul@external.example")


def test_local_account_contains_no_auth_credentials():
    user = db_user_model(
        full_name="Abdul Mannan",
        email="abdul@orionintelligence.org",
        username="abdul",
        orion_user_id="orion-user-id",
        orion_tenant_id="orion-tenant-id",
    )

    assert "password" not in user.model_dump()
    assert "password_hash" not in user.model_dump()
