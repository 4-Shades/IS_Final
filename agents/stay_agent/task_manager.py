from shared.schemas import StayAgentResponse, TravelRequest

from .agent import execute


async def run(payload: TravelRequest) -> StayAgentResponse:
    return await execute(payload)
