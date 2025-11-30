import subprocess
import sys
import time
import os
from dotenv import load_dotenv

load_dotenv()


# Define the agents and their ports
AGENTS = [
    {"name": "Host Agent", "app": "agents.host_agent.__main__:app", "port": 8000},
    {"name": "Flight Agent", "app": "agents.flight_agent.__main__:app", "port": 8001},
    {"name": "Stay Agent", "app": "agents.stay_agent.__main__:app", "port": 8002},
    {"name": "Activities Agent", "app": "agents.activities_agent.__main__:app", "port": 8003},
]

def kill_existing_processes():
    """Kills processes running on the configured ports (Windows specific)."""
    print("Cleaning up existing processes...")
    for agent in AGENTS:
        port = agent["port"]
        try:
            # Find PID using netstat
            cmd = f'netstat -ano | findstr :{port}'
            output = subprocess.check_output(cmd, shell=True).decode()
            
            for line in output.splitlines():
                if str(port) in line and "LISTENING" in line:
                    parts = line.strip().split()
                    pid = parts[-1]
                    print(f"Killing process {pid} on port {port}")
                    subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            # No process found on this port
            pass
        except Exception as e:
            print(f"Error cleaning up port {port}: {e}")

def main():
    # 1. Clean up ports
    if sys.platform == "win32":
        kill_existing_processes()
    
    processes = []
    
    try:
        # 2. Start Agents
        for agent in AGENTS:
            print(f"Starting {agent['name']} on port {agent['port']}...")
            p = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", agent["app"], "--port", str(agent["port"])],
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            processes.append(p)
            time.sleep(1) # Give it a moment to bind

        # 3. Start UI
        print("Starting Travel UI...")
        ui_process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "travel_ui.py"],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        processes.append(ui_process)
        
        print("\nAll services running. Press Ctrl+C to stop.")
        ui_process.wait()

    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        print("Terminating processes...")
        for p in processes:
            p.terminate()
            print("Cleanup complete.")

if __name__ == "__main__":
    main()