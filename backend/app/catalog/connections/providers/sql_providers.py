"""SQL Database Connection Providers."""

from __future__ import annotations

import time
from abc import abstractmethod
from typing import Any, List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.catalog.connections.base_provider import (
    BaseConnectionProvider,
    ConnectionFieldDefinition,
    ConnectionTestResult,
)


class BaseSqlProvider(BaseConnectionProvider):
    """Common foundation for SQL database providers."""

    @property
    def category(self) -> str:
        return "database"

    @abstractmethod
    def build_url(self, config: dict[str, Any], auth_config: Optional[dict[str, Any]] = None) -> str:
        pass

    def build_engine(
        self,
        config: dict[str, Any],
        auth_config: Optional[dict[str, Any]] = None,
    ) -> Engine:
        url = self.build_url(config, auth_config)
        connect_args: dict[str, Any] = {}
        if config.get("ssl_required") and self.type_id == "postgres":
            connect_args["sslmode"] = "require"
        return create_engine(url, connect_args=connect_args, pool_pre_ping=True)

    def test_connection(
        self,
        config: dict[str, Any],
        auth_config: Optional[dict[str, Any]] = None,
    ) -> ConnectionTestResult:
        start = time.time()
        try:
            engine = self.build_engine(config, auth_config)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            latency_ms = int((time.time() - start) * 1000)
            return ConnectionTestResult(
                success=True,
                message=f"Successfully connected to {self.name}",
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = int((time.time() - start) * 1000)
            return ConnectionTestResult(
                success=False,
                message=f"Connection failed: {str(exc)}",
                latency_ms=latency_ms,
            )


class PostgresProvider(BaseSqlProvider):
    @property
    def type_id(self) -> str:
        return "postgres"

    @property
    def name(self) -> str:
        return "PostgreSQL"

    @property
    def description(self) -> str:
        return "Connect to PostgreSQL 10+ databases with SSL and connection pooling."

    @property
    def is_popular(self) -> bool:
        return True

    @property
    def default_port(self) -> int:
        return 5432

    @property
    def config_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(
                name="host",
                label="Host",
                placeholder="cloud.databricks.com or localhost",
                help_text="Host name of the foreign server without scheme (i.e. no 'jdbc://' or 'https://' prefix).",
                required=True,
            ),
            ConnectionFieldDefinition(
                name="port",
                label="Port",
                type="number",
                default=5432,
                placeholder="5432",
                help_text="Port of the foreign postgresql instance, default to 5432.",
                required=False,
            ),
            ConnectionFieldDefinition(
                name="database",
                label="Database",
                placeholder="postgres",
                help_text="Initial database or catalog name on the foreign instance.",
                required=True,
            ),
            ConnectionFieldDefinition(
                name="ssl_required",
                label="Require SSL",
                type="boolean",
                default=False,
                help_text="Require secure SSL connection mode.",
                required=False,
            ),
        ]

    @property
    def auth_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(
                name="username",
                label="User",
                placeholder="username",
                help_text="User identity used to access the foreign instance.",
                required=True,
            ),
            ConnectionFieldDefinition(
                name="password",
                label="Password",
                type="password",
                placeholder="password123",
                help_text="Password of the foreign instance.",
                required=True,
            ),
        ]

    def build_url(self, config: dict[str, Any], auth_config: Optional[dict[str, Any]] = None) -> str:
        auth = auth_config or {}
        user = auth.get("username", "")
        pwd = auth.get("password", "")
        host = config.get("host", "localhost")
        port = config.get("port", 5432)
        db = config.get("database", "postgres")
        return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"


