from __future__ import annotations

from orion.api.server.config_manager.config_enums import CONFIG_DEFAULTS
from orion.services.mongo_manager.shared_model.db_system_config_model import db_system_config_model


class FakeConfigEngine:
    def __init__(self, documents=None, save_error=None):
        self.documents = documents or {}
        self.save_error = save_error
        self.saved = []

    async def find_one(self, _model, query):
        return self.documents.get(dict(query)["key"]["$eq"])

    async def save(self, config):
        if self.save_error is not None:
            raise self.save_error
        self.documents[config.key] = config
        self.saved.append(config)
        return config


class FakeSystemConfigEngine:
    def __init__(self):
        self.documents = {config["key"]: db_system_config_model(**config) for config in CONFIG_DEFAULTS.VALUES}
        self.saved = []

    async def find_one(self, _model, query):
        return self.documents.get(dict(query)["key"]["$eq"])

    async def save(self, config):
        self.documents[config.key] = config
        self.saved.append(config)
        return config
