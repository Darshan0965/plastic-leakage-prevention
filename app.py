
import streamlit as st

st.set_page_config(
    page_title="Plastic Leakage Prevention",
    page_icon="🌱",
    layout="wide"
)

st.title("🌱 Plastic Leakage Prevention")
st.subheader("Drainage Hotspot Intelligence System")

st.write(
    "Monitor drainage networks, record field observations, "
    "and prioritize plastic pollution cleanup."
)

st.info(
    "Streamlit interface is running. Connect the FastAPI "
    "backend to load your actual network and hotspot data."
)

col1, col2 = st.columns(2)

with col1:
    st.metric("System", "Online")

with col2:
    st.metric("Backend", "Not connected")

st.header("Project Overview")

st.markdown("""
- Drainage network visualization
- Field observation management
- Potential drainage pathway analysis
- Cleanup hotspot prioritization
""")

st.caption(
    "Connect verified drainage data before using this "
    "system for real-world decisions."
)
