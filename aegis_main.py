from __future__ import annotations

import uvicorn

from aegis_agent.core.app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("aegis_main:app", host="0.0.0.0", port=8001, reload=True)
