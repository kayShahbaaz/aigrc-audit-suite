"""
modules/gap.py — AI GRC Audit Suite
======================================
Module 4: Gap Assessment Tool

The most complex module — uses RAG (Retrieval-Augmented Generation) to assess
a client's existing policy documents against a framework's controls.

How it works:
1. User uploads existing policy/security documents (PDF, DOCX, TXT)
2. Documents are chunked and stored in ChromaDB (local vector store)
3. For each framework control, the most relevant document chunks are retrieved
4. Groq is asked: does this evidence satisfy this control? (Met / Partially Met / Not Met)
5. Scores are tallied and a full gap report is generated (DOCX + PDF)

Why RAG instead of just sending everything to Groq:
- Client documents can be 50-100 pages — too large for a single Groq context
- RAG retrieves only the 5 most relevant chunks per control
- Faster, cheaper, and more accurate than brute-force full-document prompting
- Client documents stay local — never fully sent to any cloud API

This module calls:
    utils/vectorstore.py    → load_and_chunk_files(), store_documents(), query()
    utils/groq_client.py    → generate_gap_verdict(), generate_policy()
    utils/docx_exporter.py  → export_gap_assessment()
    utils/pdf_exporter.py   → export_gap_assessment()
    config/frameworks.py    → get_all_controls_flat()
"""

import os
import tempfile
import traceback
import streamlit as st

from config.frameworks import (
    get_framework_list,
    get_framework_by_id,
    get_all_controls_flat,
)
from utils.groq_client import generate_gap_verdict, generate_audit_report_section
from utils.vectorstore import (
    load_and_chunk_files,
    store_documents,
    query,
    collection_exists,
    get_collection_info,
    make_collection_name,
    delete_collection,
)
from utils.docx_exporter import export_gap_assessment as docx_export_gap
from utils.pdf_exporter  import export_gap_assessment as pdf_export_gap


# =============================================================
# CONSTANTS
# =============================================================

# Compliance verdict options the LLM can return
VERDICT_MET         = "Met"
VERDICT_PARTIAL     = "Partially Met"
VERDICT_NOT_MET     = "Not Met"
VALID_VERDICTS      = {VERDICT_MET, VERDICT_PARTIAL, VERDICT_NOT_MET}

# Minimum evidence text length to attempt a verdict (in characters)
# If retrieved chunks are too short, mark as Not Met automatically
MIN_EVIDENCE_LENGTH = 50


# =============================================================
# PROMPT BUILDERS
# =============================================================

def _build_verdict_prompt(control: dict, evidence_chunks: list) -> str:
    """
    Build the prompt for Groq to assess a single framework control.

    Takes the control definition and the retrieved document chunks,
    and asks Groq to give a structured verdict: Met / Partially Met / Not Met.

    Returns a prompt that instructs the model to respond in JSON only.
    """
    evidence_text = "\n\n---\n\n".join(evidence_chunks) if evidence_chunks else "No relevant evidence found."

    prompt = f"""
You are a senior cybersecurity auditor assessing compliance evidence.

FRAMEWORK CONTROL BEING ASSESSED:
Control ID: {control['id']}
Control Name: {control['name']}
Domain: {control['domain']}
Control Requirement: {control['description']}

EVIDENCE RETRIEVED FROM CLIENT DOCUMENTS:
{evidence_text[:3000]}

Based ONLY on the evidence above, assess whether this control is satisfied.

Return ONLY this JSON — no preamble, no explanation:
{{
  "verdict": "Met",
  "confidence": "High",
  "justification": "One sentence explaining why this verdict was given.",
  "gap_description": "What is missing or incomplete (empty string if Met)."
}}

Rules:
- verdict must be exactly one of: "Met", "Partially Met", "Not Met"
- Met: evidence clearly and completely satisfies the control requirement
- Partially Met: some evidence exists but it is incomplete or vague
- Not Met: no relevant evidence found, or evidence directly contradicts the requirement
- confidence must be "High", "Medium", or "Low"
- Be conservative — if evidence is unclear, choose Partially Met over Met
- gap_description must be empty string "" if verdict is "Met"
"""
    return prompt.strip()


