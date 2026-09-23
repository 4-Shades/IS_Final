import logging

from common.llm import LLMError, get_llm_client
from common.rag import get_rag_index
from shared.schemas import FlightResponse, TravelRequest

logger = logging.getLogger(__name__)


async def execute(request: TravelRequest) -> FlightResponse:
    rag_prompt, _ = get_rag_index().augment_prompt(
        (
            f"Suggest 2-3 non-live, illustrative flights from {request.origin} to {request.destination} "
            f"from {request.start_date} to {request.end_date} for {request.travellers} traveller(s), "
            f"within {request.budget} {request.currency}."
        ),
        destination=request.destination,
    )
    prompt = (
        f"{rag_prompt} Use this exact response structure: "
        '{"flights":[{"airline":"string","departure_time":"ISO-8601 or clear local time",'
        '"return_time":"ISO-8601 or clear local time","price":0,"currency":"USD",'
        '"stops":0,"booking_url":null}]}. Do not claim options are live or bookable.'
    )
    try:
        return await get_llm_client().generate_structured(prompt, FlightResponse)
    except LLMError as exc:
        logger.warning("flight_generation_failed request_id=%s error=%s", request.request_id, exc)
        return FlightResponse(error="Flight planner is temporarily unavailable.")
