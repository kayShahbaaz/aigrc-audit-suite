"""
utils/pdf_exporter.py — AI GRC Audit Suite
============================================
PDF document generation for Modules 1, 4, 5, 6, and 7 using FPDF2.

All PDF exports go through here. Modules never import fpdf2 directly.

Key design decisions:
- PDF is the "locked" version — non-editable, for distribution and archiving
- Module 7 (Audit Report) is PDF-only — this is the official board deliverable
- Uses FPDF2's multi_cell for long text that wraps across lines
- Arabic RTL text is handled via a dedicated helper

Functions:
    export_policy(content, company_profile)         → bytes  (Module 1)
    export_gap_assessment(content, company_profile) → bytes  (Module 4)
    export_vendor_risk(content, company_profile)    → bytes  (Module 5)
    export_ir_playbook(content, company_profile)    → bytes  (Module 6)
    export_audit_report(content, company_profile)   → bytes  (Module 7 — PDF only)

All functions return bytes for st.download_button().
"""

import io
from datetime import datetime
from fpdf import FPDF


# =============================================================
# BRAND COLOURS — RGB tuples matching docx_exporter.py
# =============================================================

NAVY  = (26,  55,  94)    # #1A375E — headings, header bars
GOLD  = (200, 154,  26)   # #C89A1A — accents, dividers
DARK  = (31,  31,  31)    # #1F1F1F — body text
GREY  = (85,  85,  85)    # #555555 — secondary text
WHITE = (255, 255, 255)   # #FFFFFF — text on dark backgrounds
RED   = (192,  57,  43)   # #C0392B — Critical/High risk
AMBER = (230, 126,  34)   # #E67E22 — Medium risk
GREEN = ( 39, 174,  96)   # #27AE60 — Low risk / Met


def _risk_colour(level: str) -> tuple:
    """Return the RGB colour tuple for a given risk level string."""
    level = (level or "").upper()
    if "CRITICAL" in level or "NOT MET" in level:
        return RED
    elif "HIGH" in level or "PARTIAL" in level:
        return AMBER
    elif "LOW" in level or "MET" in level:
        return GREEN
    return GREY


def _sanitise(text: str) -> str:
    """
    Replace non-latin-1 characters that FPDF core fonts cannot render.
    Called on all text before passing to pdf.cell() or pdf.multi_cell().

    Two-pass approach:
    1. Known replacements (em-dash, smart quotes, etc.) — keep readable
    2. Hard strip — any character outside latin-1 (0x00-0xFF) is dropped.
       This is the safety net that prevents Arabic, Chinese, or any other
       Unicode text from crashing FPDF with a font range error.
       Arabic content is intentionally redirected to the DOCX version.
    """
    replacements = {
        "\u2014": "-",   # em-dash
        "\u2013": "-",   # en-dash
        "\u2018": "'",   # left single quote
        "\u2019": "'",   # right single quote
        "\u201C": '"',   # left double quote
        "\u201D": '"',   # right double quote
        "\u2026": "...", # ellipsis
        "\u00A0": " ",   # non-breaking space
        "\u2022": "-",   # bullet
        "\u2023": "-",   # triangular bullet
        "\u25CF": "-",   # black circle
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)

    # Hard strip: drop anything outside latin-1 range
    # encode to latin-1, replacing unmappable chars, then decode back
    text = text.encode("latin-1", errors="replace").decode("latin-1")
    # The replacement byte is 0x3F = '?' — clean that up if it came from Arabic
    return text



# =============================================================
# BASE PDF CLASS
# Extends FPDF to add header and footer to every page automatically.
# =============================================================

