from pydantic import BaseModel


class GenerateDisposableMailboxRequest(BaseModel):
    pgp_key_id: str | None = None


class DeleteDisposableMailboxRequest(BaseModel):
    keep_pgp: bool = False
