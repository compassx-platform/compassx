# Screen

The product screens live in `frontend/src/modules/notebooks`. Routes, under the workspace app:

- `notebooks` — the list. The heading is **Notebooks**. The button is **New Notebook**. Search placeholder is `Search notebooks...`. An empty list says `No notebooks yet. Create one to get started.`
- `notebooks/open` — the editor.
- A catalog notebook also opens at `data-catalog/{catalog}/{schema}/notebook/{notebook}`.

**New Notebook** opens a dialog titled **Create New Notebook**. It asks for a name, placeholder `e.g. data_transformation`, plus a catalog and a schema. An empty name says `Please enter a notebook name.` A missing catalog says `Please select a catalog.` A missing schema says `Please select a schema.` Submit reads **Create Notebook**, and **Creating...** while the request is in flight. The request is `POST /notebook/create` with the name, catalog, and schema. A server error is shown as the response detail, or `Failed to create notebook.`

The editor sidebar has an info panel with the label **Created**. The experiments panel filters runs with `Filter runs by name, param, metric...` and models with `Search registered models, stages, aliases...`. Registering a model asks for a name, placeholder `e.g. churn_classifier`, an artifact path, placeholder `model`, and a description.

Scheduling a notebook opens a dialog with **Create new job**. Saving a new schedule reads **Create & Publish**. Adding to an existing job reads **Add & Publish**. While it saves, the button reads **Saving...**. That dialog creates a job. The job itself belongs to Jobs.

The bottom terminal placeholder is `Type bash command...`, or `Executing...` while a command is running. The compute panel accepts a requirement line with placeholder `e.g. scikit-learn>=1.4.0 or -r requirements.txt`.
