from common.a2a_server import create_app
from .task_manager import run

app = create_app(service_name="activities", execute=run)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
