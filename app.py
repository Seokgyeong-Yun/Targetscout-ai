import streamlit as st
import requests
import json
import urllib.parse

st.set_page_config(
    page_title="TargetScout AI",
    page_icon="🧬",
    layout="wide"
)

st.title("🧬 TargetScout AI")
st.subheader("AI-powered antibody target evaluation platform for drug discovery research")

st.markdown("""
TargetScout AI is a Bio-AI web application designed to support early-stage
antibody target evaluation.

This platform helps researchers quickly explore target information, related literature,
clinical development status, competitive antibody landscape, and research suitability.
""")

st.divider()

st.header("Target Evaluation")

target = st.text_input(
    "Enter a target gene or protein name",
    placeholder="Example: MSLN, HER2, HER3, TROP2, CLDN18"
)

if target:
    target_key = target.upper()
    st.success(f"Target entered: {target_key}")

    # --- UniProt Protein Information ---
    st.subheader("Protein Information (UniProt)")

    uniprot_id = None
    try:
        uniprot_url = (
            "https://rest.uniprot.org/uniprotkb/search?"
            f"query=gene_exact:{target_key}+AND+organism_id:9606+AND+reviewed:true"
            "&format=json&size=1"
        )
        uniprot_response = requests.get(uniprot_url)
        uniprot_data = uniprot_response.json()
        results = uniprot_data.get("results", [])

        if not results:
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
                    .get("fullName", {}).get("value", "Unknown")
                )
            elif "submissionNames" in protein_description:
                names = protein_description["submissionNames"]
                if names:
                    recommended_name = names[0].get("fullName", {}).get("value", "Unknown")

            genes = protein.get("genes", [])
            gene_name = genes[0].get("geneName", {}).get("value", "Unknown") if genes else "Unknown"

            # Get function from comments
            function_text = ""
            comments = protein.get("comments", [])
            for comment in comments:
                if comment.get("commentType") == "FUNCTION":
                    texts = comment.get("texts", [])
                    if texts:
                        function_text = texts[0].get("value", "")
                    break

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**UniProt ID:** {uniprot_id}")
                st.markdown(f"**Protein Name:** {recommended_name}")
                st.markdown(f"**Gene Name:** {gene_name}")
                st.markdown(f"**Organism:** {organism}")
                st.markdown(f"**Protein Length:** {protein_length} amino acids")
                st.markdown(f"[View on UniProt](https://www.uniprot.org/uniprotkb/{uniprot_id}/entry)")
            with col2:
                if function_text:
                    st.markdown("**Function**")
                    st.markdown(function_text)

    except Exception as e:
        st.error(f"UniProt Error: {e}")

    # --- NCBI Gene Summary ---
    st.subheader("Gene Summary (NCBI Gene)")

    try:
        gene_search_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
            f"esearch.fcgi?db=gene&term={target_key}[gene]+AND+human[organism]"
            "&retmode=json"
        )
        gene_search_resp = requests.get(gene_search_url)
        gene_search_data = gene_search_resp.json()
        gene_ids = gene_search_data["esearchresult"]["idlist"]

        if not gene_ids:
            st.warning("No NCBI Gene entry found.")
        else:
            gene_id = gene_ids[0]
            gene_summary_url = (
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
                f"esummary.fcgi?db=gene&id={gene_id}&retmode=json"
            )
            gene_summary_resp = requests.get(gene_summary_url)
            gene_summary_data = gene_summary_resp.json()

            gene_record = gene_summary_data["result"][gene_id]
            description = gene_record.get("description", "")
            summary = gene_record.get("summary", "")

            if description:
                st.markdown(f"**{description}**")
            if summary:
                st.markdown(summary)
            else:
                st.info("No detailed summary available for this gene.")

            st.markdown(f"[View on NCBI Gene](https://www.ncbi.nlm.nih.gov/gene/{gene_id})")

    except Exception as e:
        st.error(f"NCBI Gene Error: {e}")

    # --- PDB Structure ---
    st.subheader("Protein 3D Structure (PDB)")

    try:
        pdb_search_url = "https://search.rcsb.org/rcsbsearch/v2/query"
        pdb_query = {
            "query": {
                "type": "terminal",
                "service": "text",
                "parameters": {
                    "attribute": "rcsb_entity_source_organism.rcsb_gene_name.value",
                    "operator": "exact_match",
                    "value": target_key
                }
            },
            "return_type": "entry",
            "request_options": {
                "paginate": {"start": 0, "rows": 5},
                "sort": [{"sort_by": "score", "direction": "desc"}]
            }
        }
        pdb_response = requests.post(pdb_search_url, json=pdb_query)
        pdb_data = pdb_response.json()
        pdb_entries = pdb_data.get("result_set", [])

        if not pdb_entries:
            st.warning("No PDB structures found for this target.")
        else:
            pdb_ids = [entry["identifier"] for entry in pdb_entries]

            # Fetch titles for each PDB entry
            pdb_info = {}
            for pid in pdb_ids:
                try:
                    detail_url = f"https://data.rcsb.org/rest/v1/core/entry/{pid}"
                    detail_resp = requests.get(detail_url)
                    detail_data = detail_resp.json()
                    title = detail_data.get("struct", {}).get("title", pid)
                    pdb_info[pid] = title
                except Exception:
                    pdb_info[pid] = pid

            # Display each structure with image and title
            for pid in pdb_ids:
                title = pdb_info[pid]
                img_url = f"https://cdn.rcsb.org/images/structures/{pid.lower()[1:3]}/{pid.lower()}/{pid.lower()}_assembly-1.jpeg"
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.image(img_url, width=180)
                with col2:
                    st.markdown(
                        f"<div style='padding-top:8px'>"
                        f"<p style='font-size:18px; font-weight:bold; margin-bottom:4px'>{pid}</p>"
                        f"<p style='font-size:16px; margin-bottom:6px'>{title}</p>"
                        f"<a href='https://www.rcsb.org/structure/{pid}' target='_blank' style='font-size:15px'>View on RCSB PDB</a>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                st.markdown("<div style='margin-bottom:8px'></div>", unsafe_allow_html=True)

            rcsb_request = {
                "query": {
                    "type": "terminal",
                    "service": "full_text",
                    "parameters": {"value": target_key}
                },
                "return_type": "entry"
            }
            rcsb_search_url = (
                "https://www.rcsb.org/search?request="
                + urllib.parse.quote(json.dumps(rcsb_request))
            )
            st.markdown(
                f"<a href='{rcsb_search_url}' target='_blank' "
                f"style='font-size:22px; font-weight:bold'>🔍 View more 3D structures on RCSB PDB →</a>",
                unsafe_allow_html=True
            )

    except Exception as e:
        st.error(f"PDB Error: {e}")

    # --- Most Cited Publications ---
    st.subheader("Most Cited Publications (PubMed)")
    st.caption(
        f"Results for the search query **'{target_key} + antibody'**, ranked by citation count (most cited first). "
        "To see the latest research trends, click **🕒 View recent publications on PubMed** at the bottom."
    )

    try:
        # Pull a wider candidate pool, then rank by citation count
        search_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
            f"esearch.fcgi?db=pubmed&term={target_key}[gene]+AND+antibody"
            "&retmax=20&retmode=json&sort=relevance"
        )
        search_response = requests.get(search_url)
        search_data = search_response.json()
        pmids = search_data["esearchresult"]["idlist"]

        if not pmids:
            st.warning("No publications found.")
        else:
            # Get all article summaries in one PubMed call
            summary_url = (
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
                f"esummary.fcgi?db=pubmed&id={','.join(pmids)}&retmode=json"
            )
            summary_response = requests.get(summary_url)
            summary_data = summary_response.json()

            # Get all citation counts in one Semantic Scholar batch call
            citation_map = {}
            try:
                ss_url = (
                    "https://api.semanticscholar.org/graph/v1/paper/batch"
                    "?fields=citationCount"
                )
                ss_body = {"ids": [f"PMID:{pmid}" for pmid in pmids]}
                ss_resp = requests.post(ss_url, json=ss_body)
                if ss_resp.status_code == 200:
                    for pmid, paper in zip(pmids, ss_resp.json()):
                        if paper and paper.get("citationCount") is not None:
                            citation_map[pmid] = paper["citationCount"]
            except Exception:
                citation_map = {}

            # Sort PMIDs by citation count (most cited first), then show top 5
            sorted_pmids = sorted(
                pmids,
                key=lambda p: citation_map.get(p, -1),
                reverse=True
            )[:5]

            for pmid in sorted_pmids:
                if "result" not in summary_data or pmid not in summary_data["result"]:
                    continue

                article = summary_data["result"][pmid]
                title = article.get("title", "No title")
                pub_date = article.get("pubdate", "")
                journal = article.get("fulljournalname", "") or article.get("source", "")
                authors = article.get("authors", [])
                first_author = authors[0].get("name", "") if authors else ""
                citation_count = citation_map.get(pmid)

                st.markdown(f"**{title}**")
                meta_line = f"{first_author} et al. · {pub_date}"
                if journal:
                    meta_line += f" · *{journal}*"
                if citation_count is not None:
                    meta_line += f" · 📊 {citation_count} citations"
                meta_line += f" · PMID: {pmid}"
                st.markdown(meta_line)
                st.markdown(f"[View on PubMed](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")
                st.divider()

            recent_search_url = (
                f"https://pubmed.ncbi.nlm.nih.gov/?term="
                f"{urllib.parse.quote(target_key + ' AND antibody')}&sort=date"
            )
            st.markdown(
                f"<a href='{recent_search_url}' target='_blank' "
                f"style='font-size:22px; font-weight:bold'>🕒 View recent publications on PubMed →</a>",
                unsafe_allow_html=True
            )

    except Exception as e:
        st.error(f"PubMed Error: {e}")

else:
    st.info("Please enter a target name to start evaluation.")
