from shared.schemas import ActivitiesAgentResponse, TravelRequest

from .agent import execute


async def run(payload: TravelRequest) -> ActivitiesAgentResponse:
    return await execute(payload)
