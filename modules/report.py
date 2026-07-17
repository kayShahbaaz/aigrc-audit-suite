"""
modules/report.py — AI GRC Audit Suite
========================================
Module 7: Audit Report Generator

Generates the final board-ready audit report in PDF format only.
This is the official deliverable — locked, non-editable, professional.

The auditor pastes or summarises findings from earlier modules,
selects which frameworks were audited, and the AI produces a complete
formal report including executive summary, key findings by severity,
compliance scores, and prioritised recommendations.

PDF only — no DOCX. This is intentional:
- Board reports must be locked and non-editable
- PDF ensures consistent formatting on any device
- Prevents accidental or deliberate modification after delivery

How it works:
1. User enters audit findings as free-form text (from any module output)
2. User selects frameworks audited and audit period
3. User enters compliance scores per framework (from Modules 3/4)
4. Click Generate → AI structures findings into a formal report format
5. PDF download button appears

This module calls:
    utils/groq_client.py    → generate_audit_report_section()
    utils/pdf_exporter.py   → export_audit_report()
"""

import streamlit as st
from datetime import datetime

from config.frameworks import get_framework_list, get_framework_by_id, FRAMEWORKS
from config.settings import RISK_LEVEL_THRESHOLDS
from utils.groq_client import generate_audit_report_section, generate_structured
from utils.findings_store import get_all_findings, format_for_module7, get_findings_summary, clear_findings
from utils.pdf_exporter import export_audit_report as pdf_export_report


# =============================================================
# SEVERITY LEVELS — used for findings input
# =============================================================

SEVERITY_LEVELS = ["Critical", "High", "Medium", "Low", "Informational"]

FINDING_TEMPLATE = """Finding title here
Severity: High
Description: Describe what was found and the evidence observed.
Recommendation: Specific remediation action with timeline.

---

Finding title here
Severity: Medium
Description: Another finding.
Recommendation: Remediation step."""


# =============================================================
# PROMPT BUILDERS
# =============================================================

def _build_exec_summary_prompt(
    company_profile: dict,
    frameworks: list,
    audit_period: str,
    findings_text: str,
    scores: list,
) -> str:
    """
    Build prompt for Groq to write the executive summary section.
    Returns formal, board-level prose.
    """
    company_name = company_profile.get("company_name", "the organisation")
    industry     = company_profile.get("industry", "general industry")
    fw_names     = ", ".join(frameworks) if frameworks else "multiple frameworks"

    scores_text = "\n".join(
        f"- {s['framework']}: {s['score_pct']}" for s in scores
    ) if scores else "Scores not provided"

    return f"""
Write a formal executive summary for a cybersecurity audit report.

AUDIT DETAILS:
- Organisation: {company_name} ({industry}, Saudi Arabia)
- Frameworks audited: {fw_names}
- Audit period: {audit_period}
- Compliance scores:
{scores_text}

FINDINGS SUMMARY PROVIDED BY AUDITOR:
{findings_text[:2000]}

Write 4-5 sentences of formal, board-level prose. Requirements:
- Reference the specific Saudi frameworks audited
- State the overall compliance posture directly (strong/moderate/weak)
- Mention the most critical finding without technical jargon
- Close with a forward-looking statement about remediation priority
- Do NOT use bullet points. Pure prose only.
- Language must be suitable for a board of directors
""".strip()


def _build_scope_methodology_prompt(
    company_profile: dict,
    frameworks: list,
    audit_period: str,
    audit_methods_used: list,
) -> str:
    """Build prompt for the scope and methodology section."""
    company_name = company_profile.get("company_name", "the organisation")
    fw_text      = ", ".join(frameworks) if frameworks else "multiple frameworks"
    methods_text = ", ".join(audit_methods_used) if audit_methods_used else "document review, interviews, technical inspection"

    return f"""
Write a formal scope and methodology section for a cybersecurity audit report.

DETAILS:
- Organisation: {company_name}
- Frameworks: {fw_text}
- Audit period: {audit_period}
- Methods used: {methods_text}

Write 3-4 sentences covering: what was in scope, what was out of scope,
the audit methodology used, and any limitations or caveats.
Professional, formal tone. No bullet points.
""".strip()


