import io
import duckdb
import numpy as np
import pandas as pd
import pytest

from services.compassx_sql.zorder import z_order_dataframe


def test_duckdb_query_zordered_parquet():
    # Create dataset with 2 correlated/clustered columns
    n_rows = 1000
    df = pd.DataFrame({
        "id": range(n_rows),
        "region": np.random.choice(["APAC", "EMEA", "LATAM", "NA"], size=n_rows),
        "val": np.random.uniform(0, 1000, size=n_rows),
        "comment": [f"row_{i}" for i in range(n_rows)],
    })

    # Apply Z-ordering on (region, val)
    z_df = z_order_dataframe(df, ["region", "val"])
    assert len(z_df) == n_rows

    # Write to Parquet in memory with small row group size
    buf = io.BytesIO()
    z_df.to_parquet(buf, index=False, engine="pyarrow", row_group_size=100)
    parquet_bytes = buf.getvalue()

    # Query with DuckDB
    con = duckdb.connect(":memory:")
    # Register buffer or scan directly
    con.register("z_table", z_df)
    result = con.execute("SELECT region, AVG(val) as avg_val FROM z_table WHERE region = 'EMEA' GROUP BY region").fetchdf()
    assert len(result) == 1
    assert result["region"].iloc[0] == "EMEA"
