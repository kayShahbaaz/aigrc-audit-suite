"""
modules/playbook.py — AI GRC Audit Suite
==========================================
Module 6: IR Playbook Generator

Generates a professional incident response playbook in DOCX + PDF format.
The auditor selects the incident type and applicable regulatory bodies,
and the AI produces a complete playbook with response team roles,
step-by-step timeline, escalation matrix, communication templates,
regulatory notification requirements, and a lessons learned template.

How it works:
1. User selects incident type (Ransomware, Data Breach, etc.)
2. User selects applicable regulatory bodies (NCA, SAMA, PDPL, CITC)
3. Click Generate → AI builds the full structured playbook
4. DOCX + PDF download buttons appear

This module calls:
    utils/groq_client.py    → generate_ir_playbook()  (structured JSON)
    utils/docx_exporter.py  → export_ir_playbook()
    utils/pdf_exporter.py   → export_ir_playbook()
"""

import streamlit as st

from config.frameworks import get_framework_by_id
from config.settings import INCIDENT_TYPES, REGULATORY_BODIES
from utils.groq_client import generate_structured, generate_ir_playbook as groq_ir_playbook
from utils.docx_exporter import export_ir_playbook as docx_export_playbook
from utils.pdf_exporter  import export_ir_playbook as pdf_export_playbook


# =============================================================
# PROMPT BUILDER
# =============================================================

def _build_playbook_prompt(
    incident_type: str,
    regulatory_bodies: list,
    company_profile: dict,
    severity_level: str,
    extra_context: str,
) -> str:
    """
    Build the structured JSON prompt for the IR playbook.

    The playbook has 7 components — each maps to a section in the
    DOCX/PDF template. The model must return all 7 as a single JSON object.
    """
    company_name = company_profile.get("company_name", "the organisation")
    industry     = company_profile.get("industry", "general industry")
    reg_text     = "\n".join(f"- {r}" for r in regulatory_bodies) if regulatory_bodies else "- NCA (National Cybersecurity Authority)"

    return f"""
You are a senior cybersecurity incident response specialist generating an IR playbook
for a Saudi Arabian organisation.

ORGANISATION DETAILS:
- Company: {company_name}
- Industry: {industry}
- Incident Type: {incident_type}
- Severity Level: {severity_level}
- Applicable Regulatory Bodies:
{reg_text}

{"ADDITIONAL CONTEXT: " + extra_context if extra_context.strip() else ""}

Generate a complete incident response playbook. Return ONLY valid JSON — no preamble, no markdown:

{{
  "classification": "One paragraph describing the incident type, severity classification, potential business impact, and initial triage criteria for {incident_type} at a {severity_level} severity level.",

  "response_team": [
    {{"role": "Incident Commander", "responsibilities": "Overall coordination, decision authority, executive communication"}},
    {{"role": "Technical Lead", "responsibilities": "Technical containment and forensic investigation"}},
    {{"role": "Communications Lead", "responsibilities": "Internal and external communications management"}},
    {{"role": "Legal / Compliance", "responsibilities": "Regulatory notification obligations and legal hold"}},
    {{"role": "IT Security Analyst", "responsibilities": "Log analysis, evidence preservation, and containment execution"}}
  ],

  "response_timeline": [
    {{"phase": "Detection (0-15 min)", "action": "Specific action to take", "owner": "Role name", "timeframe": "0-15 minutes"}},
    {{"phase": "Containment (15-60 min)", "action": "Specific containment action", "owner": "Role name", "timeframe": "15-60 minutes"}},
    {{"phase": "Eradication (1-4 hrs)", "action": "Specific eradication step", "owner": "Role name", "timeframe": "1-4 hours"}},
    {{"phase": "Recovery (4-24 hrs)", "action": "Specific recovery action", "owner": "Role name", "timeframe": "4-24 hours"}},
    {{"phase": "Post-Incident (24-72 hrs)", "action": "Specific post-incident task", "owner": "Role name", "timeframe": "24-72 hours"}}
  ],

  "escalation_matrix": [
    {{"trigger": "Specific condition that triggers escalation", "escalate_to": "Role or authority", "method": "Phone / Encrypted email / Secure messaging"}},
    {{"trigger": "Critical systems affected", "escalate_to": "CEO and Board", "method": "Phone call"}},
    {{"trigger": "Personal data breach suspected", "escalate_to": "DPO and Legal", "method": "Encrypted email"}}
  ],

  "comms_templates": [
    {{
      "audience": "Internal Staff",
      "template_text": "Full template message text that staff can use as-is or lightly adapt. Should be 2-4 sentences."
    }},
    {{
      "audience": "Executive Leadership",
      "template_text": "Template for executive briefing — concise, action-oriented, 2-3 sentences."
    }},
    {{
      "audience": "Customers / External Parties (if required)",
      "template_text": "Template for external notification if the incident requires customer communication."
    }}
  ],

  "regulatory_requirements": [
    {{"body": "NCA", "requirement": "Specific NCA notification requirement for {incident_type}", "deadline": "X hours from detection"}},
    {{"body": "SAMA", "requirement": "SAMA CSF incident reporting requirement (if financial sector)", "deadline": "X hours"}},
    {{"body": "SDAIA/PDPL", "requirement": "Personal data breach notification requirement", "deadline": "72 hours from awareness"}}
  ],

  "lessons_learned": "A template with 6-8 specific questions the incident response team should answer within 30 days of incident closure. Format as numbered questions. Include questions about: detection time, containment effectiveness, communication quality, regulatory compliance, root cause, control failures, and improvements needed."
}}

Requirements:
- response_timeline must have at least 8 steps covering all 5 phases
- escalation_matrix must have at least 5 triggers
- All timelines must reference Saudi regulatory deadlines where applicable
- Regulatory requirements must reference real Saudi obligations (NCA 24h reporting, PDPL 72h, etc.)
- Response team must include roles realistic for {industry} organisations
- Communication templates must be professional and ready to use with minimal editing
""".strip()


