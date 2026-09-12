from __future__ import annotations


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