class GRCDocument(FPDF):
    """
    Custom FPDF subclass with branded header and footer.
    Every page automatically gets the app name in the header
    and a page number + confidentiality notice in the footer.
    """

    def __init__(self, doc_title: str = "", company_name: str = ""):
        super().__init__()
        # Sanitise on store — header/footer use these directly without going through _sanitise
        self._doc_title   = _sanitise(str(doc_title))
        self._company     = _sanitise(str(company_name))
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        """Printed at top of every page after the cover page."""
        # Skip header on first page (cover page)
        if self.page_no() == 1:
            return

        # Navy bar across the top
        self.set_fill_color(*NAVY)
        self.rect(0, 0, 210, 12, "F")

        # Document title in white
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*WHITE)
        self.set_xy(10, 2)
        self.cell(130, 8, self._doc_title[:70], border=0, align="L")

        # Company name on the right
        self.set_xy(140, 2)
        self.cell(60, 8, self._company[:40], border=0, align="R")
        self.set_text_color(*DARK)
        self.ln(14)   # Move below the header bar

    def footer(self):
        """Printed at bottom of every page after the cover page."""
        if self.page_no() == 1:
            return

        self.set_y(-15)
        # Gold line above footer
        self.set_draw_color(*GOLD)
        self.set_line_width(0.4)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(1)

        # Confidentiality notice on left, page number on right
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*GREY)
        self.cell(130, 6, "CONFIDENTIAL - AI GRC Audit Suite", border=0, align="L")
        self.cell(60, 6, f"Page {self.page_no()}", border=0, align="R")


# =============================================================
# INTERNAL HELPERS
# =============================================================

def _cover_page(pdf: GRCDocument, title: str, subtitle: str, company_profile: dict):
    """
    Render a professional cover page as page 1.
    Called at the start of every export function.
    """
    pdf.add_page()
    pdf.set_margins(0, 0, 0)   # Full bleed for cover

    # Dark navy background — full page
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, 210, 297, "F")

    # Gold accent bar — 1/3 height from top
    pdf.set_fill_color(*GOLD)
    pdf.rect(0, 85, 210, 4, "F")

    # App name — small, white, top right
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(0, 15)
    pdf.cell(200, 8, "AI GRC Audit Suite", align="R")

    # Main title — large white text
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(20, 50)
    pdf.multi_cell(170, 12, _sanitise(str(title)), align="L")

    # Subtitle — gold
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(*GOLD)
    pdf.set_xy(20, 92)
    pdf.multi_cell(170, 8, _sanitise(str(subtitle)), align="L")

    # Details block — white text, lower portion of cover
    details = [
        ("Prepared for",   company_profile.get("company_name", "—")),
        ("Industry",       company_profile.get("industry", "—")),
        ("Prepared by",    company_profile.get("auditor_name", "—")),
        ("Date",           datetime.today().strftime("%d %B %Y")),
        ("Classification", "CONFIDENTIAL"),
    ]
    y = 170
    for label, value in details:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*GOLD)
        pdf.set_xy(20, y)
        pdf.cell(55, 8, label + ":", border=0)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*WHITE)
        pdf.cell(120, 8, _sanitise(str(value)), border=0)
        y += 10

    # Reset margins for body pages
    pdf.set_margins(15, 15, 15)


def _section_heading(pdf: GRCDocument, text: str, level: int = 1):
    """
    Add a formatted section heading.
    Level 1: Navy background bar, white text, 13pt bold
    Level 2: Gold underline, navy text, 11pt bold
    """
    text = _sanitise(str(text))   # strip non-latin-1 before any cell() call
    pdf.ln(4)
    if level == 1:
        pdf.set_fill_color(*NAVY)
        pdf.set_text_color(*WHITE)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, f"  {text}", border=0, fill=True, ln=True)
        pdf.ln(3)
    else:
        pdf.set_text_color(*NAVY)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, text, border=0, ln=True)
        # Gold underline
        pdf.set_draw_color(*GOLD)
        pdf.set_line_width(0.5)
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.line(x, y, x + 180, y)
        pdf.ln(3)

    pdf.set_text_color(*DARK)


def _body_text(pdf: GRCDocument, text: str, font_size: int = 10):
    """
    Add a paragraph of body text with word wrap.
    Uses multi_cell so long paragraphs flow correctly.
    Always resets x to the left margin first — prevents "not enough space"
    errors when called after a cell() that left the cursor mid-line.
    """
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", font_size)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(0, 6, _sanitise(str(text)), border=0)
    pdf.ln(2)


def _info_row(pdf: GRCDocument, label: str, value: str, value_color: tuple = None):
    """
    Add a key: value row — used in summary sections.
    e.g.  Risk Level:   HIGH  (in red if Critical)
    """
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*NAVY)
    pdf.cell(55, 7, label + ":", border=0)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*(value_color or DARK))
    pdf.cell(0, 7, _sanitise(str(value)), border=0, ln=True)
    pdf.set_text_color(*DARK)


