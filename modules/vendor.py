"""
modules/vendor.py — AI GRC Audit Suite
========================================
Module 5: Vendor Risk Assessment

Generates a professional vendor risk report in DOCX + PDF format.
The auditor enters vendor details and optionally uploads the vendor's
security questionnaire or SLA — the AI produces a risk score, red flags,
recommended contract clauses, and a due diligence checklist.

How it works:
1. User enters vendor name and service type
2. User optionally uploads vendor's security questionnaire or SLA document
3. Selects the applicable framework(s) for risk mapping
4. Click Generate → AI produces structured risk assessment
5. DOCX + PDF download buttons appear

This module calls:
    utils/groq_client.py    → generate_vendor_assessment()
    utils/docx_exporter.py  → export_vendor_risk()
    utils/pdf_exporter.py   → export_vendor_risk()
"""

import os
import tempfile
import streamlit as st

from config.frameworks import get_framework_list, get_framework_by_id
from utils.groq_client import generate_vendor_assessment
from utils.docx_exporter import export_vendor_risk as docx_export_vendor
from utils.pdf_exporter  import export_vendor_risk as pdf_export_vendor


# =============================================================
# CONSTANTS
# =============================================================

SERVICE_TYPES = [
    "Cloud Infrastructure (IaaS)",
    "Software as a Service (SaaS)",
    "Managed Security Services (MSSP)",
    "Payment Processing / Fintech",
    "Data Centre / Hosting",
    "IT Outsourcing",
    "Software Development / DevOps",
    "Network and Connectivity",
    "HR and Payroll Services",
    "Legal and Professional Services",
    "Logistics and Supply Chain",
    "Other",
]

DATA_ACCESS_LEVELS = [
    "No access to company data",
    "Access to non-sensitive operational data",
    "Access to sensitive business data",
    "Access to personal/customer data",
    "Access to financial / payment data",
    "Access to critical infrastructure / core systems",
]

RISK_LEVELS = ["Low", "Medium", "High", "Critical"]


# =============================================================
# PROMPT BUILDER
# =============================================================

def _build_vendor_prompt(
    vendor_name: str,
    service_type: str,
    data_access: str,
    framework_names: list,
    company_profile: dict,
    vendor_doc_text: str,
) -> str:
    """
    Build the structured JSON prompt for Groq to generate the vendor assessment.

    If vendor document text is provided, include it as evidence for Groq
    to analyse. Otherwise, base the assessment on known risks for this
    type of vendor and service.
    """
    company_name = company_profile.get("company_name", "the organisation")
    industry     = company_profile.get("industry", "general industry")
    fw_text      = ", ".join(framework_names) if framework_names else "NCA ECC"

    doc_section = ""
    if vendor_doc_text.strip():
        doc_section = f"""
VENDOR DOCUMENTATION PROVIDED (analyse for red flags and compliance gaps):
{vendor_doc_text[:4000]}
"""

    return f"""
You are a cybersecurity third-party risk analyst assessing a vendor for a Saudi Arabian organisation.

CLIENT DETAILS:
- Organisation: {company_name}
- Industry: {industry}
- Applicable Frameworks: {fw_text}

VENDOR BEING ASSESSED:
- Vendor Name: {vendor_name}
- Service Type: {service_type}
- Data Access Level: {data_access}
{doc_section}

Produce a comprehensive vendor risk assessment. Return ONLY valid JSON — no preamble, no markdown:

{{
  "risk_score": 65,
  "risk_level": "High",
  "summary": "2-3 sentence narrative risk summary for this vendor.",
  "red_flags": [
    "Specific red flag or concern identified",
    "Second red flag",
    "Third red flag"
  ],
  "contract_clauses": [
    "Specific contract clause to include",
    "Second clause",
    "Third clause"
  ],
  "due_diligence": [
    "Due diligence item to verify",
    "Second item",
    "Third item"
  ],
  "framework_gaps": [
    "Specific gap against {fw_text} requirements",
    "Second gap"
  ]
}}

Requirements:
- risk_score: integer 0-100 (0=no risk, 100=extreme risk)
- risk_level: one of "Low", "Medium", "High", "Critical"
- red_flags: 3-6 specific, concrete risk concerns relevant to {service_type}
- contract_clauses: 4-6 specific contractual protections needed given the risks
- due_diligence: 5-8 specific verification steps the client should take
- framework_gaps: 2-4 specific gaps against Saudi compliance requirements
- All items must be specific to this vendor type and data access level
- Reference Saudi regulatory context (NCA, SAMA, PDPL) where relevant
- If vendor documentation was provided, reference specific issues found in it
""".strip()


