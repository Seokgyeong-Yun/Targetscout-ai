import streamlit as st
import requests
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

    st.subheader("Recent Publications")

    try:
        search_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
            f"esearch.fcgi?db=pubmed&term={target}"
            "&retmax=5&retmode=json"
        )

        search_response = requests.get(search_url)
        search_data = search_response.json()

        pmids = search_data["esearchresult"]["idlist"]

        if len(pmids) == 0:
            st.warning("No publications found.")

        else:

            for pmid in pmids:

                summary_url = (
                    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
                    f"esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
                )

                summary_response = requests.get(summary_url)
                summary_data = summary_response.json()

                article = summary_data["result"][pmid]

                title = article.get("title", "No title")

                st.markdown(
                    f"**{title}**"
                )

                st.markdown(
                    f"PMID: {pmid}"
                )

                st.markdown(
                    f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                )

                st.divider()

    except Exception as e:
        st.error(f"Error: {e}")

else:
    st.info("Please enter a target name to start evaluation.")
