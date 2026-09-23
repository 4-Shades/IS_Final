"""Request-scoped concurrent orchestration of specialist services."""

from __future__ import annotations

import asyncio

from common.a2a_client import call_agent
from shared.config import get_settings
from shared.schemas import (
    ActivitiesResponse,
    FlightResponse,
    ServiceError,
    StayResponse,
    TravelRequest,
    TripPlanResponse,
)


async def run(payload: TravelRequest) -> TripPlanResponse:
    settings = get_settings()
    body = payload.model_dump(mode="json")
    flight_body, stay_body, activities_body = await asyncio.gather(
        call_agent(settings.flight_service_url, body, request_id=payload.request_id,
                   timeout_seconds=settings.downstream_timeout_seconds),
        call_agent(settings.stay_service_url, body, request_id=payload.request_id,
                   timeout_seconds=settings.downstream_timeout_seconds),
        call_agent(settings.activities_service_url, body, request_id=payload.request_id,
                   timeout_seconds=settings.downstream_timeout_seconds),
    )
    flights = FlightResponse.model_validate(flight_body)
    stays = StayResponse.model_validate(stay_body)
    activities = ActivitiesResponse.model_validate(activities_body)
    errors = [
        ServiceError(service=service, message=response.error)
        for service, response in (("flights", flights), ("stay", stays), ("activities", activities))
        if response.error
    ]
    return TripPlanResponse(
        request_id=payload.request_id,
        trip_id=payload.trip_id,
        flights=flights.flights,
        stay=stays.stays,
        activities=activities.activities,
        errors=errors,
    )
