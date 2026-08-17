"""Runtime metadata repository (repository pattern).

Maps stable Runtime IDs to internal infrastructure IDs and persists
runtime metadata. The infra_id never leaves the platform layer.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from compassx.models import RuntimeNotFoundError, RuntimePhase


@dataclass
class RuntimeRecord:
    runtime_id: str
    runtime_type: str
    driver: str
    infra_id: str = ""
    namespace: str = ""
    user_id: str = ""
    workspace_id: str = ""
    phase: RuntimePhase = RuntimePhase.CREATING
    spec: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RuntimeRepository(ABC):
    @abstractmethod
    def save(self, record: RuntimeRecord) -> None: ...

    @abstractmethod
    def get(self, runtime_id: str) -> RuntimeRecord: ...

    @abstractmethod
    def find(self, runtime_id: str) -> Optional[RuntimeRecord]: ...

    @abstractmethod
    def update(
        self,
        runtime_id: str,
        *,
        infra_id: str | None = None,
        phase: RuntimePhase | None = None,
    ) -> None: ...

    @abstractmethod
    def delete(self, runtime_id: str) -> None: ...

    @abstractmethod
    def list(
        self,
        *,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> list[RuntimeRecord]: ...


class InMemoryRuntimeRepository(RuntimeRepository):
    """Dict-backed repository for tests and the CLI."""

    def __init__(self) -> None:
        self._records: dict[str, RuntimeRecord] = {}

    def save(self, record: RuntimeRecord) -> None:
        self._records[record.runtime_id] = record

    def get(self, runtime_id: str) -> RuntimeRecord:
        record = self._records.get(runtime_id)
        if record is None:
            raise RuntimeNotFoundError(f"Unknown runtime: {runtime_id}")
        return record

    def find(self, runtime_id: str) -> Optional[RuntimeRecord]:
        return self._records.get(runtime_id)

    def update(
        self,
        runtime_id: str,
        *,
        infra_id: str | None = None,
        phase: RuntimePhase | None = None,
    ) -> None:
        record = self.get(runtime_id)
        if infra_id is not None:
            record.infra_id = infra_id
        if phase is not None:
            record.phase = phase
        record.updated_at = datetime.now(timezone.utc)

    def delete(self, runtime_id: str) -> None:
        self._records.pop(runtime_id, None)

    def list(
        self,
        *,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> list[RuntimeRecord]:
        records = list(self._records.values())
        if user_id is not None:
            records = [r for r in records if r.user_id == user_id]
        if workspace_id is not None:
            records = [r for r in records if r.workspace_id == workspace_id]
        return records


class SqlRuntimeRepository(RuntimeRepository):
    """SQLAlchemy-backed repository over the platform_runtimes table."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def _to_record(self, row) -> RuntimeRecord:
        return RuntimeRecord(
            runtime_id=row.runtime_id,
            runtime_type=row.runtime_type,
            driver=row.driver,
            infra_id=row.infra_id or "",
            namespace=row.namespace or "",
            user_id=row.user_id or "",
            workspace_id=row.workspace_id or "",
            phase=RuntimePhase(row.phase or RuntimePhase.UNKNOWN.value),
            spec=json.loads(row.spec_json) if row.spec_json else {},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def save(self, record: RuntimeRecord) -> None:
        from compassx.runtime.db_models import PlatformRuntime

        with self._session_factory() as session:
            row = session.get(PlatformRuntime, record.runtime_id)
            if row is None:
                row = PlatformRuntime(runtime_id=record.runtime_id)
                session.add(row)
            row.runtime_type = record.runtime_type
            row.driver = record.driver
            row.infra_id = record.infra_id
            row.namespace = record.namespace
            row.user_id = record.user_id
            row.workspace_id = record.workspace_id
            row.phase = record.phase.value
            row.spec_json = json.dumps(record.spec)
            row.created_at = record.created_at
            row.updated_at = record.updated_at
            session.commit()

    def get(self, runtime_id: str) -> RuntimeRecord:
        record = self.find(runtime_id)
        if record is None:
            raise RuntimeNotFoundError(f"Unknown runtime: {runtime_id}")
        return record

    def find(self, runtime_id: str) -> Optional[RuntimeRecord]:
        from compassx.runtime.db_models import PlatformRuntime

        with self._session_factory() as session:
            row = session.get(PlatformRuntime, runtime_id)
            return self._to_record(row) if row else None

    def update(
        self,
        runtime_id: str,
        *,
        infra_id: str | None = None,
        phase: RuntimePhase | None = None,
    ) -> None:
        from compassx.runtime.db_models import PlatformRuntime

        with self._session_factory() as session:
            row = session.get(PlatformRuntime, runtime_id)
            if row is None:
                raise RuntimeNotFoundError(f"Unknown runtime: {runtime_id}")
            if infra_id is not None:
                row.infra_id = infra_id
            if phase is not None:
                row.phase = phase.value
            row.updated_at = datetime.now(timezone.utc)
            session.commit()

    def delete(self, runtime_id: str) -> None:
        from compassx.runtime.db_models import PlatformRuntime

        with self._session_factory() as session:
            row = session.get(PlatformRuntime, runtime_id)
            if row is not None:
                session.delete(row)
                session.commit()

    def list(
        self,
        *,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> list[RuntimeRecord]:
        from compassx.runtime.db_models import PlatformRuntime

        with self._session_factory() as session:
            query = session.query(PlatformRuntime)
            if user_id is not None:
                query = query.filter(PlatformRuntime.user_id == user_id)
            if workspace_id is not None:
                query = query.filter(PlatformRuntime.workspace_id == workspace_id)
            return [self._to_record(row) for row in query.all()]
