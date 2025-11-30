import streamlit as st
import requests

st.set_page_config(page_title="ADK-Powered Travel Planner", page_icon="✈️")
st.title("🌍 ADK-Powered Travel Planner")
origin = st.text_input("Where are you flying from?", placeholder="e.g., New York")
destination = st.text_input("Destination", placeholder="e.g., Paris")
start_date = st.date_input("Start Date")
end_date = st.date_input("End Date")
budget = st.number_input("Budget (in USD)", min_value=100, step=50)
if st.button("Plan My Trip ✨"):
    if not all([origin, destination, start_date, end_date, budget]):
        st.warning("Please fill in all the details.")
    else:
        payload = {
            "origin": origin,
            "destination": destination,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "budget": budget
        }
        response = requests.post("http://localhost:8000/run", json=payload)
        if response.status_code == 200:
            data = response.json()
            
            st.subheader("Flights")
            st.write(data.get("flights", "No flight information available."))

            st.subheader("Accommodation")
            st.write(data.get("accommodation", "No accommodation information available."))

            st.subheader("Activities")
            st.write(data.get("activities", "No activities information available."))
        
        else:
            st.error(f"Error: {response.status_code}")