class MySQLProvider(BaseSqlProvider):
    @property
    def type_id(self) -> str:
        return "mysql"

    @property
    def name(self) -> str:
        return "MySQL"

    @property
    def description(self) -> str:
        return "Connect to MySQL and MariaDB databases."

    @property
    def is_popular(self) -> bool:
        return True

    @property
    def default_port(self) -> int:
        return 3306

    @property
    def config_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="host", label="Host / Server", placeholder="localhost or mysql.example.com", required=True),
            ConnectionFieldDefinition(name="port", label="Port", type="number", default=3306, required=True),
            ConnectionFieldDefinition(name="database", label="Database Name", placeholder="mydb", required=True),
        ]

    @property
    def auth_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="username", label="Username", placeholder="root", required=True),
            ConnectionFieldDefinition(name="password", label="Password", type="password", placeholder="••••••••", required=False),
        ]

    def build_url(self, config: dict[str, Any], auth_config: Optional[dict[str, Any]] = None) -> str:
        auth = auth_config or {}
        user = auth.get("username", "")
        pwd = auth.get("password", "")
        host = config.get("host", "localhost")
        port = config.get("port", 3306)
        db = config.get("database", "")
        return f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}"


class MSSQLProvider(BaseSqlProvider):
    @property
    def type_id(self) -> str:
        return "mssql"

    @property
    def name(self) -> str:
        return "Microsoft SQL Server"

    @property
    def description(self) -> str:
        return "Connect to Microsoft SQL Server and Azure SQL Database."

    @property
    def is_popular(self) -> bool:
        return True

    @property
    def default_port(self) -> int:
        return 1433

    @property
    def config_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="host", label="Host / Server", placeholder="localhost or sql.database.windows.net", required=True),
            ConnectionFieldDefinition(name="port", label="Port", type="number", default=1433, required=True),
            ConnectionFieldDefinition(name="database", label="Database Name", placeholder="master", required=True),
        ]

    @property
    def auth_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="username", label="Username", placeholder="sa", required=True),
            ConnectionFieldDefinition(name="password", label="Password", type="password", placeholder="••••••••", required=False),
        ]

    def build_url(self, config: dict[str, Any], auth_config: Optional[dict[str, Any]] = None) -> str:
        auth = auth_config or {}
        user = auth.get("username", "")
        pwd = auth.get("password", "")
        host = config.get("host", "localhost")
        port = config.get("port", 1433)
        db = config.get("database", "")
        return f"mssql+pyodbc://{user}:{pwd}@{host}:{port}/{db}?driver=ODBC+Driver+17+for+SQL+Server"


class SnowflakeProvider(BaseSqlProvider):
    @property
    def type_id(self) -> str:
        return "snowflake"

    @property
    def name(self) -> str:
        return "Snowflake"

    @property
    def description(self) -> str:
        return "Connect to Snowflake cloud data warehouse."

    @property
    def is_popular(self) -> bool:
        return True

    @property
    def config_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="account", label="Account Identifier", placeholder="xy12345.us-east-1", required=True),
            ConnectionFieldDefinition(name="warehouse", label="Warehouse", placeholder="COMPUTE_WH", required=True),
            ConnectionFieldDefinition(name="database", label="Database Name", placeholder="ANALYTICS", required=True),
            ConnectionFieldDefinition(name="schema", label="Schema", placeholder="PUBLIC", default="PUBLIC", required=False),
        ]

    @property
    def auth_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="username", label="Username", required=True),
            ConnectionFieldDefinition(name="password", label="Password", type="password", required=True),
        ]

    def build_url(self, config: dict[str, Any], auth_config: Optional[dict[str, Any]] = None) -> str:
        auth = auth_config or {}
        user = auth.get("username", "")
        pwd = auth.get("password", "")
        account = config.get("account", "")
        wh = config.get("warehouse", "")
        db = config.get("database", "")
        return f"snowflake://{user}:{pwd}@{account}/{db}?warehouse={wh}"


