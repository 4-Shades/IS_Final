"""Container entry point that lets Uvicorn handle SIGTERM gracefully."""

from __future__ import annotations

import importlib
import os

import uvicorn


def main() -> None:
    module_name = os.getenv("APP_MODULE")
    if not module_name:
        raise RuntimeError("APP_MODULE must name a service module, for example agents.host_agent.__main__")
    app = importlib.import_module(module_name).app
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")), log_level="info")


if __name__ == "__main__":
    main()
