import logging

from common.llm import LLMError, get_llm_client
from common.rag import retrieve_guidance
from shared.schemas import StayAgentResponse, StayResponse, TravelRequest

logger = logging.getLogger(__name__)

STAY_RESPONSE_FORMAT = (
    '{"stays":[{"name":"string","location":"string",'
    '"price_per_night":0,"currency":"USD","booking_url":null}]}'
)


async def execute(request: TravelRequest) -> StayAgentResponse:
    guidance = await retrieve_guidance("stay", request.destination)
    prompt = (
        f"Suggest 2-3 non-live, illustrative accommodation options in {request.destination} from "
        f"{request.start_date} to {request.end_date} within {request.budget} {request.currency}."
        f"\n\n{guidance.prompt_block}\n\n"
        f"Use this exact response structure: {STAY_RESPONSE_FORMAT}. "
        "Do not claim options are live or bookable."
    )
    try:
        result = await get_llm_client().generate_structured(prompt, StayResponse)
    except LLMError as exc:
        logger.warning("stay_generation_failed request_id=%s error=%s", request.request_id, exc)
        return StayAgentResponse(error="Stay planner is temporarily unavailable.")
    return StayAgentResponse(**result.model_dump(), sources=guidance.sources)
