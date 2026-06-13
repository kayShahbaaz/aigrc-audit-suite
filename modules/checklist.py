"""
modules/checklist.py — AI GRC Audit Suite
==========================================
Module 3: Audit Checklist Generator

Generates a detailed audit checklist in Excel format.
The auditor selects a framework, chooses which control domains to include,
and the AI produces a complete checklist with evidence requirements,
audit methods, and a Compliant column ready to fill in during fieldwork.

Key fix: controls are sent to Groq in batches of 8 to avoid hitting the
max_tokens limit which caused JSON truncation with 27 controls at once.

Output Excel columns (per reference spec):
    Control ID, Control Name, Control Description, Evidence Required,
    Responsible Owner, Audit Method, Compliant (Yes/No/Partial/NA),
    Evidence Reference, Auditor Notes, Finding

This module calls:
    utils/groq_client.py    → generate_checklist_items()
    config/frameworks.py    → get_controls_for_framework(), get_domain_names()
    utils/excel_exporter.py → export_audit_checklist()
    utils/findings_store.py → add_finding()
"""

import streamlit as st

from config.frameworks import (
    get_framework_list,
    get_framework_by_id,
    get_controls_for_framework,
    get_all_controls_flat,
    get_domain_names,
)
from utils.groq_client import generate_checklist_items
from utils.excel_exporter import export_audit_checklist


# =============================================================
# CONSTANTS
# =============================================================

AUDIT_SCOPE_OPTIONS = ["Full Audit", "Partial Audit (select domains)"]

# Batch size — how many controls to send to Groq per API call.
# 8 is safe: each control produces ~300 tokens of JSON output,
# so 8 × 300 = 2400 tokens well within the 4096 max_tokens limit.
BATCH_SIZE = 8


# =============================================================
# HELPERS
# =============================================================

def _build_checklist_prompt(
    framework_name: str,
    framework_full_name: str,
    controls: list,
    company_profile: dict,
) -> str:
    """
    Build the structured JSON prompt for a batch of controls.
    Each call handles BATCH_SIZE controls to avoid token truncation.
    """
    company_name = company_profile.get("company_name", "the organisation")
    industry     = company_profile.get("industry", "general industry")

    controls_text = "\n".join([
        f"{i+1}. [{c['id']}] {c['name']}: {c['description']}"
        for i, c in enumerate(controls)
    ])

    prompt = f"""
You are a senior cybersecurity auditor generating an audit checklist for a Saudi Arabian organisation.

ORGANISATION DETAILS:
- Company: {company_name}
- Industry: {industry}
- Framework: {framework_name} ({framework_full_name})

CONTROLS TO INCLUDE (this batch):
{controls_text}

For each control listed above, generate one audit checklist row.
Return ONLY a valid JSON object — no preamble, no markdown, no explanation:

{{
  "controls": [
    {{
      "control_id": "1-1",
      "control_name": "Cybersecurity Leadership and Oversight",
      "control_description": "CISO appointed with board-level oversight of cybersecurity risks",
      "evidence_required": "CISO appointment letter; Board meeting minutes showing cybersecurity agenda; CISO reporting line documentation",
      "responsible_owner": "CEO / Board of Directors",
      "audit_method": "Document review and interview",
      "compliant": "",
      "evidence_reference": "",
      "auditor_notes": "",
      "finding": ""
    }}
  ]
}}

Requirements:
- Return exactly {len(controls)} rows — one per control in the list above
- evidence_required must list 2-4 specific, verifiable evidence items separated by semicolons
- responsible_owner must be a realistic job title for {industry} organisations
- audit_method: use Document review, Staff interview, Technical inspection, Configuration review, Process walkthrough, Evidence sampling, or Tool demonstration
- compliant, evidence_reference, auditor_notes, finding must all be empty strings
- Keep each field concise — this is a checklist, not an essay
""".strip()
    return prompt


