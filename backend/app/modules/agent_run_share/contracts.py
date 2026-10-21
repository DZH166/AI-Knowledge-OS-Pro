from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CreateShareLink:
    run_id: str
    expires_in_days: int = 7


@dataclass(frozen=True, slots=True)
class RevokeShareLink:
    token: str


@dataclass(frozen=True, slots=True)
class GetSharedRunTrace:
    token: str
    now: datetime | None = None


@dataclass(frozen=True, slots=True)
class ShareLinkReceipt:
    token: str
    url_path: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class RevokeShareReceipt:
    revoked: bool


ShareCommand = CreateShareLink | RevokeShareLink
