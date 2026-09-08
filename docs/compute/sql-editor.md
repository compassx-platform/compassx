# SQL Editor & Query Execution

The **CompassX SQL Editor** (`/sql-warehouse/editor`) is a multi-tab analytical development studio designed for authoring queries, exploring Data Catalog schemas, analyzing query execution plans, and inspecting structured result sets.

---

## 1. The SQL Editor Interface

The SQL Editor provides a developer-focused environment powered by the **Monaco Editor**:

```
+-----------------------------------------------------------------------------------------------+
| [ Warehouse: analytics-prod ▾ ]  [ Catalog: production ▾ ]  [ Schema: curated_marts ▾ ]       |
+-----------------------------------------------------------------------------------------------+
|  QUERY TABS: [ Query 1 (Active) ]  [ Q3 Regional Revenue ]  [ Churn Analysis ] [ + New Tab ]  |
+-----------------------------------------------------------------------------------------------+
|  1  -- Analyze monthly customer acquisition and revenue by region                             |
|  2  SELECT                                                                                    |
|  3      region,                                                                               |
|  4      DATE_TRUNC('month', order_timestamp) AS order_month,                                  |
|  5      COUNT(DISTINCT customer_id) AS active_buyers,                                         |
|  6      SUM(revenue_usd) AS total_revenue                                                     |
|  7  FROM daily_revenue                                                                        |
|  8  WHERE order_timestamp >= '2025-01-01'                                                     |
|  9  GROUP BY region, order_month                                                              |
| 10  ORDER BY order_month DESC, total_revenue DESC;                                            |
+-----------------------------------------------------------------------------------------------+
| [ ▶ Run (Ctrl+Enter) ]  [ ⏹ Abort ]  [ 🔍 Explain Plan ]  [ 💾 Save Query ]  [ ⬇ Export CSV ]  |
+-----------------------------------------------------------------------------------------------+
|  QUERY RESULTS: 142 rows returned in 18ms (Scanned 4.2 MB)                                    |
|  #   region        order_month              active_buyers   total_revenue                     |
|  1   North         2025-08-01 00:00:00      1,420           $1,420,500.00                     |
|  2   South         2025-08-01 00:00:00      980             $980,200.00                       |
|  3   West          2025-08-01 00:00:00      850             $850,100.00                       |
+-----------------------------------------------------------------------------------------------+
```

---

## 2. Key Editor Features

### 1. Multi-Tab Draft Management
- Open multiple concurrent query tabs.
- Draft queries are automatically saved to your user profile in the database (`SqlDraftQuery`), preventing accidental work loss when closing the browser.

### 2. Schema Context Selector
- Set the default **Catalog** and **Schema** in the top header toolbar.
- When context is selected, you can query tables using simple table names (`SELECT * FROM daily_revenue`) rather than full three-level paths (`production.curated_marts.daily_revenue`).

### 3. Contextual Autocomplete & Linting
- Intelligent schema autocomplete recommends catalog table names, views, and column definitions as you type.
- Syntax errors and missing join keys are flagged before execution.

---

## 3. Query Execution & Keyboard Shortcuts

| Shortcut (Windows / Linux) | Shortcut (macOS) | Action |
| :--- | :--- | :--- |
| **Ctrl + Enter** | **Cmd + Return** | Execute the currently selected SQL block (or full script if none selected). |
| **Ctrl + Shift + F** | **Cmd + Shift + F** | Format and auto-indent the active SQL query. |
| **Ctrl + S** | **Cmd + S** | Save the active query to the Data Catalog. |
| **Ctrl + /** | **Cmd + /** | Toggle line comment (`--`). |

---

## 4. Query Execution Plans (`EXPLAIN`)

To optimize slow-running analytical queries, click **Explain Plan** or prefix queries with `EXPLAIN ANALYZE`:

```sql
EXPLAIN ANALYZE
SELECT region, SUM(revenue_usd)
FROM production.curated_marts.daily_revenue
WHERE order_timestamp >= '2025-01-01'
GROUP BY region;
```

### Plan Insights:
- **Filter Pushdown**: Verifies that date and categorical filters are pushed directly to the Parquet reader, avoiding full table scans.
- **Join Strategies**: Inspects hash joins, broadcast joins, and in-memory build tables.
- **Memory Consumption**: Highlights peak memory utilization across query operators.

---

## 5. Result Grid & Data Export

The interactive results table renders query outputs with rich data tools:
- **Instant Sorting & Filtering**: Sort ascending/descending on any column header.
- **Column Type Tags**: Visual badges identifying data types (`VARCHAR`, `BIGINT`, `DOUBLE`, `TIMESTAMP`, `BOOLEAN`).
- **One-Click Export**: Download results as formatted CSV or JSON files, or copy row selections to clipboard.

---

## Next Steps

To learn how to configure multi-language compute clusters and kernel sandboxes (Python, Spark, Ray, Flink), proceed to **[Compute Clusters & Kernel Pods](clusters-and-runtimes.md)**.
