from datetime import UTC, datetime

from bson.errors import InvalidId
from fastapi import HTTPException, status
from odmantic import ObjectId
from odmantic.query import and_, or_

from orion.api.interactive.disposable_mailbox_manager.disposable_mailbox_manager import disposable_mailbox_manager
from orion.api.interactive.e2e_key_manager.e2e_key_manager import e2e_key_manager
from orion.api.interactive.messenger_manager.messenger_enums import MESSENGER_TEXT
from orion.api.interactive.messenger_manager.models.messenger_param_model import MessengerSendRequest
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_messenger_conversation_model import db_messenger_conversation_model
from orion.services.mongo_manager.shared_model.db_messenger_message_model import db_messenger_message_model
from orion.services.mongo_manager.shared_model.db_pgp_key_model import PGP_KEY_TYPE, db_pgp_key_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


class messenger_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if messenger_manager.__instance is None:
            messenger_manager()
        return messenger_manager.__instance

    def __init__(self):
        if messenger_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        messenger_manager.__instance = self
        self._engine = mongo_controller.get_instance().get_engine()

    async def list_users(self, current_user: db_user_model, query: str = "", limit: int = 100, offset: int = 0) -> list[dict]:
        search = query.strip().lower()

        mailboxes = await self._engine.find(db_mailbox_model, db_mailbox_model.is_active == True)
        users: list[dict] = []

        for mailbox in mailboxes:
            if mailbox.user_id == current_user.id:
                continue

            user = await self._engine.find_one(db_user_model, db_user_model.id == mailbox.user_id)

            if user is None:
                continue

            pgp_key = await self.get_original_pgp_key(user, mailbox, ensure_create=True)

            user_data = self.user_response(user, mailbox, pgp_key)

            searchable = " ".join([
                user_data["full_name"],
                user_data["username"],
                user_data["mailbox_address"],
            ]).lower()

            if search and search not in searchable:
                continue

            users.append(user_data)

        users.sort(key=lambda item: (
            item["full_name"].lower() if item["full_name"] else item["mailbox_address"].lower(),
            item["mailbox_address"].lower(),
        ))

        return users[offset:offset + limit]

    async def list_conversations(self, current_user: db_user_model) -> list[dict]:
        await self.get_user_mailbox(current_user)

        conversations = await self._engine.find(
            db_messenger_conversation_model,
            or_(
                db_messenger_conversation_model.user_a_id == current_user.id,
                db_messenger_conversation_model.user_b_id == current_user.id,
            ),
        )

        conversations.sort(key=lambda item: item.last_message_at or item.updated_at, reverse=True)

        results: list[dict] = []

        for conversation in conversations:
            results.append(
                await self.conversation_response(
                    conversation=conversation,
                    current_user=current_user,
                )
            )

        return results

    async def get_messages(self, current_user: db_user_model, other_user_id: str) -> list[dict]:
        current_mailbox = await self.get_user_mailbox(current_user)

        other_user = await self.get_user_by_id(other_user_id)
        other_mailbox = await self.get_user_mailbox(other_user)

        conversation = await self.find_conversation(current_mailbox, other_mailbox)

        if conversation is None:
            return []

        messages = await self._engine.find(db_messenger_message_model, db_messenger_message_model.conversation_id == conversation.id)

        messages.sort(key=lambda item: item.created_at)

        now = datetime.now(UTC)
        results: list[dict] = []

        for message in messages:
            if message.receiver_user_id == current_user.id and message.read_at is None:
                message.read_at = now
                message.updated_at = now
                await self._engine.save(message)

            results.append(
                self.message_response(
                    message=message,
                    current_user=current_user,
                )
            )

        return results

    async def send_message(self, current_user: db_user_model, request: MessengerSendRequest) -> dict:
        receiver_user = await self.get_user_by_id(request.receiver_user_id)

        if receiver_user.id == current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot send a chat message to yourself")

        sender_mailbox = await self.get_user_mailbox(current_user)
        receiver_mailbox = await self.get_user_mailbox(receiver_user)

        conversation = await self.get_or_create_conversation(
            current_user=current_user,
            receiver_user=receiver_user,
            sender_mailbox=sender_mailbox,
            receiver_mailbox=receiver_mailbox,
        )

        sender_e2e_key = await e2e_key_manager.get_instance().get_mailbox_key(sender_mailbox)
        receiver_e2e_key = await e2e_key_manager.get_instance().get_mailbox_key(receiver_mailbox)

        if sender_e2e_key is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Set up your encryption key before sending chat messages")
        if receiver_e2e_key is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This person has not set up encrypted mail yet, so they cannot receive chat messages")
        if not e2e_key_manager.is_e2e_body(request.body):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chat messages must be end-to-end encrypted")

        message = await self._engine.save(
            db_messenger_message_model(
                conversation_id=conversation.id,
                sender_user_id=current_user.id,
                receiver_user_id=receiver_user.id,
                sender_mailbox_id=sender_mailbox.id,
                receiver_mailbox_id=receiver_mailbox.id,
                encrypted_for_sender=request.body,
                encrypted_for_receiver=request.body,
                sender_key_fingerprint=sender_e2e_key.fingerprint,
                receiver_key_fingerprint=receiver_e2e_key.fingerprint,
            )
        )

        conversation.last_message_id = message.id
        conversation.last_message_at = message.created_at
        conversation.updated_at = datetime.now(UTC)
        await self._engine.save(conversation)

        return self.message_response(message=message, current_user=current_user)

    async def get_user_by_id(self, user_id: str) -> db_user_model:
        try:
            parsed_id = ObjectId(user_id)
        except (InvalidId, ValueError, TypeError) as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id") from error

        user = await self._engine.find_one(db_user_model, db_user_model.id == parsed_id)

        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        return user

    async def get_user_mailbox(self, user: db_user_model) -> db_mailbox_model:
        mailbox = await self._engine.find_one(db_mailbox_model, db_mailbox_model.user_id == user.id)

        if mailbox is None or not mailbox.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User mailbox not found")

        return mailbox

    async def get_original_pgp_key(self, user: db_user_model, mailbox: db_mailbox_model, ensure_create: bool) -> db_pgp_key_model:
        pgp_key = await self._engine.find_one(
            db_pgp_key_model,
            and_(
                db_pgp_key_model.user_id == user.id,
                db_pgp_key_model.owner_mailbox_id == mailbox.id,
                db_pgp_key_model.key_type == PGP_KEY_TYPE.ORIGINAL,
            ),
        )

        if pgp_key is not None:
            return pgp_key

        if ensure_create:
            return await disposable_mailbox_manager.get_instance().get_or_create_original_pgp(user, mailbox)

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User public key not found")

    async def find_conversation(self, mailbox_a: db_mailbox_model, mailbox_b: db_mailbox_model) -> db_messenger_conversation_model | None:
        conversation_key = self.build_conversation_key(mailbox_a.id, mailbox_b.id)

        return await self._engine.find_one(db_messenger_conversation_model, db_messenger_conversation_model.conversation_key == conversation_key)

    async def get_or_create_conversation(self, current_user: db_user_model, receiver_user: db_user_model, sender_mailbox: db_mailbox_model, receiver_mailbox: db_mailbox_model) -> db_messenger_conversation_model:
        existing = await self.find_conversation(sender_mailbox, receiver_mailbox)

        if existing is not None:
            return existing

        first, second = sorted(
            [
                {
                    "user": current_user,
                    "mailbox": sender_mailbox,
                },
                {
                    "user": receiver_user,
                    "mailbox": receiver_mailbox,
                },
            ],
            key=lambda item: str(item["mailbox"].id),
        )

        return await self._engine.save(
            db_messenger_conversation_model(
                conversation_key=self.build_conversation_key(sender_mailbox.id, receiver_mailbox.id),
                user_a_id=first["user"].id,
                user_b_id=second["user"].id,
                user_a_mailbox_id=first["mailbox"].id,
                user_b_mailbox_id=second["mailbox"].id,
                user_a_address=first["mailbox"].mailbox_address,
                user_b_address=second["mailbox"].mailbox_address,
            )
        )

    async def conversation_response(self, conversation: db_messenger_conversation_model, current_user: db_user_model) -> dict:
        other_user_id = conversation.user_b_id if conversation.user_a_id == current_user.id else conversation.user_a_id

        other_user = await self._engine.find_one(db_user_model, db_user_model.id == other_user_id)

        if other_user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation user not found")

        other_mailbox = await self.get_user_mailbox(other_user)
        other_pgp_key = await self.get_original_pgp_key(other_user, other_mailbox, ensure_create=True)

        messages = await self._engine.find(db_messenger_message_model, db_messenger_message_model.conversation_id == conversation.id)

        latest_message = max(messages, key=lambda item: item.created_at) if messages else None
        latest_body = ""

        if latest_message is not None:
            latest_body = self.stored_body_for_user(
                message=latest_message,
                current_user=current_user,
            )

        unread_count = len([
            message for message in messages
            if message.receiver_user_id == current_user.id and message.read_at is None
        ])

        return {
            "id": str(conversation.id),
            "other_user": self.user_response(other_user, other_mailbox, other_pgp_key),
            "last_message": latest_body,
            "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None,
            "unread_count": unread_count,
        }

    def message_response(self, message: db_messenger_message_model, current_user: db_user_model) -> dict:
        body = self.stored_body_for_user(message=message, current_user=current_user)

        return {
            "id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "sender_user_id": str(message.sender_user_id),
            "receiver_user_id": str(message.receiver_user_id),
            "direction": "sent" if message.sender_user_id == current_user.id else "received",
            "body": body,
            "created_at": message.created_at.isoformat(),
            "read_at": message.read_at.isoformat() if message.read_at else None,
        }

    @staticmethod
    def stored_body_for_user(message: db_messenger_message_model, current_user: db_user_model) -> str:
        if message.sender_user_id == current_user.id:
            encrypted_text = message.encrypted_for_sender
        elif message.receiver_user_id == current_user.id:
            encrypted_text = message.encrypted_for_receiver
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this chat message")

        return encrypted_text if e2e_key_manager.is_e2e_body(encrypted_text) else MESSENGER_TEXT.LEGACY_CHAT

    @staticmethod
    def build_conversation_key(mailbox_a_id: ObjectId, mailbox_b_id: ObjectId) -> str:
        return ":".join(sorted([str(mailbox_a_id), str(mailbox_b_id)]))

    @staticmethod
    def user_response(user: db_user_model, mailbox: db_mailbox_model, pgp_key: db_pgp_key_model) -> dict:
        return {
            "id": str(user.id),
            "full_name": user.full_name,
            "username": user.username,
            "mailbox_address": mailbox.mailbox_address,
            "fingerprint": pgp_key.fingerprint,
            "has_public_key": True,
        }
