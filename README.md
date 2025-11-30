# ADK-Powered Travel Planner

**Project Proponents:** Chaim Joseph Cordova & Psalmantha Allaine Ipong

## Overview
The **ADK-Powered Travel Planner** is a demonstration application that showcases the capabilities of the **Agent Development Kit (ADK)** and **Generative AI** in a multi-agent environment. The system automates the process of planning a trip by coordinating multiple specialized agents to find flights, accommodation, and activities based on user preferences.

## Features
*   **Multi-Agent Architecture:** Orchestrates specialized agents for different travel aspects.
*   **Generative AI Integration:** Uses LLMs (GPT-4o) to generate realistic travel options.
*   **Interactive UI:** User-friendly web interface built with Streamlit.
*   **Microservices:** Each agent runs as an independent service.

## System Components
1.  **Host Agent:** The central orchestrator that manages the workflow.
2.  **Flight Agent:** Suggests flight options.
3.  **Stay Agent:** Suggests accommodation options.
4.  **Activities Agent:** Recommends local activities.
5.  **Frontend:** Streamlit application for user interaction.

## Prerequisites
*   Python 3.8+
*   OpenAI API Key

## Installation

1.  Clone the repository or navigate to the project directory.

2.  Install the required dependencies:
    ```bash
    pip install google-adk litellm fastapi uvicorn httpx pydantic openai streamlit
    ```

3.  Create a `.env` file in the root directory and add your OpenAI API key:
    ```env
    OPENAI_API_KEY=your_api_key_here
    GOOGLE_API_KEY=your_google_api_key_here_if_needed
    ```

## Usage

The application consists of a backend (agents) and a frontend (UI). You need to run both.

### 1. Start the Backend Agents
Run the `run.py` script to start all agent services (Host, Flight, Stay, Activities):
```bash
python run.py
```
*This will start the agents on ports 8000, 8001, 8002, and 8003.*

### 2. Start the Frontend UI
Open a new terminal and run the Streamlit app:
```bash
streamlit run travel_ui.py
```
*This will open the application in your default web browser (usually at http://localhost:8501).*

## Project Structure
```
ADK_Demo/
├── agents/                 # Agent implementations
│   ├── activities_agent/
│   ├── flight_agent/
│   ├── host_agent/
│   └── stay_agent/
├── common/                 # Shared communication utilities
├── shared/                 # Shared data schemas
├── run.py                  # Script to start all agents
├── travel_ui.py            # Streamlit frontend application
├── Software_Design_Document.md
└── README.md
```
