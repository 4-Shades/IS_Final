"""Versioned request and response contracts shared by every service."""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class TravelRequest(BaseModel):
    """A validated request for a single travel-planning operation."""

    origin: str = Field(min_length=2, max_length=120)
    destination: str = Field(min_length=2, max_length=120)
    start_date: date
    end_date: date
    budget: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    travellers: int = Field(default=1, ge=1, le=9)
    preferences: list[str] = Field(default_factory=list, max_length=20)
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    trip_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str | None = Field(default=None, max_length=128)

    @field_validator("origin", "destination")
    @classmethod
    def normalise_location(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("currency")
    @classmethod
    def normalise_currency(cls, value: str) -> str:
        value = value.upper()
        if not value.isalpha():
            raise ValueError("currency must contain three letters")
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> "TravelRequest":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class FlightOffer(BaseModel):
    airline: str
    departure_time: str
    return_time: str
    price: float = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    stops: int = Field(ge=0, default=0)
    booking_url: str | None = None


class StayOffer(BaseModel):
    name: str
    location: str
    price_per_night: float = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    booking_url: str | None = None


class ActivityOffer(BaseModel):
    name: str
    description: str
    price: float = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    duration_hours: float = Field(gt=0)
    source_url: str | None = None


class FlightResponse(BaseModel):
    flights: list[FlightOffer] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def validate_flight_payload(self) -> "FlightResponse":
        if not self.flights and self.error is None:
            raise ValueError("flight response must include at least one flight or an explicit error")
        return self


class StayResponse(BaseModel):
    stays: list[StayOffer] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def validate_stay_payload(self) -> "StayResponse":
        if not self.stays and self.error is None:
            raise ValueError("stay response must include at least one stay or an explicit error")
        return self


class ActivitiesResponse(BaseModel):
    activities: list[ActivityOffer] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def validate_activity_payload(self) -> "ActivitiesResponse":
        if not self.activities and self.error is None:
            raise ValueError("activity response must include at least one activity or an explicit error")
        return self


class ServiceError(BaseModel):
    service: Literal["flights", "stay", "activities"]
    message: str


class TripPlanResponse(BaseModel):
    request_id: str
    trip_id: str
    flights: list[FlightOffer] = Field(default_factory=list)
    stay: list[StayOffer] = Field(default_factory=list)
    activities: list[ActivityOffer] = Field(default_factory=list)
    errors: list[ServiceError] = Field(default_factory=list)
