import pytest
from fastapi import HTTPException
from odmantic import ObjectId

from orion.api.interactive.message_manager.message_manager import message_manager
from orion.api.interactive.message_manager.models.message_param_model import MESSAGE_SEARCH_SCOPE
from orion.services.mongo_manager.shared_model.db_label_model import db_label_model
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


class FakeSearchEngine:
    def __init__(self, mailbox, messages=None, label=None):
        self.mailbox = mailbox
        self.messages = list(messages or [])
        self.label = label
        self.search_query = None
        self.search_limit = None

    async def find_one(self, model, *_args, **_kwargs):
        if model is db_mailbox_model:
            return self.mailbox
        if model is db_label_model:
            return self.label
        return None

    async def find(self, model, query, *, sort=None, limit=None, **_kwargs):
        assert model is db_message_model
        assert sort is not None
        self.search_query = query
        self.search_limit = limit
        return self.messages[:limit] if limit is not None else self.messages


def search_manager(engine):
    manager = object.__new__(message_manager)
    manager._engine = engine
    return manager


@pytest.mark.anyio
async def test_search_is_mailbox_scoped_filters_folder_and_matches_every_term():
    user = db_user_model(full_name="Admin", email="admin@orion.test", username="admin")
    mailbox = db_mailbox_model(user_id=user.id, mailbox_address="admin@mail.orion.test")
    message = db_message_model(owner_mailbox_id=mailbox.id, sender_address="alice@example.com", receiver_address=mailbox.mailbox_address, subject="Quarterly invoice", body="Attached report", direction=MESSAGE_DIRECTION.INCOMING, folder=MESSAGE_FOLDER.INBOX)
    engine = FakeSearchEngine(mailbox, [message])

    results = await search_manager(engine).search_messages(user, "Quarterly Alice", MESSAGE_SEARCH_SCOPE.INBOX, limit=6)

    assert [result["id"] for result in results] == [str(message.id)]
    assert engine.search_limit == 6
    conditions = dict(engine.search_query)["$and"]
    assert any(dict(condition).get("owner_mailbox_id") == {"$eq": mailbox.id} for condition in conditions)
    assert any(dict(condition).get("folder") == {"$eq": MESSAGE_FOLDER.INBOX.value} for condition in conditions)
    term_conditions = [dict(condition)["$or"] for condition in conditions if "$or" in dict(condition)]
    assert [[next(iter(dict(field_condition).values())).pattern for field_condition in term] for term in term_conditions] == [["Quarterly"] * 6, ["Alice"] * 6]


@pytest.mark.anyio
async def test_label_search_requires_an_owned_label_and_escapes_regex_input():
    user = db_user_model(full_name="Admin", email="admin@orion.test", username="admin")
    mailbox = db_mailbox_model(user_id=user.id, mailbox_address="admin@mail.orion.test")
    label = db_label_model(user_id=user.id, name="Clients", normalized_name="clients")
    engine = FakeSearchEngine(mailbox, label=label)

    await search_manager(engine).search_messages(user, "a+b", MESSAGE_SEARCH_SCOPE.LABEL, label_id=str(label.id))

    conditions = dict(engine.search_query)["$and"]
    assert any(dict(condition).get("label_ids") == {"$eq": label.id} for condition in conditions)
    term_condition = next(dict(condition)["$or"] for condition in conditions if "$or" in dict(condition))
    assert all(next(iter(dict(field_condition).values())).pattern == r"a\+b" for field_condition in term_condition)

    with pytest.raises(HTTPException) as missing_label:
        await search_manager(FakeSearchEngine(mailbox)).search_messages(user, "invoice", MESSAGE_SEARCH_SCOPE.LABEL, label_id=str(ObjectId()))
    assert missing_label.value.status_code == 404
