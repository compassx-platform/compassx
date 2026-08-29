from types import SimpleNamespace

import pytest

from app.agents.services.agent.tools.platform.notebooks.notebook_manager_tool import NotebookManagerTool
from app.agents.services.agent.tools.platform.notebooks.operations import execute_notebook_manager_operation
from app.agents.services.agent.tools.registry import get_tool_definitions
from app.nova.services import notebook_tools


def test_notebook_manager_tool_definition_registered():
    definitions = get_tool_definitions(["notebook_manager"])

    assert len(definitions) == 1
    function = definitions[0]["function"]
    assert function["name"] == "notebook_manager"
    assert "get_cell_output" in function["parameters"]["properties"]["operation"]["enum"]
    assert "read_notebook" in function["parameters"]["properties"]["operation"]["enum"]
    assert "edit_cell" in function["parameters"]["properties"]["operation"]["enum"]
    assert "add_multiple_cells" in function["parameters"]["properties"]["operation"]["enum"]
    assert "create_notebook" in function["parameters"]["properties"]["operation"]["enum"]


def test_unknown_operation_returns_tool_error():
    result = NotebookManagerTool().execute(
        {"operation": "delete_notebook", "payload": {}},
        agent=SimpleNamespace(created_by="tester"),
        db=SimpleNamespace(),
    )

    assert result.ok is False
    assert "Unsupported notebook_manager operation" in result.error
    assert result.result["operation"] == "delete_notebook"


def test_payload_must_be_object():
    result = NotebookManagerTool().execute(
        {"operation": "list_imports", "payload": "bad"},
        agent=SimpleNamespace(created_by="tester"),
        db=SimpleNamespace(),
    )

    assert result.ok is False
    assert result.error == "payload must be an object"


def test_get_cell_output_dispatch_uses_notebook_context():
    result = execute_notebook_manager_operation(
        operation="get_cell_output",
        payload={"cell_index": 1},
        context={
            "notebook_id": "nb-1",
            "cells": [
                {"index": 0, "output": "first"},
                {"index": 1, "output": "answer"},
            ],
        },
    )

    assert result["ok"] is True
    assert result["operation"] == "get_cell_output"
    assert result["resource_id"] == "nb-1"
    assert result["data"] == {"cell_index": 1, "output": "answer"}


def test_get_cell_output_dispatch_uses_nested_nova_notebook_context():
    result = execute_notebook_manager_operation(
        operation="get_cell_output",
        payload={"cell_index": 2},
        context={
            "notebook": {
                "notebook_path": "analysis.ipynb",
                "cell_states": [
                    {"cell_index": 0, "output": "first"},
                    {"cell_index": 1, "output": "second"},
                    {"cell_index": 2, "output": "chart"},
                ],
            },
        },
    )

    assert result["ok"] is True
    assert result["resource_id"] == "analysis.ipynb"
    assert result["data"] == {"cell_index": 2, "output": "chart"}


def test_edit_cell_returns_approval_required_replace_request():
    result = execute_notebook_manager_operation(
        operation="edit_cell",
        payload={
            "cell_index": 1,
            "cell_type": "code",
            "code": "df.head()",
            "explanation": "Show the first rows.",
        },
        context={
            "path": "analysis.ipynb",
            "cell_states": [
                {"cell_index": 0},
                {"cell_index": 1},
            ],
        },
    )

    assert result["ok"] is True
    assert result["operation"] == "edit_cell"
    assert result["data"] == {
        "action": "replace_cell",
        "cell_index": 1,
        "cell_type": "code",
        "code": "df.head()",
        "explanation": "Show the first rows.",
        "requires_approval": False,
    }


def test_edit_cell_uses_nested_nova_notebook_context():
    result = execute_notebook_manager_operation(
        operation="edit_cell",
        payload={
            "cell_index": 2,
            "cell_type": "code",
            "code": "fig.update_layout(height=420)",
        },
        context={
            "notebook": {
                "notebook_path": "analysis.ipynb",
                "cell_states": [
                    {"cell_index": 0},
                    {"cell_index": 1},
                    {"cell_index": 2},
                ],
            },
        },
    )

    assert result["ok"] is True
    assert result["resource_id"] == "analysis.ipynb"
    assert result["data"]["action"] == "replace_cell"
    assert result["data"]["cell_index"] == 2


