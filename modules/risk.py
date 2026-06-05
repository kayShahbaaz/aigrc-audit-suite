"""
modules/risk.py — AI GRC Audit Suite
======================================
Module 2: Risk Register Builder

Generates a professional, colour-coded risk register in Excel format.
The auditor selects a framework and infrastructure type, and the AI
produces a complete risk register with assets, threats, vulnerabilities,
likelihood/impact scores, and recommended controls mapped to framework IDs.

How it works:
1. User selects framework and infrastructure type (Cloud/On-prem/Hybrid)
2. User optionally describes specific assets to include
3. Click Generate → Groq produces structured JSON risk rows
4. Rows are validated, risk ratings calculated, risk levels assigned
5. Excel file generated with colour-coded Risk Level column
6. Single Download Excel button

Output Excel columns (per reference spec):
    Asset ID, Asset Name, Asset Type, Threat, Vulnerability,
    Likelihood (1-5), Impact (1-5), Risk Rating, Risk Level,
    Recommended Control, Control Reference, Control Owner,
    Target Date, Status

This module calls:
    utils/groq_client.py    → generate_risk_items()
    utils/excel_exporter.py → export_risk_register()

Coding rules:
    - render(company_profile) is the only public function
    - Never calls Groq directly — always via groq_client.py
    - Never re-asks for company name — reads from company_profile
    - Progress bars for long operations
    - Risk rating = Likelihood × Impact, calculated here not by LLM
"""

import streamlit as st
from datetime import datetime, timedelta

from config.frameworks import get_framework_list, get_framework_by_id
from config.settings import RISK_LEVEL_THRESHOLDS
from utils.groq_client import generate_risk_items
from utils.excel_exporter import export_risk_register


# =============================================================
# CONSTANTS
# =============================================================

INFRASTRUCTURE_TYPES = ["Cloud", "On-Premise", "Hybrid"]

ASSET_TYPES = [
    "Application", "Database", "Server", "Network Device",
    "Endpoint", "Cloud Service", "API", "Data Store",
    "Identity System", "Physical Asset",
]

# Default target date for remediation — 90 days from today
DEFAULT_TARGET_DATE = (datetime.today() + timedelta(days=90)).strftime("%Y-%m-%d")


# =============================================================
# HELPERS
# =============================================================

def _calculate_risk_level(rating: int) -> str:
    """
    Determine the risk level label from a numeric risk rating.
    Risk Rating = Likelihood × Impact (both 1-5), so range is 1-25.
    Thresholds are defined in config/settings.py.
    """
    for level, (low, high) in RISK_LEVEL_THRESHOLDS.items():
        if low <= rating <= high:
            return level
    return "Low"   # fallback for rating of 0 or out of range


def _validate_and_fix_row(row: dict, index: int) -> dict:
    """
    Validate a risk row from the LLM and fix any bad values.

    LLMs occasionally return out-of-range numbers or missing fields.
    This function ensures every row is safe to write to Excel.

    Args:
        row   : Raw dict from LLM JSON response
        index : Row number (1-based) for generating fallback Asset IDs

    Returns:
        Cleaned and validated dict with all required keys present
    """
    # Ensure likelihood and impact are valid integers 1-5
    try:
        likelihood = max(1, min(5, int(row.get("likelihood", 3))))
    except (ValueError, TypeError):
        likelihood = 3

    try:
        impact = max(1, min(5, int(row.get("impact", 3))))
    except (ValueError, TypeError):
        impact = 3

    # Always calculate risk rating ourselves — never trust the LLM's arithmetic
    risk_rating = likelihood * impact
    risk_level  = _calculate_risk_level(risk_rating)

    return {
        "asset_id":            row.get("asset_id") or f"A-{index:03d}",
        "asset_name":          str(row.get("asset_name", f"Asset {index}"))[:80],
        "asset_type":          str(row.get("asset_type", "Application"))[:40],
        "threat":              str(row.get("threat", ""))[:200],
        "vulnerability":       str(row.get("vulnerability", ""))[:200],
        "likelihood":          likelihood,
        "impact":              impact,
        "risk_rating":         risk_rating,
        "risk_level":          risk_level,
        "recommended_control": str(row.get("recommended_control", ""))[:200],
        "control_reference":   str(row.get("control_reference", ""))[:60],
        "control_owner":       str(row.get("control_owner", "IT Security"))[:60],
        "target_date":         str(row.get("target_date", DEFAULT_TARGET_DATE))[:20],
        "status":              str(row.get("status", "Open"))[:30],
    }


