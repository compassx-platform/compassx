from app.config import settings
from app.sql_warehouse.engine.clickhouse_adapter import ClickHouseAdapter
from app.sql_warehouse.engine.duckdb_adapter import DuckDBAdapter
from app.sql_warehouse.engine.postgres_adapter import PostgresAdapter

_adapters: dict[str, object] = {}


def get_adapter(warehouse):
    key = f"{warehouse.id}:{warehouse.engine}:{warehouse.updated_at}"
    if key in _adapters:
        return _adapters[key]

    cfg = warehouse.config or {}
    if warehouse.engine == "clickhouse":
        adapter = ClickHouseAdapter(
            host=cfg.get("host", getattr(settings, "SW_CLICKHOUSE_HOST", "localhost")),
            port=cfg.get("port", getattr(settings, "SW_CLICKHOUSE_PORT", 8123)),
            user=cfg.get("user", getattr(settings, "SW_CLICKHOUSE_USER", "default")),
            password=cfg.get("password", getattr(settings, "SW_CLICKHOUSE_PASSWORD", "")),
            database=cfg.get("database", getattr(settings, "SW_CLICKHOUSE_DATABASE", "default")),
        )
    elif warehouse.engine == "duckdb":
        adapter = DuckDBAdapter(database=cfg.get("database", ":memory:"))
    elif warehouse.engine == "postgres":
        adapter = PostgresAdapter(dsn=cfg.get("dsn", settings.database_url))
    else:
        raise ValueError(f"Unknown engine: {warehouse.engine}")
    _adapters[key] = adapter
    return adapter

