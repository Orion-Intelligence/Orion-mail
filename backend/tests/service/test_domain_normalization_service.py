import pytest
from bson import ObjectId

from orion.services.mongo_manager.shared_model.db_domain_safety_model import db_domain_report_model, db_domain_reputation_model, db_sender_block_model


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
