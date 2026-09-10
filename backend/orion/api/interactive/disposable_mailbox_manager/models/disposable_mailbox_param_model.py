from pydantic import BaseModel


class GenerateDisposableMailboxRequest(BaseModel):
    identity_signature: str
    pgp_key_id: str | None = None

class DeleteDisposableMailboxRequest(BaseModel):
    keep_pgp: bool = False
