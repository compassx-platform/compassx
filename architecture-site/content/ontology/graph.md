# Knowledge graph

A graph is an `OntologyGraph` row. Nodes and edges belong to it. The screen and the API use the graph id `default` unless a call passes another id. Node ids are unique inside one graph. The same id can exist in another graph because the primary key is the pair of id and graph id.

## Read

`GET /api/v1/ontology/graph/active` calls `GetActiveGraph`. It seeds when needed, loads the graph row, and returns nodes and edges. The node field `kind` is the type id. `parentId` is the parent node id. Edge `type` is the relation name. A missing graph is seeded once more and then raises `Graph '{id}' not found.` A failure on this route logs `Failed to load active graph: %s` at error and answers HTTP 500. The logger for that line stays `app.ontology.routes.ontology_routes`, because the handler was not moved.

## Validate

`POST /api/v1/ontology/graph/validate` checks a YAML string or a dataset and writes nothing. The caller must send `yaml_content` or `dataset`. Neither one is HTTP 400 `Must provide 'yaml_content' or 'dataset'.` A YAML parse error returns a result with `valid: false` and the error text, not an HTTP error.

Validation checks three things.

1. Every node's `kind` is a registered type. Otherwise: `Node '{id}' specifies unregistered entity type '{kind}'.`
2. A `parentId` must name a node in the same payload, and `(parent.kind, contains, node.kind)` must be an allowed rule. A missing parent is `Node '{id}' specifies non-existent parentId '{parent}'.` A disallowed pair is `Hierarchical containment violation: '{parent kind}' cannot contain '{kind}'.`
3. An edge's source and target must be nodes in the payload, and `(source.kind, relation, target.kind)` must be an allowed rule. The relation is lowercased and spaces become `_`. A disallowed edge is `Relationship violation on edge '{id}': '{source kind} --[{relation}]--> {target kind}' is not allowed by the ontology schema metamodel.`

`valid` is true only when the error list is empty. Warnings are returned and are currently unused.

## Import

`POST /api/v1/ontology/graph/import-yaml` parses YAML or takes a dataset, applies `graph_id`, `name`, `version`, and `description` from the request when they are set, validates, and replaces that graph's nodes and edges. The raw YAML is stored on the graph row when the request sent YAML. A failed validation is HTTP 422 and starts `Schema metamodel validation failed with {n} errors:`. Any other failure logs `Failed to import knowledge graph: %s` at error and answers HTTP 500.

`PersistDataset` upserts the graph row, deletes the previous nodes and edges for that graph id, and inserts the new ones. It does not delete other graphs.

## Edit one node or edge

`POST /api/v1/ontology/graph/nodes` adds one node. The kind must already be a type. The id must be new in that graph. A parent must exist, and that parent's type must be allowed to `contains` the new kind. When a parent is set, a `contains` edge `{parent}->{id}` is added if that edge id is free. The description of that edge is `{parent title} contains {node title}`. Success is HTTP 201 and the whole graph. A `ValueError` is HTTP 422. Anything else logs `Failed to add node: %s` and answers HTTP 500.

`PUT /api/v1/ontology/graph/nodes/{node_id}` updates title, kind, description, parent, domain, path, tags, status, and properties. A missing node is HTTP 404 `Node '{id}' not found in graph '{graph}'.` Changing kind requires the new type to exist. Changing parent removes the old `contains` edge that targets this node and, when the new parent is set, inserts `{parent}->{node}`. The new parent must be allowed to contain the node's kind. A metamodel miss is `Metamodel violation: '{parent type}' cannot contain '{kind}'.`

`DELETE /api/v1/ontology/graph/nodes/{node_id}` deletes every edge that starts or ends at the node, then the node, and returns the graph. A failure logs `Failed to delete node: %s`.

`POST /api/v1/ontology/graph/edges` requires both nodes. The relation must be allowed for their types, or the error is `Disallowed relationship: '{source type} --[{relation}]--> {target type}' is not permitted by the metamodel schema.` The edge id defaults to `{source}->{target}`. A duplicate id raises `Edge with ID '{id}' already exists.` HTTP 422 carries the `ValueError`. Other failures log `Failed to add edge: %s`.

`DELETE /api/v1/ontology/graph/edges/{edge_id}` deletes that edge id in the graph and returns the graph. A failure logs `Failed to delete edge: %s`.

## YAML shape

`ParseYaml` expects a top-level mapping. A bad document raises `Invalid YAML format: {error}` or `YAML must contain a top-level dictionary with 'nodes' and 'edges'.` A node needs `id`. `kind` defaults to `element`. `title` defaults to the id. Keys other than the known node fields are stored in `properties`. An edge needs `id`, `source`, and `target`. `type` defaults to `contains`. Nodes or edges that are not mappings, or that omit those keys, are skipped.