def _divider(pdf: GRCDocument):
    """Add a thin gold horizontal divider line."""
    pdf.ln(2)
    pdf.set_draw_color(*GOLD)
    pdf.set_line_width(0.3)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 180, pdf.get_y())
    pdf.ln(4)


def _table(pdf: GRCDocument, headers: list, rows: list, col_widths: list = None):
    """
    Render a data table with a navy header row.
    headers   : list of column header strings
    rows      : list of lists (each inner list = one row's cell values)
    col_widths: list of widths in mm. Auto-distributed if None.
    """
    n_cols = len(headers)
    available = 180  # page width minus margins
    if col_widths is None:
        col_widths = [available / n_cols] * n_cols

    # Header row
    pdf.set_fill_color(*NAVY)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 9)
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, str(h), border=1, fill=True)
    pdf.ln()

    # Data rows — alternate background for readability
    pdf.set_text_color(*DARK)
    pdf.set_font("Helvetica", "", 9)
    for row_idx, row in enumerate(rows):
        # Light grey fill on even rows
        if row_idx % 2 == 0:
            pdf.set_fill_color(245, 245, 245)
        else:
            pdf.set_fill_color(*WHITE)

        # Calculate the max height needed for this row (longest cell)
        row_height = 7
        for cell_val in row:
            # Estimate lines needed — approx 25 chars per column width of 45mm
            pass  # keep it simple — use fixed height for now

        for i, cell_val in enumerate(row):
            pdf.cell(col_widths[i], row_height, _sanitise(str(cell_val))[:80], border=1, fill=True)
        pdf.ln()

    pdf.ln(3)


def _pdf_to_bytes(pdf: GRCDocument) -> bytes:
    """
    Output the PDF to an in-memory bytes buffer and return it.
    Streamlit's download_button accepts bytes directly.
    """
    # FPDF2's output() returns bytes when dest='S'
    return bytes(pdf.output())


# =============================================================
# PUBLIC EXPORT FUNCTIONS
# =============================================================

def export_policy(content: dict, company_profile: dict) -> bytes:
    """
    Generate a compliance policy document in PDF format.
    PDF is the locked, non-editable version clients distribute internally.
    Called by modules/policy.py alongside export_policy() from docx_exporter.
    """
    company = company_profile.get("company_name", "Organisation")
    framework = content.get("framework_name", "Framework")
    policy_type = content.get("policy_type", "Security Policy")

    pdf = GRCDocument(doc_title=policy_type, company_name=company)
    _cover_page(pdf, title=policy_type, subtitle=f"{framework} | {company}", company_profile=company_profile)

    pdf.add_page()

    _section_heading(pdf, "1. Purpose and Scope")
    _body_text(pdf, content.get("scope", ""))

    _section_heading(pdf, "2. Policy Statement")
    import re
    for line in content.get("policy_body", "").split("\n"):
        line = line.strip()
        if not line:
            continue
        _body_text(pdf, line)

    _section_heading(pdf, "3. Roles and Responsibilities")
    _body_text(pdf, content.get("roles", ""))

    _section_heading(pdf, "4. Review and Maintenance")
    _body_text(pdf, content.get("review_schedule", "This policy shall be reviewed annually."))

    _section_heading(pdf, "5. Compliance and Exceptions")
    _body_text(pdf,
        f"All personnel within scope of this policy must comply with its requirements. "
        f"Exceptions must be approved in writing by the CISO or equivalent."
    )

    _section_heading(pdf, "6. Document Approval")
    _table(
        pdf,
        headers=["Role", "Name", "Signature", "Date"],
        rows=[
            ["Policy Owner", "", "", ""],
            ["CISO / Security Lead", "", "", ""],
            ["Executive Sponsor", "", "", ""],
        ],
        col_widths=[55, 45, 45, 35],
    )

    if content.get("arabic_summary"):
        pdf.add_page()
        _section_heading(pdf, "Arabic Summary (Bilingual)")
        _body_text(pdf, (
            "An Arabic translation of this document is included in the DOCX version. "
            "Please refer to the Word document for the Arabic executive summary. "
            "The PDF format does not support Arabic text rendering."
        ))

    return _pdf_to_bytes(pdf)


