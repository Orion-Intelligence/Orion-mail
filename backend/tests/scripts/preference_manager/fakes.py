from __future__ import annotations


class FakeUserEngine:
    def __init__(self):
        self.saved = []

    async def save(self, user):
        self.saved.append(user)
        return user