def _validate_vendor_result(raw: dict) -> dict:
    """
    Validate and normalise the LLM vendor assessment response.
    Ensures all required keys are present with correct types.
    """
    # Clamp risk score 0-100
    try:
        risk_score = max(0, min(100, int(raw.get("risk_score", 50))))
    except (ValueError, TypeError):
        risk_score = 50

    # Validate risk level
    risk_level = raw.get("risk_level", "Medium")
    if risk_level not in RISK_LEVELS:
        risk_level = "Medium"

    return {
        "risk_score":      risk_score,
        "risk_level":      risk_level,
        "summary":         str(raw.get("summary", "Risk assessment completed."))[:500],
        "red_flags":       [str(f)[:200] for f in raw.get("red_flags", [])[:8]],
        "contract_clauses":[str(c)[:200] for c in raw.get("contract_clauses", [])[:8]],
        "due_diligence":   [str(d)[:200] for d in raw.get("due_diligence", [])[:10]],
        "framework_gaps":  [str(g)[:200] for g in raw.get("framework_gaps", [])[:6]],
    }


# =============================================================
# MAIN RENDER FUNCTION
# =============================================================

def render(company_profile: dict):
    """
    Main entry point for Module 5 — Vendor Risk Assessment.
    Called by app.py with the company_profile dict.
    """

    st.markdown("## 🏢 Vendor Risk Assessment")
    st.markdown(
        "Generate a professional vendor risk report with risk score, red flags, "
        "recommended contract clauses, and a due diligence checklist. "
        "Optionally upload the vendor's security questionnaire or SLA for deeper analysis."
    )
    st.divider()

    if not company_profile.get("company_name"):
        st.warning("⚠️ Please fill in the **Company Profile** before generating a vendor assessment.")
        return

    # =============================================================
    # SECTION 1: VENDOR DETAILS
    # =============================================================

    st.markdown("### Step 1 — Vendor Details")

    col1, col2 = st.columns(2)

    with col1:
        vendor_name = st.text_input(
            "Vendor Name *",
            placeholder="e.g. Microsoft Azure, SAP, Infosys",
            key="vendor_name_input",
        )

        service_type = st.selectbox(
            "Service Type *",
            options=SERVICE_TYPES,
            key="vendor_service_type",
        )

    with col2:
        data_access = st.selectbox(
            "Data Access Level",
            options=DATA_ACCESS_LEVELS,
            index=2,
            help="What level of access does this vendor have to your client's data?",
            key="vendor_data_access",
        )

        # Framework multi-select — for risk mapping context
        framework_options = get_framework_list()
        fw_display        = [d for _, d in framework_options]
        fw_ids            = [i for i, _ in framework_options]

        selected_fw_displays = st.multiselect(
            "Applicable Frameworks",
            options=fw_display,
            default=[fw_display[0]] if fw_display else [],
            help="Select the compliance frameworks relevant to this vendor relationship.",
            key="vendor_fw_select",
        )
        selected_fw_names = []
        for disp in selected_fw_displays:
            idx = fw_display.index(disp)
            fw_id   = fw_ids[idx]
            fw_meta = get_framework_by_id(fw_id)
            if fw_meta:
                selected_fw_names.append(fw_meta["name"])

    st.divider()

    # =============================================================
    # SECTION 2: OPTIONAL DOCUMENT UPLOAD
    # =============================================================

    st.markdown("### Step 2 — Upload Vendor Document (Optional)")
    st.caption(
        "Upload the vendor's security questionnaire, SLA, or security policy. "
        "The AI will analyse it for red flags and compliance gaps."
    )

    vendor_file = st.file_uploader(
        "Vendor security questionnaire or SLA",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=False,
        key="vendor_doc_upload",
    )

    vendor_doc_text = ""
    if vendor_file:
        st.caption(f"📎 Uploaded: {vendor_file.name}")
        try:
            # Extract text from the vendor document
            with tempfile.NamedTemporaryFile(
                suffix=os.path.splitext(vendor_file.name)[1],
                delete=False
            ) as tmp:
                tmp.write(vendor_file.getbuffer())
                tmp_path = tmp.name

            from utils.vectorstore import _load_file_text
            vendor_doc_text = _load_file_text(tmp_path)
            os.unlink(tmp_path)

            if vendor_doc_text.strip():
                st.success(f"✅ Document loaded — {len(vendor_doc_text):,} characters extracted.")
            else:
                st.warning("Document loaded but no text could be extracted.")
        except Exception as e:
            st.warning(f"Could not read vendor document: {e}. Proceeding without it.")
            vendor_doc_text = ""

    st.divider()

    # =============================================================
    # SECTION 3: GENERATE
    # =============================================================

    st.markdown("### Step 3 — Generate Assessment")

    if not vendor_name.strip():
        st.info("Enter vendor name above to enable generation.")
        return

    with st.expander("📋 Using company profile", expanded=False):
        st.markdown(f"**{company_profile.get('company_name')}** — {company_profile.get('industry')} | Auditor: {company_profile.get('auditor_name')}")

    # State key — include vendor name so different vendors get different cached results
    safe_vendor = vendor_name.strip().replace(" ", "_")[:30]
    state_key   = f"vendor_{safe_vendor}_{service_type[:20]}"

    generate_clicked = st.button(
        "Generate Vendor Risk Assessment",
        type="primary",
        use_container_width=True,
        key="vendor_generate_btn",
    )

    if generate_clicked and state_key in st.session_state:
        del st.session_state[state_key]

    if generate_clicked or state_key in st.session_state:

        if state_key not in st.session_state:

            with st.status("Generating vendor risk assessment...", expanded=True) as status:
                try:
                    st.write(f"🔍 Analysing risk profile for {vendor_name} ({service_type})...")

                    prompt  = _build_vendor_prompt(
                        vendor_name     = vendor_name.strip(),
                        service_type    = service_type,
                        data_access     = data_access,
                        framework_names = selected_fw_names,
                        company_profile = company_profile,
                        vendor_doc_text = vendor_doc_text,
                    )

                    st.write("AI assessing vendor risk against Saudi compliance requirements...")
                    raw_data = generate_vendor_assessment(prompt)

                    validated = _validate_vendor_result(raw_data)

                    # Assemble content dict for exporters
                    content = {
                        "vendor_name":     vendor_name.strip(),
                        "service_type":    service_type,
                        "risk_score":      validated["risk_score"],
                        "risk_level":      validated["risk_level"],
                        "summary":         validated["summary"],
                        "red_flags":       validated["red_flags"] + validated["framework_gaps"],
                        "contract_clauses":validated["contract_clauses"],
                        "due_diligence":   validated["due_diligence"],
                        "arabic_summary":  "",
                    }

                    st.write("📄 Building DOCX and PDF reports...")
                    docx_bytes = docx_export_vendor(content, company_profile)
                    pdf_bytes  = pdf_export_vendor(content, company_profile)

                    # --- Write vendor findings to shared findings store for Module 7 ---
                    from utils.findings_store import add_finding, add_findings_bulk
                    # Map vendor risk level to finding severity
                    sev_map = {"Critical": "Critical", "High": "High", "Medium": "Medium", "Low": "Low"}
                    vendor_severity = sev_map.get(validated["risk_level"], "Medium")
                    add_finding(
                        source         = f"Module 5 — Vendor Risk Assessment",
                        severity       = vendor_severity,
                        title          = f"Vendor Risk ({validated['risk_level']}): {vendor_name.strip()}",
                        description    = f"Service: {service_type}. Risk Score: {validated['risk_score']}/100. {validated['summary']} Red flags: {'; '.join(validated['red_flags'][:3])}.",
                        recommendation = f"Implement recommended contract clauses and complete due diligence checklist for {vendor_name.strip()}. Key actions: {'; '.join(validated['contract_clauses'][:2])}.",
                    )

                    st.session_state[state_key] = {
                        "content":    content,
                        "validated":  validated,
                        "docx_bytes": docx_bytes,
                        "pdf_bytes":  pdf_bytes,
                    }

                    status.update(label="✅ Vendor assessment ready!", state="complete", expanded=False)

                except EnvironmentError as e:
                    st.error(f"**API Key Error:** {e}")
                    status.update(label="API key not configured", state="error")
                    return
                except ValueError as e:
                    st.error(f"**Data Error:** {e}")
                    status.update(label="Generation failed", state="error")
                    return
                except RuntimeError as e:
                    st.error(f"**AI Error:** {e}")
                    status.update(label="Generation failed", state="error")
                    return
                except Exception as e:
                    st.error(f"**Unexpected error:** {e}")
                    status.update(label="Generation failed", state="error")
                    return

        # =============================================================
        # RESULTS
        # =============================================================

        cached = st.session_state.get(state_key)
        if not cached:
            return

        content   = cached["content"]
        validated = cached["validated"]

        # Risk score display with colour
        score = validated["risk_score"]
        level = validated["risk_level"]
        score_colour = {"Low": "🟢", "Medium": "🟡", "High": "🟠", "Critical": "🔴"}.get(level, "⚪")

        st.markdown(
            f"### {score_colour} Risk Level: **{level}** &nbsp;&nbsp; Score: **{score}/100**"
        )
        st.markdown(f"*{content['summary']}*")

        # Downloads
        st.divider()
        company_slug = company_profile.get("company_name", "Organisation").replace(" ", "_")
        vendor_slug  = vendor_name.strip().replace(" ", "_")
        base_name    = f"{company_slug}_Vendor_Risk_{vendor_slug}"

        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button(
                "📥 Download DOCX Report",
                data=cached["docx_bytes"],
                file_name=f"{base_name}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        with dl2:
            st.download_button(
                "📥 Download PDF Report",
                data=cached["pdf_bytes"],
                file_name=f"{base_name}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

        # Details
        st.divider()
        st.markdown("### 📋 Assessment Details")

        tab1, tab2, tab3 = st.tabs(["🚩 Red Flags", "📝 Contract Clauses", "✅ Due Diligence"])

        with tab1:
            for flag in content["red_flags"]:
                st.markdown(f"🚩 {flag}")

        with tab2:
            for i, clause in enumerate(content["contract_clauses"], 1):
                st.markdown(f"**{i}.** {clause}")

        with tab3:
            for item in content["due_diligence"]:
                st.checkbox(item, key=f"dd_{hash(item)}")

        st.divider()
        if st.button("🔄 Re-assess Vendor", key="vendor_regen_btn"):
            if state_key in st.session_state:
                del st.session_state[state_key]
            st.rerun()
