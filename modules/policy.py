"""
modules/policy.py — AI GRC Audit Suite
========================================
Module 1: Compliance Policy Generator

Generates professional compliance policy documents in DOCX + PDF format.
The user selects a framework, picks a policy type, and the AI produces
a complete, clause-numbered policy document ready to hand to a client.

How it works:
1. User selects framework → policy type list updates automatically
2. User optionally adds context (company-specific details to include)
3. User selects language (English only or English + Arabic bilingual)
4. Click Generate → Groq writes the full policy
5. Two download buttons appear: Download DOCX and Download PDF

This module calls:
    utils/groq_client.py    → generate_policy()
    utils/groq_client.py    → translate_to_arabic()  (bilingual mode only)
    utils/docx_exporter.py  → export_policy()
    utils/pdf_exporter.py   → export_policy()

Coding rules followed:
    - render(company_profile) is the only public function
    - Never calls Groq directly — always via groq_client.py
    - Never asks user for company name — reads from company_profile
    - Progress bars for long operations
    - Clear success and error messages
"""

import streamlit as st

from config.frameworks import (
    get_framework_list,
    get_framework_by_id,
    get_policy_types_for_framework,
)
from config.settings import LANGUAGE_OPTIONS
from utils.groq_client import generate_policy, translate_to_arabic
from utils.docx_exporter import export_policy as docx_export_policy
from utils.pdf_exporter  import export_policy as pdf_export_policy


# =============================================================
# PROMPT BUILDERS
# Build the exact prompts sent to Groq for each policy section.
# Kept here (not in groq_client.py) because they are module-specific.
# =============================================================

def _build_policy_prompt(
    framework_name: str,
    framework_full_name: str,
    policy_type: str,
    company_profile: dict,
    extra_context: str,
) -> str:
    """
    Build the full prompt for Groq to generate the policy document content.

    Returns a prompt that instructs the model to produce four clearly
    separated sections that we can parse and route to the right parts
    of the DOCX/PDF template.

    The prompt uses XML-style tags as delimiters so we can reliably
    extract each section even if the model adds extra commentary.
    """
    company_name   = company_profile.get("company_name", "the organisation")
    industry       = company_profile.get("industry", "general industry")
    company_size   = company_profile.get("company_size", "SME")
    city           = company_profile.get("city", "Saudi Arabia")

    prompt = f"""
You are writing a professional compliance policy document for a Saudi Arabian organisation.

ORGANISATION DETAILS:
- Company: {company_name}
- Industry: {industry}
- Size: {company_size}
- Location: {city}, Saudi Arabia
- Compliance Framework: {framework_name} ({framework_full_name})
- Policy Required: {policy_type}

{"ADDITIONAL CONTEXT PROVIDED BY AUDITOR: " + extra_context if extra_context.strip() else ""}

Write the complete policy document with the following four sections.
Use the exact XML tags shown — they are used to extract each section.

<SCOPE>
Write 2-3 sentences defining who this policy applies to, what systems/data it covers,
and any explicit exclusions. Be specific to {company_name}'s industry ({industry}).
</SCOPE>

<POLICY_BODY>
Write the full policy statement as numbered clauses.
Format EXACTLY as:
2.1  [First policy clause — complete sentence ending in full stop.]
2.2  [Second policy clause.]
2.3  [Third clause.]
... and so on.

Requirements:
- Minimum 12 clauses, maximum 20 clauses
- Each clause must be a specific, enforceable requirement (not vague guidance)
- Map clauses directly to {framework_name} requirements where possible
- Include clauses specific to Saudi regulatory context where relevant
- Use "must" for mandatory requirements, "should" for recommended
- Do NOT use bullet points — numbered clauses only
- Do NOT add section headers inside the body — just the numbered clauses
</POLICY_BODY>

<ROLES>
Write 3-5 sentences defining roles and responsibilities.
Name specific roles (CISO, IT Security Manager, Department Managers, All Staff).
State what each role is responsible for in relation to this specific policy.
</ROLES>

<REVIEW>
Write 2 sentences: one stating the review frequency (annual minimum),
one stating what triggers an out-of-cycle review.
</REVIEW>

Write nothing outside these four XML tags.
"""
    return prompt.strip()


