# Query Execution Tutorial

Learn how to trigger vectorized DuckDB queries through CompassX AI agents and REST APIs.

---

## Quick Example

```python
from compassx import Client

client = Client(base_url="http://localhost:8000")
result = client.query("SELECT category, SUM(amount) FROM s3_data GROUP BY category")
print(result.to_pandas())
```
