# Storage & Object Data Lakes

CompassX utilizes **MinIO** as an enterprise S3-compatible object storage layer for raw datasets, analytical tables, model checkpoints, and user artifacts.

---

## Object Storage Architecture

- **Buckets**: Organized per workspace and system tenant.
- **Formats Supported**: Apache Parquet, Feather/Arrow, CSV, Delta Lake, JSONL.
- **S3 API Compatibility**: Seamlessly integrates with AWS SDKs, `boto3`, and DuckDB `httpfs`.
