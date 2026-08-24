# API & Code Reference

CompassX provides programmatic APIs and internal Python modules for extending compute tasks, managing workspaces, and connecting external agents.

---

## Interactive API Documentation

When the backend is running locally, access the interactive OpenAPI documentation directly:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON Schema**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## Core Python Package Reference

The `compassx` Python package provides the CLI tooling and helper libraries for interacting with the platform.

### CLI Package Structure

- `compassx.cli.main`: Root CLI entrypoint and argument parser.
- `compassx.client`: REST client for interacting with CompassX services.

> [!NOTE]
> Detailed inline code docstrings are rendered automatically as modules are decorated with docstrings across the codebase.
