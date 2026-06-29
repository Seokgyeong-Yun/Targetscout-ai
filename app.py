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

THICK_DIVIDER = "<hr style='border:none; border-top:4px solid #444; margin:32px 0 16px 0'>"

# Greek letter expansions for trailing abbreviations (e.g. FRa -> FR alpha)
GREEK_LETTERS = {
    "A": "alpha", "B": "beta", "G": "gamma",
    "D": "delta", "E": "epsilon",
}

# Common antibody-target shorthands that don't resolve cleanly in UniProt search.
# Maps the typed alias (uppercase) -> official gene symbol.
TARGET_ALIASES = {
    "FRA": "FOLR1", "FRALPHA": "FOLR1", "FOLRA": "FOLR1",
    "FRB": "FOLR2", "FRBETA": "FOLR2",
    "PD1": "PDCD1", "PD-1": "PDCD1",
    "PDL1": "CD274", "PD-L1": "CD274",
    "PDL2": "PDCD1LG2", "PD-L2": "PDCD1LG2",
    "HER1": "EGFR", "ERBB1": "EGFR",
    "HER2": "ERBB2", "NEU": "ERBB2",
    "HER3": "ERBB3", "HER4": "ERBB4",
    "FCRN": "FCGRT",
    "TROP2": "TACSTD2",
    "CLDN18.2": "CLDN18", "CLDN182": "CLDN18",
    "B7H3": "CD276", "B7-H3": "CD276",
    "B7H4": "VTCN1", "B7-H4": "VTCN1",
    "EPCAM": "EPCAM", "CEA": "CEACAM5",
    "GD2": "B4GALNT1",
    "BCMA": "TNFRSF17", "CD319": "SLAMF7",
}


def make_search_variants(term):
    """Generate search variants: known alias first, then greek-letter expansions."""
    variants = []
    if term in TARGET_ALIASES:
        variants.append(TARGET_ALIASES[term])
    variants.append(term)
    if len(term) > 1 and term[-1] in GREEK_LETTERS:
        base = term[:-1]
        word = GREEK_LETTERS[term[-1]]
        variants.append(f"{base} {word}")  # e.g. "FR alpha"
        variants.append(f"{base}{word}")   # e.g. "FRalpha"
    return variants


def resolve_uniprot(term):
    """Find a UniProt entry. Returns (protein, match_type, used_query).

    Tries exact gene matches first (precise), then falls back to full-text
    search (labeled as a closest match that should be verified).
    """
    variants = make_search_variants(term)

    # Pass 1: exact gene-name match for each variant
    for v in variants:
        url = (
            "https://rest.uniprot.org/uniprotkb/search?"
            f"query=gene_exact:{urllib.parse.quote(v)}"
            "+AND+organism_id:9606+AND+reviewed:true&format=json&size=1"
        )
        results = requests.get(url).json().get("results", [])
        if results:
            return results[0], "exact", v

    # Pass 2: full-text search for each variant (closest match)
    for v in variants:
        url = (
            "https://rest.uniprot.org/uniprotkb/search?"
            f"query={urllib.parse.quote(v)}"
            "+AND+organism_id:9606+AND+reviewed:true&format=json&size=1"
        )
        results = requests.get(url).json().get("results", [])
        if results:
            return results[0], "closest", v

    return None, None, None


