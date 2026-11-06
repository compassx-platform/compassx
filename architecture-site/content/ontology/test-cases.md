# Test cases

A person or an agent runs these in the product, end to end. They are not code tests. Pass means the outcome below is what you see.

## Open the map

Open `/ontology`.

You should see the enterprise graph: one organization, the domains Operations & Execution, Intelligence & Analytics, and Core Platform & Infrastructure, subdomains under those domains, and elements under the subdomains. `/topology` shows the same map.

## Focus a node

Search for Knowledge Graph and open it. Then open the page again with `focus` set to that node's id.

You should see the side drawer for that node, and the URL carrying `focus`.

## Add a node the schema allows

Add an element under the Knowledge Graph subdomain. Give it a new id and a title.

You should see the new element on the map, under that subdomain, and the drawer open on it. Leave and come back. The element is still there.

## Refuse a parent the schema does not allow

Add an element whose parent is the organization.

You should see the add refused because an organization cannot contain an element. The map is unchanged.

## Add a link the schema allows, and refuse one it does not

Draw a `depends_on` link from one element to another element. Then try a `contains` link from an element to a domain.

You should see the first link on the map. The second is refused because that relationship is not in the metamodel.

## Change and delete a node

Rename the element you added. Delete it.

You should see the new title, then the element and its links gone. The seeded elements remain.

## Add a custom type and a custom rule

Open the schema settings. Add a type, for example `service`, with a label and a shape. Add a rule `service calls service`. Delete that rule, then delete the type.

You should see the type and the rule in the lists, then both gone after delete.

## Leave the system schema in place

In schema settings, try to delete Organization, and try to change its tier. Try to delete or edit the rule that says an organization contains a domain.

You should see each change refused because the type or the rule is protected. Organization is still tier 0, and the containment rule is still there.

## Replace the graph from YAML

Submit a YAML document to `POST /api/v1/ontology/graph/validate` whose nodes use a kind that is not registered. Then submit a small valid document to `POST /api/v1/ontology/graph/import-yaml` for the `default` graph: an organization containing one domain. Open `/ontology`.

You should see the validate call report the unknown kind and write nothing. After the import, the map shows the organization and that domain, and the previous seeded nodes are gone from the `default` graph.
