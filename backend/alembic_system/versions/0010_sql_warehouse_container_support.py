"""Add is_default, runtime_id, and endpoint_url to sql_warehouse_warehouses table.

Revision ID: 0010_sql_warehouse_container_support
Revises: 0009_agent_runtime_sessions
Create Date: 2026-10-21
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0010_sql_warehouse_container_support"
down_revision: Union[str, None] = "0009_agent_runtime_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # Table is in "compute" schema if supported, or public/default
    schema_name = "compute" if "compute" in insp.get_schema_names() else None
    table_name = "sql_warehouse_warehouses"
    
    # Check if table exists
    existing_tables = insp.get_table_names(schema=schema_name)
    if table_name not in existing_tables:
        schema_name = None
        existing_tables = insp.get_table_names()
    
    if table_name in existing_tables:
        existing_cols = [c["name"] for c in insp.get_columns(table_name, schema=schema_name)]
        if "is_default" not in existing_cols:
            op.add_column(
                table_name,
                sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
                schema=schema_name,
            )
            op.create_index(
                "ix_sql_warehouse_is_default",
                table_name,
                ["is_default"],
                schema=schema_name,
            )
        if "runtime_id" not in existing_cols:
            op.add_column(
                table_name,
                sa.Column("runtime_id", sa.String(length=255), nullable=True),
                schema=schema_name,
            )
        if "endpoint_url" not in existing_cols:
            op.add_column(
                table_name,
                sa.Column("endpoint_url", sa.String(length=255), nullable=True),
                schema=schema_name,
            )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    schema_name = "compute" if "compute" in insp.get_schema_names() else None
    table_name = "sql_warehouse_warehouses"
    existing_tables = insp.get_table_names(schema=schema_name)
    if table_name not in existing_tables:
        schema_name = None
        existing_tables = insp.get_table_names()

    if table_name in existing_tables:
        existing_cols = [c["name"] for c in insp.get_columns(table_name, schema=schema_name)]
        if "endpoint_url" in existing_cols:
            op.drop_column(table_name, "endpoint_url", schema=schema_name)
        if "runtime_id" in existing_cols:
            op.drop_column(table_name, "runtime_id", schema=schema_name)
        if "is_default" in existing_cols:
            op.drop_index("ix_sql_warehouse_is_default", table_name=table_name, schema=schema_name)
            op.drop_column(table_name, "is_default", schema=schema_name)
