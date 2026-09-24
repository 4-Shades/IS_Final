from __future__ import annotations

import requests
import streamlit as st

from shared.config import get_settings


def _host_service_url() -> str:
    try:
        configured_url = st.secrets.get("HOST_SERVICE_URL")
    except (FileNotFoundError, KeyError):
        configured_url = None
    return (configured_url or get_settings().host_service_url).rstrip("/")


def _show_offers(title: str, offers: list[dict] | None) -> None:
    if not offers:
        st.info(f"No {title.lower()} suggestions were returned.")
        return

    st.subheader(title)
    st.dataframe(offers, use_container_width=True)


st.set_page_config(page_title="Travel Planner", page_icon="✈️")
st.title("🌍 Travel Planner")

origin = st.text_input("Where are you flying from?", placeholder="e.g., New York")
destination = st.text_input("Destination", placeholder="e.g., Paris")
start_date = st.date_input("Start Date")
end_date = st.date_input("End Date")
budget = st.number_input("Budget (in USD)", min_value=100, step=50)
travellers = st.number_input("Travellers", min_value=1, max_value=9, value=1, step=1)

if st.button("Plan My Trip ✨"):
    if not origin or not destination:
        st.warning("Please enter both the origin and destination.")
    elif end_date <= start_date:
        st.warning("End date must be after the start date.")
    else:
        payload = {
            "origin": origin.strip(),
            "destination": destination.strip(),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "budget": float(budget),
            "currency": "USD",
            "travellers": int(travellers),
            "preferences": [],
        }
        try:
            response = requests.post(
                f"{_host_service_url()}/run",
                json=payload,
                timeout=35,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            st.error(f"The planning service is unavailable: {exc}")
            st.stop()

        for error in data.get("errors", []):
            service_name = error.get("service", "service").title()
            message = error.get("message", "Unknown issue")
            st.warning(f"{service_name}: {message}")

        flights = data.get("flights") or []
        stays = data.get("stay") or []
        activities = data.get("activities") or []

        _show_offers("Flights", flights)
        _show_offers("Accommodation", stays)
        _show_offers("Activities", activities)

        if not flights and not stays and not activities:
            st.info("The host agent did not return any trip options. Try adjusting the travel window or budget.")