def _build_executive_summary_prompt(
    framework_name: str,
    company_profile: dict,
    score_pct: int,
    met: int,
    partial: int,
    not_met: int,
    top_gaps: list,
) -> str:
    """
    Build the prompt for generating the executive summary of the gap report.
    Called once after all controls are assessed.
    """
    company_name = company_profile.get("company_name", "the organisation")
    industry     = company_profile.get("industry", "general industry")
    total        = met + partial + not_met

    top_gaps_text = "\n".join(f"- {g}" for g in top_gaps[:5])

    return f"""
Write a professional executive summary for a {framework_name} gap assessment report.

ASSESSMENT RESULTS:
- Organisation: {company_name} ({industry})
- Overall compliance score: {score_pct}%
- Controls Met: {met} / {total}
- Controls Partially Met: {partial} / {total}
- Controls Not Met: {not_met} / {total}

TOP GAPS IDENTIFIED:
{top_gaps_text}

Write 3-4 sentences suitable for a board-level audience. Be direct about the compliance
posture. Do not use bullet points. Do not mention specific control IDs.
Reference Saudi regulatory context (NCA, SAMA, or PDPL as appropriate for {framework_name}).
""".strip()


# =============================================================
# CORE ASSESSMENT LOGIC
# =============================================================

def _run_assessment(
    controls: list,
    collection_name: str,
    progress_bar,
    status_text,
) -> list:
    """
    Run the full RAG-based gap assessment across all controls.

    For each control:
    1. Query ChromaDB for the most relevant document chunks
    2. Send chunks + control definition to Groq for a verdict
    3. Store verdict, justification, and gap description

    Args:
        controls        : List of control dicts from get_all_controls_flat()
        collection_name : ChromaDB collection containing client documents
        progress_bar    : st.progress() object to update
        status_text     : st.empty() text placeholder for status messages

    Returns:
        List of result dicts, one per control:
        {id, name, domain, verdict, confidence, justification, gap_description}
    """
    results    = []
    total      = len(controls)

    for i, control in enumerate(controls):
        # Update progress UI
        progress_bar.progress((i + 1) / total)
        status_text.text(
            f"Assessing control {i+1}/{total}: [{control['id']}] {control['name'][:50]}..."
        )

        # Retrieve relevant evidence chunks from ChromaDB
        # Query using control name + description for best semantic match
        query_text     = f"{control['name']}: {control['description']}"
        evidence_chunks = query(collection_name, query_text, n_results=5)

        # If no evidence at all — mark Not Met immediately, skip Groq call
        combined_evidence = " ".join(evidence_chunks)
        if len(combined_evidence.strip()) < MIN_EVIDENCE_LENGTH:
            results.append({
                "id":              control["id"],
                "name":            control["name"],
                "domain":          control["domain"],
                "verdict":         VERDICT_NOT_MET,
                "confidence":      "High",
                "justification":   "No relevant evidence found in uploaded documents.",
                "gap_description": f"No documentation found for {control['name']}.",
            })
            continue

        # Build verdict prompt and ask Groq
        try:
            prompt       = _build_verdict_prompt(control, evidence_chunks)
            verdict_data = generate_gap_verdict(prompt)

            # Validate verdict value — default to Partially Met if invalid
            verdict = verdict_data.get("verdict", VERDICT_PARTIAL)
            if verdict not in VALID_VERDICTS:
                verdict = VERDICT_PARTIAL

            results.append({
                "id":              control["id"],
                "name":            control["name"],
                "domain":          control["domain"],
                "verdict":         verdict,
                "confidence":      verdict_data.get("confidence", "Medium"),
                "justification":   verdict_data.get("justification", ""),
                "gap_description": verdict_data.get("gap_description", ""),
            })

        except Exception as e:
            # Don't fail the whole assessment if one control errors
            # Mark as Partially Met with an error note
            results.append({
                "id":              control["id"],
                "name":            control["name"],
                "domain":          control["domain"],
                "verdict":         VERDICT_PARTIAL,
                "confidence":      "Low",
                "justification":   f"Assessment error: {str(e)[:100]}",
                "gap_description": "Could not assess this control — please review manually.",
            })

    return results


