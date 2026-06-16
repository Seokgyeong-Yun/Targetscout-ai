import streamlit as st

# Page settings
st.set_page_config(
    page_title="TargetScout AI",
    page_icon="🧬",
    layout="wide"
)

# Header
st.title("🧬 TargetScout AI")
st.subheader("AI-powered antibody target evaluation platform for drug discovery research")

st.markdown("""
TargetScout AI is a Bio-AI web application designed to support early-stage 
antibody target evaluation.

This platform helps researchers quickly explore target information, related literature,
clinical development status, competitive antibody landscape, and research suitability.
""")

st.divider()

# About Me section
st.header("About Me")

st.markdown("""
I am a graduate student in antibody engineering and drug discovery.

My research interests include:

- Antibody therapeutics
- Oncology target discovery
- Therapeutic target validation
- Competitive landscape analysis
- AI and data-driven drug discovery
""")

st.divider()

# Target search section
st.header("Target Evaluation")

target = st.text_input(
    "Enter a target gene or protein name",
    placeholder="Example: MSLN, HER3, TROP2, CLDN18.2"
)

if target:
    st.success(f"Target entered: {target}")

    st.subheader("TargetScout AI Summary")
    st.markdown(f"""
    You searched for **{target}**.

    In the full version, this app will provide:

    - Basic target overview
    - Related diseases
    - Recent PubMed literature
    - Clinical trial information
    - Competitive antibody landscape
    - Patent search resources
    - Target suitability assessment
    - Daily research trend monitoring
    """)

else:
    st.info("Please enter a target name to start evaluation.")
