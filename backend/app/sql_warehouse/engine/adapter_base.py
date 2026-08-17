from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]
    rows_returned: int
    bytes_scanned: int
    duration_ms: int
    engine_query_id: str | None = None
    query_analysis: dict[str, Any] | None = None


class EngineAdapter(ABC):
    @abstractmethod
    async def execute(
        self,
        sql: str,
        query_id: str,
        timeout_sec: int,
        max_threads: int | None,
        max_memory_mb: int | None,
        setup_sql: list[str] | None = None,
    ) -> QueryResult:
        ...

    @abstractmethod
    async def cancel(self, engine_query_id: str) -> None:
        ...

    @abstractmethod
    async def explain(self, sql: str) -> str:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...

