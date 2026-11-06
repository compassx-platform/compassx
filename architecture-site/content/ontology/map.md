# Map

The screen is `OntologyPage` at `/ontology` and `/topology`. It draws the active knowledge graph. The canvas implementation stays under `frontend/src/modules/ontology/atlas-engine` and was not moved in this restructure.

## What loads

On open, the page asks for types, relationship rules, and the active graph. Types and rules are saved in the browser config the page already uses. The graph is parsed by `processRawOntologyData` and becomes the nodes and edges on the map. If a call fails, the page keeps the fallback dataset and writes `Could not load ontology from DB, using fallback dataset:` to the browser console. A `focus` query parameter selects that node and opens the side drawer when the id matches.

The seeded picture is one organization, three domains under it (Operations & Execution, Intelligence & Analytics, Core Platform & Infrastructure), subdomains under those domains, and elements under the subdomains. Cross links such as `depends_on` and `reads` are edges, not parents.

## What you can do on the map

Select a node to open the side drawer and to set `focus` on the URL. Search opens the search modal and can focus a match. Expand a parent to show its children. Expand all includes every parent and every org, domain, subdomain, and element. Collapse all clears that set and fits the view. Auto-arrange and fit view re-lay the same nodes. The arrangement toggle switches between `ownership` and `coupling`. The theme toggle stores `ontology_theme_mode` as `light` or `dark`.

## Add, change, and remove

Add node calls `POST /api/v1/ontology/graph/nodes` and replaces the map with the returned graph. The new node becomes the selection. Update from the drawer calls `PUT /api/v1/ontology/graph/nodes/{id}` with title, description, tags, or status. Delete calls `DELETE` for that node and clears the selection when it was the deleted node. Add edge calls `POST /api/v1/ontology/graph/edges`. Each of these re-layouts the map from the graph the API returns. A metamodel refusal comes back as HTTP 422 and the map stays on the previous graph because the page does not apply a failed response.

## Schema from the screen

The config panel lists kinds and relationship rules. Creating, editing, or deleting a kind calls the schema type routes. Creating, editing, or deleting a rule calls the schema relation routes. System types and system rules are refused by the API when the change is one the service protects: deleting them, changing a system type's tier, or editing or deleting a system rule. The panel then shows that error from the response.
