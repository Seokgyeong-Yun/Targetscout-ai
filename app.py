import streamlit as st
import requests
import json
import urllib.parse

st.set_page_config(
    page_title="TargetScout AI",
    page_icon="🧬",
    layout="wide"
)

SITE_URL = "https://targetscout-ai-2r93scygucnqwntbd5ta2q.streamlit.app"

st.title("🧬 TargetScout AI")
st.subheader("AI-powered antibody target evaluation platform for drug discovery research")

# Click-to-copy site link button
st.components.v1.html(
    f"""
    <button id="copyBtn"
        onclick="navigator.clipboard.writeText('{SITE_URL}').then(() => {{
            const b = document.getElementById('copyBtn');
            b.innerText = '✅ Link copied!';
            setTimeout(() => b.innerText = '🔗 Copy site link', 1500);
        }})"
        style="background:#f0f2f6; border:1px solid #ccc; border-radius:8px;
               padding:6px 14px; font-size:15px; cursor:pointer; font-family:inherit;">
        🔗 Copy site link
    </button>
    """,
    height=45,
)

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

# Latin -> Greek letter map, so a trailing abbreviation like "FRa" can be
# matched against the real greek symbol "FRα" used by gene-name databases.
GREEK_CHARS = {
    "A": "α", "B": "β", "G": "γ", "D": "δ", "E": "ε", "K": "κ",
}

HGNC_HEADERS = {"Accept": "application/json"}


def search_variants(term):
    """Greek form first (e.g. FRA -> FRα), then the literal term."""
    variants = []
    if len(term) > 1 and term[-1] in GREEK_CHARS:
        variants.append(term[:-1] + GREEK_CHARS[term[-1]])
    variants.append(term)
    return variants


def _hgnc_docs(path):
    try:
        resp = requests.get(f"https://rest.genenames.org/{path}", headers=HGNC_HEADERS)
        return resp.json().get("response", {}).get("docs", [])
    except Exception:
        return []


def resolve_official_symbol(term):
    """Resolve any input to an official HGNC gene symbol via search (no hardcoding).

    Returns (official_symbol, quality): quality is 'exact' for an
    official/alias/previous-symbol match, 'closest' for a fuzzy match,
    or (None, None) if nothing is found.
    """
    variants = search_variants(term)

    # 1. exact official symbol
    for v in variants:
        docs = _hgnc_docs(f"fetch/symbol/{urllib.parse.quote(v)}")
        if docs:
            return docs[0]["symbol"], "exact"

    # 2. exact alias or previous symbol
    for v in variants:
        docs = _hgnc_docs(f"search/alias_symbol/{urllib.parse.quote(v)}")
        if docs:
            return docs[0]["symbol"], "exact"
        docs = _hgnc_docs(f"search/prev_symbol/{urllib.parse.quote(v)}")
        if docs:
            return docs[0]["symbol"], "exact"

    # 3. fuzzy full-text search (closest match)
    for v in variants:
        docs = _hgnc_docs(f"search/{urllib.parse.quote(v)}")
        if docs:
            return docs[0]["symbol"], "closest"

    return None, None


def fetch_fda_approval(drug_name):
    """Look up a drug in openFDA (Drugs@FDA). Returns FDA info dict or None.

    Confirms the drug is FDA-approved and returns brand name, sponsor,
    and the earliest approval date.
    """
    try:
        url = (
            "https://api.fda.gov/drug/drugsfda.json?search="
            f"openfda.generic_name:{urllib.parse.quote(drug_name.lower())}&limit=20"
        )
        results = requests.get(url).json().get("results", [])
        if not results:
            return None

        # Among all applications, pick the one with the earliest approval date
        # (the original drug, not a newer combination product).
        best = None
        for entry in results:
            approval_dates = [
                s.get("submission_status_date")
                for s in entry.get("submissions", [])
                if s.get("submission_status") == "AP" and s.get("submission_status_date")
            ]
            if not approval_dates:
                continue
            earliest = min(approval_dates)
            if best is None or earliest < best["_date"]:
                openfda = entry.get("openfda", {})
                brand = openfda.get("brand_name", [])
                best = {
                    "_date": earliest,
                    "brand_name": brand[0] if brand else None,
                    "sponsor": entry.get("sponsor_name"),
                    "application_number": entry.get("application_number"),
                }

        if best is None:
            return None

        d = best["_date"]
        if len(d) == 8:
            best["approval_date"] = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        else:
            best["approval_date"] = d
        return best
    except Exception:
        return None


