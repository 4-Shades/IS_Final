import logging

from common.llm import LLMError, get_llm_client
from common.rag import get_rag_index
from shared.schemas import ActivitiesResponse, TravelRequest

logger = logging.getLogger(__name__)

ACTIVITIES_RESPONSE_FORMAT = (
    '{"activities":[{"name":"string","description":"string",'
    '"price":0,"currency":"USD","duration_hours":1,"source_url":null}]}'
)


async def execute(request: TravelRequest) -> ActivitiesResponse:
    preferences = ", ".join(request.preferences) if request.preferences else "general sightseeing"
    request_prompt = (
        f"Suggest 2-3 non-live, illustrative activities in {request.destination} from "
        f"{request.start_date} to {request.end_date} for {request.travellers} traveller(s) "
        f"with preferences in {preferences}, within {request.budget} {request.currency}."
    )
    rag_prompt, _ = get_rag_index().augment_prompt(
        request_prompt,
        destination=request.destination,
    )
    prompt = (
        f"{rag_prompt} Use this exact response structure: {ACTIVITIES_RESPONSE_FORMAT}. "
        "Do not claim activities have live availability, a live price, or a verified source. "
        "Keep suggestions local, illustrative, and suitable for a travel-planning prototype."
    )
    try:
        return await get_llm_client().generate_structured(prompt, ActivitiesResponse)
    except LLMError as exc:
        logger.warning("activities_generation_failed request_id=%s error=%s", request.request_id, exc)
        return ActivitiesResponse(error="Activity planner is temporarily unavailable.")