class SQLiteProvider(BaseSqlProvider):
    @property
    def type_id(self) -> str:
        return "sqlite"

    @property
    def name(self) -> str:
        return "SQLite"

    @property
    def description(self) -> str:
        return "Connect to a local or embedded SQLite database file."

    @property
    def is_popular(self) -> bool:
        return False

    @property
    def config_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="database", label="Database File Path", placeholder="/path/to/db.sqlite or :memory:", default=":memory:", required=True),
        ]

    @property
    def auth_fields(self) -> List[ConnectionFieldDefinition]:
        return []

    def build_url(self, config: dict[str, Any], auth_config: Optional[dict[str, Any]] = None) -> str:
        path = config.get("database", ":memory:")
        return f"sqlite:///{path}"


class OracleProvider(BaseSqlProvider):
    @property
    def type_id(self) -> str:
        return "oracle"

    @property
    def name(self) -> str:
        return "Oracle Database"

    @property
    def description(self) -> str:
        return "Connect to Oracle Enterprise Databases."

    @property
    def is_popular(self) -> bool:
        return False

    @property
    def default_port(self) -> int:
        return 1521

    @property
    def config_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="host", label="Host / Server", placeholder="oracle.example.com", required=True),
            ConnectionFieldDefinition(name="port", label="Port", type="number", default=1521, required=True),
            ConnectionFieldDefinition(name="database", label="Service Name / SID", placeholder="ORCL", required=True),
        ]

    @property
    def auth_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="username", label="Username", required=True),
            ConnectionFieldDefinition(name="password", label="Password", type="password", required=True),
        ]

    def build_url(self, config: dict[str, Any], auth_config: Optional[dict[str, Any]] = None) -> str:
        auth = auth_config or {}
        user = auth.get("username", "")
        pwd = auth.get("password", "")
        host = config.get("host", "localhost")
        port = config.get("port", 1521)
        db = config.get("database", "ORCL")
        return f"oracle+cx_oracle://{user}:{pwd}@{host}:{port}/{db}"


class BigQueryProvider(BaseSqlProvider):
    @property
    def type_id(self) -> str:
        return "bigquery"

    @property
    def name(self) -> str:
        return "Google BigQuery"

    @property
    def description(self) -> str:
        return "Connect to Google Cloud BigQuery datasets."

    @property
    def is_popular(self) -> bool:
        return False

    @property
    def config_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="project_id", label="GCP Project ID", placeholder="my-gcp-project", required=True),
            ConnectionFieldDefinition(name="dataset", label="Default Dataset", placeholder="analytics", required=False),
        ]

    @property
    def auth_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="service_account_json", label="Service Account Key JSON", type="textarea", placeholder='{"type": "service_account", ...}', required=True),
        ]

    def build_url(self, config: dict[str, Any], auth_config: Optional[dict[str, Any]] = None) -> str:
        project = config.get("project_id", "")
        return f"bigquery://{project}"


class DatabricksProvider(BaseSqlProvider):
    @property
    def type_id(self) -> str:
        return "databricks"

    @property
    def name(self) -> str:
        return "Databricks SQL"

    @property
    def description(self) -> str:
        return "Connect to Databricks SQL Warehouses and Unity Catalog."

    @property
    def is_popular(self) -> bool:
        return False

    @property
    def config_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="server_hostname", label="Server Hostname", placeholder="dbc-xxxx.cloud.databricks.com", required=True),
            ConnectionFieldDefinition(name="http_path", label="HTTP Path", placeholder="/sql/1.0/warehouses/xxxx", required=True),
            ConnectionFieldDefinition(name="catalog", label="Catalog Name", placeholder="main", required=False),
        ]

    @property
    def auth_fields(self) -> List[ConnectionFieldDefinition]:
        return [
            ConnectionFieldDefinition(name="access_token", label="Personal Access Token (PAT)", type="password", placeholder="dapi...", required=True),
        ]

    def build_url(self, config: dict[str, Any], auth_config: Optional[dict[str, Any]] = None) -> str:
        auth = auth_config or {}
        token = auth.get("access_token", "")
        host = config.get("server_hostname", "")
        path = config.get("http_path", "")
        cat = config.get("catalog", "main")
        return f"databricks://token:{token}@{host}?http_path={path}&catalog={cat}"