def generate_ai_assessment(ctx):
    """Call Groq (free tier) to produce a structured target assessment.

    Reads the API key from Streamlit secrets ("GROQ_API_KEY").
    Returns a parsed dict, or an error string starting with 'ERROR:'.
    """
    api_key = st.secrets.get("GROQ_API_KEY", "")
    if not api_key:
        return "ERROR: No Groq API key configured."

    # Build a compact context from the gathered data
    def block(title, items, limit=6):
        if not items:
            return f"{title}: none found\n"
        if isinstance(items, list):
            items = "; ".join(str(i) for i in items[:limit])
        return f"{title}: {items}\n"

    context = (
        block("Target gene symbol", ctx.get("symbol"))
        + block("Protein name", ctx.get("protein_name"))
        + block("Protein function", ctx.get("function"))
        + block("Gene summary", ctx.get("gene_summary"))
        + block("Competitive drugs/candidates", ctx.get("competitive"))
        + block("FDA-approved drugs", ctx.get("fda"))
        + block("Recent clinical trials", ctx.get("trials"))
        + block("Most-cited publications", ctx.get("publications"))
    )

    prompt = (
        "You are a critical antibody drug-discovery analyst scoring how attractive an "
        "antigen is as a target for a NEW antibody program. Base your answer ONLY on the "
        "data below.\n\n"
        "Score 1-10 using this rubric, and USE THE FULL RANGE — do not default to 7-8:\n"
        "- 9-10: Strong biological validation AND clear white space (little/no direct "
        "antibody competition). Rare.\n"
        "- 7-8: Well validated but already has approved antibodies / crowded competition, "
        "OR promising but early. Novelty is limited.\n"
        "- 5-6: Mixed signals — some validation but notable risks (toxicity, shedding, "
        "poor specificity) or heavy crowding.\n"
        "- 3-4: Weak validation, major liabilities, or extremely crowded with little "
        "differentiation.\n"
        "- 1-2: Little evidence supporting it as an antibody target.\n\n"
        "Key principle: a heavily crowded target with many approved antibodies is LESS "
        "attractive for a NEW program (lower score), even if biologically validated. "
        "Weigh competition, validation, and target liabilities against each other and "
        "differentiate targets — they should not all get the same score.\n\n"
        "Respond in JSON with exactly these keys:\n"
        '{"score": <integer 1-10>, "justification": "<one sentence citing the main '
        'drivers of the score>", "opportunities": ["<point>", ...], '
        '"risks": ["<point>", ...], "competitive_crowding": "<one to two sentences>", '
        '"summary": "<2-3 sentence final verdict / bottom line>"}\n'
        "Give 2-4 items each for opportunities and risks. Be objective, note where "
        "evidence is limited, and do not invent facts not supported by the data.\n\n"
        f"=== DATA ===\n{context}"
    )

    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        resp = requests.post(url, headers=headers, json=body, timeout=60)
        data = resp.json()
        if "choices" not in data:
            return f"ERROR: {data.get('error', {}).get('message', 'Unexpected response')}"
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        return f"ERROR: {e}"


def fetch_uniprot(symbol):
    """Fetch the reviewed human UniProt entry for an exact gene symbol."""
    url = (
        "https://rest.uniprot.org/uniprotkb/search?"
        f"query=gene_exact:{urllib.parse.quote(symbol)}"
        "+AND+organism_id:9606+AND+reviewed:true&format=json&size=1"
    )
    results = requests.get(url).json().get("results", [])
    return results[0] if results else None


