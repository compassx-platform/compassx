# Backend Architecture

The CompassX backend is built on **FastAPI**, **SQLAlchemy (Async)**, **Alembic**, and **Pydantic v2**.

---

## Directory Structure

```
backend/
├── app/
│   ├── api/              # API router definitions & endpoint handlers
│   ├── core/             # Application config, security, and logging
│   ├── db/               # Database engine, session maker, base models
│   ├── models/           # SQLAlchemy ORM entity models
│   ├── schemas/          # Pydantic validation & serialization schemas
│   └── services/         # Core business logic layer
├── alembic_system/       # System database migrations
├── alembic_account/      # Tenant / Account database migrations
├── compassx/             # Core library & CLI interface
└── tests/                # Automated pytest unit & integration tests
```

---

## Testing

Run backend automated test suites with `pytest`:

```bash
pytest
```