def _build_conclusion_prompt(
    company_profile: dict,
    score_summary: str,
    critical_count: int,
    high_count: int,
) -> str:
    """Build prompt for the conclusion section."""
    company_name = company_profile.get("company_name", "the organisation")

    urgency = "immediate" if critical_count > 0 else ("urgent" if high_count > 0 else "timely")

    return f"""
Write a formal conclusion for a cybersecurity audit report.

CONTEXT:
- Organisation: {company_name}
- Compliance summary: {score_summary}
- Critical findings: {critical_count}
- High severity findings: {high_count}

Write 2-3 sentences that:
1. Summarise the audit outcome objectively
2. State the {urgency} remediation priority
3. Reference the organisation's obligation under Saudi regulatory requirements

Formal board-level tone. No bullet points. Third person where appropriate.
""".strip()


def _parse_findings_text(raw_text: str) -> list:
    """
    Parse free-form findings text into structured finding dicts.

    Expects each finding separated by '---' and with these fields:
    - First line: title
    - Severity: <level>
    - Description: <text>
    - Recommendation: <text>

    Falls back gracefully for any finding that doesn't match the format.
    """
    findings = []
    blocks   = [b.strip() for b in raw_text.split("---") if b.strip()]

    for block in blocks:
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue

        title       = lines[0]
        severity    = "Medium"
        description = ""
        recommendation = ""

        for line in lines[1:]:
            lower = line.lower()
            if lower.startswith("severity:"):
                sev_val = line.split(":", 1)[1].strip()
                if sev_val in SEVERITY_LEVELS:
                    severity = sev_val
            elif lower.startswith("description:"):
                description = line.split(":", 1)[1].strip()
            elif lower.startswith("recommendation:"):
                recommendation = line.split(":", 1)[1].strip()

        if title:
            findings.append({
                "severity":       severity,
                "title":          title[:100],
                "description":    description[:300] or f"See finding: {title}",
                "recommendation": recommendation[:300] or "Remediation required — see report.",
            })

    return findings


def _build_recommendations_from_findings(findings: list) -> list:
    """
    Derive a prioritised recommendations list from the parsed findings.
    Critical first, then High, Medium, Low.
    """
    severity_order = {s: i for i, s in enumerate(SEVERITY_LEVELS)}
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f["severity"], 99))

    recommendations = []
    for i, f in enumerate(sorted_findings[:10], start=1):
        recommendations.append({
            "priority":       str(i),
            "recommendation": f["recommendation"] or f"Remediate: {f['title']}",
            "owner":          "CISO / IT Security",
            "timeline":       "30 days" if f["severity"] in ("Critical", "High") else "90 days",
        })

    return recommendations


# =============================================================
# MAIN RENDER FUNCTION
# =============================================================