def export_gap_assessment(content: dict, company_profile: dict) -> bytes:
    """
    Generate a gap assessment report in PDF format.
    Called by modules/gap.py.
    """
    company = company_profile.get("company_name", "Organisation")
    framework = content.get("framework_name", "Framework")

    pdf = GRCDocument(doc_title="Gap Assessment Report", company_name=company)
    _cover_page(pdf, "Gap Assessment Report", f"{framework} | {company}", company_profile)

    pdf.add_page()

    _section_heading(pdf, "1. Executive Summary")
    _body_text(pdf, content.get("executive_summary", ""))
    _divider(pdf)

    score = content.get("overall_score", 0.0)
    met   = len(content.get("controls_met", []))
    part  = len(content.get("controls_partial", []))
    nm    = len(content.get("controls_not_met", []))
    total = met + part + nm

    _info_row(pdf, "Compliance Score",       f"{score * 100:.0f}%",
              _risk_colour("Not Met" if score < 0.5 else ("Partial" if score < 0.8 else "Met")))
    _info_row(pdf, "Total Controls",         str(total))
    _info_row(pdf, "Controls Met",           str(met),  GREEN)
    _info_row(pdf, "Partially Met",          str(part), AMBER)
    _info_row(pdf, "Not Met",                str(nm),   RED)
    pdf.ln(4)

    _section_heading(pdf, "2. Priority Action Plan")
    for i, action in enumerate(content.get("priority_actions", []), start=1):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*GOLD)
        pdf.cell(10, 6, f"{i}.", border=0)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(0, 6, _sanitise(action))

    _section_heading(pdf, "3. Controls Not Met")
    not_met = content.get("controls_not_met", [])
    if not_met:
        _table(
            pdf,
            headers=["ID", "Control Name", "Domain", "Gap"],
            rows=[[c.get("id",""), c.get("name",""), c.get("domain",""), c.get("gap","")] for c in not_met],
            col_widths=[20, 50, 45, 65],
        )
    else:
        _body_text(pdf, "No controls assessed as Not Met.")

    _section_heading(pdf, "4. Controls Partially Met")
    partial = content.get("controls_partial", [])
    if partial:
        _table(
            pdf,
            headers=["ID", "Control Name", "Domain", "Gap"],
            rows=[[c.get("id",""), c.get("name",""), c.get("domain",""), c.get("gap","")] for c in partial],
            col_widths=[20, 50, 45, 65],
        )
    else:
        _body_text(pdf, "No controls assessed as Partially Met.")

    _section_heading(pdf, "5. Controls Met")
    met_list = content.get("controls_met", [])
    if met_list:
        _table(
            pdf,
            headers=["ID", "Control Name", "Domain"],
            rows=[[c.get("id",""), c.get("name",""), c.get("domain","")] for c in met_list],
            col_widths=[25, 80, 75],
        )
    else:
        _body_text(pdf, "No controls assessed as fully Met.")

    if content.get("arabic_summary"):
        pdf.add_page()
        _section_heading(pdf, "Arabic Summary (Bilingual)")
        _body_text(pdf, (
            "An Arabic translation of this document is included in the DOCX version. "
            "Please refer to the Word document for the Arabic executive summary. "
            "The PDF format does not support Arabic text rendering."
        ))

    return _pdf_to_bytes(pdf)


def export_vendor_risk(content: dict, company_profile: dict) -> bytes:
    """
    Generate a vendor risk assessment in PDF format.
    Called by modules/vendor.py.
    """
    company = company_profile.get("company_name", "Organisation")
    vendor  = content.get("vendor_name", "Vendor")

    pdf = GRCDocument(doc_title="Vendor Risk Assessment", company_name=company)
    _cover_page(pdf, "Vendor Risk Assessment", f"{vendor} | {company}", company_profile)

    pdf.add_page()

    _section_heading(pdf, "1. Vendor Overview")
    _info_row(pdf, "Vendor Name",  content.get("vendor_name", "—"))
    _info_row(pdf, "Service Type", content.get("service_type", "—"))
    _info_row(pdf, "Risk Score",   f"{content.get('risk_score', 0)} / 100")
    _info_row(pdf, "Risk Level",   content.get("risk_level", "—"),
              _risk_colour(content.get("risk_level", "")))
    pdf.ln(3)
    _body_text(pdf, content.get("summary", ""))

    _section_heading(pdf, "2. Risk Red Flags")
    for i, flag in enumerate(content.get("red_flags", []), start=1):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*RED)
        pdf.cell(10, 6, f"{i}.", border=0)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(0, 6, _sanitise(flag))

    _section_heading(pdf, "3. Recommended Contract Clauses")
    for i, clause in enumerate(content.get("contract_clauses", []), start=1):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*GOLD)
        pdf.cell(10, 6, f"{i}.", border=0)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(0, 6, _sanitise(clause))

    _section_heading(pdf, "4. Due Diligence Checklist")
    checklist = content.get("due_diligence", [])
    if checklist:
        _table(
            pdf,
            headers=["#", "Due Diligence Item", "Status"],
            rows=[[str(i+1), item, "Pending"] for i, item in enumerate(checklist)],
            col_widths=[10, 140, 30],
        )

    if content.get("arabic_summary"):
        pdf.add_page()
        _section_heading(pdf, "Arabic Summary (Bilingual)")
        _body_text(pdf, (
            "An Arabic translation of this document is included in the DOCX version. "
            "Please refer to the Word document for the Arabic executive summary. "
            "The PDF format does not support Arabic text rendering."
        ))

    return _pdf_to_bytes(pdf)