def _build_priority_actions(results: list) -> list:
    """
    Generate the top 10 priority action items from assessment results.

    Prioritises Not Met controls first, then Partially Met.
    Returns a list of action strings suitable for the report.
    """
    not_met  = [r for r in results if r["verdict"] == VERDICT_NOT_MET]
    partial  = [r for r in results if r["verdict"] == VERDICT_PARTIAL]
    priority = (not_met + partial)[:10]

    actions = []
    for r in priority:
        gap = r["gap_description"] or f"Address gaps in {r['name']}"
        actions.append(f"[{r['id']}] {r['name']}: {gap}")

    return actions


# =============================================================
# MAIN RENDER FUNCTION
# =============================================================

def render(company_profile: dict):
    """
    Main entry point for Module 4 — Gap Assessment Tool.
    Called by app.py with the company_profile dict.
    """

    st.markdown("## 🔍 Gap Assessment Tool")
    st.markdown(
        "Upload your client's existing policy documents and run an AI-powered gap assessment "
        "against a Saudi compliance framework. The AI analyses each control individually "
        "using your documents as evidence."
    )

    # RAG explanation callout
    with st.expander("ℹ️ How this works — click to learn", expanded=False):
        st.markdown("""
**Step-by-step process:**
1. Upload the client's existing policies, procedures, and security documentation
2. Documents are split into chunks and stored locally using ChromaDB
3. For each framework control, the most relevant document sections are retrieved
4. The AI assesses each control: **Met** / **Partially Met** / **Not Met**
5. A full gap report is generated — DOCX (editable) and PDF (locked)

**Privacy:** Your documents are processed locally using ChromaDB.
Only small relevant excerpts (not full documents) are sent to the AI for each control assessment.
        """)

    st.divider()

    if not company_profile.get("company_name"):
        st.warning("⚠️ Please fill in the **Company Profile** before running a gap assessment.")
        return

    # =============================================================
    # SECTION 1: FRAMEWORK SELECTION
    # =============================================================

    st.markdown("### Step 1 — Select Framework")

    col1, col2 = st.columns([2, 1])

    with col1:
        framework_options = get_framework_list()
        framework_display = [d for _, d in framework_options]
        framework_ids     = [i for i, _ in framework_options]

        selected_display  = st.selectbox(
            "Target Framework",
            options=framework_display,
            help="The framework you are assessing compliance against.",
            key="gap_fw_select",
        )
        selected_fw_id = framework_ids[framework_display.index(selected_display)]
        fw_meta        = get_framework_by_id(selected_fw_id)

        if fw_meta:
            st.caption(f"**{fw_meta['full_name']}** — {fw_meta['applies_to']}")

    with col2:
        # Show control count for the selected framework
        controls = get_all_controls_flat(selected_fw_id)
        if controls:
            st.metric("Controls to assess", len(controls))
            st.caption(f"Est. time: {len(controls) * 4 // 60 + 1}–{len(controls) * 6 // 60 + 2} mins")
        else:
            st.info("Control count will be determined during assessment.")

    st.divider()

    # =============================================================
    # SECTION 2: DOCUMENT UPLOAD
    # =============================================================

    st.markdown("### Step 2 — Upload Client Documents")
    st.caption(
        "Upload the client's existing policies, procedures, standards, and any other "
        "security documentation. Accepted formats: PDF, DOCX, TXT."
    )

    uploaded_files = st.file_uploader(
        "Upload policy and security documents",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="You can upload multiple files. The more complete the documentation, the more accurate the assessment.",
        key="gap_file_uploader",
    )

    if uploaded_files:
        st.caption(f"📎 {len(uploaded_files)} file(s) uploaded: {', '.join(f.name for f in uploaded_files)}")

    st.divider()

    # =============================================================
    # SECTION 3: PROCESS DOCUMENTS BUTTON
    # Uploads and chunks documents — separate step from assessment
    # so user can see how many chunks were created before running assessment
    # =============================================================

    st.markdown("### Step 3 — Process Documents")

    company_name    = company_profile.get("company_name", "organisation")
    collection_name = make_collection_name(company_name, selected_fw_id)
    col_info_key    = f"gap_col_info_{collection_name}"

    process_clicked = st.button(
        "📂 Process Uploaded Documents",
        disabled=not uploaded_files,
        help="Chunks and indexes documents into the local vector database. Must be done before running assessment.",
        key="gap_process_btn",
    )

    if process_clicked and uploaded_files:
        with st.status("Processing documents...", expanded=True) as proc_status:
            try:
                # Save uploaded files to temp directory so file loaders can read them
                st.write("💾 Saving uploaded files...")
                tmp_paths = []
                with tempfile.TemporaryDirectory() as tmpdir:
                    for uf in uploaded_files:
                        tmp_path = os.path.join(tmpdir, uf.name)
                        with open(tmp_path, "wb") as f:
                            f.write(uf.getbuffer())
                        tmp_paths.append(tmp_path)

                    st.write("🔪 Chunking documents into searchable pieces...")
                    chunks = load_and_chunk_files(tmp_paths)

                # Check for errors
                error_chunks = [c for c in chunks if c["source"] == "__ERRORS__"]
                valid_chunks = [c for c in chunks if c["source"] != "__ERRORS__"]

                if error_chunks:
                    st.warning(f"⚠️ Some files had issues:\n{error_chunks[0]['text']}")

                if not valid_chunks:
                    st.error("No text could be extracted from any uploaded file.")
                    proc_status.update(label="Processing failed", state="error")
                    return

                st.write(f"🧮 Embedding {len(valid_chunks)} chunks into ChromaDB...")
                stored_count = store_documents(valid_chunks, collection_name)

                st.session_state[col_info_key] = {
                    "chunk_count": stored_count,
                    "file_count":  len(uploaded_files),
                    "file_names":  [f.name for f in uploaded_files],
                }

                proc_status.update(
                    label=f"✅ {stored_count} chunks indexed from {len(uploaded_files)} file(s)",
                    state="complete",
                    expanded=False,
                )

            except RuntimeError as e:
                if "download" in str(e).lower() or "model" in str(e).lower():
                    st.error(
                        "**Embedding model not available.**\n\n"
                        "The HuggingFace model needs to download (~420MB) on first use. "
                        "Please ensure you have internet access and try again."
                    )
                else:
                    st.error(f"**Processing error:** {e}")
                proc_status.update(label="Processing failed", state="error")
                return
            except Exception as e:
                tb = traceback.format_exc()
                st.error(f"**Unexpected error:** {e}\n\n```\n{tb}\n```")
                proc_status.update(label="Processing failed", state="error")
                return

    # Show indexed document info if available
    col_info = st.session_state.get(col_info_key)
    if col_info:
        st.success(
            f"✅ Documents indexed: **{col_info['file_count']} file(s)**, "
            f"**{col_info['chunk_count']} chunks** stored in ChromaDB."
        )
        st.caption(f"Files: {', '.join(col_info['file_names'])}")
    elif collection_exists(collection_name):
        info = get_collection_info(collection_name)
        st.info(f"ℹ️ Previously indexed collection found: {info['chunk_count']} chunks available.")

    st.divider()

    # =============================================================
    # SECTION 4: RUN ASSESSMENT
    # =============================================================

    st.markdown("### Step 4 — Run Gap Assessment")

    docs_ready = col_info is not None or collection_exists(collection_name)

    if not docs_ready:
        st.warning("⚠️ Please upload and process documents before running the assessment.")

    state_key = f"gap_results_{collection_name}"

    assess_clicked = st.button(
        "Run Gap Assessment",
        type="primary",
        use_container_width=True,
        disabled=not docs_ready,
        key="gap_assess_btn",
    )

    if assess_clicked and state_key in st.session_state:
        del st.session_state[state_key]

    if assess_clicked or state_key in st.session_state:

        if state_key not in st.session_state:

            controls = get_all_controls_flat(selected_fw_id)

            if not controls:
                st.error(
                    f"No controls defined for {fw_meta['name']} in the local database. "
                    "This framework's detailed controls will be added in a future update."
                )
                return

            with st.container():
                st.markdown(
                    f"**Assessing {len(controls)} controls** — "
                    f"this takes {len(controls) * 4 // 60 + 1}–{len(controls) * 6 // 60 + 2} minutes."
                )
                progress_bar = st.progress(0)
                status_text  = st.empty()

                try:
                    results = _run_assessment(controls, collection_name, progress_bar, status_text)

                    progress_bar.progress(1.0)
                    status_text.text("✅ All controls assessed — building report...")

                    # Tally results
                    met_list     = [r for r in results if r["verdict"] == VERDICT_MET]
                    partial_list = [r for r in results if r["verdict"] == VERDICT_PARTIAL]
                    not_met_list = [r for r in results if r["verdict"] == VERDICT_NOT_MET]
                    total        = len(results)
                    score        = len(met_list) / total if total else 0.0
                    score_pct    = int(score * 100)

                    # Priority actions
                    top_gaps        = [r["gap_description"] for r in not_met_list + partial_list if r["gap_description"]]
                    priority_actions = _build_priority_actions(results)

                    # Executive summary
                    status_text.text("📝 Generating executive summary...")
                    exec_summary_prompt = _build_executive_summary_prompt(
                        framework_name  = fw_meta["name"],
                        company_profile = company_profile,
                        score_pct       = score_pct,
                        met             = len(met_list),
                        partial         = len(partial_list),
                        not_met         = len(not_met_list),
                        top_gaps        = top_gaps[:5],
                    )
                    try:
                        executive_summary = generate_audit_report_section(exec_summary_prompt)
                    except Exception:
                        executive_summary = (
                            f"{company_profile.get('company_name')} achieved a {score_pct}% compliance score "
                            f"against {fw_meta['name']}. {len(not_met_list)} controls were not met and "
                            f"{len(partial_list)} were partially met, requiring immediate attention."
                        )

                    # Assemble content dict for exporters
                    content = {
                        "framework_name":   fw_meta["name"],
                        "executive_summary": executive_summary,
                        "overall_score":    score,
                        "controls_met":     [{"id": r["id"], "name": r["name"], "domain": r["domain"]} for r in met_list],
                        "controls_partial": [{"id": r["id"], "name": r["name"], "domain": r["domain"], "gap": r["gap_description"]} for r in partial_list],
                        "controls_not_met": [{"id": r["id"], "name": r["name"], "domain": r["domain"], "gap": r["gap_description"]} for r in not_met_list],
                        "priority_actions": priority_actions,
                        "arabic_summary":   "",
                    }

                    status_text.text("📄 Building DOCX and PDF reports...")
                    docx_bytes = docx_export_gap(content, company_profile)
                    pdf_bytes  = pdf_export_gap(content, company_profile)

                    # --- Write gap findings to shared findings store for Module 7 ---
                    from utils.findings_store import add_findings_bulk
                    gap_findings = []
                    for r in not_met_list:
                        gap_findings.append({
                            "severity":       "High",
                            "title":          f"Gap — Not Met: [{r['id']}] {r['name']}",
                            "description":    f"Domain: {r['domain']}. {r.get('gap_description','No evidence found for this control.')}",
                            "recommendation": f"Implement controls to satisfy {fw_meta['name']} requirement [{r['id']}]: {r['name']}.",
                        })
                    for r in partial_list:
                        gap_findings.append({
                            "severity":       "Medium",
                            "title":          f"Gap — Partially Met: [{r['id']}] {r['name']}",
                            "description":    f"Domain: {r['domain']}. {r.get('gap_description','Partial evidence found.')}",
                            "recommendation": f"Strengthen existing controls to fully satisfy [{r['id']}]: {r['name']}.",
                        })
                    # Add overall score as an informational finding
                    gap_findings.append({
                        "severity":       "Informational",
                        "title":          f"Overall Compliance Score: {score_pct}% against {fw_meta['name']}",
                        "description":    f"Gap assessment of {total} controls: {len(met_list)} Met, {len(partial_list)} Partially Met, {len(not_met_list)} Not Met. Overall compliance score: {score_pct}%.",
                        "recommendation": "Address all Not Met and Partially Met controls per the priority action plan in the gap assessment report.",
                    })
                    add_findings_bulk(f"Module 4 — Gap Assessment ({fw_meta['name']})", gap_findings)

                    st.session_state[state_key] = {
                        "results":   results,
                        "content":   content,
                        "docx_bytes": docx_bytes,
                        "pdf_bytes":  pdf_bytes,
                        "score_pct": score_pct,
                        "fw_name":   fw_meta["name"],
                    }

                    status_text.text("✅ Report complete!")

                except EnvironmentError as e:
                    st.error(f"**API Key Error:** {e}")
                    return
                except RuntimeError as e:
                    st.error(f"**AI Error:** {e}")
                    return
                except Exception as e:
                    st.error(f"**Unexpected error:** {e}")
                    return

        # =============================================================
        # RESULTS
        # =============================================================

        cached = st.session_state.get(state_key)
        if not cached:
            return

        results    = cached["results"]
        content    = cached["content"]
        docx_bytes = cached["docx_bytes"]
        pdf_bytes  = cached["pdf_bytes"]
        score_pct  = cached["score_pct"]
        fw_name    = cached["fw_name"]

        total    = len(results)
        met_n    = len(content["controls_met"])
        part_n   = len(content["controls_partial"])
        not_met_n = len(content["controls_not_met"])

        # Score display
        st.success(f"✅ Gap assessment complete — **{score_pct}% compliance** against {fw_name}.")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Overall Score", f"{score_pct}%")
        m2.metric("✅ Controls Met",        met_n)
        m3.metric("⚠️ Partially Met",       part_n)
        m4.metric("❌ Not Met",             not_met_n)

        # Downloads
        st.divider()
        company_slug = company_profile.get("company_name", "Organisation").replace(" ", "_")
        fw_slug      = fw_name.replace(" ", "_")
        base_name    = f"{company_slug}_Gap_Assessment_{fw_slug}"

        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button(
                "📥 Download DOCX Report",
                data=docx_bytes,
                file_name=f"{base_name}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        with dl2:
            st.download_button(
                "📥 Download PDF Report",
                data=pdf_bytes,
                file_name=f"{base_name}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

        # Findings breakdown
        st.divider()
        st.markdown("### 📋 Assessment Details")

        tab_not_met, tab_partial, tab_met = st.tabs([
            f"❌ Not Met ({not_met_n})",
            f"⚠️ Partially Met ({part_n})",
            f"✅ Met ({met_n})",
        ])

        with tab_not_met:
            for r in content["controls_not_met"]:
                with st.expander(f"[{r['id']}] {r['name']} — {r['domain']}"):
                    st.markdown(f"**Gap:** {r.get('gap', 'No evidence found.')}")

        with tab_partial:
            for r in content["controls_partial"]:
                with st.expander(f"[{r['id']}] {r['name']} — {r['domain']}"):
                    st.markdown(f"**Gap:** {r.get('gap', 'Partial evidence found.')}")

        with tab_met:
            for r in content["controls_met"]:
                st.markdown(f"✅ [{r['id']}] **{r['name']}** — {r['domain']}")

        # Priority actions
        st.divider()
        st.markdown("### 🎯 Top Priority Actions")
        for i, action in enumerate(content["priority_actions"], 1):
            st.markdown(f"**{i}.** {action}")

        st.divider()
        if st.button("🔄 Re-run Assessment", key="gap_rerun_btn"):
            if state_key in st.session_state:
                del st.session_state[state_key]
            st.rerun()