if target:
    target_key = target.upper()
    st.success(f"Target entered: {target_key}")

    # Collects key facts from each section for the AI assessment at the bottom
    ai_ctx = {
        "symbol": target_key,
        "protein_name": None,
        "function": None,
        "gene_summary": None,
        "competitive": [],   # "name (type) — stage"
        "fda": [],           # "name — brand, approval date"
        "trials": [],        # "title — status, phase"
        "publications": [],  # "title (citations)"
    }

    # --- UniProt Protein Information ---
    st.markdown(THICK_DIVIDER, unsafe_allow_html=True)
    st.subheader("Protein Information (UniProt)")

    uniprot_id = None
    try:
        # Resolve the input to an official gene symbol via HGNC, then fetch UniProt
        official_symbol, match_type = resolve_official_symbol(target_key)
        protein = fetch_uniprot(official_symbol) if official_symbol else None
        used_query = official_symbol

        if protein is None:
            st.warning(f"No gene/protein found for '{target_key}' (also tried greek-letter forms).")
        else:
            if match_type == "closest":
                st.info(
                    f"No exact gene-symbol match for '{target_key}'. "
                    f"Showing the closest match (official symbol: {official_symbol}) — please verify."
                )
            elif official_symbol and official_symbol.upper() != target_key:
                st.caption(f"Resolved '{target_key}' → official gene symbol **{official_symbol}**")
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
                ai_ctx["symbol"] = target_key
            ai_ctx["protein_name"] = recommended_name

            # Get function from comments
            function_text = ""
            comments = protein.get("comments", [])
            for comment in comments:
                if comment.get("commentType") == "FUNCTION":
                    texts = comment.get("texts", [])
                    if texts:
                        function_text = texts[0].get("value", "")
                    break
            ai_ctx["function"] = function_text

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
                    # Wrap sequence at 120 residues per line
                    wrapped = "\n".join(
                        canonical_sequence[i:i + 120]
                        for i in range(0, len(canonical_sequence), 120)
                    )
                    st.code(f">{uniprot_id}|{gene_name}\n{wrapped}", language=None)
                    st.markdown(
                        f"Source: [UniProt {uniprot_id} — Sequence]"
                        f"(https://www.uniprot.org/uniprotkb/{uniprot_id}/entry#sequences)"
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
            ai_ctx["gene_summary"] = summary or description

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

    # --- Fetch Open Targets drug data once (shared by FDA + Competitive sections) ---
    ot_ensembl_id = None
    ot_sorted_rows = []      # list of (rank, row), highest stage first
    ot_unique_count = 0
    approved_drug_names = []  # all approved drug names, used by the FDA section
    ot_error = None

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
        for hit in hits:
            if hit.get("name", "").upper() == target_key:
                ot_ensembl_id = hit.get("id")
                break
        if ot_ensembl_id is None and hits:
            ot_ensembl_id = hits[0].get("id")

        # Step 2: fetch drugs / clinical candidates for the target
        if ot_ensembl_id is not None:
            ot_drug_query = {
                "query": (
                    "query($id:String!){target(ensemblId:$id){"
                    "drugAndClinicalCandidates{count rows{maxClinicalStage "
                    "drug{id name drugType description "
                    "mechanismsOfAction{rows{mechanismOfAction}}}}}}}"
                ),
                "variables": {"id": ot_ensembl_id}
            }
            ot_drug_resp = requests.post(ot_url, json=ot_drug_query)
            rows = (
                ot_drug_resp.json().get("data", {}).get("target", {})
                .get("drugAndClinicalCandidates", {}).get("rows", [])
            )

            stage_rank = {
                "APPROVAL": 9, "PHASE_4": 8, "PHASE_3": 7, "PHASE_2_3": 6,
                "PHASE_2": 5, "PHASE_1_2": 4, "PHASE_1": 3,
                "EARLY_PHASE_1": 2, "PRECLINICAL": 1,
            }
            # Deduplicate by drug id (keep the highest-stage row per drug)
            unique = {}
            for row in rows:
                drug_id = row.get("drug", {}).get("id", "")
                if not drug_id:
                    continue
                rank = stage_rank.get(row.get("maxClinicalStage", ""), 0)
                if drug_id not in unique or rank > unique[drug_id][0]:
                    unique[drug_id] = (rank, row)

            ot_unique_count = len(unique)
            ot_sorted_rows = sorted(unique.values(), key=lambda x: x[0], reverse=True)
            approved_drug_names = [
                r[1].get("drug", {}).get("name", "")
                for r in ot_sorted_rows
                if r[1].get("maxClinicalStage") == "APPROVAL"
            ]
            for _, row in ot_sorted_rows[:8]:
                drug = row.get("drug", {})
                stage = row.get("maxClinicalStage", "").replace("_", " ").title()
                ai_ctx["competitive"].append(
                    f"{drug.get('name', '')} ({drug.get('drugType', '')}) — {stage}"
                )
    except Exception as e:
        ot_error = str(e)

    # --- FDA-Approved Drugs (openFDA) ---
    st.markdown(THICK_DIVIDER, unsafe_allow_html=True)
    st.subheader("FDA-Approved Drugs (openFDA)")
    st.info("✅ Shows only **FDA-approved** drugs (confirmed in the FDA Drugs@FDA database).")

    try:
        if ot_error:
            st.error(f"openFDA Error: {ot_error}")
        elif not approved_drug_names:
            st.warning("No FDA-approved drugs found for this target.")
        else:
            # Look up each approved drug in openFDA, keep those that are FDA-approved
            fda_drugs = []
            for drug_name in approved_drug_names:
                fda = fetch_fda_approval(drug_name)
                if fda is not None:
                    fda_drugs.append((drug_name, fda))

            if not fda_drugs:
                st.warning("No FDA-approved drugs found for this target.")
            else:
                # Sort by FDA approval date, newest first
                fda_drugs.sort(key=lambda x: x[1].get("_date", ""), reverse=True)
                shown = fda_drugs[:5]

                for drug_name, fda in fda_drugs:
                    ai_ctx["fda"].append(
                        f"{drug_name.title()} — {fda.get('brand_name', '')}, "
                        f"approved {fda.get('approval_date', '')}"
                    )

                for drug_name, fda in shown:
                    st.markdown(
                        f"<p style='font-size:24px; font-weight:bold; margin-bottom:2px'>"
                        f"{drug_name.title()}</p>",
                        unsafe_allow_html=True
                    )
                    if fda.get("brand_name"):
                        st.markdown(f"**Brand name:** {fda['brand_name']}")
                    if fda.get("sponsor"):
                        st.markdown(f"**Sponsor:** {fda['sponsor'].title()}")
                    if fda.get("approval_date"):
                        st.markdown(f"**First FDA approval:** {fda['approval_date']}")
                    app_no = fda.get("application_number")
                    if app_no:
                        st.markdown(
                            f"[View on Drugs@FDA]"
                            f"(https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={app_no.replace('BLA','').replace('NDA','').replace('ANDA','')})"
                        )
                    st.divider()

                # Drugs@FDA has no target-based search, so only link out (to the
                # FDA search page) when there are more approved drugs than shown.
                if len(fda_drugs) > len(shown):
                    st.markdown(
                        f"<a href='https://www.accessdata.fda.gov/scripts/cder/daf/' "
                        f"target='_blank' style='font-size:22px; font-weight:bold'>"
                        f"💊 {len(fda_drugs)} FDA-approved in total — search more on Drugs@FDA →</a>",
                        unsafe_allow_html=True
                    )

    except Exception as e:
        st.error(f"openFDA Error: {e}")

    # --- Competitive Drug (Open Targets) ---
    st.markdown(THICK_DIVIDER, unsafe_allow_html=True)
    st.subheader("Competitive Drug (Open Targets)")
    st.caption(f"Drugs and clinical candidates targeting **{target_key}**, from Open Targets.")
    st.warning(
        "⚠️ **Approval status may differ from the FDA.** Open Targets aggregates global "
        "regulators (FDA, EMA, etc.) and past approvals, so a drug marked *Approval* here "
        "may not be FDA-approved (e.g. EMA-only or later withdrawn).\n\n"
        "Check the FDA section above."
    )

    try:
        if ot_error:
            st.error(f"Open Targets Error: {ot_error}")
        elif not ot_sorted_rows:
            st.warning("No drugs or clinical candidates found for this target.")
        else:
            # Show top 5 by clinical stage (highest first)
            shown = ot_sorted_rows[:5]
            st.markdown(
                f"**Showing {len(shown)} of {ot_unique_count} drug(s)** "
                f"(top candidates by clinical stage):"
            )

            for _, row in shown:
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
                f"<a href='https://platform.opentargets.org/target/{ot_ensembl_id}/known_drugs' "
                f"target='_blank' style='font-size:22px; font-weight:bold'>"
                f"💊 View all {ot_unique_count} drugs on Open Targets →</a>",
                unsafe_allow_html=True
            )

    except Exception as e:
        st.error(f"Open Targets Error: {e}")

    # --- Clinical Trials (ClinicalTrials.gov) ---
    st.markdown(THICK_DIVIDER, unsafe_allow_html=True)
    st.subheader("Clinical Trials (ClinicalTrials.gov)")
    st.caption(
        f"Recent clinical trials for **{target_key} + antibody**, newest update first."
    )

    try:
        ct_url = (
            "https://clinicaltrials.gov/api/v2/studies?"
            f"query.term={urllib.parse.quote(target_key + ' antibody')}"
            "&pageSize=5&countTotal=true&sort=LastUpdatePostDate:desc"
        )
        ct_data = requests.get(ct_url).json()
        studies = ct_data.get("studies", [])
        total = ct_data.get("totalCount")

        if not studies:
            st.warning("No clinical trials found.")
        else:
            for s in studies:
                p = s.get("protocolSection", {})
                idm = p.get("identificationModule", {})
                status_mod = p.get("statusModule", {})
                status = status_mod.get("overallStatus", "")
                phases = p.get("designModule", {}).get("phases", [])
                conditions = p.get("conditionsModule", {}).get("conditions", [])

                nct_id = idm.get("nctId", "")
                title = idm.get("briefTitle", "No title")
                phase_text = ", ".join(ph.replace("PHASE", "Phase ") for ph in phases) if phases else "N/A"
                status_text = status.replace("_", " ").title() if status else "Unknown"

                start_date = status_mod.get("startDateStruct", {}).get("date", "")
                end_date = (
                    status_mod.get("completionDateStruct", {}).get("date", "")
                    or status_mod.get("primaryCompletionDateStruct", {}).get("date", "")
                )

                st.markdown(
                    f"<p style='font-size:18px; font-weight:bold; margin-bottom:2px'>{title}</p>",
                    unsafe_allow_html=True
                )
                meta = f"**Status:** {status_text} · **Phase:** {phase_text}"
                st.markdown(meta)
                if start_date or end_date:
                    st.markdown(f"**Start:** {start_date or 'N/A'} · **Completion:** {end_date or 'N/A'}")
                if conditions:
                    st.markdown(f"**Conditions:** {', '.join(conditions[:4])}")
                st.markdown(f"[View on ClinicalTrials.gov](https://clinicaltrials.gov/study/{nct_id})")
                st.divider()

                ai_ctx["trials"].append(f"{title} — {status_text}, {phase_text}")

            ct_search_url = (
                "https://clinicaltrials.gov/search?term="
                + urllib.parse.quote(target_key + " antibody")
            )
            more_label = f"🧪 View all {total} trials on ClinicalTrials.gov →" if total else "🧪 View more trials on ClinicalTrials.gov →"
            st.markdown(
                f"<a href='{ct_search_url}' target='_blank' "
                f"style='font-size:22px; font-weight:bold'>{more_label}</a>",
                unsafe_allow_html=True
            )

    except Exception as e:
        st.error(f"ClinicalTrials.gov Error: {e}")

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

                cites = f"{citation_count} citations" if citation_count is not None else "citation count N/A"
                ai_ctx["publications"].append(f"{title} ({cites})")

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

    # --- AI Target Assessment (Google Gemini) ---
    st.markdown(THICK_DIVIDER, unsafe_allow_html=True)
    st.subheader("AI Target Assessment")
    st.warning(
        "🤖 **AI-generated opinion for reference only.** This summary is produced by an "
        "AI model from the data above and may contain errors. Always verify against "
        "primary sources before making research decisions."
    )

    with st.expander("ℹ️ How the suitability score is defined"):
        st.markdown(
            "The score (1–10) rates how attractive this antigen is as a target for a "
            "**new** antibody program — weighing biological validation, target liabilities, "
            "and competitive crowding.\n\n"
            "- **9–10:** Strong validation **and** clear white space (little/no direct "
            "antibody competition). Rare.\n"
            "- **7–8:** Well validated but already has approved antibodies / crowded "
            "competition, or promising but early. Limited novelty.\n"
            "- **5–6:** Mixed signals — some validation but notable risks (toxicity, "
            "shedding, poor specificity) or heavy crowding.\n"
            "- **3–4:** Weak validation, major liabilities, or extremely crowded with "
            "little differentiation.\n"
            "- **1–2:** Little evidence supporting it as an antibody target.\n\n"
            "**Note:** a heavily crowded target with many approved antibodies scores "
            "*lower* for a new program, even if biologically well validated."
        )

    if st.button(f"🧠 Generate AI assessment for {target_key}"):
        with st.spinner("Analyzing target with AI..."):
            result = generate_ai_assessment(ai_ctx)

        if isinstance(result, str) and result.startswith("ERROR:"):
            st.error(
                result + "\n\nMake sure a Groq API key is set in Streamlit secrets "
                "as `GROQ_API_KEY`."
            )
        else:
            score = result.get("score", 0)
            try:
                score = int(score)
            except (ValueError, TypeError):
                score = 0

            # Colour the score box by band
            if score >= 8:
                bg, border = "#d4edda", "#28a745"   # green
            elif score >= 5:
                bg, border = "#fff3cd", "#ffc107"   # yellow
            else:
                bg, border = "#f8d7da", "#dc3545"   # red

            # Score box
            st.markdown(
                f"<div style='background:{bg}; border:2px solid {border}; border-radius:12px; "
                f"padding:18px; text-align:center; margin-bottom:16px'>"
                f"<div style='font-size:16px; color:#555'>Suitability Score</div>"
                f"<div style='font-size:56px; font-weight:bold; color:{border}'>{score}<span style='font-size:24px; color:#888'>/10</span></div>"
                f"<div style='font-size:15px; color:#444'>{result.get('justification', '')}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

            col_o, col_r = st.columns(2)
            with col_o:
                opp_items = "".join(f"<li>{o}</li>" for o in result.get("opportunities", []))
                st.markdown(
                    f"<div style='background:#eafaf1; border:2px solid #28a745; border-radius:12px; padding:16px'>"
                    f"<div style='font-size:18px; font-weight:bold; color:#1e7e34; margin-bottom:6px'>✅ Opportunities</div>"
                    f"<ul style='margin:0; padding-left:20px; font-size:15px'>{opp_items}</ul>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with col_r:
                risk_items = "".join(f"<li>{r}</li>" for r in result.get("risks", []))
                st.markdown(
                    f"<div style='background:#fdeaea; border:2px solid #dc3545; border-radius:12px; padding:16px'>"
                    f"<div style='font-size:18px; font-weight:bold; color:#b02a37; margin-bottom:6px'>⚠️ Risks / Challenges</div>"
                    f"<ul style='margin:0; padding-left:20px; font-size:15px'>{risk_items}</ul>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            crowding = result.get("competitive_crowding", "")
            if crowding:
                st.markdown(
                    f"<div style='background:#e7f1ff; border:2px solid #0d6efd; border-radius:12px; "
                    f"padding:16px; margin-top:16px'>"
                    f"<div style='font-size:18px; font-weight:bold; color:#0a58ca; margin-bottom:6px'>🏁 Competitive Crowding</div>"
                    f"<div style='font-size:15px'>{crowding}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            summary = result.get("summary", "")
            if summary:
                st.markdown(
                    f"<div style='background:#2b2b2b; border:2px solid #111; border-radius:12px; "
                    f"padding:18px; margin-top:16px'>"
                    f"<div style='font-size:18px; font-weight:bold; color:#f5f5f5; margin-bottom:6px'>📋 Bottom Line</div>"
                    f"<div style='font-size:16px; color:#eaeaea; line-height:1.5'>{summary}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

else:
    st.info("Please enter a target name to start evaluation.")
