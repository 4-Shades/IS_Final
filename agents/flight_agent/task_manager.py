from shared.schemas import FlightResponse, TravelRequest

from .agent import execute

async def run(payload: TravelRequest) -> FlightResponse:
    return await execute(payload)
