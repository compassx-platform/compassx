# Vector Search Tutorial

Perform semantic embeddings and similarity searches over unstructured datasets using PostgreSQL `pgvector`.

---

## Semantic Query Example

```sql
SELECT document_id, content, 1 - (embedding <=> '[0.1, 0.2, ...]') AS similarity
FROM document_embeddings
ORDER BY embedding <=> '[0.1, 0.2, ...]'
LIMIT 5;
```
