# Datasets

`Dataset` is the system-database model in `app.data.models.dataset`. The table is `datasets`. Columns are `id`, `dataset_id`, `type`, `source`, `entity_id`, and `config`. `dataset_id` is unique. `type` is recorded in the model comment as `entity`, `projection`, or `api`. `source` is recorded as a value such as `projection_table` or `entity_records`. `config` is JSON and defaults to an empty object.

`main.py` imports `app.data.models.dataset` so the model is registered. `app.models.dataset` re-exports it. There is no HTTP route in this module that creates, lists, or queries a `Dataset` row.

`DatasetQuery` in `app.data.dataset.dsl_models` is the DSL shape: `dataset`, `filters`, `select`, `aggregation`, `group_by`, `pagination`, and `sort`. Pagination defaults to page `1` and size `50`. Filters, select, group by, and sort default to empty. Aggregation defaults to null. `app.dataset` and `app.dataset.dsl_models` re-export that model. `app.data.dataset.adapters` is empty. Nothing in the legacy routes calls `DatasetQuery`.
