import logging

from common.llm import LLMError, get_llm_client
from common.rag import get_rag_index
from shared.schemas import StayResponse, TravelRequest

logger = logging.getLogger(__name__)

STAY_RESPONSE_FORMAT = (
    '{"stays":[{"name":"string","location":"string",'
    '"price_per_night":0,"currency":"USD","booking_url":null}]}'
)


async def execute(request: TravelRequest) -> StayResponse:
    request_prompt = (
        f"Suggest 2-3 non-live, illustrative accommodation options in {request.destination} from "
        f"{request.start_date} to {request.end_date} within {request.budget} {request.currency}."
    )
    rag_prompt, _ = get_rag_index().augment_prompt(
        request_prompt,
        destination=request.destination,
    )
    prompt = (
        f"{rag_prompt} Use this exact response structure: {STAY_RESPONSE_FORMAT}. "
        "Do not claim options are live or bookable."
    )
    try:
        return await get_llm_client().generate_structured(prompt, StayResponse)
    except LLMError as exc:
        logger.warning("stay_generation_failed request_id=%s error=%s", request.request_id, exc)
        return StayResponse(error="Stay planner is temporarily unavailable.")