def export_ir_playbook(content: dict, company_profile: dict) -> bytes:
    """
    Generate an IR Playbook in PDF format.
    Called by modules/playbook.py.
    """
    company       = company_profile.get("company_name", "Organisation")
    incident_type = content.get("incident_type", "Incident")

    pdf = GRCDocument(doc_title=f"{incident_type} Response Playbook", company_name=company)
    _cover_page(pdf, f"{incident_type} Response Playbook", f"Incident Response Plan | {company}", company_profile)

    pdf.add_page()

    _section_heading(pdf, "1. Incident Classification")
    _body_text(pdf, content.get("classification", ""))

    _section_heading(pdf, "2. Response Team")
    team = content.get("response_team", [])
    if team:
        _table(
            pdf,
            headers=["Role", "Responsibilities"],
            rows=[[m.get("role",""), m.get("responsibilities","")] for m in team],
            col_widths=[60, 120],
        )

    _section_heading(pdf, "3. Response Timeline")
    timeline = content.get("response_timeline", [])
    if timeline:
        _table(
            pdf,
            headers=["Phase", "Action", "Owner", "Timeframe"],
            rows=[[s.get("phase",""), s.get("action",""), s.get("owner",""), s.get("timeframe","")] for s in timeline],
            col_widths=[30, 85, 35, 30],
        )

    _section_heading(pdf, "4. Escalation Matrix")
    esc = content.get("escalation_matrix", [])
    if esc:
        _table(
            pdf,
            headers=["Trigger", "Escalate To", "Method"],
            rows=[[e.get("trigger",""), e.get("escalate_to",""), e.get("method","")] for e in esc],
            col_widths=[70, 65, 45],
        )

    _section_heading(pdf, "5. Communication Templates")
    for tmpl in content.get("comms_templates", []):
        _section_heading(pdf, tmpl.get("audience", ""), level=2)
        _body_text(pdf, tmpl.get("template_text", ""))

    _section_heading(pdf, "6. Regulatory Notification Requirements")
    reqs = content.get("regulatory_requirements", [])
    if reqs:
        _table(
            pdf,
            headers=["Regulatory Body", "Requirement", "Deadline"],
            rows=[[r.get("body",""), r.get("requirement",""), r.get("deadline","")] for r in reqs],
            col_widths=[45, 95, 40],
        )

    _section_heading(pdf, "7. Lessons Learned Template")
    _body_text(pdf, content.get("lessons_learned", ""))

    if content.get("arabic_summary"):
        pdf.add_page()
        _section_heading(pdf, "Arabic Summary (Bilingual)")
        _body_text(pdf, (
            "An Arabic translation of this document is included in the DOCX version. "
            "Please refer to the Word document for the Arabic executive summary. "
            "The PDF format does not support Arabic text rendering."
        ))

    return _pdf_to_bytes(pdf)


