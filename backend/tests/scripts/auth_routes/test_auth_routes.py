from __future__ import annotations

from configs.app_dependency import get_current_user
from routes import auth_routes
from tests.scripts.auth_routes.fakes import (
    FakeIdentityClient,
    FakeIdentityManager,
    FakeMailbox,
    FakePreferenceInstance,
    build_user,
)

CSRF_HEADERS = {"x-requested-with": "XMLHttpRequest"}


async def _no_mailbox(_user):
    return None


async def _with_mailbox(_user):
    return FakeMailbox()


def test_login_redirects_and_sets_sso_cookies(client):
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 302
    assert "/api/sso/mail/authorize?" in response.headers["location"]
    assert "orion_mail_sso_state" in response.headers.get("set-cookie", "")


def test_login_rejects_unknown_origin(client):
    response = client.get("/auth/login", params={"origin": "https://attacker.example"}, follow_redirects=False)
    assert response.status_code == 400


def test_me_returns_current_user_without_mailbox(client, override, monkeypatch):
    user = build_user()
    override(get_current_user, lambda: user)
    monkeypatch.setattr(auth_routes, "mailbox_for_user", _no_mailbox)
    response = client.get("/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "abdul@orionintelligence.org"
    assert body["mailbox_configured"] is False
    assert body["mailbox_address"] is None
    assert body["preferences"] == {"theme": "light"}


def test_me_reports_configured_mailbox(client, override, monkeypatch):
    user = build_user()
    override(get_current_user, lambda: user)
    monkeypatch.setattr(auth_routes, "mailbox_for_user", _with_mailbox)
    response = client.get("/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["mailbox_configured"] is True
    assert body["mailbox_address"] == "abdul@mail.orionintelligence.org"


def test_me_requires_authentication(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_update_preferences_persists_via_manager(client, override, monkeypatch):
    user = build_user()
    override(get_current_user, lambda: user)
    instance = FakePreferenceInstance({"theme": "dark"})
    monkeypatch.setattr(auth_routes.preference_manager, "get_instance", lambda: instance)
    response = client.put("/auth/me/preferences", json={"theme": "dark"}, headers=CSRF_HEADERS)
    assert response.status_code == 200
    assert response.json() == {"theme": "dark"}
    assert instance.calls == [{"theme": "dark"}]


def test_update_preferences_rejects_invalid_theme(client, override):
    override(get_current_user, lambda: build_user())
    response = client.put("/auth/me/preferences", json={"theme": "rainbow"}, headers=CSRF_HEADERS)
    assert response.status_code == 422


def test_logout_without_session_returns_message(client):
    response = client.post("/auth/logout", headers=CSRF_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Logged out successfully"
    assert body["redirect_url"].endswith("/login")


def test_logout_requires_csrf_header(client):
    response = client.post("/auth/logout")
    assert response.status_code == 403


def test_logout_revokes_existing_session(client, monkeypatch):
    identity_client = FakeIdentityClient()
    monkeypatch.setattr(auth_routes.orion_identity_client, "get_instance", lambda: identity_client)
    client.cookies.set("orion_mail_session", "session-token")
    response = client.post("/auth/logout", headers=CSRF_HEADERS)
    assert response.status_code == 200
    assert identity_client.revoked == ["session-token"]


def test_callback_rejects_invalid_state(client):
    response = client.get("/auth/callback", params={"code": "abc", "state": "mismatch"}, follow_redirects=False)
    assert response.status_code == 400


def _install_callback_managers(monkeypatch, user, exchange_result):
    monkeypatch.setattr(auth_routes.orion_identity_client, "get_instance", lambda: FakeIdentityClient(exchange_result))
    monkeypatch.setattr(auth_routes.orion_identity_manager, "get_instance", lambda: FakeIdentityManager(user))


def _set_callback_cookies(client):
    client.cookies.set("orion_mail_sso_state", "the-state")
    client.cookies.set("orion_mail_sso_redirect", "http://localhost:4200/auth/callback")


def test_callback_success_with_mailbox_redirects_to_inbox(client, monkeypatch):
    user = build_user()
    _install_callback_managers(monkeypatch, user, {"session_token": "tok", "identity": {"sub": "1"}, "expires_in": 3600})
    monkeypatch.setattr(auth_routes, "mailbox_for_user", _with_mailbox)
    _set_callback_cookies(client)
    response = client.get("/auth/callback", params={"code": "abc", "state": "the-state"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/inbox"
    assert "orion_mail_session" in response.headers.get("set-cookie", "")


def test_callback_success_without_mailbox_redirects_to_configure(client, monkeypatch):
    user = build_user()
    _install_callback_managers(monkeypatch, user, {"session_token": "tok", "identity": {"sub": "1"}, "expires_in": 3600})
    monkeypatch.setattr(auth_routes, "mailbox_for_user", _no_mailbox)
    _set_callback_cookies(client)
    response = client.get("/auth/callback", params={"code": "abc", "state": "the-state"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/configure-email"


def test_callback_rejects_invalid_exchange_response(client, monkeypatch):
    _install_callback_managers(monkeypatch, build_user(), {"session_token": "", "identity": None})
    _set_callback_cookies(client)
    response = client.get("/auth/callback", params={"code": "abc", "state": "the-state"}, follow_redirects=False)
    assert response.status_code == 503
