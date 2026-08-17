from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ActiveStream:
    id: str
    kind: str
    status: str
    started_at: datetime
    updated_at: datetime
    agent_id: int | None = None
    session_id: int | None = None
    workspace_id: str | None = None
    user_id: str | None = None
    llm_connection_id: int | None = None
    context_type: str | None = None
    detail: str | None = None
    event_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    task: asyncio.Task | None = field(default=None, repr=False, compare=False)
    subscribers: list[asyncio.Queue[dict[str, Any] | None]] = field(default_factory=list, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "llm_connection_id": self.llm_connection_id,
            "context_type": self.context_type,
            "detail": self.detail,
            "event_count": self.event_count,
            "metadata": self.metadata,
        }


class StreamRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._streams: dict[str, ActiveStream] = {}

    def start(
        self,
        *,
        kind: str,
        agent_id: int | None = None,
        session_id: int | None = None,
        workspace_id: str | None = None,
        user_id: str | None = None,
        llm_connection_id: int | None = None,
        context_type: str | None = None,
        detail: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        stream_id = str(uuid4())
        now = _now()
        stream = ActiveStream(
            id=stream_id,
            kind=kind,
            status="running",
            started_at=now,
            updated_at=now,
            agent_id=agent_id,
            session_id=session_id,
            workspace_id=workspace_id,
            user_id=user_id,
            llm_connection_id=llm_connection_id,
            context_type=context_type,
            detail=detail,
            metadata=metadata or {},
        )
        with self._lock:
            self._streams[stream_id] = stream
        return stream_id

    def touch(self, stream_id: str, *, status: str | None = None, detail: str | None = None) -> None:
        with self._lock:
            stream = self._streams.get(stream_id)
            if not stream:
                return
            stream.updated_at = _now()
            stream.event_count += 1
            if status:
                stream.status = status
            if detail:
                stream.detail = detail

    def finish(self, stream_id: str) -> None:
        with self._lock:
            stream = self._streams.pop(stream_id, None)
            subscribers = list(stream.subscribers) if stream else []
        for queue in subscribers:
            queue.put_nowait(None)

    def set_task(self, stream_id: str, task: asyncio.Task) -> None:
        with self._lock:
            stream = self._streams.get(stream_id)
            if stream:
                stream.task = task

    def cancel(self, stream_id: str) -> bool:
        with self._lock:
            stream = self._streams.get(stream_id)
            if not stream:
                return False
            stream.status = "cancelling"
            stream.detail = "Cancellation requested"
            stream.updated_at = _now()
            task = stream.task
        if task and not task.done():
            task.cancel()
        return True

    def exists(self, stream_id: str) -> bool:
        with self._lock:
            return stream_id in self._streams

    def subscribe(self, stream_id: str) -> asyncio.Queue[dict[str, Any] | None] | None:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        with self._lock:
            stream = self._streams.get(stream_id)
            if not stream:
                return None
            stream.subscribers.append(queue)
        return queue

    def unsubscribe(self, stream_id: str, queue: asyncio.Queue[dict[str, Any] | None]) -> None:
        with self._lock:
            stream = self._streams.get(stream_id)
            if not stream:
                return
            stream.subscribers = [item for item in stream.subscribers if item is not queue]

    def publish(self, stream_id: str, event: dict[str, Any]) -> None:
        with self._lock:
            stream = self._streams.get(stream_id)
            subscribers = list(stream.subscribers) if stream else []
        for queue in subscribers:
            queue.put_nowait(event)

    def list(self, *, kind: str | None = None, agent_id: int | None = None, session_id: int | None = None, workspace_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            streams = list(self._streams.values())
        if kind:
            streams = [stream for stream in streams if stream.kind == kind]
        if agent_id is not None:
            streams = [stream for stream in streams if stream.agent_id == agent_id]
        if session_id is not None:
            streams = [stream for stream in streams if stream.session_id == session_id]
        if workspace_id is not None:
            streams = [stream for stream in streams if stream.workspace_id == workspace_id]
        return [stream.to_dict() for stream in sorted(streams, key=lambda item: item.started_at, reverse=True)]


stream_registry = StreamRegistry()
