from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.agents import Agent, AgentDBConnection, DataSourceProfile, Skill
from app.jobs.models.job import Job
from app.dashboards.models.dashboard import Dashboard
from app.agents.services.agent.tools.db_explorer_tool import DatabaseExplorerTool
from app.agents.services.agent.tools.base_tool import ToolResult


@pytest.fixture
def mock_agent():
    agent = MagicMock(spec=Agent)
    agent.id = 1
    return agent


@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


@pytest.fixture
def mock_adc():
    adc = MagicMock(spec=AgentDBConnection)
    adc.db_connection_id = 42
    adc.allowed_tables = ["users", "public.orders", "products"]
    return adc


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    return engine


class TestDatabaseExplorerTool:
    def test_list_tables(self, mock_agent, mock_db, mock_adc, mock_engine):
        tool = DatabaseExplorerTool()
        with patch("app.agents.services.agent.tools.db_explorer_tool._get_adc_and_engine", return_value=(mock_adc, mock_engine)):
            result = tool.execute(
                {"operation": "list_tables", "payload": {}},
                mock_agent,
                mock_db
            )
            assert result.ok is True
            assert result.result == ["users", "public.orders", "products"]

    def test_get_table_schema_allowed(self, mock_agent, mock_db, mock_adc, mock_engine):
        tool = DatabaseExplorerTool()
        mock_inspector = MagicMock()
        mock_inspector.get_columns.return_value = [
            {"name": "id", "type": "INTEGER", "nullable": False},
            {"name": "name", "type": "VARCHAR(100)", "nullable": True}
        ]
        mock_inspector.get_pk_constraint.return_value = {"constrained_columns": ["id"]}
        mock_inspector.get_foreign_keys.return_value = []

        with patch("app.agents.services.agent.tools.db_explorer_tool._get_adc_and_engine", return_value=(mock_adc, mock_engine)), \
             patch("app.agents.services.agent.tools.db_explorer_tool.inspect", return_value=mock_inspector):
            
            result = tool.execute(
                {"operation": "get_table_schema", "payload": {"table_name": "users"}},
                mock_agent,
                mock_db
            )
            assert result.ok is True
            assert result.result["table_name"] == "users"
            assert len(result.result["columns"]) == 2
            assert result.result["primary_keys"] == ["id"]

    def test_get_table_schema_denied(self, mock_agent, mock_db, mock_adc, mock_engine):
        tool = DatabaseExplorerTool()
        with patch("app.agents.services.agent.tools.db_explorer_tool._get_adc_and_engine", return_value=(mock_adc, mock_engine)):
            result = tool.execute(
                {"operation": "get_table_schema", "payload": {"table_name": "secret_table"}},
                mock_agent,
                mock_db
            )
            assert result.ok is False
            assert "Access Denied" in result.error

    def test_list_table_relationships(self, mock_agent, mock_db, mock_adc, mock_engine):
        tool = DatabaseExplorerTool()
        mock_inspector = MagicMock()
        mock_inspector.get_foreign_keys.return_value = [
            {
                "constrained_columns": ["manager_id"],
                "referred_table": "users",
                "referred_columns": ["id"]
            }
        ]

        # Mock query return for DataSourceProfile candidate relationships
        mock_profile = MagicMock(spec=DataSourceProfile)
        mock_profile.candidate_relationships = [
            {
                "from_col": "profile_id",
                "to_table": "profiles",
                "to_col": "id",
                "overlap_ratio": 0.95
            }
        ]
        mock_db.query.return_value.filter.return_value.first.return_value = mock_profile

        with patch("app.agents.services.agent.tools.db_explorer_tool._get_adc_and_engine", return_value=(mock_adc, mock_engine)), \
             patch("app.agents.services.agent.tools.db_explorer_tool.inspect", return_value=mock_inspector):
            
            result = tool.execute(
                {"operation": "list_table_relationships", "payload": {"table_name": "users"}},
                mock_agent,
                mock_db
            )
            assert result.ok is True
            rels = result.result["relationships"]
            assert len(rels) == 2
            assert rels[0]["type"] == "declared_fk"
            assert rels[1]["type"] == "candidate_profiled"

    def test_get_data_profile(self, mock_agent, mock_db, mock_adc, mock_engine):
        tool = DatabaseExplorerTool()
        mock_profile = MagicMock(spec=DataSourceProfile)
        mock_profile.table_name = "users"
        mock_profile.row_count = 1200
        mock_profile.detected_layer = "core"
        mock_profile.unresolved_ambiguities = ["duplicate_usernames"]
        mock_profile.prior_art_references = []
        mock_profile.last_profiled_at = None

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_profile

        with patch.object(DatabaseExplorerTool, "_resolve_profile_connection_id", return_value=mock_adc.db_connection_id):
            result = tool.execute(
                {"operation": "get_data_profile", "payload": {"table_name": "users"}},
                mock_agent,
                mock_db
            )
            assert result.ok is True
            assert result.result["row_count"] == 1200
            assert result.result["unresolved_ambiguities"] == ["duplicate_usernames"]

    def test_get_column_stats(self, mock_agent, mock_db, mock_adc, mock_engine):
        tool = DatabaseExplorerTool()
        
        # Mock connection and fetch results
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # COUNT(*), COUNT(IS NULL), COUNT(DISTINCT), MIN/MAX, Top values
        mock_res_count = MagicMock()
        mock_res_count.scalar.return_value = 500
        
        mock_res_null = MagicMock()
        mock_res_null.scalar.return_value = 10
        
        mock_res_distinct = MagicMock()
        mock_res_distinct.scalar.return_value = 20
        
        mock_res_minmax = MagicMock()
        mock_res_minmax.fetchone.return_value = (1, 100)
        
        mock_res_top = MagicMock()
        mock_res_top.fetchall.return_value = [(10, 50), (20, 30)]

        mock_conn.execute.side_effect = [
            mock_res_count,
            mock_res_null,
            mock_res_distinct,
            mock_res_minmax,
            mock_res_top
        ]

        with patch("app.agents.services.agent.tools.db_explorer_tool._get_adc_and_engine", return_value=(mock_adc, mock_engine)):
            result = tool.execute(
                {"operation": "get_column_stats", "payload": {"table_name": "users", "column_name": "age"}},
                mock_agent,
                mock_db
            )
            assert result.ok is True
            assert result.result["row_count"] == 500
            assert result.result["null_count"] == 10
            assert result.result["null_rate"] == 0.02
            assert result.result["distinct_count"] == 20
            assert result.result["min"] == 1
            assert result.result["max"] == 100
            assert len(result.result["top_values"]) == 2

    def test_get_row_count_valid(self, mock_agent, mock_db, mock_adc, mock_engine):
        tool = DatabaseExplorerTool()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_res = MagicMock()
        mock_res.scalar.return_value = 42
        mock_conn.execute.return_value = mock_res

        with patch("app.agents.services.agent.tools.db_explorer_tool._get_adc_and_engine", return_value=(mock_adc, mock_engine)):
            result = tool.execute(
                {"operation": "get_row_count", "payload": {"table_name": "users", "filters": "age > 18"}},
                mock_agent,
                mock_db
            )
            assert result.ok is True
            assert result.result["row_count"] == 42
            executed_sql = str(mock_conn.execute.call_args[0][0])
            assert "WHERE age > 18" in executed_sql

    def test_get_row_count_invalid_filters(self, mock_agent, mock_db, mock_adc, mock_engine):
        tool = DatabaseExplorerTool()
        with patch("app.agents.services.agent.tools.db_explorer_tool._get_adc_and_engine", return_value=(mock_adc, mock_engine)):
            # SQL Injection attempt / forbidden keyword in filters
            result = tool.execute(
                {"operation": "get_row_count", "payload": {"table_name": "users", "filters": "1=1; DROP TABLE users"}},
                mock_agent,
                mock_db
            )
            assert result.ok is False
            assert "Invalid characters" in result.error

    def test_sample_rows_limit_cap(self, mock_agent, mock_db, mock_adc, mock_engine):
        tool = DatabaseExplorerTool()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock returned rows
        mock_row = MagicMock()
        mock_row._mapping = {"id": 1, "name": "Alice"}
        mock_conn.execute.return_value.fetchall.return_value = [mock_row]

        with patch("app.agents.services.agent.tools.db_explorer_tool._get_adc_and_engine", return_value=(mock_adc, mock_engine)):
            result = tool.execute(
                {"operation": "sample_rows", "payload": {"table_name": "users", "limit": 200}},
                mock_agent,
                mock_db
            )
            assert result.ok is True
            assert result.result["count"] == 1
            executed_sql = str(mock_conn.execute.call_args[0][0])
            assert "LIMIT 100" in executed_sql

    def test_run_query_select_only(self, mock_agent, mock_db, mock_adc, mock_engine):
        tool = DatabaseExplorerTool()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_conn.execution_options.return_value = mock_conn
        
        # Test DML rejection
        with patch("app.agents.services.agent.tools.db_explorer_tool._get_adc_and_engine", return_value=(mock_adc, mock_engine)):
            result = tool.execute(
                {"operation": "run_query", "payload": {"sql": "INSERT INTO users (name) VALUES ('Bob')"}},
                mock_agent,
                mock_db
            )
            assert result.ok is False
            assert "Only SELECT queries are allowed" in result.error

            result = tool.execute(
                {"operation": "run_query", "payload": {"sql": "SELECT * FROM users; DELETE FROM users"}},
                mock_agent,
                mock_db
            )
            assert result.ok is False
            assert "DML/DDL operations are forbidden" in result.error

    def test_run_query_table_scoping(self, mock_agent, mock_db, mock_adc, mock_engine):
        tool = DatabaseExplorerTool()
        mock_conn = MagicMock()
        mock_conn.execution_options.return_value = mock_conn
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        with patch("app.agents.services.agent.tools.db_explorer_tool._get_adc_and_engine", return_value=(mock_adc, mock_engine)):
            # "secret_table" is not in allowed_tables
            result = tool.execute(
                {"operation": "run_query", "payload": {"sql": "SELECT * FROM secret_table"}},
                mock_agent,
                mock_db
            )
            assert result.ok is False
            assert "Access Denied" in result.error

            # "users" and "products" are allowed
            mock_row = MagicMock()
            mock_row._mapping = {"id": 1}
            mock_conn.execute.return_value.fetchmany.return_value = [mock_row]

            result = tool.execute(
                {"operation": "run_query", "payload": {"sql": "SELECT * FROM users JOIN products ON users.id = products.user_id"}},
                mock_agent,
                mock_db
            )
            assert result.ok is True
            assert result.result["count"] == 1

    def test_search_workspace(self, mock_agent, mock_db, mock_adc, mock_engine):
        tool = DatabaseExplorerTool()
        
        mock_job = MagicMock(spec=Job)
        mock_job.name = "Import Users"
        mock_job.description = "Imports the users notebook"
        mock_job.job_id = "job-1"
        
        mock_dbd = MagicMock(spec=Dashboard)
        mock_dbd.id = 7
        mock_dbd.name = "Users Retention Dashboard"

        mock_sk = MagicMock(spec=Skill)
        mock_sk.name = "User Metrics calculator"
        mock_sk.description = "Calculates retention metrics"
        mock_sk.body = "code here"

        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [mock_job],
            [mock_dbd],
            [mock_sk]
        ]

        with patch("app.agents.services.agent.tools.db_explorer_tool._get_adc_and_engine", return_value=(mock_adc, mock_engine)):
            result = tool.execute(
                {"operation": "search_workspace", "payload": {"query": "users"}},
                mock_agent,
                mock_db
            )
            assert result.ok is True
            assert len(result.result) == 3
            assert result.result[0]["source_type"] == "job"
            assert result.result[1]["source_type"] == "dashboard"
            assert result.result[2]["source_type"] == "skill"

    def test_save_data_profile(self, mock_agent, mock_db, mock_adc, mock_engine):
        tool = DatabaseExplorerTool(session_id=123)
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        with patch("app.agents.services.agent.tools.db_explorer_tool._get_adc_and_engine", return_value=(mock_adc, mock_engine)):
            result = tool.execute(
                {
                    "operation": "save_data_profile",
                    "payload": {
                        "table_name": "users",
                        "row_count": 500,
                        "detected_layer": "core"
                    }
                },
                mock_agent,
                mock_db
            )
            assert result.ok is True
            assert result.result["success"] is True
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
    def test_get_data_profile_without_agent_db_connection_uses_saved_profile(self, mock_agent, mock_db):
        tool = DatabaseExplorerTool()
        mock_profile = MagicMock(spec=DataSourceProfile)
        mock_profile.connection_id = 42
        mock_profile.table_name = "users"
        mock_profile.row_count = 123
        mock_profile.detected_layer = "gold"
        mock_profile.unresolved_ambiguities = []
        mock_profile.prior_art_references = []
        mock_profile.last_profiled_at = None

        mock_profile.domain_inference = {}
        mock_profile.timeseries_profile = {}

        mock_profile_query = MagicMock()
        mock_profile_query.filter.return_value = mock_profile_query
        mock_profile_query.first.return_value = mock_profile
        mock_db.query.return_value = mock_profile_query

        with patch.object(DatabaseExplorerTool, "_resolve_profile_connection_id", return_value=42):
            result = tool.execute(
                {"operation": "get_data_profile", "payload": {"table_name": "users"}},
                mock_agent,
                mock_db,
            )

        assert result.ok is True
        assert result.result["table_name"] == "users"
        assert result.result["row_count"] == 123
        assert result.result["detected_layer"] == "gold"



