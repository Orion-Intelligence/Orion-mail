from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator


def _normalize_domain(value: str) -> str:
    return value.strip().lower().rstrip(".")


def _normalize_mailbox_address(value: str) -> str:
    return value.strip().lower()


NormalizedDomain = Annotated[str, AfterValidator(_normalize_domain)]
NormalizedMailboxAddress = Annotated[str, AfterValidator(_normalize_mailbox_address)]
StrippedStr = Annotated[str, AfterValidator(str.strip)]
