from shared.schemas import ActivitiesResponse, TravelRequest

from .agent import execute

async def run(payload: TravelRequest) -> ActivitiesResponse:
    return await execute(payload)