def _build_risk_prompt(
    framework_name: str,
    framework_full_name: str,
    infrastructure_type: str,
    company_profile: dict,
    asset_context: str,
    num_risks: int,
) -> str:
    """
    Build the structured prompt for Groq to generate risk register rows.

    Instructs the model to return a JSON object with a 'risks' array.
    Each risk is a dict matching the Excel column structure exactly.
    """
    company_name = company_profile.get("company_name", "the organisation")
    industry     = company_profile.get("industry", "general industry")

    prompt = f"""
You are a senior cybersecurity risk analyst generating a risk register for a Saudi Arabian organisation.

ORGANISATION DETAILS:
- Company: {company_name}
- Industry: {industry}
- Infrastructure: {infrastructure_type}
- Framework: {framework_name} ({framework_full_name})

{"SPECIFIC ASSETS/CONTEXT: " + asset_context if asset_context.strip() else ""}

Generate exactly {num_risks} realistic cybersecurity risk register entries for this organisation.
Map each risk to a real {framework_name} control reference.

Return ONLY a valid JSON object in this exact format — no preamble, no markdown:

{{
  "risks": [
    {{
      "asset_id": "A-001",
      "asset_name": "Core Banking Application",
      "asset_type": "Application",
      "threat": "SQL injection attack targeting customer database",
      "vulnerability": "Lack of input validation and WAF controls",
      "likelihood": 3,
      "impact": 5,
      "recommended_control": "Deploy WAF, implement parameterised queries, conduct quarterly DAST scanning",
      "control_reference": "NCA ECC 3-4",
      "control_owner": "Application Security Team",
      "target_date": "2025-09-30",
      "status": "Open"
    }}
  ]
}}

Requirements:
- Asset types must be realistic for {industry} organisations on {infrastructure_type} infrastructure
- Threats must be specific — not generic ("cyber attack") but precise ("ransomware via phishing")
- Vulnerabilities must explain WHY the threat can succeed
- Likelihood and Impact must be integers 1-5 (1=Very Low, 5=Very High)
- Control references must be real {framework_name} control IDs
- Recommended controls must be specific and actionable, not vague
- Vary risk levels — include Critical, High, Medium, and Low risks
- Do NOT include likelihood × impact calculation — just provide the two numbers
- Return exactly {num_risks} risks in the array
"""
    return prompt.strip()


# =============================================================
# MAIN RENDER FUNCTION
# =============================================================