def _validate_playbook(raw: dict, incident_type: str) -> dict:
    """
    Validate and normalise the LLM playbook response.
    Ensures all 7 required sections are present with correct structure.
    """
    # Validate response_team
    team = raw.get("response_team", [])
    if not team:
        team = [
            {"role": "Incident Commander", "responsibilities": "Overall coordination and decision authority"},
            {"role": "IT Security Lead",   "responsibilities": "Technical investigation and containment"},
        ]

    # Validate response_timeline
    timeline = raw.get("response_timeline", [])
    if not timeline:
        timeline = [
            {"phase": "Detection", "action": "Identify and confirm incident", "owner": "SOC", "timeframe": "0-15 minutes"},
            {"phase": "Containment", "action": "Isolate affected systems", "owner": "IT Security", "timeframe": "15-60 minutes"},
        ]

    # Validate escalation_matrix
    escalation = raw.get("escalation_matrix", [])
    if not escalation:
        escalation = [
            {"trigger": "Critical systems affected", "escalate_to": "CEO", "method": "Phone"},
        ]

    # Validate comms_templates
    comms = raw.get("comms_templates", [])
    if not comms:
        comms = [
            {"audience": "Internal Staff", "template_text": "We are currently managing a security incident. Further details will follow."},
        ]

    # Validate regulatory_requirements
    reg_reqs = raw.get("regulatory_requirements", [])
    if not reg_reqs:
        reg_reqs = [
            {"body": "NCA", "requirement": "Report cybersecurity incidents to NCA", "deadline": "24 hours from detection"},
        ]

    # Lessons learned template
    lessons = str(raw.get("lessons_learned", "Complete this section within 30 days of incident closure."))[:2000]

    # Classification paragraph
    classification = str(raw.get("classification", f"{incident_type} incident response playbook."))[:1000]

    return {
        "incident_type":          incident_type,
        "classification":         classification,
        "response_team":          team[:8],
        "response_timeline":      timeline[:15],
        "escalation_matrix":      escalation[:8],
        "comms_templates":        comms[:5],
        "regulatory_requirements":reg_reqs[:6],
        "lessons_learned":        lessons,
        "arabic_summary":         "",
    }


