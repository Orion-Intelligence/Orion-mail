from __future__ import annotations

import re

from odmantic import ObjectId


class FakeCursor:
    def __init__(self, entries):
        self.entries = list(entries)
        self.offset = 0
        self.maximum = None

    def sort(self, fields):
        field, direction = fields[0]
        self.entries.sort(key=lambda entry: entry[field], reverse=direction < 0)
        return self

    def skip(self, amount):
        self.offset = amount
        return self

    def limit(self, amount):
        self.maximum = amount
        return self

    async def to_list(self, length):
        maximum = self.maximum if self.maximum is not None else length
        entries = self.entries[self.offset:]
        return entries if maximum is None else entries[:maximum]


class FakeAddressCollection:
    def __init__(self, entries=None):
        self.entries = list(entries or [])

    async def update_one(self, query, update, upsert=False):
        entry = next((candidate for candidate in self.entries if candidate["owner_mailbox_id"] == query["owner_mailbox_id"] and candidate["email_address"] == query["email_address"]), None)
        if entry is None:
            if not upsert:
                return
            entry = dict(update["$setOnInsert"])
            entry["_id"] = ObjectId()
            entry["use_count"] = 0
            self.entries.append(entry)
        entry.update(update["$set"])
        entry["use_count"] += update["$inc"]["use_count"]

    def find(self, query, _projection=None):
        entries = [entry for entry in self.entries if entry["owner_mailbox_id"] == query["owner_mailbox_id"]]
        regex = query.get("email_address", {}).get("$regex")
        if regex:
            entries = [entry for entry in entries if re.search(regex, entry["email_address"])]
        return FakeCursor(entries)

    async def delete_many(self, query):
        stale_ids = set(query["_id"]["$in"])
        self.entries = [entry for entry in self.entries if entry["_id"] not in stale_ids]


class FakeAddressEngine:
    def __init__(self, mailbox, collection):
        self.mailbox = mailbox
        self.collection = collection

    async def find_one(self, *_args, **_kwargs):
        return self.mailbox

    def get_collection(self, _model):
        return self.collection
