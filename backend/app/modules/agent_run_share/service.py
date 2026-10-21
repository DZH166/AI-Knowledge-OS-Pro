from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.models.agent_run import AgentRun
from app.models.workbench import AgentRunShareLink
from app.modules.agent_control.contracts import RunTrace
from app.modules.agent_run_share.contracts import (
    CreateShareLink,
    GetSharedRunTrace,
    RevokeShareLink,
    RevokeShareReceipt,
    ShareCommand,
    ShareLinkReceipt,
)


SessionFactory = Callable[[], Session]
TraceReader = Callable[[str], RunTrace]


class SqlAgentRunShare:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        trace_reader: TraceReader,
        clock: Callable[[], datetime] | None = None,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._trace_reader = trace_reader
        self._clock = clock or (lambda: datetime.now(UTC))
        self._token_factory = token_factory or (lambda: secrets.token_hex(32))

    def submit(self, command: ShareCommand) -> ShareLinkReceipt | RevokeShareReceipt:
        if isinstance(command, CreateShareLink):
            return self._create(command)
        if isinstance(command, RevokeShareLink):
            return self._revoke(command)
        raise TypeError(f"Unsupported Agent Run share command: {type(command).__name__}")

    def inspect(self, query: GetSharedRunTrace) -> RunTrace:
        moment = query.now or self._clock()
        with self._sessions() as session:
            link = session.get(AgentRunShareLink, query.token)
            expires_at = _aware(link.expires_at) if link is not None else None
            if (
                link is None
                or link.revoked_at is not None
                or expires_at is None
                or expires_at <= moment
            ):
                _not_found()
            run_id = link.run_id
        return self._trace_reader(run_id)

    def list_active(self, run_id: str) -> tuple[ShareLinkReceipt, ...]:
        with self._sessions() as session:
            if session.get(AgentRun, run_id) is None:
                raise ServiceError(code="RUN_NOT_FOUND", message="Agent run not found.", status_code=404)
            rows = session.scalars(select(AgentRunShareLink).where(
                AgentRunShareLink.run_id == run_id,
                AgentRunShareLink.revoked_at.is_(None),
                AgentRunShareLink.expires_at > self._clock(),
            ).order_by(AgentRunShareLink.created_at.desc(), AgentRunShareLink.token).limit(100)).all()
            return tuple(ShareLinkReceipt(
                token=row.token, url_path=f"/api/v1/agent-runs/shared/{row.token}",
                expires_at=_aware(row.expires_at),
            ) for row in rows)

    def _create(self, command: CreateShareLink) -> ShareLinkReceipt:
        if type(command.expires_in_days) is not int or not 1 <= command.expires_in_days <= 30:
            raise ServiceError(
                code="SHARE_LINK_EXPIRY_INVALID",
                message="Share-link expiry must be between 1 and 30 days.",
                status_code=422,
            )
        now = self._clock()
        token = self._token_factory()
        if len(token) != 64 or any(character not in "0123456789abcdefABCDEF" for character in token):
            raise RuntimeError("Share token factory returned an invalid token.")
        expires_at = now + timedelta(days=command.expires_in_days)
        with self._sessions() as session, session.begin():
            if session.get(AgentRun, command.run_id) is None:
                raise ServiceError(code="RUN_NOT_FOUND", message="Agent run not found.", status_code=404)
            session.add(
                AgentRunShareLink(
                    token=token.lower(),
                    run_id=command.run_id,
                    created_at=now,
                    expires_at=expires_at,
                )
            )
        return ShareLinkReceipt(
            token=token.lower(),
            url_path=f"/api/v1/agent-runs/shared/{token.lower()}",
            expires_at=expires_at,
        )

    def _revoke(self, command: RevokeShareLink) -> RevokeShareReceipt:
        now = self._clock()
        with self._sessions() as session, session.begin():
            link = session.get(AgentRunShareLink, command.token)
            if (
                link is None
                or link.revoked_at is not None
                or _aware(link.expires_at) <= now
            ):
                _not_found()
            link.revoked_at = now
        return RevokeShareReceipt(revoked=True)


def _not_found() -> None:
    raise ServiceError(
        code="SHARE_LINK_NOT_FOUND",
        message="Share link is invalid, expired, or revoked.",
        status_code=404,
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
