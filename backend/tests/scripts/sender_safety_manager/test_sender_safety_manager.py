from __future__ import annotations

import pytest
from bson import ObjectId
from orion.api.interactive.sender_safety_manager.sender_safety_manager import sender_safety_manager
from orion.services.mongo_manager.shared_model.db_domain_safety_model import REPORT_TYPE, db_domain_report_model, db_domain_reputation_model, db_sender_block_model
from orion.services.mongo_manager.shared_model.db_message_model import MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


USER = db_user_model(full_name="Test One", email="test1@orionintelligence.org", username="test1")


class FakeCollection:
    def __init__(self, find_one_result=None, update_result=None, deleted=0):
        self._find_one = find_one_result
        self._update = update_result
        self._deleted = deleted

    async def find_one(self, *_args, **_kwargs):
        return self._find_one

    async def find_one_and_update(self, *_args, **_kwargs):
        return self._update

    async def delete_one(self, *_args, **_kwargs):
        class Result:
            deleted_count = self._deleted

        return Result()


class FakeEngine:
    def __init__(self, by_model):
        self.by_model = by_model

    def get_collection(self, model):
        return self.by_model.get(model, FakeCollection())


def make_manager(by_model):
    manager = object.__new__(sender_safety_manager)
    manager._engine = FakeEngine(by_model)
    return manager


def message_from(sender: str):
    return db_message_model(
        owner_mailbox_id=ObjectId(),
        sender_address=sender,
        receiver_address="test1@mail.orionintelligence.org",
        subject="s",
        body="b",
        direction=MESSAGE_DIRECTION.INCOMING,
        folder=MESSAGE_FOLDER.INBOX,
    )


def test_sender_domain_extracts_and_lowercases():
    assert sender_safety_manager.sender_domain("User@Spammy-Example.COM") == "spammy-example.com"


def test_sender_domain_rejects_invalid_address():
    with pytest.raises(ValueError):
        sender_safety_manager.sender_domain("not-an-email")


@pytest.mark.anyio
async def test_is_domain_blocked_true_for_personal_block():
    manager = make_manager({
        db_sender_block_model: FakeCollection(find_one_result={"_id": ObjectId()}),
        db_domain_reputation_model: FakeCollection(find_one_result=None),
    })
    assert await manager.is_domain_blocked_for_user(USER.id, "spam@bad.com") is True


@pytest.mark.anyio
async def test_is_domain_blocked_false_when_clean():
    manager = make_manager({
        db_sender_block_model: FakeCollection(find_one_result=None),
        db_domain_reputation_model: FakeCollection(find_one_result=None),
    })
    assert await manager.is_domain_blocked_for_user(USER.id, "friend@good.com") is False


@pytest.mark.anyio
async def test_get_domain_state_reports_reputation_and_block():
    manager = make_manager({
        db_domain_report_model: FakeCollection(find_one_result={"report_type": "spam"}),
        db_domain_reputation_model: FakeCollection(find_one_result={"is_blocked": True, "spam_reports": 3, "total_reports": 3}),
        db_sender_block_model: FakeCollection(find_one_result=None),
    })
    state = await manager.get_domain_state(USER, "promo@bad.com")
    assert state["reported_as"] == "spam"
    assert state["globally_blocked"] is True
    assert state["sender_blocked"] is True
    assert state["spam_reports"] == 3


@pytest.mark.anyio
async def test_block_domain_marks_new_block():
    manager = make_manager({
        db_sender_block_model: FakeCollection(update_result=None),
        db_domain_reputation_model: FakeCollection(update_result={"user_block_count": 1, "total_reports": 0}),
    })
    result = await manager.block_domain(USER, message_from("bad@bad.com"))
    assert result["sender_blocked"] is True
    assert result["new_block"] is True


@pytest.mark.anyio
async def test_unblock_domain_removes_existing_block():
    manager = make_manager({
        db_sender_block_model: FakeCollection(deleted=1),
        db_domain_reputation_model: FakeCollection(update_result={"user_block_count": 0}),
    })
    result = await manager.unblock_domain(USER, "bad@bad.com")
    assert result["sender_blocked"] is False
    assert result["removed"] is True


@pytest.mark.anyio
async def test_report_domain_records_spam():
    manager = make_manager({
        db_domain_report_model: FakeCollection(update_result=None),
        db_domain_reputation_model: FakeCollection(update_result={"spam_reports": 1, "total_reports": 1}),
    })
    result = await manager.report_domain(USER, message_from("spam@bad.com"), REPORT_TYPE.SPAM)
    assert result["report_type"] == REPORT_TYPE.SPAM.value
    assert result["new_report"] is True
    assert result["spam_reports"] == 1


@pytest.mark.parametrize(
    "model, extra",
    [
        (db_domain_report_model, {"reporter_user_id": ObjectId(), "report_type": "spam"}),
        (db_domain_reputation_model, {}),
        (db_sender_block_model, {"user_id": ObjectId()}),
    ],
)
def test_sender_domain_is_normalized(model, extra):
    instance = model(sender_domain="  Example.COM.  ", **extra)
    assert instance.sender_domain == "example.com"
