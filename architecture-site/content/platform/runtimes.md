# Runtimes

A runtime is one user execution environment: Spark, Flink, Ray, DuckDB, or a notebook job. `DefaultRuntimeManager` builds a `RuntimeSpec`. `DefaultResourceManager` asks a driver to create it and stores the infrastructure id. Neither manager imports Docker or Kubernetes.

The id is `runtime-` plus 8 hex characters unless the caller supplies one. Create rejects an id whose stored phase is not `deleted`, `failed`, `stopped`, or `missing`, after it asks the driver whether the infrastructure is still there. If the driver still has it, the error is `Runtime already exists: {id}`. If the driver reports it missing, the row is marked `missing` and create continues.

The builder comes from `SpecBuilderRegistry`. An unknown type raises `Unknown runtime type: {type}. Registered: {list}`. The driver name comes from the profile policy. The resource manager's default driver is `local` unless the container passes `profile.compute_driver`.

An unknown driver raises `Unknown driver: {name}. Registered: {list}`.

Create writes phase `creating`, then `pending` after the driver returns an infrastructure id. A driver exception sets phase `failed`, logs `runtime.create failed runtime_id=%s driver=%s type=%s user=%s workspace=%s` at exception level, and re-raises. Success logs `runtime.create runtime_id=%s driver=%s type=%s duration_ms=%s user=%s workspace=%s`.

Delete removes the infrastructure, then the row, and logs `runtime.delete runtime_id=%s`. A missing infrastructure id is ignored and the row is still removed. Start logs `runtime.start runtime_id=%s` and sets `pending`. If the driver says the runtime is gone, start sets `missing`, clears `infra_id`, and re-raises. Stop sets `stopped` and logs `runtime.stop runtime_id=%s`. Restart stops, starts, sets `pending`, and logs `runtime.restart runtime_id=%s`.

`suspend_runtime` stops the runtime and sets phase `suspended`. `resume_runtime` starts it. Status copies the driver's phase back onto the row when it differs. A driver `RuntimeNotFoundError` on status returns phase `missing`.

`get_metadata` returns the stored id, type, driver, namespace, user, workspace, phase, and timestamps. It does not include `infra_id`.

## Specs

Images are Spark `apache/spark:3.5.0`, Flink `flink:1.18-scala_2.12`, Ray `rayproject/ray:2.9.0`, DuckDB from `COMPASSX_DUCKDB_IMAGE` defaulting to `ghcr.io/compassx-platform/compute-duckdb:v0.16.0`, and notebook jobs from `COMPASSX_NOTEBOOK_JOB_IMAGE` defaulting to `ghcr.io/compassx-platform/airflow-notebook-runner:v0.16.0`. `COMPUTE_REGISTRY_PREFIX` is prepended when the image does not already start with it.

Every spec receives MinIO variables `AWS_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_DEFAULT_REGION=us-east-1`. The endpoint default inside the container is `minio:9000`. The container passes the registry's MinIO address instead. Access keys default to `minioadmin` unless `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` are set.

Spark runs `org.apache.spark.deploy.master.Master` and sets `SPARK_MODE=master`. Flink sets jobmanager and taskmanager memory from the limit, default `1Gi`, and opens ports `8081` and `6123`. Ray starts a head node and opens `8265`, `6379`, and `10001`. DuckDB and notebook jobs stay up with `tail -f /dev/null`. DuckDB accepts profiles `local`, `cloud-xs`, and `cloud-s` only. Any other non-empty `profile_id` raises `DuckDB is only valid with profiles: cloud-s, cloud-xs, local`.

A built spec logs `RuntimeSpec built: runtime_id=%s type=%s profile=%s env=%s` at debug.

## Rows

`SqlRuntimeRepository` stores the mapping on the system database, schema `compute`, table `platform_runtimes`. Columns are `runtime_id`, `runtime_type`, `driver`, `infra_id`, `namespace`, `user_id`, `workspace_id`, `phase`, `spec_json`, `created_at`, and `updated_at`. The model is `PlatformRuntime` in `compassx.runtime.db_models`. The CLI and the unit tests use `InMemoryRuntimeRepository` instead. `infra_id` is not a public API field.