def render(company_profile: dict):
    """
    Main entry point for Module 7 — Audit Report Generator.
    Called by app.py with the company_profile dict.
    """

    st.markdown("## 📊 Audit Report Generator")
    st.markdown(
        "Generate the final, board-ready audit report in PDF format. "
        "This is the official deliverable — professional, locked, and ready to present."
    )

    st.info(
        "**PDF only.** The audit report is the final locked deliverable. "
        "It cannot be edited after generation — this is intentional for integrity."
    )
    st.divider()

    if not company_profile.get("company_name"):
        st.warning("⚠️ Please fill in the **Company Profile** before generating the audit report.")
        return

    # =============================================================
    # SECTION 1: ENGAGEMENT DETAILS
    # =============================================================

    st.markdown("### Step 1 — Engagement Details")

    col1, col2 = st.columns(2)

    with col1:
        # Frameworks audited — multi-select
        fw_options  = get_framework_list()
        fw_display  = [d for _, d in fw_options]
        fw_ids      = [i for i, _ in fw_options]

        selected_fw_displays = st.multiselect(
            "Frameworks Audited *",
            options=fw_display,
            default=fw_display[:2] if fw_display else [],
            help="Select all frameworks covered in this engagement.",
            key="rpt_fw_select",
        )
        selected_fw_names = []
        for disp in selected_fw_displays:
            idx = fw_display.index(disp)
            fw_meta = get_framework_by_id(fw_ids[idx])
            if fw_meta:
                selected_fw_names.append(fw_meta["name"])

        audit_methods_used = st.multiselect(
            "Audit Methods Used",
            options=[
                "Document review",
                "Staff interviews",
                "Technical inspection",
                "Configuration review",
                "Penetration testing",
                "Vulnerability scanning",
                "Process walkthroughs",
                "Evidence sampling",
            ],
            default=["Document review", "Staff interviews", "Technical inspection"],
            key="rpt_methods",
        )

    with col2:
        audit_period = st.text_input(
            "Audit Period *",
            value=f"Q{(datetime.today().month - 1) // 3 + 1} {datetime.today().year}",
            placeholder="e.g. Q2 2025 or January–March 2025",
            key="rpt_period",
        )

        # Compliance scores — one per selected framework
        st.markdown("**Compliance Scores (%)**")
        scores = []
        for fw_name in selected_fw_names:
            score_val = st.number_input(
                f"{fw_name}",
                min_value=0,
                max_value=100,
                value=70,
                step=5,
                key=f"rpt_score_{fw_name}",
            )
            scores.append({"framework": fw_name, "score_pct": f"{score_val}%"})

    st.divider()

    # =============================================================
    # SECTION 2: FINDINGS INPUT
    # =============================================================

    st.markdown("### Step 2 — Audit Findings")

    # --- Auto-fill from modules 2-6 ---
    summary      = get_findings_summary()
    auto_text    = format_for_module7()
    findings_count = summary.get("total", 0)

    if findings_count > 0:
        sources_list = summary.get("sources", [])
        st.success(
            f"✅ **{findings_count} finding(s) collected automatically** from: "
            f"{', '.join(sources_list)}\n\n"
            f"🔴 Critical: {summary.get('Critical',0)}  "
            f"🟠 High: {summary.get('High',0)}  "
            f"🟡 Medium: {summary.get('Medium',0)}  "
            f"🟢 Low: {summary.get('Low',0)}  "
            f"⚪ Info: {summary.get('Informational',0)}"
        )
        col_clear, col_space = st.columns([1, 4])
        with col_clear:
            if st.button("🗑️ Clear collected findings", key="rpt_clear_findings"):
                clear_findings()
                # Reset sync tracker so the textarea re-syncs to empty on rerun
                st.session_state["_rpt_findings_synced_count"] = -1
                st.session_state["rpt_findings_text"] = ""
                st.rerun()
    else:
        st.info(
            "ℹ️ No findings collected yet from other modules.\n\n"
            "Run Modules 2–6 first and their findings will appear here automatically.\n\n"
            "Or type findings manually using the format below."
        )

    with st.expander("📖 Findings format (for manual entry)", expanded=findings_count == 0):
        st.code(FINDING_TEMPLATE, language=None)

    # --- Seed the textarea's session_state value BEFORE the widget renders ---
    # Streamlit ignores `value=` on st.text_area() once its `key` already exists
    # in session_state (which it will, on every rerun after the first). So we
    # must write directly to session_state[key] ourselves, and only do it when
    # the underlying findings have actually changed — otherwise we'd overwrite
    # anything the auditor typed or edited by hand.
    #
    # _rpt_findings_synced_count tracks how many findings were present the last
    # time we synced the textarea. If the live count differs (new findings
    # arrived from another module, or findings were cleared), we re-sync.
    last_synced_count = st.session_state.get("_rpt_findings_synced_count", -1)

    if findings_count != last_synced_count:
        st.session_state["rpt_findings_text"] = auto_text
        st.session_state["_rpt_findings_synced_count"] = findings_count

    findings_text = st.text_area(
        "Audit Findings *",
        placeholder=FINDING_TEMPLATE,
        height=350,
        key="rpt_findings_text",
        help="Auto-filled from Modules 2–6. Edit freely — add, remove, or adjust any finding.",
    )

    st.divider()

    # =============================================================
    # SECTION 3: GENERATE
    # =============================================================

    st.markdown("### Step 3 — Generate Report")

    with st.expander("📋 Using company profile", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**{company_profile.get('company_name')}**")
            st.caption(company_profile.get("industry", ""))
        with c2:
            st.markdown(f"**{company_profile.get('auditor_name')}**")
            st.caption(f"{company_profile.get('city')}, Saudi Arabia")
        with c3:
            st.markdown(f"**{audit_period}**")
            st.caption(", ".join(selected_fw_names) if selected_fw_names else "No frameworks selected")

    # Validation
    can_generate = bool(
        findings_text.strip() and
        selected_fw_names and
        audit_period.strip()
    )

    if not can_generate:
        missing = []
        if not findings_text.strip():   missing.append("audit findings")
        if not selected_fw_names:       missing.append("frameworks audited")
        if not audit_period.strip():    missing.append("audit period")
        st.warning(f"⚠️ Please provide: {', '.join(missing)}")

    # State key
    fw_key    = "_".join(sorted(selected_fw_names))[:40]
    state_key = f"report_{fw_key}_{audit_period.replace(' ', '_')[:20]}"

    generate_clicked = st.button(
        "Generate Audit Report",
        type="primary",
        use_container_width=True,
        disabled=not can_generate,
        key="rpt_generate_btn",
    )

    if generate_clicked and state_key in st.session_state:
        del st.session_state[state_key]

    if generate_clicked or state_key in st.session_state:

        if state_key not in st.session_state:

            with st.status("Generating audit report...", expanded=True) as status:
                try:
                    # Step 1: Parse findings text into structured list
                    st.write("🔍 Parsing audit findings...")
                    findings = _parse_findings_text(findings_text)

                    if not findings:
                        # If no '---' separators, treat the whole text as one finding
                        findings = [{
                            "severity":       "High",
                            "title":          "Audit Findings",
                            "description":    findings_text[:500],
                            "recommendation": "Review findings and implement recommended controls.",
                        }]

                    critical_count = sum(1 for f in findings if f["severity"] == "Critical")
                    high_count     = sum(1 for f in findings if f["severity"] == "High")
                    total_findings = len(findings)

                    st.write(f"✅ {total_findings} finding(s) parsed — {critical_count} Critical, {high_count} High")

                    # Step 2: Generate executive summary
                    st.write("✍️ Writing executive summary...")
                    exec_prompt   = _build_exec_summary_prompt(
                        company_profile = company_profile,
                        frameworks      = selected_fw_names,
                        audit_period    = audit_period,
                        findings_text   = findings_text,
                        scores          = scores,
                    )
                    executive_summary = generate_audit_report_section(exec_prompt)

                    # Step 3: Generate scope and methodology
                    st.write("✍️ Writing scope and methodology...")
                    scope_prompt      = _build_scope_methodology_prompt(
                        company_profile     = company_profile,
                        frameworks          = selected_fw_names,
                        audit_period        = audit_period,
                        audit_methods_used  = audit_methods_used,
                    )
                    scope_methodology = generate_audit_report_section(scope_prompt)

                    # Step 4: Generate conclusion
                    st.write("✍️ Writing conclusion...")
                    avg_score     = sum(int(s["score_pct"].rstrip("%")) for s in scores) / len(scores) if scores else 0
                    score_summary = f"Average compliance: {avg_score:.0f}% across {len(selected_fw_names)} framework(s)"
                    conc_prompt   = _build_conclusion_prompt(
                        company_profile = company_profile,
                        score_summary   = score_summary,
                        critical_count  = critical_count,
                        high_count      = high_count,
                    )
                    conclusion = generate_audit_report_section(conc_prompt)

                    # Step 5: Build prioritised recommendations
                    recommendations = _build_recommendations_from_findings(findings)

                    # Step 6: Assemble full content dict
                    content = {
                        "frameworks_audited": selected_fw_names,
                        "audit_period":       audit_period,
                        "executive_summary":  executive_summary,
                        "scope_methodology":  scope_methodology,
                        "key_findings":       findings,
                        "compliance_scores":  scores,
                        "recommendations":    recommendations,
                        "conclusion":         conclusion,
                        "arabic_summary":     "",
                    }

                    # Step 7: Generate PDF
                    st.write("🔒 Building final PDF report...")
                    pdf_bytes = pdf_export_report(content, company_profile)

                    st.session_state[state_key] = {
                        "content":   content,
                        "pdf_bytes": pdf_bytes,
                        "findings":  findings,
                        "scores":    scores,
                    }

                    status.update(
                        label="✅ Audit report ready!",
                        state="complete",
                        expanded=False,
                    )

                except EnvironmentError as e:
                    st.error(f"**API Key Error:** {e}")
                    status.update(label="API key not configured", state="error")
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

        content  = cached["content"]
        findings = cached["findings"]
        scores   = cached["scores"]

        # Summary metrics
        critical_n = sum(1 for f in findings if f["severity"] == "Critical")
        high_n     = sum(1 for f in findings if f["severity"] == "High")
        medium_n   = sum(1 for f in findings if f["severity"] == "Medium")
        low_n      = sum(1 for f in findings if f["severity"] in ("Low", "Informational"))

        st.success(f"✅ Audit report generated — {len(findings)} finding(s) across {len(selected_fw_names)} framework(s).")

        # Metrics row
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total Findings",  len(findings))
        m2.metric("🔴 Critical",     critical_n)
        m3.metric("🟠 High",         high_n)
        m4.metric("🟡 Medium",       medium_n)
        m5.metric("🟢 Low",          low_n)

        # Compliance scores
        if scores:
            st.divider()
            st.markdown("**Compliance Scores**")
            score_cols = st.columns(len(scores))
            for i, s in enumerate(scores):
                score_val = int(s["score_pct"].rstrip("%"))
                colour = "🟢" if score_val >= 80 else ("🟡" if score_val >= 60 else "🔴")
                score_cols[i].metric(f"{colour} {s['framework']}", s["score_pct"])

        # Download
        st.divider()
        company_slug = company_profile.get("company_name", "Organisation").replace(" ", "_")
        period_slug  = audit_period.replace(" ", "_")
        filename     = f"{company_slug}_Audit_Report_{period_slug}.pdf"

        st.download_button(
            label="📥 Download Audit Report (PDF)",
            data=cached["pdf_bytes"],
            file_name=filename,
            mime="application/pdf",
            use_container_width=True,
        )

        st.caption(
            "⚠️ This PDF is the official locked deliverable. "
            "Store it securely. Share with client management and board."
        )

        # Report preview
        st.divider()
        st.markdown("### 📋 Report Preview")

        with st.expander("Executive Summary", expanded=True):
            st.write(content["executive_summary"])

        with st.expander("Scope and Methodology", expanded=False):
            st.write(content["scope_methodology"])

        with st.expander(f"Key Findings ({len(findings)})", expanded=True):
            severity_icons = {
                "Critical": "🔴", "High": "🟠",
                "Medium": "🟡", "Low": "🟢", "Informational": "⚪"
            }
            for f in findings:
                icon = severity_icons.get(f["severity"], "⚪")
                with st.expander(f"{icon} [{f['severity']}] {f['title']}"):
                    st.markdown(f"**Description:** {f['description']}")
                    st.markdown(f"**Recommendation:** {f['recommendation']}")

        with st.expander("Recommendations", expanded=False):
            for r in content["recommendations"]:
                st.markdown(
                    f"**{r['priority']}.** {r['recommendation']}  \n"
                    f"*Owner: {r['owner']} | Timeline: {r['timeline']}*"
                )

        with st.expander("Conclusion", expanded=False):
            st.write(content["conclusion"])

        st.divider()
        if st.button("🔄 Regenerate Report", key="rpt_regen_btn"):
            if state_key in st.session_state:
                del st.session_state[state_key]
            st.rerun()
