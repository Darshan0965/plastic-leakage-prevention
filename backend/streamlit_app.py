
import streamlit as st
import requests

API_BASE_URL = "https://plastic-leakage-prevention.onrender.com"

st.set_page_config(
    page_title="Drainage Hotspot Intelligence System",
    page_icon="🌿",
    layout="wide",
)

st.title("Drainage Hotspot Intelligence System")

if st.button("Connect to backend"):
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/field-observations",
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()

        st.success("Backend connected successfully!")

        col1, col2, col3 = st.columns(3)
        col1.metric("Field records", result["count"])
        col2.metric("Verified", result["verified_count"])
        col3.metric("Unverified", result["unverified_count"])

        st.dataframe(
            result["observations"],
            use_container_width=True,
        )

    except requests.RequestException as exc:
        st.error(f"Backend connection failed: {exc}")
