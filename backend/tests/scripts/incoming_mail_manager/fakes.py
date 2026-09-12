from __future__ import annotations


class FakeCrypto:
    def __init__(self):
        self.saved = []

    async def save_message(self, message):
        self.saved.append(message)
        return message


class FakeRawMessage:
    async def read(self):
        return b"raw-bytes"


class FakeCollection:
    def __init__(self, stored_count):
        self.stored_count = stored_count
        self.queries = []

    async def count_documents(self, query):
        self.queries.append(query)
        return self.stored_count


class FakeCapEngine:
    def __init__(self, stored_count, evictable):
        self.collection = FakeCollection(stored_count)
        self.evictable = evictable
        self.deleted = []

    def get_collection(self, _model):
        return self.collection

    async def find(self, _model, _query, sort=None, limit=None):
        return self.evictable[:limit] if limit is not None else self.evictable

    async def delete(self, instance):
        self.deleted.append(instance)


class FakeAttachmentManager:
    def __init__(self):
        self.purged_messages = []
        self.purged_raw_sources = []

    async def delete_message_attachments(self, message_id):
        self.purged_messages.append(message_id)

    async def delete_raw_source(self, stored_filename):
        self.purged_raw_sources.append(stored_filename)
