import asyncio
from datetime import UTC, datetime

from email_validator import EmailNotValidError, validate_email
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_domain_safety_model import REPORT_TYPE, db_domain_report_model, db_domain_reputation_model, db_sender_block_model
from orion.services.mongo_manager.shared_model.db_message_model import db_message_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


class sender_safety_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if sender_safety_manager.__instance is None:
            sender_safety_manager()
        return sender_safety_manager.__instance

    def __init__(self):
        if sender_safety_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        sender_safety_manager.__instance = self
        self._engine = mongo_controller.get_instance().get_engine()

    @staticmethod
    def sender_domain(sender_address: str) -> str:
        try:
            validated = validate_email(sender_address.strip(), check_deliverability=False)
        except EmailNotValidError as error:
            raise ValueError("Sender address is not valid") from error

        domain = validated.ascii_domain or validated.domain
        return domain.lower().rstrip(".")

    async def _apply_reputation_delta(self, domain: str, *, spam_delta: int = 0, phishing_delta: int = 0, block_delta: int = 0) -> dict:
        reputation_collection = self._engine.get_collection(db_domain_reputation_model)
        now = datetime.now(UTC)
        reputation = await reputation_collection.find_one_and_update(
            {"sender_domain": domain},
            {
                "$inc": {
                    "spam_reports": spam_delta,
                    "phishing_reports": phishing_delta,
                    "total_reports": spam_delta + phishing_delta,
                    "user_block_count": block_delta,
                },
                "$set": {"updated_at": now},
                "$setOnInsert": {"sender_domain": domain, "is_blocked": False, "created_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return {
            "spam_reports": reputation.get("spam_reports", 0),
            "phishing_reports": reputation.get("phishing_reports", 0),
            "total_reports": reputation.get("total_reports", 0),
            "user_block_count": reputation.get("user_block_count", 0),
        }

    async def get_domain_state(self, current_user: db_user_model, sender_address: str) -> dict:
        domain = self.sender_domain(sender_address)
        report_collection = self._engine.get_collection(db_domain_report_model)
        reputation_collection = self._engine.get_collection(db_domain_reputation_model)
        block_collection = self._engine.get_collection(db_sender_block_model)

        report, reputation, personal_block = await asyncio.gather(
            report_collection.find_one({"reporter_user_id": current_user.id, "sender_domain": domain}),
            reputation_collection.find_one({"sender_domain": domain}),
            block_collection.find_one({"user_id": current_user.id, "sender_domain": domain}),
        )

        return {
            "sender_domain": domain,
            "reported_as": report.get("report_type") if report else None,
            "sender_blocked": bool(personal_block or (reputation and reputation.get("is_blocked"))),
            "globally_blocked": bool(reputation and reputation.get("is_blocked")),
            "spam_reports": reputation.get("spam_reports", 0) if reputation else 0,
            "phishing_reports": reputation.get("phishing_reports", 0) if reputation else 0,
            "total_reports": reputation.get("total_reports", 0) if reputation else 0,
            "user_block_count": reputation.get("user_block_count", 0) if reputation else 0,
        }

    async def report_domain(self, current_user: db_user_model, message: db_message_model, report_type: REPORT_TYPE) -> dict:
        domain = self.sender_domain(message.sender_address)
        now = datetime.now(UTC)
        report_collection = self._engine.get_collection(db_domain_report_model)

        query = {"reporter_user_id": current_user.id, "sender_domain": domain}
        update = {
            "$set": {
                "report_type": report_type.value,
                "sample_sender_address": message.sender_address,
                "last_message_id": message.id,
                "updated_at": now,
            },
            "$setOnInsert": {"reporter_user_id": current_user.id, "sender_domain": domain, "created_at": now},
        }
        try:
            previous = await report_collection.find_one_and_update(query, update, upsert=True, return_document=ReturnDocument.BEFORE)
        except DuplicateKeyError:
            previous = await report_collection.find_one_and_update(query, update, upsert=False, return_document=ReturnDocument.BEFORE)

        previous_type = previous.get("report_type") if previous else None
        spam_delta = int(report_type == REPORT_TYPE.SPAM and previous_type != REPORT_TYPE.SPAM.value) - int(previous_type == REPORT_TYPE.SPAM.value and report_type != REPORT_TYPE.SPAM)
        phishing_delta = int(report_type == REPORT_TYPE.PHISHING and previous_type != REPORT_TYPE.PHISHING.value) - int(previous_type == REPORT_TYPE.PHISHING.value and report_type != REPORT_TYPE.PHISHING)
        counts = await self._apply_reputation_delta(domain, spam_delta=spam_delta, phishing_delta=phishing_delta)
        return {
            "sender_domain": domain,
            "report_type": report_type.value,
            "new_report": previous is None,
            "changed_report_type": bool(previous and previous_type != report_type.value),
            **counts,
        }

    async def block_domain(self, current_user: db_user_model, message: db_message_model) -> dict:
        domain = self.sender_domain(message.sender_address)
        now = datetime.now(UTC)
        block_collection = self._engine.get_collection(db_sender_block_model)
        query = {"user_id": current_user.id, "sender_domain": domain}
        update = {
            "$set": {"sample_sender_address": message.sender_address, "updated_at": now},
            "$setOnInsert": {"user_id": current_user.id, "sender_domain": domain, "created_at": now},
        }
        try:
            previous = await block_collection.find_one_and_update(query, update, upsert=True, return_document=ReturnDocument.BEFORE)
        except DuplicateKeyError:
            previous = await block_collection.find_one_and_update(query, update, upsert=False, return_document=ReturnDocument.BEFORE)
        counts = await self._apply_reputation_delta(domain, block_delta=1 if previous is None else 0)
        return {"sender_domain": domain, "sender_blocked": True, "new_block": previous is None, **counts}

    async def unblock_domain(self, current_user: db_user_model, sender_address: str) -> dict:
        domain = self.sender_domain(sender_address)
        result = await self._engine.get_collection(db_sender_block_model).delete_one({"user_id": current_user.id, "sender_domain": domain})
        counts = await self._apply_reputation_delta(domain, block_delta=-1 if result.deleted_count > 0 else 0)
        return {"sender_domain": domain, "sender_blocked": False, "removed": result.deleted_count > 0, **counts}

    async def is_domain_blocked_for_user(self, user_id, sender_address: str) -> bool:
        domain = self.sender_domain(sender_address)
        personal_block, reputation = await asyncio.gather(
            self._engine.get_collection(db_sender_block_model).find_one({"user_id": user_id, "sender_domain": domain}, {"_id": 1}),
            self._engine.get_collection(db_domain_reputation_model).find_one({"sender_domain": domain, "is_blocked": True}, {"_id": 1}),
        )
        return bool(personal_block or reputation)
