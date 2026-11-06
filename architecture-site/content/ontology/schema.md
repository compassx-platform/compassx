# Schema

An entity type is an `OntologyType` row. A relationship rule is an `OntologyTypeRelation` row: one source type, one relation name, one target type. The HTTP edge is `/api/v1/ontology/schema/types` and `/api/v1/ontology/schema/relations`.

## Seed

The first read of types or relations calls `ensure_default_seed`. An empty type table, or a legacy seed that still has `project` or `capability` and does not have `org`, is replaced. The replacement deletes edges, nodes, graphs, relations, and types, then inserts the seed. The log line is `Migrating / Seeding default ontology schema (org -> domain -> subdomain -> element)...` at info.

The system types are `org` (tier 0, hexagon), `domain` (tier 1, chip), `subdomain` (tier 2, circle), and `element` (tier 3, pad). Each is `is_system`. Containment rules are `org contains domain`, `domain contains subdomain`, and `subdomain contains element`. Peer rules on the same tier include `depends_on`, `relies_on`, `reads`, `is_similar_to`, and `relates`. Those rules are system rules too. If relations are missing but types already exist, only the relation seed is inserted. If the `default` graph or its nodes are missing, the seed graph is written without wiping types.

## Create a type

`CreateType` slugifies the id: lower case, characters other than letters, digits, `_`, and `-` become `-`, and a blank result becomes `custom-type`. A duplicate id raises `Entity type with ID '{id}' already exists.` The route turns that into HTTP 400. The new row is not a system type. Label, description, shape, radius, tier, color, and icon are stored as sent. Shape is `hexagon`, `chip`, `circle`, or `pad`. Tier is 0 through 5. Radius is 5 through 80.

## Change and delete a type

`UpdateType` raises `Entity type '{id}' not found.` when the id is missing. The route turns that `KeyError` into HTTP 404. A system type refuses a tier change with `System type '{id}' is protected and its hierarchy tier cannot be changed.` Other fields on a system type can still change. A custom type can change its tier.

`DeleteType` returns false when the id is missing, and the route answers 404 `Entity type '{id}' not found.` A system type raises `System type '{id}' is protected and cannot be deleted.` Deleting a custom type also deletes the relationship rules that point at it, because the foreign keys cascade.

## Relationship rules

`CreateTypeRelation` requires both types to exist. The relation name is stripped, lowercased, and spaces become `_`. A duplicate triple raises `Relationship rule '{source} --[{relation}]--> {target}' already exists.` A relation named `contains` is stored as hierarchical even when the request does not say so. The route's 400 body is that `ValueError` text.

`UpdateTypeRelation` refuses every system rule with `System relationship rule is protected and cannot be edited.` A missing id is HTTP 404. A custom rule can change its ends, its relation name, the hierarchical flag, and the description. The new ends must be existing types, and the new triple must not already exist.

`DeleteTypeRelation` refuses a system rule with `System relationship rule is protected and cannot be deleted.` A missing id is HTTP 404 `Relationship rule with ID '{id}' not found.`
