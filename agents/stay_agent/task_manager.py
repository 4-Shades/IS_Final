from shared.schemas import StayResponse, TravelRequest

from .agent import execute

async def run(payload: TravelRequest) -> StayResponse:
    return await execute(payload)
