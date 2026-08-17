import os

import uvicorn

if __name__ == "__main__":
    reload_enabled = os.environ.get("COMPASSX_BACKEND_RUNTIME", "").strip().lower() != "pod" and os.environ.get("UVICORN_RELOAD", "1").strip().lower() in {"1", "true", "yes", "on"}
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=reload_enabled,
    )
