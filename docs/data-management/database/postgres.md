# PostgreSQL & pgvector

CompassX uses PostgreSQL 16 equipped with the `pgvector` extension for transactional metadata and semantic vector embeddings.

---

## Vector Indexing Capabilities

- **HNSW Indexing**: High-performance approximate nearest neighbor search.
- **Cosine & L2 Distance**: Native vector similarity operations directly inside SQL queries.
- **Relational Metadata Join**: Combine vector embeddings with SQL filters, role-based access control, and workspace tenancy.