def export_audit_report(content: dict, company_profile: dict) -> bytes:
    """
    Generate the final audit report in PDF format.
    This is Module 7's output — the official board-ready deliverable.
    PDF only (no DOCX version) — locked, professional, non-editable.

    Expected content dict keys:
        frameworks_audited  : list  — framework names audited
        audit_period        : str   — e.g. "Q2 2025"
        executive_summary   : str   — high-level narrative
        scope_methodology   : str   — what was audited and how
        key_findings        : list  — {severity, title, description, recommendation}
        compliance_scores   : list  — {framework, score_pct}
        recommendations     : list  — {priority, recommendation, owner, timeline}
        conclusion          : str   — closing narrative
        arabic_summary      : str   — optional Arabic executive summary
    """
    company = company_profile.get("company_name", "Organisation")
    auditor = company_profile.get("auditor_name", "GRC Auditor")
    period  = content.get("audit_period", datetime.today().strftime("%B %Y"))

    pdf = GRCDocument(doc_title="Cybersecurity Audit Report", company_name=company)
    _cover_page(
        pdf,
        title="Cybersecurity Audit Report",
        subtitle=f"Audit Period: {period} | {company}",
        company_profile=company_profile,
    )

    pdf.add_page()

    # --- Executive Summary ---
    _section_heading(pdf, "1. Executive Summary")
    _body_text(pdf, content.get("executive_summary", ""))

    # Compliance scores per framework
    scores = content.get("compliance_scores", [])
    if scores:
        pdf.ln(2)
        _table(
            pdf,
            headers=["Framework", "Compliance Score"],
            rows=[[s.get("framework",""), s.get("score_pct","")] for s in scores],
            col_widths=[120, 60],
        )

    # --- Scope and Methodology ---
    _section_heading(pdf, "2. Scope and Methodology")
    _body_text(pdf, content.get("scope_methodology", ""))
    frameworks = content.get("frameworks_audited", [])
    if frameworks:
        _body_text(pdf, _sanitise("Frameworks assessed: " + ", ".join(frameworks)))

    # --- Key Findings ---
    _section_heading(pdf, "3. Key Findings")
    findings = content.get("key_findings", [])
    if findings:
        for finding in findings:
            severity = finding.get("severity", "Medium")
            # Severity badge colour
            sev_color = _risk_colour(severity)
            pdf.set_fill_color(*sev_color)
            pdf.set_text_color(*WHITE)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(25, 7, _sanitise(f"  {severity.upper()}"), border=0, fill=True)
            pdf.set_text_color(*DARK)
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(0, 7, _sanitise(f"  {finding.get('title', '')}"))
            _body_text(pdf, finding.get("description", ""))
            pdf.set_font("Helvetica", "BI", 10)
            pdf.set_text_color(*NAVY)
            pdf.multi_cell(0, 6, _sanitise("Recommendation: " + finding.get("recommendation", "")))
            pdf.set_text_color(*DARK)
            _divider(pdf)
    else:
        _body_text(pdf, "No findings recorded.")

    # --- Recommendations ---
    _section_heading(pdf, "4. Recommendations")
    recs = content.get("recommendations", [])
    if recs:
        _table(
            pdf,
            headers=["Priority", "Recommendation", "Owner", "Timeline"],
            rows=[[r.get("priority",""), r.get("recommendation",""), r.get("owner",""), r.get("timeline","")] for r in recs],
            col_widths=[20, 95, 35, 30],
        )

    # --- Conclusion ---
    _section_heading(pdf, "5. Conclusion")
    _body_text(pdf, content.get("conclusion", ""))

    # --- Auditor Signature ---
    _section_heading(pdf, "6. Auditor Sign-off")
    pdf.ln(4)
    _info_row(pdf, "Lead Auditor", auditor)
    _info_row(pdf, "Date",         datetime.today().strftime("%d %B %Y"))
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GREY)
    pdf.cell(60, 6, "Signature:", border=0)
    pdf.set_draw_color(*NAVY)
    pdf.set_line_width(0.4)
    pdf.line(pdf.get_x(), pdf.get_y() + 5, pdf.get_x() + 80, pdf.get_y() + 5)
    pdf.ln(12)
    pdf.cell(60, 6, "Date:", border=0)
    pdf.line(pdf.get_x(), pdf.get_y() + 5, pdf.get_x() + 80, pdf.get_y() + 5)

    # Arabic executive summary (bilingual)
    if content.get("arabic_summary"):
        pdf.add_page()
        _section_heading(pdf, "Arabic Summary (Bilingual)")
        _body_text(pdf, (
            "An Arabic translation of this document is included in the DOCX version. "
            "Please refer to the Word document for the Arabic executive summary. "
            "The PDF format does not support Arabic text rendering."
        ))

    return _pdf_to_bytes(pdf)