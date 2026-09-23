import os
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Service:
    name: str
    module: str
    port: int


SERVICES = (
    Service("Host Agent", "agents.host_agent.__main__", 8000),
    Service("Flight Agent", "agents.flight_agent.__main__", 8001),
    Service("Stay Agent", "agents.stay_agent.__main__", 8002),
    Service("Activities Agent", "agents.activities_agent.__main__", 8003),
)


def _port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.5)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def _wait_for_service(service: Service, process: subprocess.Popen[bytes], timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{service.name} exited with code {process.returncode}")
        if _port_is_open(service.port):
            return
        time.sleep(0.25)
    raise TimeoutError(f"{service.name} did not listen on port {service.port}")


def _terminate_processes(processes: list[subprocess.Popen[bytes]]) -> None:
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()

    for process in reversed(processes):
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def _wait_for_ui(process: subprocess.Popen[bytes], stop_event: threading.Event) -> None:
    while process.poll() is None and not stop_event.is_set():
        time.sleep(0.2)

    if stop_event.is_set():
        raise KeyboardInterrupt


def _handle_shutdown(signum: int, frame: object) -> None:
    del signum, frame
    raise KeyboardInterrupt


def main():
    processes: list[subprocess.Popen[bytes]] = []
    stop_event = threading.Event()

    def _shutdown_handler(signum: int, frame: object) -> None:
        del signum, frame
        stop_event.set()
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    try:
        for service in SERVICES:
            print(f"Starting {service.name} on port {service.port}...")
            environment = os.environ.copy()
            environment.update(
                {
                    "APP_MODULE": service.module,
                    "PORT": str(service.port),
                }
            )
            p = subprocess.Popen(
                [sys.executable, "-m", "common.serve"],
                cwd=ROOT_DIR,
                env=environment,
            )
            processes.append(p)
            _wait_for_service(service, p)

        print("Starting Travel UI...")
        ui_environment = os.environ.copy()
        ui_environment["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
        ui_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "travel_ui.py",
                "--server.address=127.0.0.1",
                "--server.port=8501",
                "--server.headless=true",
                "--browser.gatherUsageStats=false",
            ],
            cwd=ROOT_DIR,
            env=ui_environment,
        )
        processes.append(ui_process)

        print("\nAll services running. Ollama must be running separately. Press Ctrl+C to stop.")
        _wait_for_ui(ui_process, stop_event)

    except KeyboardInterrupt:
        print("\nStopping services...")
    except (OSError, RuntimeError, TimeoutError) as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        _terminate_processes(processes)
        print("Cleanup complete.")


if __name__ == "__main__":
    main()
