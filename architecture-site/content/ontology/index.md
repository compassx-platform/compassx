# Ontology

Product module. The metamodel of entity types and allowed relationships, and the knowledge graph drawn from that metamodel.

The HTTP router is `app.ontology.routes.ontology_routes.router` at `/api/v1/ontology`. The public Python type is still `OntologyService`, imported from `app.ontology.services` and from `app.ontology.services.ontology_service`. Each classmethod forwards to one application type. Callers do not change.

## Code

- `backend/app/ontology/routes/ontology_routes.py` — HTTP edge. It calls `OntologyService` and maps `ValueError`, `KeyError`, and unexpected errors to the same status codes as before.
- `backend/app/ontology/services/ontology_service.py` — facade. Same classmethod names, including `_persist_dataset`.
- `backend/app/ontology/composition.py` — builds the logger used by the application types.
- `backend/app/ontology/models/ontology.py` and `schemas/ontology.py` — the existing ORM models and request models. There is no second domain model.
- `backend/app/ontology/services/default_seed.py` — the seed lists. They stay data, not behavior.
- `backend/app/ontology/types/application/` — list, get, create, update, and delete an entity type. `types/repository.py` holds `slugify_type_id`.
- `backend/app/ontology/relations/application/` — list, create, update, and delete a relationship rule.
- `backend/app/ontology/graph/application/` — seed, validate, parse YAML, read, replace, and edit nodes and edges.
- The map UI stays in `frontend/src/modules/ontology`. It was not split.

## Owns

`ontology_types`, `ontology_type_relations`, `ontology_graphs`, `ontology_nodes`, and `ontology_edges` on the account database. Startup in `main.py` creates those tables and calls `OntologyService.ensure_default_seed`.

## Calls

Nothing outside this module for the graph itself. The map screen calls the ontology HTTP API. A failed seed logs `Ontology default seed warning (non-fatal): %s` at warning, on the logger `app.ontology.services.ontology_service`, and does not stop the process.

## Topics

- [Schema](schema.md)
- [Knowledge graph](graph.md)
- [Map](map.md)

## Test cases

[Test cases](test-cases.md) are the end-to-end checks for this module.