def _parse_policy_sections(raw_text: str) -> dict:
    """
    Parse the Groq response and extract each tagged section.

    The model is instructed to wrap each section in XML tags.
    This function extracts the content between each pair of tags.
    Falls back gracefully if a section is missing.

    Returns a dict with keys: scope, policy_body, roles, review_schedule
    """
    import re

    def extract(tag: str) -> str:
        """Extract text between <TAG> and </TAG>, stripping whitespace."""
        pattern = rf"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, raw_text, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    return {
        "scope":           extract("SCOPE"),
        "policy_body":     extract("POLICY_BODY"),
        "roles":           extract("ROLES"),
        "review_schedule": extract("REVIEW"),
    }


# =============================================================
# MAIN RENDER FUNCTION
# =============================================================

def render(company_profile: dict):
    """
    Main entry point for Module 1 — Policy Generator.
    Called by app.py. Streamlit renders this as a full tab.

    company_profile contains:
        company_name, industry, company_size, country, city,
        target_frameworks, auditor_name, engagement_date
    """

    # --- Module header ---
    st.markdown("## 📄 Compliance Policy Generator")
    st.markdown(
        "Generate a professional compliance policy document in minutes. "
        "Select a framework, choose the policy type, and the AI produces a complete, "
        "clause-numbered policy ready to hand to your client."
    )
    st.divider()

    # --- Guard: company profile must be filled ---
    # We cannot generate a meaningful policy without at least a company name.
    if not company_profile.get("company_name"):
        st.warning(
            "⚠️ Please fill in the **Company Profile** at the top of the page "
            "before generating a policy."
        )
        return

    # =============================================================
    # SECTION 1: USER SELECTIONS
    # =============================================================

    st.markdown("### Step 1 — Select Framework and Policy")

    col1, col2 = st.columns(2)

    with col1:
        # Framework selector — populated from config/frameworks.py
        # get_framework_list() returns [(id, display_name), ...]
        framework_options = get_framework_list()
        framework_display = [display for _, display in framework_options]
        framework_ids     = [fw_id   for fw_id, _ in framework_options]

        selected_display = st.selectbox(
            "Compliance Framework",
            options=framework_display,
            help="Select the Saudi compliance framework this policy must satisfy.",
        )

        # Get the ID (e.g. "NCA_ECC") from the display name chosen
        selected_fw_id = framework_ids[framework_display.index(selected_display)]

        # Show framework description as an info callout
        fw_meta = get_framework_by_id(selected_fw_id)
        if fw_meta:
            st.caption(f"**Applies to:** {fw_meta['applies_to']}")

    with col2:
        # Policy type selector — updates when framework changes
        policy_types = get_policy_types_for_framework(selected_fw_id)

        if not policy_types:
            st.warning("No policy types defined for this framework yet.")
            return

        selected_policy_type = st.selectbox(
            "Policy Type",
            options=policy_types,
            help="Select the specific policy document you need to generate.",
        )

    st.divider()

    # =============================================================
    # SECTION 2: OPTIONAL CONTEXT + LANGUAGE
    # =============================================================

    st.markdown("### Step 2 — Optional Details")

    col3, col4 = st.columns([2, 1])

    with col3:
        extra_context = st.text_area(
            "Additional context for the AI (optional)",
            placeholder=(
                "e.g. Include a clause about remote desktop access restrictions. "
                "The company uses Microsoft 365 and Azure. "
                "We have 3rd party contractors accessing the network via VPN."
            ),
            height=100,
            help=(
                "Provide any specific requirements, technologies, or restrictions "
                "you want the policy to include. Leave blank for a standard policy."
            ),
        )

    with col4:
        # Language selector — English only or bilingual with Arabic
        language_choice = st.radio(
            "Output Language",
            options=list(LANGUAGE_OPTIONS.keys()),
            format_func=lambda k: LANGUAGE_OPTIONS[k],
            help=(
                "Bilingual adds an Arabic executive summary page. "
                "The rest of the document remains in English."
            ),
        )
        bilingual = (language_choice == "Bilingual")

        if bilingual:
            st.caption(
                "🇸🇦 Arabic summary will be added as a final page. "
                "Technical terms (NCA, SAMA, ECC) stay in English."
            )

    st.divider()

    # =============================================================
    # SECTION 3: COMPANY PROFILE PREVIEW
    # So the auditor can confirm before generating
    # =============================================================

    st.markdown("### Step 3 — Confirm Details")

    with st.expander("📋 Company profile being used", expanded=False):
        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.markdown(f"**Company:** {company_profile.get('company_name', '—')}")
            st.markdown(f"**Industry:** {company_profile.get('industry', '—')}")
            st.markdown(f"**Size:** {company_profile.get('company_size', '—')}")
        with info_col2:
            st.markdown(f"**City:** {company_profile.get('city', '—')}")
            st.markdown(f"**Auditor:** {company_profile.get('auditor_name', '—')}")
            st.markdown(f"**Date:** {company_profile.get('engagement_date', '—')}")

    st.markdown(
        f"**Policy to generate:** `{selected_policy_type}` "
        f"under **{fw_meta['name']} — {fw_meta['full_name']}**"
    )

    st.divider()

    # =============================================================
    # SECTION 4: GENERATE BUTTON
    # =============================================================

    # Use session state to hold the generated content so the user
    # can download DOCX and PDF without re-generating each time.
    # Key includes framework + policy type so changing selections clears the cache.
    state_key = f"policy_{selected_fw_id}_{selected_policy_type.replace(' ', '_')}"

    generate_clicked = st.button(
        "Generate Policy",
        type="primary",
        use_container_width=True,
        help="Click to generate the policy document using AI. Takes 10-30 seconds.",
    )

    if generate_clicked:
        # Clear any previously generated content for this key
        if state_key in st.session_state:
            del st.session_state[state_key]

    # =============================================================
    # SECTION 5: AI GENERATION LOGIC
    # Runs when Generate is clicked or when state already has content
    # =============================================================

    if generate_clicked or state_key in st.session_state:

        # Only call the API if we don't already have this result cached
        if state_key not in st.session_state:

            # --- Step 1: Generate policy text ---
            with st.status("Generating policy document...", expanded=True) as status:

                try:
                    st.write("📝 Building policy framework context...")
                    prompt = _build_policy_prompt(
                        framework_name      = fw_meta["name"],
                        framework_full_name = fw_meta["full_name"],
                        policy_type         = selected_policy_type,
                        company_profile     = company_profile,
                        extra_context       = extra_context,
                    )

                    st.write("Sending to AI — generating policy clauses...")
                    raw_text = generate_policy(prompt)

                    st.write("🔍 Parsing policy sections...")
                    sections = _parse_policy_sections(raw_text)

                    # Validate that we got usable content
                    if not sections["policy_body"]:
                        st.error(
                            "The AI response did not contain the expected policy body. "
                            "Please try again."
                        )
                        status.update(label="Generation failed", state="error")
                        return

                    # --- Step 2: Translate to Arabic if bilingual ---
                    arabic_summary = ""
                    if bilingual:
                        st.write("🌐 Translating executive summary to Arabic...")
                        # Translate the scope section as the Arabic executive summary
                        # (Scope is the most readable section for a non-technical audience)
                        arabic_input = (
                            f"Policy: {selected_policy_type}\n\n"
                            f"Framework: {fw_meta['name']} — {fw_meta['full_name']}\n\n"
                            f"Summary: {sections['scope']}\n\n"
                            f"This policy applies to {company_profile.get('company_name')} "
                            f"and was prepared by {company_profile.get('auditor_name', 'the auditor')}."
                        )
                        try:
                            arabic_summary = translate_to_arabic(arabic_input)
                        except Exception as e:
                            # Don't fail the whole generation if Arabic translation fails
                            st.warning(f"Arabic translation failed: {e}. Continuing with English only.")
                            arabic_summary = ""

                    # --- Step 3: Assemble the full content dict ---
                    content = {
                        "framework_name":  fw_meta["name"],
                        "policy_type":     selected_policy_type,
                        "scope":           sections["scope"],
                        "policy_body":     sections["policy_body"],
                        "roles":           sections["roles"],
                        "review_schedule": sections["review_schedule"],
                        "arabic_summary":  arabic_summary,
                    }

                    # --- Step 4: Generate DOCX and PDF bytes ---
                    st.write("📄 Building DOCX document...")
                    docx_bytes = docx_export_policy(content, company_profile)

                    st.write("🔒 Building PDF document...")
                    pdf_bytes = pdf_export_policy(content, company_profile)

                    # Cache everything in session state
                    st.session_state[state_key] = {
                        "content":    content,
                        "docx_bytes": docx_bytes,
                        "pdf_bytes":  pdf_bytes,
                    }

                    status.update(
                        label="✅ Policy generated successfully!",
                        state="complete",
                        expanded=False,
                    )

                except EnvironmentError as e:
                    # API key missing — show helpful setup instructions
                    st.error(f"**API Key Error:** {e}")
                    status.update(label="API key not configured", state="error")
                    return

                except RuntimeError as e:
                    # Groq rate limit or network error
                    st.error(f"**AI Generation Error:** {e}")
                    status.update(label="Generation failed", state="error")
                    return

                except Exception as e:
                    st.error(f"**Unexpected error:** {e}")
                    status.update(label="Generation failed", state="error")
                    return

        # =============================================================
        # SECTION 6: DISPLAY RESULTS + DOWNLOAD BUTTONS
        # =============================================================

        cached = st.session_state.get(state_key)
        if not cached:
            return

        content    = cached["content"]
        docx_bytes = cached["docx_bytes"]
        pdf_bytes  = cached["pdf_bytes"]

        st.success("✅ Policy document ready for download.")

        # Download buttons — side by side
        dl_col1, dl_col2 = st.columns(2)

        # Build a clean filename: CompanyName_PolicyType_Framework.docx
        company_slug = company_profile.get("company_name", "Organisation").replace(" ", "_")
        policy_slug  = selected_policy_type.replace(" ", "_")
        fw_slug      = fw_meta["name"].replace(" ", "_")
        filename_base = f"{company_slug}_{policy_slug}_{fw_slug}"

        with dl_col1:
            st.download_button(
                label="📥 Download DOCX",
                data=docx_bytes,
                file_name=f"{filename_base}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                help="Editable Word document — share with client for internal review and sign-off.",
            )

        with dl_col2:
            st.download_button(
                label="📥 Download PDF",
                data=pdf_bytes,
                file_name=f"{filename_base}.pdf",
                mime="application/pdf",
                use_container_width=True,
                help="Locked PDF — for formal distribution and archiving.",
            )

        # =============================================================
        # SECTION 7: POLICY PREVIEW
        # Let the auditor read the generated content before downloading
        # =============================================================

        st.divider()
        st.markdown("### 👁️ Policy Preview")
        st.caption(
            "This is the generated content. "
            "Download DOCX to edit, or PDF for the final locked version."
        )

        with st.expander("📋 Scope and Purpose", expanded=True):
            st.write(content["scope"])

        with st.expander("📜 Policy Statement (Clauses)", expanded=True):
            # Render each clause on its own line for readability
            for line in content["policy_body"].split("\n"):
                line = line.strip()
                if line:
                    st.write(line)

        with st.expander("👥 Roles and Responsibilities", expanded=False):
            st.write(content["roles"])

        with st.expander("🗓️ Review Schedule", expanded=False):
            st.write(content["review_schedule"])

        if content.get("arabic_summary"):
            with st.expander("🇸🇦 Arabic Summary (ملخص)", expanded=False):
                # Right-align Arabic text using HTML
                st.markdown(
                    f'<div style="direction:rtl; text-align:right; '
                    f'font-family:Arial; font-size:16px; line-height:1.8;">'
                    f'{content["arabic_summary"]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # Regenerate button — lets auditor try again with different settings
        st.divider()
        if st.button("🔄 Regenerate Policy", use_container_width=False):
            if state_key in st.session_state:
                del st.session_state[state_key]
            st.rerun()
