import pytest
from pydantic import ValidationError

from orion.api.interactive.preference_manager.models.preference_param_model import UserPreferencesRequest
from orion.api.interactive.preference_manager.preference_manager import preference_manager
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


class FakeUserEngine:
    def __init__(self):
        self.saved = []

    async def save(self, user):
        self.saved.append(user)
        return user


def build_manager():
    manager = object.__new__(preference_manager)
    manager._engine = FakeUserEngine()
    return manager


def build_user():
    return db_user_model(full_name="Administrator", email="admin@orionintelligence.org", username="Admin")


def test_preferences_default_to_an_empty_isolated_mapping():
    first = build_user()
    second = build_user()
    assert first.preferences is not None

    first.preferences["theme"] = "dark"

    assert first.preferences == {"theme": "dark"}
    assert second.preferences == {}


@pytest.mark.anyio
async def test_update_preferences_persists_the_theme():
    manager = build_manager()
    user = build_user()

    result = await manager.update_preferences(current_user=user, preferences={"theme": "dark"})

    assert result == {"theme": "dark"}
    assert manager._engine.saved == [user]
    assert user.preferences == {"theme": "dark"}


@pytest.mark.anyio
async def test_update_preferences_keeps_unrelated_keys():
    manager = build_manager()
    user = build_user()
    user.preferences = {"density": "compact", "theme": "light"}

    await manager.update_preferences(current_user=user, preferences={"theme": "dark"})

    assert user.preferences == {"density": "compact", "theme": "dark"}


def test_serialize_preferences_reports_none_when_unset():
    assert preference_manager.serialize_preferences(build_user()) == {"theme": None}


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_request_accepts_supported_themes(theme):
    assert UserPreferencesRequest.model_validate({"theme": theme}).theme == theme


@pytest.mark.parametrize("theme", ["solarized", "", "DARK"])
def test_request_rejects_unsupported_themes(theme):
    with pytest.raises(ValidationError):
        UserPreferencesRequest.model_validate({"theme": theme})
