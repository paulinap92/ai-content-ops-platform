"""Start only the editor process. No public API or source-refresh scheduler."""
import os
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), workers=1, access_log=False, timeout_graceful_shutdown=25)