def _validate_checklist_row(row: dict, control: dict) -> dict:
    """
    Validate and normalise a checklist row from the LLM.
    Falls back to the source control definition for missing fields.
    """
    return {
        "control_id":          str(row.get("control_id",          control["id"]))[:20],
        "control_name":        str(row.get("control_name",        control["name"]))[:100],
        "control_description": str(row.get("control_description", control["description"]))[:300],
        "evidence_required":   str(row.get("evidence_required",   "Evidence to be determined"))[:300],
        "responsible_owner":   str(row.get("responsible_owner",   "IT Security"))[:80],
        "audit_method":        str(row.get("audit_method",        "Document review"))[:100],
        "compliant":           "",
        "evidence_reference":  "",
        "auditor_notes":       "",
        "finding":             "",
    }


def _generate_in_batches(
    controls: list,
    framework_name: str,
    framework_full_name: str,
    company_profile: dict,
    status_text,
    progress_bar,
    total_batches: int,
    batch_offset: int = 0,
) -> list:
    """
    Send controls to Groq in batches of BATCH_SIZE.
    Returns a flat list of validated checklist row dicts.

    Args:
        controls        : All controls to process
        batch_offset    : Used for progress bar when called from fallback path
    """
    all_rows = []
    batches  = [controls[i:i+BATCH_SIZE] for i in range(0, len(controls), BATCH_SIZE)]

    for batch_idx, batch in enumerate(batches):
        global_batch_num = batch_offset + batch_idx + 1
        status_text.text(
            f"Generating batch {global_batch_num}/{total_batches} "
            f"({batch[0]['id']} → {batch[-1]['id']})..."
        )

        prompt   = _build_checklist_prompt(framework_name, framework_full_name, batch, company_profile)
        raw_data = generate_checklist_items(prompt)
        rows_raw = raw_data.get("controls", [])

        # Validate and align each row with its source control
        for i, row in enumerate(rows_raw):
            ctrl = batch[i] if i < len(batch) else {
                "id": str(i+1), "name": f"Control {i+1}", "description": ""
            }
            all_rows.append(_validate_checklist_row(row, ctrl))

        # Update progress bar
        progress_bar.progress(global_batch_num / total_batches)

    return all_rows


# =============================================================
# MAIN RENDER FUNCTION
# =============================================================

