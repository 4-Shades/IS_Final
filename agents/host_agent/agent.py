import uuid

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from shared.config import get_settings

settings = get_settings()

host_agent = Agent(
    name="host_agent",
    model=LiteLlm(
        f"ollama/{settings.ollama_model}",
        api_base=settings.ollama_base_url,
    ),
    description="Coordinates travel planning by calling flight, stay, and activity agents.",
    instruction=(
        "You are the host agent responsible for orchestrating trip planning tasks. "
        "Call the flights, stays, and activities agents for results. "
        "Never describe generated suggestions as live availability, live prices, "
        "or bookable offers."
    ),
)

session_service = InMemorySessionService()
runner = Runner(
    agent=host_agent,
    app_name="host_app",
    session_service=session_service
)

async def execute(request: dict[str, object]) -> dict[str, str]:
    user_id = str(request.get("user_id") or "user_host")
    session_id = str(request.get("session_id") or uuid.uuid4())
    await session_service.create_session(
        app_name="host_app",
        user_id=user_id,
        session_id=session_id,
    )

    prompt = (
        f"Plan a trip to {request['destination']} from {request['start_date']} "
        f"to {request['end_date']} within a total budget of {request['budget']}. "
        "Call the flights, stays, and activities agents for results."
    )

    message = types.Content(role="user", parts=[types.Part(text=prompt)])

    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=message
    ):
        if event.is_final_response():
            text = event.content.parts[0].text if event.content and event.content.parts else ""
            return {"summary": text}

    return {"summary": "The host agent did not return a final plan."}