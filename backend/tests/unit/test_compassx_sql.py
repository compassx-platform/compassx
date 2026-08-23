import os
from unittest.mock import MagicMock, patch
import httpx
import pandas as pd
import pytest

import services.compassx_sql as cx
from services.compassx_sql.client import (
    CompassXQueryError,
    CompassXSchemaError,
    write_table,
    _serialize_dataframe,
)


def test_serialize_dataframe():
    df = pd.DataFrame({
        "id": [1, 2],
        "name": ["Turbine A", "Turbine B"],
        "val": [10.5, 20.0],
        "active": [True, False],
    })
    records, schema = _serialize_dataframe(df)
    assert len(records) == 2
    assert records[0] == {"id": 1, "name": "Turbine A", "val": 10.5, "active": True}
    assert schema == [
        {"name": "id", "type": "int64"},
        {"name": "name", "type": "string"},
        {"name": "val", "type": "float64"},
        {"name": "active", "type": "boolean"},
    ]


def test_write_table_missing_env(monkeypatch):
    monkeypatch.delenv("KERNEL_CATALOG_API_URL", raising=False)
    monkeypatch.delenv("CATALOG_API_URL", raising=False)
    monkeypatch.delenv("NOTEBOOK_SESSION_TOKEN", raising=False)
    monkeypatch.delenv("KERNEL_NOTEBOOK_SESSION_TOKEN", raising=False)
    monkeypatch.delenv("JUPYTER_TOKEN", raising=False)

    df = pd.DataFrame({"a": [1]})
    with pytest.raises(CompassXQueryError):
        cx.write_table(df, "nonexistent_catalog.nonexistent_schema.my_table")



def test_write_table_create_flow(monkeypatch):
    monkeypatch.setenv("KERNEL_CATALOG_API_URL", "http://test-server/api/v1/catalog")
    monkeypatch.setenv("NOTEBOOK_SESSION_TOKEN", "mock-token-123")

    df = pd.DataFrame({"turbine_id": ["T1"], "power_kw": [100.5]})

    def mock_post(url, headers, json, timeout):
        assert url == "http://test-server/api/v1/catalog/table/create"
        assert headers["Authorization"] == "Bearer mock-token-123"
        assert json["table_ref"] == "test_cat.test_sch.my_table"
        assert json["mode"] == "overwrite"
        assert len(json["data"]) == 1
        assert json["data"][0]["turbine_id"] == "T1"
        return httpx.Response(
            200,
            json={"status": "ok", "id": "tbl-uuid", "table_ref": "test_cat.test_sch.my_table", "rows_written": 1},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", mock_post)

    result = cx.write_table(df, "test_cat.test_sch.my_table", mode="overwrite")
    assert result["status"] == "ok"
    assert result["rows_written"] == 1


def test_write_table_append_flow(monkeypatch):
    monkeypatch.setenv("KERNEL_CATALOG_API_URL", "http://test-server/api/v1/catalog")
    monkeypatch.setenv("NOTEBOOK_SESSION_TOKEN", "mock-token-123")

    df = pd.DataFrame({"turbine_id": ["T2"], "power_kw": [120.0]})

    def mock_post(url, headers, json, timeout):
        assert url == "http://test-server/api/v1/catalog/table/write"
        assert headers["Authorization"] == "Bearer mock-token-123"
        assert json["table_ref"] == "test_cat.test_sch.my_table"
        assert json["mode"] == "append"
        assert len(json["data"]) == 1
        return httpx.Response(
            200,
            json={"status": "ok", "table_ref": "test_cat.test_sch.my_table", "rows_written": 1, "execution_ms": 15},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", mock_post)

    result = cx.write_table(df, "test_cat.test_sch.my_table", mode="append")
    assert result["status"] == "ok"
    assert result["rows_written"] == 1


def test_write_table_schema_mismatch_error(monkeypatch):
    monkeypatch.setenv("KERNEL_CATALOG_API_URL", "http://test-server/api/v1/catalog")
    monkeypatch.setenv("NOTEBOOK_SESSION_TOKEN", "mock-token-123")

    df = pd.DataFrame({"turbine_id": ["T2"]})  # Missing power_kw

    def mock_post(url, headers, json, timeout):
        return httpx.Response(
            422,
            json={
                "status": "error",
                "error_type": "schema_mismatch",
                "message": "Schema mismatch for table 'test_cat.test_sch.my_table'.",
                "details": {
                    "missing_columns": ["power_kw"],
                    "extra_columns": [],
                    "type_mismatches": [],
                },
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", mock_post)

    with pytest.raises(CompassXSchemaError) as exc_info:
        cx.write_table(df, "test_cat.test_sch.my_table", mode="append")

    err = exc_info.value
    assert "Schema mismatch" in str(err)
    assert err.details["missing_columns"] == ["power_kw"]


def test_dataframe_method_binding(monkeypatch):
    monkeypatch.setenv("KERNEL_CATALOG_API_URL", "http://test-server/api/v1/catalog")
    monkeypatch.setenv("NOTEBOOK_SESSION_TOKEN", "mock-token-123")

    df = pd.DataFrame({"x": [10]})

    def mock_post(url, headers, json, timeout):
        return httpx.Response(
            200,
            json={"status": "ok", "table_ref": "main.default.df_table", "rows_written": 1},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", mock_post)

    res = df.write_table("main.default.df_table", mode="overwrite")
    assert res["status"] == "ok"