def render(company_profile: dict):
    """
    Main entry point for Module 2 — Risk Register Builder.
    Called by app.py with the company_profile dict.
    """

    st.markdown("## ⚠️ Risk Register Builder")
    st.markdown(
        "Generate a colour-coded risk register in Excel format. "
        "Risks are mapped to your selected framework's control references "
        "and scored using Likelihood × Impact methodology."
    )
    st.divider()

    # Guard: profile must be filled
    if not company_profile.get("company_name"):
        st.warning("⚠️ Please fill in the **Company Profile** before generating a risk register.")
        return

    # =============================================================
    # SECTION 1: SELECTIONS
    # =============================================================

    st.markdown("### Step 1 — Configure Risk Register")

    col1, col2 = st.columns(2)

    with col1:
        framework_options = get_framework_list()
        framework_display = [d for _, d in framework_options]
        framework_ids     = [i for i, _ in framework_options]

        selected_display = st.selectbox(
            "Compliance Framework",
            options=framework_display,
            help="Risks will be mapped to controls from this framework.",
            key="risk_fw_select",
        )
        selected_fw_id = framework_ids[framework_display.index(selected_display)]
        fw_meta = get_framework_by_id(selected_fw_id)
        if fw_meta:
            st.caption(f"**Applies to:** {fw_meta['applies_to']}")

    with col2:
        infra_type = st.selectbox(
            "Infrastructure Type",
            options=INFRASTRUCTURE_TYPES,
            help="Determines which threats and vulnerabilities the AI includes.",
            key="risk_infra_select",
        )

        num_risks = st.slider(
            "Number of risks to generate",
            min_value=5,
            max_value=25,
            value=10,
            step=5,
            help="More risks = longer generation time. 10-15 is typical for an engagement.",
        )

    st.divider()

    # =============================================================
    # SECTION 2: OPTIONAL ASSET CONTEXT
    # =============================================================

    st.markdown("### Step 2 — Optional Asset Context")

    asset_context = st.text_area(
        "Describe specific assets or areas of concern (optional)",
        placeholder=(
            "e.g. We have a core banking system (Temenos T24) on-premise, "
            "an Azure cloud environment for analytics, customer-facing mobile app, "
            "and 3 critical APIs connecting to SWIFT. Focus on financial data risks."
        ),
        height=90,
        help="Leave blank for a standard risk register. Add context for a more targeted output.",
        key="risk_asset_context",
    )

    st.divider()

    # =============================================================
    # SECTION 3: GENERATE
    # =============================================================

    st.markdown("### Step 3 — Generate")

    # Profile preview
    with st.expander("📋 Using company profile", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**{company_profile.get('company_name')}** — {company_profile.get('industry')}")
        with c2:
            st.markdown(f"{company_profile.get('city')}, Saudi Arabia | {company_profile.get('engagement_date')}")

    state_key = f"risk_{selected_fw_id}_{infra_type}_{num_risks}"

    generate_clicked = st.button(
        "Generate Risk Register",
        type="primary",
        use_container_width=True,
        key="risk_generate_btn",
    )

    if generate_clicked and state_key in st.session_state:
        del st.session_state[state_key]

    if generate_clicked or state_key in st.session_state:

        if state_key not in st.session_state:

            with st.status("Generating risk register...", expanded=True) as status:
                try:
                    st.write(f"🔍 Analysing {infra_type} infrastructure risks for {fw_meta['name']}...")

                    prompt = _build_risk_prompt(
                        framework_name      = fw_meta["name"],
                        framework_full_name = fw_meta["full_name"],
                        infrastructure_type = infra_type,
                        company_profile     = company_profile,
                        asset_context       = asset_context,
                        num_risks           = num_risks,
                    )

                    st.write("AI generating risk entries with threat and vulnerability mapping...")
                    raw_data = generate_risk_items(prompt)

                    # Extract the risks list from the response
                    risks_raw = raw_data.get("risks", [])

                    if not risks_raw:
                        st.error("The AI response did not contain any risk entries. Please try again.")
                        status.update(label="Generation failed", state="error")
                        return

                    st.write(f"✅ {len(risks_raw)} risks generated — calculating ratings and building Excel...")

                    # Validate and fix every row — never trust raw LLM output
                    risks_clean = [_validate_and_fix_row(r, i+1) for i, r in enumerate(risks_raw)]

                    # Generate Excel bytes
                    excel_bytes = export_risk_register(risks_clean, company_profile)

                    # --- Write key findings to shared findings store for Module 7 ---
                    # Include Critical and High risks as audit findings
                    from utils.findings_store import add_findings_bulk
                    risk_findings = [
                        {
                            "severity":       r["risk_level"] if r["risk_level"] in ["Critical","High","Medium","Low"] else "Medium",
                            "title":          f"{r['risk_level']} Risk: {r['asset_name']} — {r['threat'][:60]}",
                            "description":    f"Asset: {r['asset_name']} ({r['asset_type']}). Threat: {r['threat']}. Vulnerability: {r['vulnerability']} Likelihood: {r['likelihood']}/5, Impact: {r['impact']}/5, Rating: {r['risk_rating']}/25.",
                            "recommendation": r["recommended_control"],
                        }
                        for r in risks_clean
                        if r["risk_level"] in ("Critical", "High", "Medium")
                    ]
                    add_findings_bulk(f"Module 2 — Risk Register ({fw_meta['name']})", risk_findings)

                    st.session_state[state_key] = {
                        "risks":       risks_clean,
                        "excel_bytes": excel_bytes,
                        "fw_name":     fw_meta["name"],
                        "infra":       infra_type,
                    }

                    status.update(label="✅ Risk register ready!", state="complete", expanded=False)

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

        risks       = cached["risks"]
        excel_bytes = cached["excel_bytes"]
        fw_name     = cached["fw_name"]
        infra       = cached["infra"]

        st.success(f"✅ {len(risks)} risks generated for {fw_name} — {infra} infrastructure.")

        # Summary metrics
        m1, m2, m3, m4 = st.columns(4)
        critical = sum(1 for r in risks if r["risk_level"] == "Critical")
        high     = sum(1 for r in risks if r["risk_level"] == "High")
        medium   = sum(1 for r in risks if r["risk_level"] == "Medium")
        low      = sum(1 for r in risks if r["risk_level"] == "Low")

        m1.metric("🔴 Critical", critical)
        m2.metric("🟠 High",     high)
        m3.metric("🟡 Medium",   medium)
        m4.metric("🟢 Low",      low)

        # Download button
        company_slug = company_profile.get("company_name", "Organisation").replace(" ", "_")
        fw_slug      = fw_name.replace(" ", "_")
        filename     = f"{company_slug}_Risk_Register_{fw_slug}.xlsx"

        st.download_button(
            label="📥 Download Risk Register (Excel)",
            data=excel_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        # Preview table
        st.divider()
        st.markdown("### 👁️ Risk Register Preview")
        st.caption("Showing generated risks. Download Excel for the full formatted version with colour coding.")

        import pandas as pd
        preview_data = [{
            "Asset ID":    r["asset_id"],
            "Asset Name":  r["asset_name"],
            "Threat":      r["threat"][:60] + "..." if len(r["threat"]) > 60 else r["threat"],
            "L":           r["likelihood"],
            "I":           r["impact"],
            "Rating":      r["risk_rating"],
            "Level":       r["risk_level"],
            "Control Ref": r["control_reference"],
        } for r in risks]

        df = pd.DataFrame(preview_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Regenerate
        st.divider()
        if st.button("🔄 Regenerate Risk Register", key="risk_regen_btn"):
            if state_key in st.session_state:
                del st.session_state[state_key]
            st.rerun()
