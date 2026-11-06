# Screen

The agents screen is `AgentsPage` at `agents` inside the platform app. The heading is **Agents**.

Tabs are **Agents**, **Tools**, **Skills Library**, **Active Streams**, **LLM Call Logs**, **Budgets**, and **Usage**. The `tab` query selects one of `agents`, `tools`, `skills`, `streams`, `llm_calls`, `budgets`, or `usage`.

`agents/new` and `agents/create` open the builder. `agents/:agentId` opens the chat. `agents/:agentId/edit` and `agents/:agentId/customizations` open customizations. `agents/tools/:toolKey` opens one tool.

Delete toasts `Agent "{name}" deleted` or `Failed to delete agent`. Clone toasts `Cloned as "{name}"` or `Failed to clone agent`.

A skill with an empty name toasts `Skill name is required`. Save toasts `Skill created successfully` or `Skill updated successfully`. A failure toasts the response `detail` or `Failed to save skill`. Delete toasts `Skill deleted` or `Failed to delete skill`.

## Connections screens

`connections` is **Connections**. The subtitle is `Manage external connections for databases, REST APIs, Loki, Git, and LLM providers.`

A test toasts `Connection "{name}" OK ({latency}ms)`, `Test failed: {message}`, or `Connection test failed`. A status change toasts `Connection is now {status}`. Delete toasts `Connection deleted` or `Failed to delete connection`.

`connections/databases` is **DB Connections**. Save toasts `Connection created` or `Connection updated`, or `Failed to save connection`. Delete toasts `Connection deleted` or `Failed to delete`. A test toasts the result message or `Test failed`. Reprofile toasts the response message or `Reprofile started`, or `Failed to trigger reprofile`.

`connections/llm-models` and `connections/git-servers` edit the LLM and Git rows.

## Chat

The chat page is the session transcript, the composer, and the changes dock. Streaming events render as thought blocks, tool cards, and the assistant message. Uploaded documents and proposed changes use the session routes on the [Documents and changes](documents.md) page.
