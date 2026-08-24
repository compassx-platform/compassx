# Database Migrations

CompassX manages dual database migration schemas using **Alembic**:

---

## Migration Schemas

1. **System Schema (`alembic_system`)**: Platform-wide configuration, tenant registry, and system metrics.
2. **Account Schema (`alembic_account`)**: Workspace data, tables, user catalogs, and vector stores.

---

## Running Migrations

=== "Upgrade System Schema"
    ```bash
    alembic -c alembic_system.ini upgrade head
    ```

=== "Upgrade Account Schema"
    ```bash
    alembic -c alembic_account.ini upgrade head
    ```