def render(company_profile: dict):
    """
    Main entry point for Module 3 — Audit Checklist Generator.
    Called by app.py with the company_profile dict.
    """

    st.markdown("## Audit Checklist Generator")
    st.markdown(
        "Generate a detailed audit checklist in Excel format. "
        "The checklist includes evidence requirements and audit methods — "
        "ready to fill in during your fieldwork."
    )
    st.divider()

    if not company_profile.get("company_name"):
        st.warning("Please fill in the **Company Profile** before generating a checklist.")
        return

    # =============================================================
    # SECTION 1: FRAMEWORK AND SCOPE
    # =============================================================

    st.markdown("### Step 1 — Select Framework and Scope")

    col1, col2 = st.columns(2)

    with col1:
        framework_options = get_framework_list()
        framework_display = [d for _, d in framework_options]
        framework_ids     = [i for i, _ in framework_options]

        selected_display = st.selectbox(
            "Compliance Framework",
            options=framework_display,
            help="The checklist will cover controls from this framework.",
            key="cl_fw_select",
        )
        selected_fw_id = framework_ids[framework_display.index(selected_display)]
        fw_meta = get_framework_by_id(selected_fw_id)
        if fw_meta:
            st.caption(f"**Applies to:** {fw_meta['applies_to']}")

    with col2:
        audit_scope = st.radio(
            "Audit Scope",
            options=AUDIT_SCOPE_OPTIONS,
            key="cl_scope_radio",
            help="Full audit covers all domains. Partial lets you select specific domains.",
        )

    # =============================================================
    # SECTION 2: DOMAIN SELECTION (Partial scope only)
    # =============================================================

    all_domains  = get_domain_names(selected_fw_id)
    all_controls = get_all_controls_flat(selected_fw_id)

    selected_domains = all_domains  # default: all

    if audit_scope == AUDIT_SCOPE_OPTIONS[1]:   # Partial
        st.divider()
        st.markdown("### Step 2 — Select Control Domains")

        if not all_domains:
            st.warning(
                f"No domain breakdown available for {fw_meta['name']} yet. "
                "A full-framework checklist will be generated."
            )
        else:
            selected_domains = st.multiselect(
                "Control Domains to Include",
                options=all_domains,
                default=all_domains[:2] if all_domains else [],
                help="Select the domains in scope for this audit engagement.",
                key="cl_domain_select",
            )

            if not selected_domains:
                st.warning("Please select at least one control domain.")
                return

            controls_in_scope = [c for c in all_controls if c["domain"] in selected_domains]
            st.caption(
                f"**{len(controls_in_scope)} controls** in scope across "
                f"{len(selected_domains)} domain(s)."
            )

    # Filter controls to selected domains
    controls_to_use = [c for c in all_controls if c["domain"] in selected_domains]

    # Fallback for frameworks without controls defined yet
    use_llm_controls = not controls_to_use
    if use_llm_controls:
        st.info(
            f"ℹ️ Detailed control definitions for **{fw_meta['name']}** are not yet in the "
            "local database. The AI will generate appropriate checklist items."
        )

    st.divider()

    # =============================================================
    # SECTION 3: GENERATE
    # =============================================================

    st.markdown("### Step 3 — Generate Checklist")

    with st.expander("Using company profile", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**{company_profile.get('company_name')}** — {company_profile.get('industry')}")
        with c2:
            st.markdown(f"Auditor: {company_profile.get('auditor_name')} | {company_profile.get('engagement_date')}")

    if not use_llm_controls:
        scope_label = "Full framework" if audit_scope == AUDIT_SCOPE_OPTIONS[0] else f"{len(selected_domains)} domain(s)"
        n_batches   = max(1, -(-len(controls_to_use) // BATCH_SIZE))  # ceiling division
        st.markdown(
            f"**Ready to generate:** `{fw_meta['name']}` checklist — "
            f"{scope_label} — **{len(controls_to_use)} controls** "
            f"in **{n_batches} batch{'es' if n_batches > 1 else ''}**"
        )

    domains_key = "_".join(sorted(selected_domains))[:60] if selected_domains else "all"
    state_key   = f"checklist_{selected_fw_id}_{domains_key}"

    generate_clicked = st.button(
        "Generate Audit Checklist",
        type="primary",
        use_container_width=True,
        key="cl_generate_btn",
    )

    if generate_clicked and state_key in st.session_state:
        del st.session_state[state_key]

    if generate_clicked or state_key in st.session_state:

        if state_key not in st.session_state:

            with st.status("Generating audit checklist...", expanded=True) as status:
                try:
                    rows_clean = []

                    if use_llm_controls:
                        # No local controls — ask LLM for the full checklist in one call
                        # (framework without controls in DB, so count is low enough)
                        st.write(f"Generating {fw_meta['name']} controls and checklist items...")
                        fallback_prompt = f"""
Generate a comprehensive audit checklist for {fw_meta['name']} ({fw_meta['full_name']})
for {company_profile.get('company_name')} in the {company_profile.get('industry')} sector.
Return ONLY valid JSON:
{{
  "controls": [
    {{
      "control_id": "1.1",
      "control_name": "Control Name",
      "control_description": "Description",
      "evidence_required": "Evidence 1; Evidence 2",
      "responsible_owner": "Job Title",
      "audit_method": "Document review",
      "compliant": "",
      "evidence_reference": "",
      "auditor_notes": "",
      "finding": ""
    }}
  ]
}}
Generate 15 controls covering all major domains of {fw_meta['name']}.
""".strip()
                        raw_data = generate_checklist_items(fallback_prompt)
                        for i, row in enumerate(raw_data.get("controls", [])):
                            fallback_ctrl = {
                                "id":          row.get("control_id", f"{i+1}.1"),
                                "name":        row.get("control_name", f"Control {i+1}"),
                                "description": row.get("control_description", ""),
                            }
                            rows_clean.append(_validate_checklist_row(row, fallback_ctrl))

                    else:
                        # Batch generation — main path for NCA ECC, SAMA CSF, PDPL
                        st.write(
                            f"Generating {len(controls_to_use)} controls in batches of {BATCH_SIZE}..."
                        )
                        n_batches    = max(1, -(-len(controls_to_use) // BATCH_SIZE))
                        progress_bar = st.progress(0)
                        status_text  = st.empty()

                        rows_clean = _generate_in_batches(
                            controls         = controls_to_use,
                            framework_name   = fw_meta["name"],
                            framework_full_name = fw_meta["full_name"],
                            company_profile  = company_profile,
                            status_text      = status_text,
                            progress_bar     = progress_bar,
                            total_batches    = n_batches,
                        )
                        status_text.text(f"All {n_batches} batches complete.")
                        progress_bar.progress(1.0)

                    if not rows_clean:
                        st.error("No checklist rows were generated. Please try again.")
                        status.update(label="Generation failed", state="error")
                        return

                    st.write(f"Building Excel file with {len(rows_clean)} rows...")
                    excel_bytes = export_audit_checklist(rows_clean, company_profile)

                    # Write to findings store for Module 7
                    from utils.findings_store import add_finding
                    add_finding(
                        source         = f"Module 3 — Audit Checklist ({fw_meta['name']})",
                        severity       = "Medium",
                        title          = f"Audit Checklist Generated: {fw_meta['name']}",
                        description    = (
                            f"A {len(rows_clean)}-control audit checklist was generated for "
                            f"{fw_meta['name']}. Compliance status columns are blank and must "
                            "be completed during fieldwork."
                        ),
                        recommendation = (
                            "Complete the audit checklist during fieldwork. Return to Module 7 "
                            "and update this finding with specific non-compliant controls identified."
                        ),
                    )

                    st.session_state[state_key] = {
                        "rows":        rows_clean,
                        "excel_bytes": excel_bytes,
                        "fw_name":     fw_meta["name"],
                        "scope_label": (
                            "Full framework"
                            if audit_scope == AUDIT_SCOPE_OPTIONS[0]
                            else f"{len(selected_domains)} domain(s)"
                        ),
                    }

                    status.update(label="Audit checklist ready!", state="complete", expanded=False)

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

        rows        = cached["rows"]
        excel_bytes = cached["excel_bytes"]
        fw_name     = cached["fw_name"]
        scope_lbl   = cached["scope_label"]

        st.success(f"{len(rows)} checklist items generated — {fw_name}, {scope_lbl}.")

        company_slug = company_profile.get("company_name", "Organisation").replace(" ", "_")
        fw_slug      = fw_name.replace(" ", "_")
        filename     = f"{company_slug}_Audit_Checklist_{fw_slug}.xlsx"

        st.download_button(
            label="Download Audit Checklist (Excel)",
            data=excel_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        st.divider()
        st.markdown("### Checklist Preview")
        st.caption(
            "Compliant, Evidence Reference, Auditor Notes, and Finding columns "
            "are blank — you fill these in during fieldwork."
        )

        import pandas as pd
        preview_data = [{
            "Control ID":        r["control_id"],
            "Control Name":      r["control_name"],
            "Evidence Required": r["evidence_required"][:80] + "..." if len(r["evidence_required"]) > 80 else r["evidence_required"],
            "Owner":             r["responsible_owner"],
            "Method":            r["audit_method"],
            "Compliant":         "[ fill in ]",
        } for r in rows]

        df = pd.DataFrame(preview_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.divider()
        if st.button("Regenerate Checklist", key="cl_regen_btn"):
            if state_key in st.session_state:
                del st.session_state[state_key]
            st.rerun()