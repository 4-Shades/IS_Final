from common.a2a_server import create_app
from shared.config import get_settings

from .task_manager import run

# The Host is the only publicly exposed agent, so it alone checks HOST_API_KEY.
app = create_app(service_name="host", execute=run, api_key=get_settings().host_api_key)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
