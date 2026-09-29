from shared.schemas import FlightAgentResponse, TravelRequest

from .agent import execute


async def run(payload: TravelRequest) -> FlightAgentResponse:
    return await execute(payload)
