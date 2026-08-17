import os
import httpx
import pandas as pd


class CompassXQueryError(Exception):
    pass


def sql(query: str, *, warehouse: str | None = None, timeout: int = 120) -> pd.DataFrame:
    token = (
        os.environ.get("NOTEBOOK_SESSION_TOKEN")
        or os.environ.get("KERNEL_NOTEBOOK_SESSION_TOKEN")
        or os.environ.get("JUPYTER_TOKEN")
    )
    api_url = os.environ.get("KERNEL_CATALOG_API_URL") or os.environ.get("CATALOG_API_URL")
    if not token or not api_url:
        raise CompassXQueryError("Missing auth token or API URL in environment.")

    url = f"{api_url}/query"

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "query": query,
        "warehouse": warehouse,
        "timeout_seconds": timeout,
    }

    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=timeout + 5)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        try:
            err_data = exc.response.json()
            msg = err_data.get("detail", err_data.get("message", str(exc)))
        except Exception:
            msg = exc.response.text or str(exc)
        raise CompassXQueryError(msg) from None
    except Exception as exc:
        raise CompassXQueryError(str(exc)) from None

    if data.get("status") == "error":
        raise CompassXQueryError(data.get("message", "Unknown query error"))

    if data.get("truncated"):
        print(f"Warning: Result truncated to {data.get('row_count')} rows.")

    rows = data.get("rows", [])
    raw_columns = data.get("columns", [])
    columns = [c["name"] if isinstance(c, dict) else c for c in raw_columns]
    return pd.DataFrame(rows, columns=columns)