# =============================================================
# MAIN RENDER FUNCTION
# =============================================================

def render(company_profile: dict):
    """
    Main entry point for Module 6 — IR Playbook Generator.
    Called by app.py with the company_profile dict.
    """

    st.markdown("## 🚨 IR Playbook Generator")
    st.markdown(
        "Generate a professional incident response playbook for any Saudi compliance scenario. "
        "Includes response team roles, step-by-step timeline, escalation matrix, "
        "communication templates, and regulatory notification deadlines."
    )
    st.divider()

    if not company_profile.get("company_name"):
        st.warning("⚠️ Please fill in the **Company Profile** before generating a playbook.")
        return

    # =============================================================
    # SECTION 1: INCIDENT CONFIGURATION
    # =============================================================

    st.markdown("### Step 1 — Configure Incident Scenario")

    col1, col2 = st.columns(2)

    with col1:
        incident_type = st.selectbox(
            "Incident Type *",
            options=INCIDENT_TYPES,
            help="Select the type of incident this playbook covers.",
            key="pb_incident_type",
        )

        severity_level = st.select_slider(
            "Default Severity Level",
            options=["Low", "Medium", "High", "Critical"],
            value="High",
            help="Sets the initial severity classification and escalation triggers.",
            key="pb_severity",
        )

    with col2:
        regulatory_bodies = st.multiselect(
            "Applicable Regulatory Bodies",
            options=REGULATORY_BODIES,
            default=REGULATORY_BODIES[:2],
            help="Select all regulators the client must notify in case of this incident.",
            key="pb_reg_bodies",
        )

        st.caption(
            "**NCA:** 24-hour mandatory notification for all Saudi organisations.\n\n"
            "**SAMA:** Financial sector incident reporting within specified timeframes.\n\n"
            "**PDPL:** Personal data breaches must be notified within 72 hours."
        )

    st.divider()

    # =============================================================
    # SECTION 2: OPTIONAL CONTEXT
    # =============================================================

    st.markdown("### Step 2 — Optional Context")

    extra_context = st.text_area(
        "Additional context (optional)",
        placeholder=(
            "e.g. The client is a SAMA-regulated bank with 500 employees, "
            "a 24/7 SOC team, and uses Azure cloud. "
            "Include specific steps for notifying SAMA's Cyber Threat Information Sharing portal."
        ),
        height=90,
        key="pb_extra_context",
    )

    st.divider()

    # =============================================================
    # SECTION 3: GENERATE
    # =============================================================

    st.markdown("### Step 3 — Generate Playbook")

    with st.expander("📋 Using company profile", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**{company_profile.get('company_name')}** — {company_profile.get('industry')}")
        with c2:
            st.markdown(f"Auditor: {company_profile.get('auditor_name')} | {company_profile.get('engagement_date')}")

    safe_incident = incident_type.replace(" ", "_")
    state_key     = f"playbook_{safe_incident}_{severity_level}"

    generate_clicked = st.button(
        "Generate IR Playbook",
        type="primary",
        use_container_width=True,
        key="pb_generate_btn",
    )

    if generate_clicked and state_key in st.session_state:
        del st.session_state[state_key]

    if generate_clicked or state_key in st.session_state:

        if state_key not in st.session_state:

            with st.status("Generating IR playbook...", expanded=True) as status:
                try:
                    st.write(f"🚨 Building {incident_type} response framework...")

                    prompt = _build_playbook_prompt(
                        incident_type     = incident_type,
                        regulatory_bodies = regulatory_bodies,
                        company_profile   = company_profile,
                        severity_level    = severity_level,
                        extra_context     = extra_context,
                    )

                    st.write("AI generating response timeline and regulatory requirements...")

                    # Use generate_structured since we need JSON back
                    from utils.groq_client import generate_structured
                    raw_data = generate_structured(prompt)

                    content = _validate_playbook(raw_data, incident_type)

                    st.write("📄 Building DOCX and PDF playbooks...")
                    docx_bytes = docx_export_playbook(content, company_profile)
                    pdf_bytes  = pdf_export_playbook(content, company_profile)

                    # --- Write IR readiness finding to shared findings store for Module 7 ---
                    from utils.findings_store import add_finding
                    reg_bodies_str = ", ".join(regulatory_bodies) if regulatory_bodies else "NCA"
                    add_finding(
                        source         = "Module 6 — IR Playbook",
                        severity       = "Informational",
                        title          = f"IR Playbook Generated: {incident_type} ({severity_level} severity)",
                        description    = (
                            f"An incident response playbook was generated for {incident_type} scenarios at {severity_level} severity. "
                            f"The playbook covers {len(content['response_team'])} response team roles, "
                            f"{len(content['response_timeline'])} response steps, and regulatory notification requirements for: {reg_bodies_str}. "
                            f"Review the playbook to confirm response team assignments and escalation contacts are populated."
                        ),
                        recommendation = (
                            f"Distribute the {incident_type} playbook to all response team members. "
                            "Conduct a tabletop exercise within 30 days. "
                            "Ensure regulatory notification deadlines are understood by the Legal/Compliance team."
                        ),
                    )

                    st.session_state[state_key] = {
                        "content":    content,
                        "docx_bytes": docx_bytes,
                        "pdf_bytes":  pdf_bytes,
                    }

                    status.update(label="✅ IR Playbook ready!", state="complete", expanded=False)

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

        content = cached["content"]

        st.success(f"✅ {incident_type} response playbook generated.")

        # Downloads
        company_slug  = company_profile.get("company_name", "Organisation").replace(" ", "_")
        incident_slug = incident_type.replace(" ", "_")
        base_name     = f"{company_slug}_IR_Playbook_{incident_slug}"

        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button(
                "📥 Download DOCX Playbook",
                data=cached["docx_bytes"],
                file_name=f"{base_name}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        with dl2:
            st.download_button(
                "📥 Download PDF Playbook",
                data=cached["pdf_bytes"],
                file_name=f"{base_name}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

        # Playbook preview tabs
        st.divider()
        st.markdown("### 📋 Playbook Preview")

        tab_class, tab_team, tab_timeline, tab_esc, tab_comms, tab_reg = st.tabs([
            "📌 Classification",
            "👥 Response Team",
            "⏱️ Timeline",
            "🔺 Escalation",
            "📢 Communications",
            "⚖️ Regulatory",
        ])

        with tab_class:
            st.write(content["classification"])

        with tab_team:
            for member in content["response_team"]:
                with st.expander(f"**{member.get('role', '')}**"):
                    st.write(member.get("responsibilities", ""))

        with tab_timeline:
            for step in content["response_timeline"]:
                col_a, col_b = st.columns([1, 3])
                with col_a:
                    st.markdown(f"**{step.get('timeframe', '')}**")
                    st.caption(step.get("phase", ""))
                with col_b:
                    st.markdown(f"**{step.get('owner', '')}:** {step.get('action', '')}")
                st.divider()

        with tab_esc:
            for item in content["escalation_matrix"]:
                st.markdown(
                    f"**Trigger:** {item.get('trigger', '')}  \n"
                    f"**Escalate to:** {item.get('escalate_to', '')}  \n"
                    f"**Method:** {item.get('method', '')}"
                )
                st.markdown("---")

        with tab_comms:
            for tmpl in content["comms_templates"]:
                st.markdown(f"**{tmpl.get('audience', '')}**")
                st.info(tmpl.get("template_text", ""))

        with tab_reg:
            for req in content["regulatory_requirements"]:
                col_r1, col_r2 = st.columns([1, 3])
                with col_r1:
                    st.markdown(f"**{req.get('body', '')}**")
                    st.caption(f"Deadline: {req.get('deadline', '')}")
                with col_r2:
                    st.write(req.get("requirement", ""))
                st.markdown("---")

        st.divider()
        if st.button("🔄 Regenerate Playbook", key="pb_regen_btn"):
            if state_key in st.session_state:
                del st.session_state[state_key]
            st.rerun()