if target:
    target_key = target.upper()
    st.success(f"Target entered: {target_key}")

    # --- UniProt Protein Information ---
    st.markdown(THICK_DIVIDER, unsafe_allow_html=True)
    st.subheader("Protein Information (UniProt)")

    uniprot_id = None
    try:
        protein, match_type, used_query = resolve_uniprot(target_key)

        if protein is None:
            st.warning(f"No protein found for '{target_key}' (also tried alpha/beta expansions).")
        else:
            if match_type == "closest":
                st.info(
                    f"No exact gene match for '{target_key}'. "
                    f"Showing the closest match from a search for '{used_query}' — please verify."
                )
            uniprot_id = protein.get("primaryAccession", "Unknown")
            organism = protein.get("organism", {}).get("scientificName", "Unknown")
            protein_length = protein.get("sequence", {}).get("length", "Unknown")
            canonical_sequence = protein.get("sequence", {}).get("value", "")

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

            # Use the official gene symbol for all downstream searches
            if gene_name != "Unknown":
                target_key = gene_name.upper()

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

            if canonical_sequence:
                with st.expander("Canonical Sequence (FASTA)"):
                    # Wrap sequence at 60 residues per line (standard FASTA format)
                    wrapped = "\n".join(
                        canonical_sequence[i:i + 60]
                        for i in range(0, len(canonical_sequence), 60)
                    )
                    st.code(f">{uniprot_id}|{gene_name}\n{wrapped}", language=None)
                    st.markdown(
                        f"Source: [UniProt FASTA]"
                        f"(https://rest.uniprot.org/uniprotkb/{uniprot_id}.fasta)"
                    )

    except Exception as e:
        st.error(f"UniProt Error: {e}")

    # --- NCBI Gene Summary ---
    st.markdown(THICK_DIVIDER, unsafe_allow_html=True)
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
    st.markdown(THICK_DIVIDER, unsafe_allow_html=True)
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

    # --- Competitive Drug (Open Targets) ---
    st.markdown(THICK_DIVIDER, unsafe_allow_html=True)
    st.subheader("Competitive Drug (Open Targets)")
    st.caption(
        f"Drugs and clinical candidates targeting **{target_key}**, from the Open Targets Platform."
    )

    try:
        ot_url = "https://api.platform.opentargets.org/api/v4/graphql"

        # Step 1: resolve gene symbol to Ensembl target ID
        ot_search_query = {
            "query": (
                "query($q:String!){search(queryString:$q,entityNames:[\"target\"])"
                "{hits{id name entity}}}"
            ),
            "variables": {"q": target_key}
        }
        ot_search_resp = requests.post(ot_url, json=ot_search_query)
        hits = ot_search_resp.json().get("data", {}).get("search", {}).get("hits", [])

        # Pick the hit whose name exactly matches the target
        ensembl_id = None
        for hit in hits:
            if hit.get("name", "").upper() == target_key:
                ensembl_id = hit.get("id")
                break
        if ensembl_id is None and hits:
            ensembl_id = hits[0].get("id")

        if ensembl_id is None:
            st.warning("No target found on Open Targets.")
        else:
            # Step 2: fetch drugs / clinical candidates for the target
            ot_drug_query = {
                "query": (
                    "query($id:String!){target(ensemblId:$id){"
                    "drugAndClinicalCandidates{count rows{maxClinicalStage "
                    "drug{id name drugType description "
                    "mechanismsOfAction{rows{mechanismOfAction}}}}}}}"
                ),
                "variables": {"id": ensembl_id}
            }
            ot_drug_resp = requests.post(ot_url, json=ot_drug_query)
            candidates = (
                ot_drug_resp.json()
                .get("data", {}).get("target", {})
                .get("drugAndClinicalCandidates", {})
            )
            rows = candidates.get("rows", [])

            if not rows:
                st.warning("No drugs or clinical candidates found for this target.")
            else:
                st.markdown(f"**{len(rows)} drug(s)/candidate(s) found:**")
                for row in rows:
                    drug = row.get("drug", {})
                    name = drug.get("name", "Unknown")
                    drug_id = drug.get("id", "")
                    drug_type = drug.get("drugType", "Unknown")
                    description = drug.get("description", "")
                    max_stage = row.get("maxClinicalStage", "").replace("_", " ").title()

                    moa_rows = drug.get("mechanismsOfAction", {}).get("rows", [])
                    moa_list = [m.get("mechanismOfAction", "") for m in moa_rows]
                    moa_text = ", ".join(moa_list) if moa_list else "N/A"

                    st.markdown(
                        f"<p style='font-size:26px; font-weight:bold; margin-bottom:2px'>"
                        f"{name} <span style='font-size:15px; color:gray'>({drug_type})</span></p>",
                        unsafe_allow_html=True
                    )
                    if description:
                        st.markdown(f"{description}")
                    st.markdown(f"**Max stage:** {max_stage}")
                    st.markdown(f"**Mechanism of action:** {moa_text}")
                    if drug_id:
                        st.markdown(
                            f"[View on Open Targets](https://platform.opentargets.org/drug/{drug_id})"
                        )
                    st.divider()

                st.markdown(
                    f"<a href='https://platform.opentargets.org/search?q={target_key}&page=1&entities=drug' "
                    f"target='_blank' style='font-size:22px; font-weight:bold'>"
                    f"💊 View all drugs on Open Targets →</a>",
                    unsafe_allow_html=True
                )

    except Exception as e:
        st.error(f"Open Targets Error: {e}")

    # --- Most Cited Publications ---
    st.markdown(THICK_DIVIDER, unsafe_allow_html=True)
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
