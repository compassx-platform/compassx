export type AtomicToolInfo = {
  key: string;
  name: string;
  description: string;
};

export type AvailableToolInfo = {
  key: string;
  name: string;
  description: string;
  atomicTools?: AtomicToolInfo[];
};

export const AVAILABLE_TOOLS: AvailableToolInfo[] = [
  { key: "sql_query", name: "SQL Query", description: "Run SELECT queries on connected databases." },
  { key: "python_code", name: "Python Code Runner", description: "Execute Python code in a sandbox environment." },
  { key: "visualization", name: "Visualization", description: "Render Vega-Lite charts from data." },
  { key: "rag_search", name: "RAG Document Search", description: "Search uploaded agent documents via vector similarity." },
  {
    key: "asset_manager",
    name: "Asset Manager",
    description: "Create, read, update, and explore asset types and asset instances.",
    atomicTools: [
      { key: "list_asset_types", name: "List Asset Types", description: "List available asset type definitions with optional filters." },
      { key: "get_asset_type", name: "Get Asset Type", description: "Read one asset type definition and schema." },
      { key: "create_asset_type", name: "Create Asset Type", description: "Create a new asset type definition." },
      { key: "update_asset_type", name: "Update Asset Type", description: "Update an existing asset type definition." },
      { key: "list_assets", name: "List Assets", description: "List asset instances with optional type and search filters." },
      { key: "get_asset", name: "Get Asset", description: "Read one asset instance and its metadata." },
      { key: "create_asset", name: "Create Asset", description: "Create a new asset instance." },
      { key: "update_asset", name: "Update Asset", description: "Update an existing asset instance." },
      { key: "get_import_job", name: "Get Import Job", description: "Inspect an asset import job status and details." },
      { key: "list_uploaded_files", name: "List Uploaded Files", description: "List files attached to an asset import workflow." },
      { key: "apply_import_mapping", name: "Apply Import Mapping", description: "Apply field mappings before validating an import." },
      { key: "approve_and_run_import", name: "Approve And Run Import", description: "Run an import after explicit user approval." },
    ],
  },
  {
    key: "notebook_manager",
    name: "Notebook Manager",
    description: "Inspect notebook context, read reference notebooks, request cell execution, and return notebook edits.",
    atomicTools: [
      { key: "get_cell_output", name: "Get Cell Output", description: "Fetch the current captured output for a notebook cell." },
      { key: "get_variable_state", name: "Get Variable State", description: "Fetch variable state captured for a notebook cell." },
      { key: "get_schema", name: "Get Schema", description: "Fetch schema metadata already attached to the notebook request." },
      { key: "list_imports", name: "List Imports", description: "List imports already present in the notebook." },
      { key: "read_notebook", name: "Read Notebook", description: "Read another .ipynb notebook by relative path for reference." },
      { key: "execute_cell", name: "Execute Cell", description: "Record that the agent wants a notebook cell execution." },
      { key: "edit_cell", name: "Edit Cell", description: "Propose replacing one existing notebook cell by index, with user approval in the notebook UI." },
      { key: "add_multiple_cells", name: "Add Multiple Cells", description: "Propose adding several notebook cells at once, with per-cell approval in the notebook UI." },
      { key: "apply_notebook_edit", name: "Apply Notebook Edit", description: "Return the final notebook edit to apply in the UI." },
    ],
  },
  {
    key: "dashboard_manager",
    name: "Dashboard Manager",
    description: "Create, inspect, and configure dashboards — add SQL datasets, add and configure chart/text/filter widgets, run SQL previews to validate data, and publish the result.",
    atomicTools: [
      { key: "list_dashboards", name: "List Dashboards", description: "List all dashboards with id, name, draft status, and page/dataset/widget counts." },
      { key: "get_dashboard", name: "Get Dashboard", description: "Fetch full dashboard structure including pages, widgets, and datasets." },
      { key: "create_dashboard", name: "Create Dashboard", description: "Create a new blank dashboard with a specified name and an initial empty page." },
      { key: "update_dashboard", name: "Update Dashboard", description: "Update dashboard name, permission mode, or theme/settings." },
      { key: "add_dataset", name: "Add Dataset", description: "Add a SQL dataset to a dashboard, returning the dataset id for widget wiring." },
      { key: "update_dataset", name: "Update Dataset", description: "Update an existing dataset's SQL query or name." },
      { key: "add_widget", name: "Add Widget", description: "Add a chart, text, or filter widget to a dashboard page with grid position and chart config." },
      { key: "update_widget", name: "Update Widget", description: "Update a widget's title, chart type, field mappings, or display configuration." },
      { key: "run_query", name: "Run Query", description: "Execute a read-only SQL query through the warehouse to validate SQL and preview column names and sample rows." },
      { key: "publish_dashboard", name: "Publish Dashboard", description: "Publish a draft dashboard, making it visible to consumers." },
    ],
  },
  { key: "git_workspace", name: "Git Workspace Setup", description: "Clone a repo, create a branch, and set up a git worktree." },
  { key: "claude_agent", name: "Claude Agent", description: "AI-powered code review and code generation for GitHub and Azure DevOps." },
  { key: "invoke_agent", name: "Invoke Agent", description: "Invoke another agent to handle a specialist subtask." },
  { key: "fetch_memory", name: "Fetch Memory", description: "Retrieve relevant semantic memory/facts about the user from past conversations." },
  { key: "fetch_research_memory", name: "Fetch Research Memory", description: "Retrieve active Tier-2 research memory facts for the workspace." },
  { key: "save_research_memory", name: "Save Research Memory", description: "Save durable deployment-specific strategic guidance to Tier-2 research memory." },
  { key: "fetch_research_proposal_history", name: "Fetch Research Proposal History", description: "Retrieve prior research proposals and review history." },
  { key: "get_data_profile", name: "Get Data Profile", description: "Retrieve compiled data profiling findings from Layer 1 without requiring an attached database connection." },
  {
    key: "db_explorer",
    name: "Database Explorer",
    description: "Explore database schemas, column statistics, value overlaps, data profiles, preview/sample rows, and execute read-only queries on configured connections.",
    atomicTools: [
      { key: "list_tables", name: "List Tables", description: "List allowed tables/views in scope." },
      { key: "get_table_schema", name: "Get Table Schema", description: "Get columns, types, nullability, and primary/foreign keys." },
      { key: "list_table_relationships", name: "List Table Relationships", description: "Get declared foreign keys and candidate relationships." },
      { key: "get_column_stats", name: "Get Column Stats", description: "Fetch statistics (null rate, min/max, distinct count, top values) for a column." },
      { key: "get_row_count", name: "Get Row Count", description: "Fetch row count of a table with optional filters." },
      { key: "check_value_overlap", name: "Check Value Overlap", description: "Compute value overlap ratio between two columns." },
      { key: "sample_rows", name: "Sample Rows", description: "Retrieve a preview of table rows capped at 100 rows." },
      { key: "run_query", name: "Run Query", description: "Execute read-only SELECT queries with size caps and query timeouts." },
      { key: "search_workspace", name: "Search Workspace", description: "Search notebooks, dashboards, and skills for references to database tables or concepts." },
      { key: "save_data_profile", name: "Save Data Profile", description: "Save the compiled data profile for a table." },
    ],
  },
  {
    key: "catalog",
    name: "Catalog Manager",
    description: "Discover and inspect data assets — tables, notebooks, dashboards, queries, volumes, and models — registered in the CompassX catalog.",
    atomicTools: [
      { key: "search_catalog", name: "Search Catalog", description: "Semantic search across all catalog object types in the workspace." },
      { key: "get_asset_schema", name: "Get Asset Schema", description: "Fetch the full column-level schema for a specific table or foreign table." },
      { key: "get_asset_details", name: "Get Asset Details", description: "Return metadata details about a single catalog object (tables, notebooks, volumes, etc.)." },
      { key: "check_data_coverage", name: "Check Data Coverage", description: "Verify if a table has non-empty data for a given filter (asset, date range, tag)." },
      { key: "resolve_entity", name: "Resolve Entity", description: "Resolve business-facing names (turbine tag, site name) to underlying identifiers." },
      { key: "list_related_assets", name: "List Related Assets", description: "Surface other tables commonly used alongside a table (foreign key linked tables)." },
      { key: "sync_foreign_catalog", name: "Sync Foreign Catalog", description: "Trigger an asynchronous sync of a foreign Postgres catalog." },
    ],
  },
  {
    key: "create_notebook",
    name: "Create Notebook",
    description: "Create and register a new Jupyter notebook (.ipynb) inside a specific catalog and schema.",
  },
  {
    key: "search_catalog_metadata",
    name: "Search Catalog Metadata",
    description: "Search catalogs and schemas directly from the catalog database metadata tables (not via embeddings/vectors).",
  },
  {
    key: "catalog_editor",
    name: "Catalog Editor",
    description: "Create, edit, and delete schemas, tables, and other catalog metadata.",
    atomicTools: [
      { key: "create_schema", name: "Create Schema", description: "Create a new schema inside a specific catalog." },
      { key: "update_schema", name: "Update Schema", description: "Update description or properties of a schema." },
      { key: "delete_schema", name: "Delete Schema", description: "Delete an empty schema from a specific catalog." },
      { key: "create_volume", name: "Create Volume", description: "Create a new storage volume inside a schema." },
    ],
  },
];

export function getAvailableTool(toolKey: string | undefined) {
  return AVAILABLE_TOOLS.find((tool) => tool.key === toolKey);
}
