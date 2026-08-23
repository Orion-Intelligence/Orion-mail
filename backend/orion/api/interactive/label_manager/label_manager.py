from datetime import UTC, datetime

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from odmantic.exceptions import DuplicateKeyError
from odmantic.query import and_, asc, eq

from orion.api.interactive.label_manager.models.label_param_model import LabelCreateRequest, LabelUpdateRequest
from orion.api.interactive.message_manager.message_manager import message_manager
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_label_model import db_label_model
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


class label_manager:
    __instance = None
    MAX_LABELS_PER_USER = 100
    RESERVED_NAMES = {"all mail", "archive", "drafts", "inbox", "sent", "spam", "starred", "trash"}

    @staticmethod
    def get_instance():
        if label_manager.__instance is None:
            label_manager()
        return label_manager.__instance

    def __init__(self):
        if label_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        label_manager.__instance = self
        self._engine = mongo_controller.get_instance().get_engine()

    @staticmethod
    def clean_name(name: str) -> str:
        return " ".join(name.split())

    @classmethod
    def normalized_name(cls, name: str) -> str:
        return cls.clean_name(name).casefold()

    @classmethod
    def validate_name(cls, name: str) -> str:
        cleaned_name = cls.clean_name(name)
        if not cleaned_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Label name cannot be empty")
        if cls.normalized_name(cleaned_name) in cls.RESERVED_NAMES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This name is reserved for a system folder")
        return cleaned_name

    @staticmethod
    def parse_label_id(label_id: str) -> ObjectId:
        try:
            return ObjectId(label_id)
        except InvalidId as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid label ID") from error

    async def get_owned_label(self, current_user: db_user_model, label_id: str) -> db_label_model:
        object_id = self.parse_label_id(label_id)
        label = await self._engine.find_one(db_label_model, and_(eq(db_label_model.id, object_id), eq(db_label_model.user_id, current_user.id)))
        if label is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")
        return label

    @staticmethod
    def serialize_label(label: db_label_model, message_count: int = 0) -> dict:
        return {"id": str(label.id), "name": label.name, "color": label.color, "message_count": message_count, "created_at": label.created_at, "updated_at": label.updated_at}

    async def get_labels(self, current_user: db_user_model) -> list[dict]:
        labels = await self._engine.find(db_label_model, eq(db_label_model.user_id, current_user.id), sort=asc(db_label_model.name))
        mailbox = await self._engine.find_one(db_mailbox_model, eq(db_mailbox_model.user_id, current_user.id))
        counts: dict[ObjectId, int] = {}

        if mailbox is not None and labels:
            pipeline = [
                {"$match": {"owner_mailbox_id": mailbox.id, "folder": {"$nin": [MESSAGE_FOLDER.TRASH.value, MESSAGE_FOLDER.SPAM.value]}, "label_ids": {"$ne": []}}},
                {"$unwind": "$label_ids"},
                {"$group": {"_id": "$label_ids", "count": {"$sum": 1}}},
            ]
            count_rows = await self._engine.get_collection(db_message_model).aggregate(pipeline).to_list(length=None)
            counts = {row["_id"]: row["count"] for row in count_rows}

        return [self.serialize_label(label, counts.get(label.id, 0)) for label in labels]

    async def create_label(self, current_user: db_user_model, label_data: LabelCreateRequest) -> dict:
        existing_count = await self._engine.get_collection(db_label_model).count_documents({"user_id": current_user.id})
        if existing_count >= self.MAX_LABELS_PER_USER:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"A user can have at most {self.MAX_LABELS_PER_USER} labels")

        name = self.validate_name(label_data.name)
        label = db_label_model(user_id=current_user.id, name=name, normalized_name=self.normalized_name(name), color=label_data.color)

        try:
            await self._engine.save(label)
        except DuplicateKeyError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A label with this name already exists") from error

        return self.serialize_label(label)

    async def update_label(self, current_user: db_user_model, label_id: str, label_data: LabelUpdateRequest) -> dict:
        label = await self.get_owned_label(current_user, label_id)

        if label_data.name is not None:
            label.name = self.validate_name(label_data.name)
            label.normalized_name = self.normalized_name(label.name)
        if label_data.color is not None:
            label.color = label_data.color.lower()

        label.updated_at = datetime.now(UTC)
        try:
            await self._engine.save(label)
        except DuplicateKeyError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A label with this name already exists") from error

        return self.serialize_label(label)

    async def delete_label(self, current_user: db_user_model, label_id: str) -> dict:
        label = await self.get_owned_label(current_user, label_id)
        mailbox = await self._engine.find_one(db_mailbox_model, eq(db_mailbox_model.user_id, current_user.id))

        if mailbox is not None:
            await self._engine.get_collection(db_message_model).update_many({"owner_mailbox_id": mailbox.id, "label_ids": label.id}, {"$pull": {"label_ids": label.id}})

        await self._engine.delete(label)
        return {"message": "Label deleted successfully"}

    async def get_label_messages(self, current_user: db_user_model, label_id: str) -> dict:
        label = await self.get_owned_label(current_user, label_id)
        mailbox = await self._engine.find_one(db_mailbox_model, eq(db_mailbox_model.user_id, current_user.id))
        if mailbox is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")

        cursor = self._engine.get_collection(db_message_model).find({"owner_mailbox_id": mailbox.id, "folder": {"$nin": [MESSAGE_FOLDER.TRASH.value, MESSAGE_FOLDER.SPAM.value]}, "label_ids": label.id}).sort("created_at", -1)
        messages = [db_message_model.model_validate_doc(document) async for document in cursor]
        serialized_messages = []
        for message in messages:
            state = {"is_read": message.is_read} if message.direction == MESSAGE_DIRECTION.INCOMING else {"delivery_status": message.delivery_status}
            serialized_messages.append({**message_manager.serialize_message(message), **state})

        return {"label": self.serialize_label(label, len(serialized_messages)), "messages": serialized_messages}
