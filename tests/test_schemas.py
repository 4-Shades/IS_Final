from datetime import date

import pytest
from pydantic import ValidationError

from shared.schemas import TravelRequest


def test_request_normalises_values_and_generates_identifiers() -> None:
    request = TravelRequest(
        origin="  New   York ",
        destination="Paris",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 8),
        budget=1500,
        currency="usd",
    )
    assert request.origin == "New York"
    assert request.currency == "USD"
    assert request.request_id
    assert request.trip_id


def test_request_rejects_invalid_dates() -> None:
    with pytest.raises(ValidationError, match="end_date must be after start_date"):
        TravelRequest(
            origin="New York", destination="Paris", start_date=date(2026, 9, 8),
            end_date=date(2026, 9, 8), budget=1500,
        )
