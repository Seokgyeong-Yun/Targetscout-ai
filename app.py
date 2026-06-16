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
target_database = {
    "MSLN": {
        "official_symbol": "MSLN",
        "protein_name": "Mesothelin",
        "target_class": "Cell surface glycoprotein",
        "research_area": "Solid tumor antibody therapeutics",
        "known_risks": "Shedding, soluble antigen sink, normal mesothelial expression"
    },
    "HER3": {
        "official_symbol": "ERBB3",
        "protein_name": "Receptor tyrosine-protein kinase erbB-3",
        "target_class": "Receptor tyrosine kinase family",
        "research_area": "Oncology, ADC, bispecific antibody",
        "known_risks": "Tumor heterogeneity, pathway compensation, variable expression"
    },
    "TROP2": {
        "official_symbol": "TACSTD2",
        "protein_name": "Tumor-associated calcium signal transducer 2",
        "target_class": "Cell surface glycoprotein",
        "research_area": "ADC and solid tumor therapy",
        "known_risks": "Normal epithelial expression, toxicity risk, resistance"
    },
    "CLDN18.2": {
        "official_symbol": "CLDN18",
        "protein_name": "Claudin-18 isoform 2",
        "target_class": "Tight junction protein",
        "research_area": "Gastric cancer, pancreatic cancer, antibody therapeutics",
        "known_risks": "Isoform specificity, gastric tissue expression, patient selection"
    }
}
if target:
    target_key = target.upper()

    st.success(f"Target entered: {target_key}")

    st.subheader("Target Overview")

    if target_key in target_database:
        info = target_database[target_key]

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**Official Symbol:** {info['official_symbol']}")
            st.markdown(f"**Protein Name:** {info['protein_name']}")
            st.markdown(f"**Target Class:** {info['target_class']}")

        with col2:
            st.markdown(f"**Research Area:** {info['research_area']}")
            st.markdown(f"**Known Risks:** {info['known_risks']}")

    else:
        st.warning("Target overview is not available in the local database yet.")
    st.subheader("UniProt Protein Information")

    try:
        uniprot_url = (
            "https://rest.uniprot.org/uniprotkb/search?"
            f"query=gene:{target_key}+AND+organism_id:9606&format=json&size=1"
        )

        uniprot_response = requests.get(uniprot_url)
        uniprot_data = uniprot_response.json()

        results = uniprot_data.get("results", [])

        if len(results) == 0:
            st.warning("No UniProt protein information found.")

        else:
            protein = results[0]

            uniprot_id = protein.get("primaryAccession", "Unknown")
            organism = protein.get("organism", {}).get("scientificName", "Unknown")
            protein_length = protein.get("sequence", {}).get("length", "Unknown")

            protein_description = protein.get("proteinDescription", {})

            recommended_name = "Unknown"

            if "recommendedName" in protein_description:
                recommended_name = (
                    protein_description["recommendedName"]
                    .get("fullName", {})
                    .get("value", "Unknown")
                )

            elif "submissionNames" in protein_description:
                submission_names = protein_description["submissionNames"]

                if len(submission_names) > 0:
                    recommended_name = (
                        submission_names[0]
                        .get("fullName", {})
                        .get("value", "Unknown")
                    )

            genes = protein.get("genes", [])
            gene_name = "Unknown"

            if len(genes) > 0:
                gene_name = (
                    genes[0]
                    .get("geneName", {})
                    .get("value", "Unknown")
                )

            st.markdown(f"**UniProt ID:** {uniprot_id}")
            st.markdown(f"**Protein Name:** {recommended_name}")
            st.markdown(f"**Gene Name:** {gene_name}")
            st.markdown(f"**Organism:** {organism}")
            st.markdown(f"**Protein Length:** {protein_length} amino acids")
            st.markdown(f"[View on UniProt](https://www.uniprot.org/uniprotkb/{uniprot_id}/entry)")
    except Exception as e:
        st.error(f"UniProt Error: {e}")

    st.subheader("Recent Publications")

    try:
        search_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
            f"esearch.fcgi?db=pubmed&term={target_key}"
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
                    (f"[View on PubMed](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")
                )

                st.divider()

    except Exception as e:
        st.error(f"Error: {e}")

else:
    st.info("Please enter a target name to start evaluation.")