def test_edit_cell_rejects_missing_cell():
    result = execute_notebook_manager_operation(
        operation="edit_cell",
        payload={"cell_index": 3, "code": "df.head()"},
        context={"cells": [{"index": 0}]},
    )

    assert result["ok"] is False
    assert "Cell 3 not found" in result["error"]


def test_add_multiple_cells_returns_approval_required_insert_request():
    result = execute_notebook_manager_operation(
        operation="add_multiple_cells",
        payload={
            "insert_after_cell_index": 0,
            "explanation": "Add setup and preview cells.",
            "cells": [
                {
                    "cell_type": "markdown",
                    "code": "## Load data",
                    "explanation": "Introduce the section.",
                },
                {
                    "cell_type": "code",
                    "code": "df.head()",
                    "explanation": "Preview rows.",
                },
            ],
        },
        context={"cell_states": [{"cell_index": 0}]},
    )

    assert result["ok"] is True
    assert result["operation"] == "add_multiple_cells"
    assert result["data"] == {
        "action": "add_cells",
        "insert_after_cell_index": 0,
        "cells": [
            {
                "cell_type": "markdown",
                "code": "## Load data",
                "explanation": "Introduce the section.",
            },
            {
                "cell_type": "code",
                "code": "df.head()",
                "explanation": "Preview rows.",
            },
        ],
        "explanation": "Add setup and preview cells.",
        "requires_approval": False,
    }


def test_add_multiple_cells_rejects_empty_cells():
    result = execute_notebook_manager_operation(
        operation="add_multiple_cells",
        payload={"cells": []},
        context={},
    )

    assert result["ok"] is False
    assert "cells must be a non-empty list" in result["error"]

def test_add_multiple_cells_allows_insert_into_empty_notebook_with_negative_index():
    result = execute_notebook_manager_operation(
        operation="add_multiple_cells",
        payload={
            "insert_after_cell_index": -1,
            "explanation": "Insert a first cell into an empty notebook.",
            "cells": [
                {
                    "cell_type": "code",
                    "code": "print('Hello from generate_scada_synthetic notebook')",
                    "explanation": "Add a simple dummy code cell to the notebook.",
                }
            ],
        },
        context={"cells": []},
    )

    assert result["ok"] is True
    assert result["data"] == {
        "action": "add_cells",
        "insert_after_cell_index": None,
        "cells": [
            {
                "cell_type": "code",
                "code": "print('Hello from generate_scada_synthetic notebook')",
                "explanation": "Add a simple dummy code cell to the notebook.",
            }
        ],
        "explanation": "Insert a first cell into an empty notebook.",
        "requires_approval": False,
    }


class FakeNotebookFs:
    def __init__(self, content: str):
        self.content = content
        self.last_bucket = None
        self.last_key = None

    def exists(self, bucket: str, key: str) -> bool:
        self.last_bucket = bucket
        self.last_key = key
        return True

    def read_text(self, bucket: str, key: str) -> str:
        self.last_bucket = bucket
        self.last_key = key
        return self.content


def test_read_notebook_returns_reference_cells(monkeypatch: pytest.MonkeyPatch):
    fs = FakeNotebookFs(
        """
        {
          "metadata": {"kernelspec": {"name": "python3"}},
          "cells": [
            {"cell_type": "markdown", "source": ["# Reference\\n"], "metadata": {}},
            {
              "cell_type": "code",
              "source": ["import pandas as pd\\n", "df.head()"],
              "metadata": {},
              "outputs": [{"output_type": "stream", "name": "stdout", "text": "ok\\n"}]
            }
          ]
        }
        """
    )
    monkeypatch.setattr(notebook_tools, "get_fs", lambda: fs)

    result = execute_notebook_manager_operation(
        operation="read_notebook",
        payload={"notebook_path": "reference.ipynb", "include_outputs": True},
        context={"path": "current.ipynb"},
    )

    assert result["ok"] is True
    assert result["data"]["notebook_path"] == "reference.ipynb"
    assert result["data"]["cell_count"] == 2
    assert result["data"]["cells"][1]["source"] == "import pandas as pd\ndf.head()"
    assert result["data"]["cells"][1]["outputs"][0]["text"] == "ok\n"
    assert fs.last_key.endswith("reference.ipynb")


