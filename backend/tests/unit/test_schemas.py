"""
Unit tests for Pydantic schemas

Coverage
--------
- EntityFieldCreate / EntityDefinitionCreate validation
- FormSchemaCreate / FormSchemaUpdate validation
- ConnectionCreate / ConnectionUpdate / SqlExecuteRequest validation
- ExplorerQueryRequest validation
- Edge cases: empty strings, out-of-range values, missing required fields
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.entity import (
    EntityFieldCreate,
    EntitySystemFieldCreate,
    EntityDefinitionCreate,
    EntityFieldUpdate,
    EntityDefinitionUpdate,
)
from app.schemas.form import FormSchemaCreate, FormSchemaUpdate
from app.schemas.data_catalog import (
    ConnectionCreate,
    ConnectionUpdate,
    ConnectionTestRequest,
    SqlExecuteRequest,
)
from app.schemas.explorer import ExplorerQuery as ExplorerQueryRequest


# ═══════════════════════════════════════════════════════════════════════════════
# EntityFieldCreate
# ═══════════════════════════════════════════════════════════════════════════════


class TestEntityFieldCreate:

    @pytest.mark.parametrize("field_type", [
        "string", "text", "number", "boolean", "time", "datetime", "json"
    ])
    def test_valid_field_types_accepted(self, field_type: str):
        field = EntityFieldCreate(
            field_name="my_field",
            field_type=field_type,
            is_required=False,
            is_indexed=False,
        )
        assert field.field_type == field_type

    def test_invalid_field_type_raises(self):
        with pytest.raises(ValidationError):
            EntityFieldCreate(
                field_name="my_field",
                field_type="INVALID",
                is_required=False,
                is_indexed=False,
            )

    def test_field_name_required(self):
        with pytest.raises(ValidationError):
            EntityFieldCreate(
                field_name="",
                field_type="string",
                is_required=False,
                is_indexed=False,
            )

    def test_is_required_defaults_to_false(self):
        field = EntityFieldCreate(field_name="col", field_type="string")
        assert field.is_required is False

    def test_is_indexed_defaults_to_false(self):
        field = EntityFieldCreate(field_name="col", field_type="string")
        assert field.is_indexed is False


# ═══════════════════════════════════════════════════════════════════════════════
# EntitySystemFieldCreate
# ═══════════════════════════════════════════════════════════════════════════════


class TestEntitySystemFieldCreate:

    def test_valid_system_field(self):
        sf = EntitySystemFieldCreate(
            field_name="created_at",
            field_type="datetime",
            default_value="__now__",
            system_generated=True,
            is_indexed=False,
        )
        assert sf.field_name == "created_at"
        assert sf.default_value == "__now__"
        assert sf.system_generated is True

    def test_default_value_optional(self):
        sf = EntitySystemFieldCreate(
            field_name="ref",
            field_type="string",
            system_generated=False,
            is_indexed=False,
        )
        assert sf.default_value is None

    def test_system_generated_defaults_to_false(self):
        sf = EntitySystemFieldCreate(
            field_name="ref",
            field_type="string",
            is_indexed=False,
        )
        assert sf.system_generated is False


# ═══════════════════════════════════════════════════════════════════════════════
# EntityDefinitionCreate
# ═══════════════════════════════════════════════════════════════════════════════


class TestEntityDefinitionCreate:

    def test_valid_entity_definition(self):
        ed = EntityDefinitionCreate(
            name="work_order",
            entity_type="generic",
            asset_scoped=True,
            time_based=False,
            time_series=False,
            fields=[
                EntityFieldCreate(
                    field_name="title",
                    field_type="string",
                    is_required=True,
                    is_indexed=False,
                )
            ],
            system_fields=[],
        )
        assert ed.name == "work_order"
        assert len(ed.fields) == 1

    def test_name_required(self):
        with pytest.raises(ValidationError):
            EntityDefinitionCreate(
                name="",
                entity_type="generic",
                asset_scoped=False,
                time_based=False,
                time_series=False,
                fields=[],
                system_fields=[],
            )

    @pytest.mark.parametrize("entity_type", [
        "generic", "event", "transaction", "observation", "config"
    ])
    def test_valid_entity_types(self, entity_type: str):
        ed = EntityDefinitionCreate(
            name="typed_entity",
            entity_type=entity_type,
            asset_scoped=False,
            time_based=False,
            time_series=False,
            fields=[],
            system_fields=[],
        )
        assert ed.entity_type == entity_type

    def test_fields_defaults_to_empty_list(self):
        ed = EntityDefinitionCreate(
            name="no_fields",
            entity_type="generic",
            asset_scoped=False,
            time_based=False,
            time_series=False,
        )
        assert ed.fields == []
        assert ed.system_fields == []


# ═══════════════════════════════════════════════════════════════════════════════
# EntityFieldUpdate
# ═══════════════════════════════════════════════════════════════════════════════


class TestEntityFieldUpdate:

    def test_all_fields_optional(self):
        """EntityFieldUpdate should allow partial updates (all fields optional)."""
        update = EntityFieldUpdate()
        assert update.new_field_name is None
        assert update.field_type is None
        assert update.is_required is None

    def test_rename_only(self):
        update = EntityFieldUpdate(new_field_name="new_name")
        assert update.new_field_name == "new_name"
        assert update.field_type is None

    def test_type_change_only(self):
        update = EntityFieldUpdate(field_type="number")
        assert update.field_type == "number"
        assert update.new_field_name is None

    def test_invalid_field_type_raises(self):
        with pytest.raises(ValidationError):
            EntityFieldUpdate(field_type="INVALID_TYPE")


# ═══════════════════════════════════════════════════════════════════════════════
# FormSchemaCreate
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormSchemaCreate:

    def test_valid_form_schema_create(self):
        form = FormSchemaCreate(
            form_id="my-form-001",
            entity_name="work_order",
            schema={
                "fields": [
                    {"id": "title", "type": "text", "label": "Title", "required": True}
                ]
            },
        )
        assert form.form_id == "my-form-001"
        assert form.entity_name == "work_order"

    def test_form_id_required(self):
        with pytest.raises(ValidationError):
            FormSchemaCreate(
                form_id="",
                entity_name="work_order",
                schema={"fields": []},
            )

    def test_entity_name_required(self):
        with pytest.raises(ValidationError):
            FormSchemaCreate(
                form_id="my-form",
                entity_name="",
                schema={"fields": []},
            )

    def test_schema_defaults_to_empty_dict(self):
        form = FormSchemaCreate(
            form_id="minimal-form",
            entity_name="work_order",
        )
        assert form.schema == {}


# ═══════════════════════════════════════════════════════════════════════════════
# FormSchemaUpdate
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormSchemaUpdate:

    def test_all_fields_optional(self):
        update = FormSchemaUpdate()
        assert update.entity_name is None
        assert update.schema is None

    def test_schema_only_update(self):
        update = FormSchemaUpdate(schema={"fields": []})
        assert update.schema == {"fields": []}
        assert update.entity_name is None

    def test_entity_name_only_update(self):
        update = FormSchemaUpdate(entity_name="new_entity")
        assert update.entity_name == "new_entity"
        assert update.schema is None


# ═══════════════════════════════════════════════════════════════════════════════
# ConnectionCreate
# ═══════════════════════════════════════════════════════════════════════════════


class TestConnectionCreate:

    def test_valid_connection_create(self):
        conn = ConnectionCreate(
            name="My DB",
            host="db.example.com",
            port=5432,
            username="admin",
            password="secret",
            default_database="mydb",
        )
        assert conn.name == "My DB"
        assert conn.port == 5432

    def test_name_required(self):
        with pytest.raises(ValidationError):
            ConnectionCreate(
                name="",
                host="localhost",
                port=5432,
                username="user",
                password="pass",
                default_database="db",
            )

    def test_host_required(self):
        with pytest.raises(ValidationError):
            ConnectionCreate(
                name="DB",
                host="",
                port=5432,
                username="user",
                password="pass",
                default_database="db",
            )

    def test_port_must_be_positive(self):
        with pytest.raises(ValidationError):
            ConnectionCreate(
                name="DB",
                host="localhost",
                port=0,
                username="user",
                password="pass",
                default_database="db",
            )

    def test_port_must_be_at_most_65535(self):
        with pytest.raises(ValidationError):
            ConnectionCreate(
                name="DB",
                host="localhost",
                port=65536,
                username="user",
                password="pass",
                default_database="db",
            )

    def test_default_port_is_5432(self):
        conn = ConnectionCreate(
            name="DB",
            host="localhost",
            username="user",
            password="pass",
            default_database="db",
        )
        assert conn.port == 5432

    def test_default_database_defaults_to_postgres(self):
        conn = ConnectionCreate(
            name="DB",
            host="localhost",
            username="user",
            password="pass",
        )
        assert conn.default_database == "postgres"


# ═══════════════════════════════════════════════════════════════════════════════
# ConnectionUpdate
# ═══════════════════════════════════════════════════════════════════════════════


class TestConnectionUpdate:

    def test_all_fields_optional(self):
        update = ConnectionUpdate()
        assert update.name is None
        assert update.host is None
        assert update.password is None

    def test_partial_update_name(self):
        update = ConnectionUpdate(name="New Name")
        assert update.name == "New Name"
        assert update.host is None

    def test_port_validation_in_update(self):
        with pytest.raises(ValidationError):
            ConnectionUpdate(port=99999)


# ═══════════════════════════════════════════════════════════════════════════════
# SqlExecuteRequest
# ═══════════════════════════════════════════════════════════════════════════════


class TestSqlExecuteRequest:

    def test_valid_sql_execute_request(self):
        req = SqlExecuteRequest(
            connection_id=1,
            database="mydb",
            sql="SELECT 1",
            limit=1000,
        )
        assert req.connection_id == 1
        assert req.sql == "SELECT 1"
        assert req.limit == 1000

    def test_connection_id_must_be_integer(self):
        with pytest.raises(ValidationError):
            SqlExecuteRequest(
                connection_id="not-an-int",
                database="mydb",
                sql="SELECT 1",
            )

    def test_sql_required(self):
        with pytest.raises(ValidationError):
            SqlExecuteRequest(
                connection_id=1,
                database="mydb",
                sql="",
            )

    def test_limit_defaults_to_1000(self):
        req = SqlExecuteRequest(connection_id=1, database="mydb", sql="SELECT 1")
        assert req.limit == 1000

    def test_limit_must_be_positive(self):
        with pytest.raises(ValidationError):
            SqlExecuteRequest(
                connection_id=1,
                database="mydb",
                sql="SELECT 1",
                limit=0,
            )

    def test_limit_capped_at_max(self):
        with pytest.raises(ValidationError):
            SqlExecuteRequest(
                connection_id=1,
                database="mydb",
                sql="SELECT 1",
                limit=100_001,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# ExplorerQueryRequest
# ═══════════════════════════════════════════════════════════════════════════════


class TestExplorerQueryRequest:

    def test_valid_explorer_query(self):
        req = ExplorerQueryRequest(
            dataset="breakdown_event",
            filters={},
            pagination={"page": 1, "size": 25},
        )
        assert req.dataset == "breakdown_event"
        assert req.pagination["page"] == 1

    def test_dataset_required(self):
        with pytest.raises(ValidationError):
            ExplorerQueryRequest(
                dataset="",
                filters={},
                pagination={"page": 1, "size": 25},
            )

    def test_pagination_required(self):
        with pytest.raises(ValidationError):
            ExplorerQueryRequest(
                dataset="breakdown_event",
                filters={},
            )

    def test_filters_defaults_to_empty_dict(self):
        req = ExplorerQueryRequest(
            dataset="breakdown_event",
            pagination={"page": 1, "size": 25},
        )
        assert req.filters == {}

    def test_sort_optional(self):
        req = ExplorerQueryRequest(
            dataset="breakdown_event",
            filters={},
            pagination={"page": 1, "size": 25},
            sort={"timestamp": "desc"},
        )
        assert req.sort == {"timestamp": "desc"}

    def test_sort_defaults_to_none(self):
        req = ExplorerQueryRequest(
            dataset="breakdown_event",
            filters={},
            pagination={"page": 1, "size": 25},
        )
        assert req.sort is None