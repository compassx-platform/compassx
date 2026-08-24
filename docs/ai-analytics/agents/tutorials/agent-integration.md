# Agent Integration Tutorial

Connect external LLMs and autonomous agents (LangChain, LlamaIndex, Claude, OpenAI) to CompassX compute and database tools.

---

## Agent Tool Registration

```python
from compassx.tools import TableQueryTool

tool = TableQueryTool(table_name="customer_orders")
response = tool.run("Find top 10 customers with overdue payments")
```