def test_read_notebook_rejects_path_traversal():
    result = execute_notebook_manager_operation(
        operation="read_notebook",
        payload={"notebook_path": "../secret.ipynb"},
        context={},
    )

    assert result["ok"] is False
    assert "Invalid notebook path" in result["error"]


def test_propose_cell_edit_returns_replace_request_without_approval():
    result = execute_notebook_manager_operation(
        operation="propose_cell_edit",
        payload={
            "cell_index": 1,
            "cell_type": "code",
            "code": "df.describe()",
            "explanation": "Describe data.",
        },
        context={
            "path": "analysis.ipynb",
            "cell_states": [
                {"cell_index": 0},
                {"cell_index": 1},
            ],
        },
    )

    assert result["ok"] is True
    assert result["operation"] == "propose_cell_edit"
    assert result["data"] == {
        "action": "replace_cell",
        "cell_index": 1,
        "cell_type": "code",
        "code": "df.describe()",
        "explanation": "Describe data.",
        "requires_approval": False,
    }


def test_run_cell_requests_frontend_execution_when_no_kernel():
    result = execute_notebook_manager_operation(
        operation="run_cell",
        payload={"cell_index": 0},
        context={
            "path": "analysis.ipynb",
            "cell_states": [
                {"cell_index": 0, "source": "print('hello')"},
            ],
        },
    )

    assert result["ok"] is True
    assert result["data"]["status"] == "execution_requested"


def test_approve_cell_edit_returns_approved():
    result = execute_notebook_manager_operation(
        operation="approve_cell_edit",
        payload={"cell_index": 1},
        context={},
    )

    assert result["ok"] is True
    assert result["data"] == {
        "cell_index": 1,
        "status": "approved",
    }


def test_reject_cell_edit_returns_rejected():
    result = execute_notebook_manager_operation(
        operation="reject_cell_edit",
        payload={"cell_index": 1},
        context={},
    )

    assert result["ok"] is True
    assert result["data"] == {
        "cell_index": 1,
        "status": "rejected",
    }


def test_get_cell_state_returns_state():
    result = execute_notebook_manager_operation(
        operation="get_cell_state",
        payload={"cell_index": 0},
        context={
            "cell_states": [
                {
                    "cell_index": 0,
                    "cell_type": "code",
                    "source": "committed code",
                    "committed_source": "old committed code",
                    "pending_source": "pending code",
                    "cell_status": "pending",
                    "output": [{"type": "stream", "text": "ok"}],
                }
            ]
        },
    )

    assert result["ok"] is True
    assert result["data"] == {
        "cell_index": 0,
        "cell_type": "code",
        "source": "committed code",
        "committed_source": "old committed code",
        "pending_source": "pending code",
        "cell_status": "pending",
        "output": [{"type": "stream", "text": "ok"}],
    }


def test_read_notebook_with_fqn_resolving(monkeypatch):
    class FakeSession:
        def query(self, model):
            class Query:
                def filter(self, *args, **kwargs):
                    return self
                def first(self):
                    return SimpleNamespace(
                        id="sch-123",
                        schema_id="sch-123",
                        catalog_name="solar_ecg",
                        schema_name="scada",
                        name="generate_scada_synthetic",
                        blob_path="generated_uuid.ipynb"
                    )
            return Query()
        def close(self):
            pass

    monkeypatch.setattr(
        "app.database.AccountSessionLocal",
        FakeSession,
    )

    async def fake_read_notebook_content(db, schema, blob_path):
        return {
            "metadata": {},
            "cells": [
                {"cell_type": "code", "source": "print('hello')", "metadata": {}}
            ]
        }

    monkeypatch.setattr(
        "app.catalog.service._read_notebook_content",
        fake_read_notebook_content,
    )

    result = execute_notebook_manager_operation(
        operation="read_notebook",
        payload={
            "notebook_path": "solar_ecg.scada.generate_scada_synthetic",
            "include_outputs": False,
        },
        context={},
    )

    assert result["ok"] is True
    assert result["data"]["notebook_path"] == "solar_ecg.scada.generate_scada_synthetic"
    assert result["data"]["cells"][0]["source"] == "print('hello')"
