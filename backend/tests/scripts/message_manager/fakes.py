from __future__ import annotations

from bson import ObjectId

from orion.services.mongo_manager.shared_model.db_label_model import db_label_model
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import db_message_model


class FakeCrypto:
    async def save_message(self, message):
        return message

    async def decrypt_message(self, message):
        return message

    async def decrypt_messages(self, messages):
        return messages


class FakeSafety:
    def __init__(self, domain_state=None, report=None, block=None, unblock=None, report_error=None, block_error=None, unblock_error=None):
        self._domain_state = domain_state if domain_state is not None else {"reported_as": None, "globally_blocked": False, "sender_blocked": False}
        self._report = report if report is not None else {"report_type": "spam"}
        self._block = block if block is not None else {"sender_blocked": True}
        self._unblock = unblock if unblock is not None else {"sender_blocked": False}
        self._report_error = report_error
        self._block_error = block_error
        self._unblock_error = unblock_error

    async def get_domain_state(self, _user, _sender):
        return self._domain_state

    async def report_domain(self, _user, _message, _report_type):
        if self._report_error is not None:
            raise self._report_error
        return self._report

    async def block_domain(self, _user, _message):
        if self._block_error is not None:
            raise self._block_error
        return self._block

    async def unblock_domain(self, _user, _sender):
        if self._unblock_error is not None:
            raise self._unblock_error
        return self._unblock


class FakePath:
    def __init__(self, is_file=True):
        self._is_file = is_file

    def is_file(self):
        return self._is_file


class FakeAttachments:
    def __init__(self, path=None, raw=b"raw-source", raise_path=False, raise_read=False):
        self._path = path if path is not None else FakePath(is_file=True)
        self._raw = raw
        self._raise_path = raise_path
        self._raise_read = raise_read
        self.deleted_attachments: list = []
        self.deleted_sources: list = []

    def get_raw_source_path(self, _filename):
        if self._raise_path:
            raise ValueError("bad path")
        return self._path

    async def read_raw_source(self, _message, _path):
        if self._raise_read:
            raise RuntimeError("read failed")
        return self._raw

    async def delete_message_attachments(self, message_id):
        self.deleted_attachments.append(message_id)

    async def delete_raw_source(self, filename):
        self.deleted_sources.append(filename)


class FakeSpam:
    def __init__(self):
        self.spam: list = []
        self.ham: list = []

    async def learn_spam(self, raw):
        self.spam.append(raw)

    async def learn_ham(self, raw):
        self.ham.append(raw)


class FakeAggCursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, length=None):
        return self._rows


class FakeAggCollection:
    def __init__(self, rows):
        self._rows = rows

    def aggregate(self, _pipeline):
        return FakeAggCursor(self._rows)


class FakeAggEngine:
    def __init__(self, rows):
        self._rows = rows

    def get_collection(self, _model):
        return FakeAggCollection(self._rows)


class FakeUpdateCollection:
    def __init__(self, modified):
        self.modified = modified
        self.update_many_calls: list = []

    async def update_many(self, filter_query, update):
        self.update_many_calls.append((filter_query, update))
        return type("R", (), {"modified_count": self.modified})()


class FakeUpdateEngine:
    def __init__(self, modified):
        self.collection = FakeUpdateCollection(modified)

    def get_collection(self, _model):
        return self.collection


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


class FakeMailboxEngine:
    def __init__(self, addresses: list[str]):
        self.mailboxes = [db_mailbox_model(user_id=ObjectId(), mailbox_address=address) for address in addresses]

    async def find(self, *_args, **_kwargs):
        return self.mailboxes


class FakeCryptoManager:
    def __init__(self):
        self.saved = []

    async def save_message(self, message):
        self.saved.append(message)
        return message
