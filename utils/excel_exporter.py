"""
utils/excel_exporter.py — AI GRC Audit Suite
===============================================
Excel document generation for Module 2 (Risk Register) and Module 3 (Audit Checklist).

All Excel exports go through here. Modules never call openpyxl or pandas directly.

Why Excel for these two modules:
- Risk registers are living documents — clients update them throughout the year
- Audit checklists are filled in during the engagement — auditors need to type into cells
- Both need colour-coded risk levels that Excel handles better than PDF/DOCX

Design decisions:
- Uses openpyxl directly (not pandas) for full formatting control
- Frozen header row on every sheet so columns stay visible when scrolling
- Conditional formatting colours cells by risk level / compliance status
- Auto-fitted column widths based on content length
- Returns bytes for Streamlit's st.download_button()

Functions:
    export_risk_register(rows, company_profile)   → bytes  (Module 2)
    export_audit_checklist(rows, company_profile) → bytes  (Module 3)
"""

import io
from datetime import datetime

import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, GradientFill
)
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo


# =============================================================
# COLOUR PALETTE — hex strings for openpyxl fills
# =============================================================

NAVY_HEX   = "1A375E"   # Header background
GOLD_HEX   = "C89A1A"   # Accent colour
WHITE_HEX  = "FFFFFF"
DARK_HEX   = "1F1F1F"
GREY_HEX   = "F2F2F2"   # Alternating row fill

# Risk level colours
CRITICAL_BG = "C0392B"   # Red
CRITICAL_FG = "FFFFFF"
HIGH_BG     = "E67E22"   # Orange
HIGH_FG     = "FFFFFF"
MEDIUM_BG   = "F1C40F"   # Yellow
MEDIUM_FG   = "1F1F1F"
LOW_BG      = "27AE60"   # Green
LOW_FG      = "FFFFFF"

# Compliance status colours
MET_BG      = "27AE60"   # Green
MET_FG      = "FFFFFF"
PARTIAL_BG  = "F39C12"   # Amber
PARTIAL_FG  = "FFFFFF"
NOT_MET_BG  = "C0392B"   # Red
NOT_MET_FG  = "FFFFFF"
NA_BG       = "95A5A6"   # Grey
NA_FG       = "FFFFFF"


# =============================================================
# INTERNAL HELPERS
# =============================================================

def _make_fill(hex_color: str) -> PatternFill:
    """Create a solid fill with the given hex colour string."""
    return PatternFill(fill_type="solid", fgColor=hex_color)


def _make_font(bold: bool = False, color: str = DARK_HEX, size: int = 10) -> Font:
    """Create a font with the given properties."""
    return Font(name="Calibri", bold=bold, color=color, size=size)


def _make_border(style: str = "thin") -> Border:
    """Create a full border (all 4 sides) with the given line style."""
    side = Side(style=style, color="CCCCCC")
    return Border(left=side, right=side, top=side, bottom=side)


def _make_alignment(wrap: bool = True, horizontal: str = "left") -> Alignment:
    """Create an alignment object — wrap text on by default."""
    return Alignment(wrap_text=wrap, vertical="top", horizontal=horizontal)


def _style_header_cell(cell, text: str):
    """
    Apply the standard navy header style to a cell and set its value.
    Used for the first (header) row of every sheet.
    """
    cell.value = text
    cell.font      = _make_font(bold=True, color=WHITE_HEX, size=10)
    cell.fill      = _make_fill(NAVY_HEX)
    cell.alignment = _make_alignment(wrap=False, horizontal="center")
    cell.border    = _make_border()


def _style_data_cell(cell, value, row_even: bool = False):
    """
    Apply standard data cell styling and set the value.
    Alternates background between white and light grey for readability.
    """
    cell.value     = value
    cell.font      = _make_font()
    cell.fill      = _make_fill(GREY_HEX if row_even else WHITE_HEX)
    cell.alignment = _make_alignment()
    cell.border    = _make_border()


def _colour_risk_cell(cell, risk_level: str):
    """
    Apply colour-coded fill to a risk level cell based on its value.
    Critical=Red, High=Orange, Medium=Yellow, Low=Green.
    Called for the Risk Level column in the risk register.
    """
    level = (risk_level or "").upper()
    if "CRITICAL" in level:
        cell.fill = _make_fill(CRITICAL_BG)
        cell.font = _make_font(bold=True, color=CRITICAL_FG)
    elif "HIGH" in level:
        cell.fill = _make_fill(HIGH_BG)
        cell.font = _make_font(bold=True, color=HIGH_FG)
    elif "MEDIUM" in level:
        cell.fill = _make_fill(MEDIUM_BG)
        cell.font = _make_font(bold=True, color=MEDIUM_FG)
    elif "LOW" in level:
        cell.fill = _make_fill(LOW_BG)
        cell.font = _make_font(bold=True, color=LOW_FG)
    cell.alignment = _make_alignment(horizontal="center")
    cell.border    = _make_border()


def _colour_compliance_cell(cell, status: str):
    """
    Apply colour-coded fill to a compliance status cell.
    Yes/Met=Green, Partial=Amber, No/Not Met=Red, NA=Grey.
    Called for the Compliant column in the audit checklist.
    """
    s = (status or "").upper()
    if s in ("YES", "MET", "COMPLIANT"):
        cell.fill = _make_fill(MET_BG)
        cell.font = _make_font(bold=True, color=MET_FG)
    elif "PARTIAL" in s:
        cell.fill = _make_fill(PARTIAL_BG)
        cell.font = _make_font(bold=True, color=PARTIAL_FG)
    elif s in ("NO", "NOT MET", "NON-COMPLIANT"):
        cell.fill = _make_fill(NOT_MET_BG)
        cell.font = _make_font(bold=True, color=NOT_MET_FG)
    else:  # N/A or empty
        cell.fill = _make_fill(NA_BG)
        cell.font = _make_font(bold=True, color=NA_FG)
    cell.alignment = _make_alignment(horizontal="center")
    cell.border    = _make_border()


def _autofit_columns(ws, min_width: int = 12, max_width: int = 50):
    """
    Set each column width based on the maximum content length in that column.
    openpyxl doesn't have true auto-fit — we approximate it by measuring
    the longest string in each column and adding padding.
    """
    for col_cells in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col_cells[0].column)
        for cell in col_cells:
            try:
                cell_len = len(str(cell.value or ""))
                if cell_len > max_len:
                    max_len = cell_len
            except Exception:
                pass
        # Approximate character-to-column-width ratio is ~1.2
        width = min(max(max_len * 1.2, min_width), max_width)
        ws.column_dimensions[col_letter].width = width


def _add_cover_sheet(wb: openpyxl.Workbook, doc_type: str, company_profile: dict):
    """
    Add a professional cover sheet as the first sheet of the workbook.
    Contains document title, company info, and instructions.
    """
    ws = wb.create_sheet("Cover", 0)

    # Set column widths for the cover layout
    ws.column_dimensions["A"].width = 25
    ws.column_dimensions["B"].width = 45

    # Title block
    ws.row_dimensions[1].height = 8   # spacer
    ws.row_dimensions[2].height = 40
    ws.row_dimensions[3].height = 24
    ws.row_dimensions[4].height = 8   # spacer

    # Main title in cell B2
    title_cell = ws["B2"]
    title_cell.value = doc_type
    title_cell.font  = Font(name="Calibri", bold=True, size=22, color=NAVY_HEX)
    title_cell.alignment = Alignment(vertical="center")

    # Subtitle in B3
    sub_cell = ws["B3"]
    sub_cell.value = "AI GRC Audit Suite — Saudi Arabia Compliance Toolkit"
    sub_cell.font  = Font(name="Calibri", size=12, color=GOLD_HEX)

    # Details section starting at row 6
    details = [
        ("Prepared for",  company_profile.get("company_name", "—")),
        ("Industry",      company_profile.get("industry", "—")),
        ("Auditor",       company_profile.get("auditor_name", "—")),
        ("Date",          datetime.today().strftime("%d %B %Y")),
        ("Version",       "1.0"),
        ("Classification","CONFIDENTIAL"),
    ]

    for i, (label, value) in enumerate(details, start=6):
        label_cell = ws.cell(row=i, column=1, value=label)
        label_cell.font = Font(name="Calibri", bold=True, size=11, color=NAVY_HEX)
        label_cell.alignment = Alignment(horizontal="right", vertical="center")

        value_cell = ws.cell(row=i, column=2, value=value)
        value_cell.font = Font(name="Calibri", size=11, color=DARK_HEX)
        value_cell.alignment = Alignment(horizontal="left", vertical="center")

        ws.row_dimensions[i].height = 20

    # Instructions at row 14
    ws.cell(row=14, column=1, value="Instructions").font = Font(
        name="Calibri", bold=True, size=11, color=NAVY_HEX
    )
    instructions = (
        "Use the tabs below to access the document. "
        "Colour-coded cells update automatically based on your entries. "
        "Save a copy before editing."
    )
    inst_cell = ws.cell(row=15, column=1, value=instructions)
    inst_cell.font = Font(name="Calibri", size=10, color=GREY_HEX.replace("F2", "55"))
    inst_cell.alignment = Alignment(wrap_text=True)
    ws.merge_cells("A15:C18")
    ws.row_dimensions[15].height = 55


def _wb_to_bytes(wb: openpyxl.Workbook) -> bytes:
    """
    Save the workbook to an in-memory bytes buffer and return it.
    Streamlit's download_button() accepts bytes directly.
    """
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.read()


# =============================================================
# PUBLIC EXPORT FUNCTIONS
# =============================================================

def export_risk_register(rows: list, company_profile: dict) -> bytes:
    """
    Generate a Risk Register Excel file for Module 2.

    Args:
        rows            : List of dicts from the LLM, each representing one risk.
                          Keys: asset_id, asset_name, asset_type, threat, vulnerability,
                                likelihood, impact, risk_rating, risk_level,
                                recommended_control, control_reference,
                                control_owner, target_date, status
        company_profile : Dict with company_name, industry, auditor_name, etc.

    Returns:
        bytes — ready for st.download_button()
    """
    wb = openpyxl.Workbook()

    # Add cover sheet first
    _add_cover_sheet(wb, "Risk Register", company_profile)

    # Create the main data sheet
    ws = wb.create_sheet("Risk Register")

    # --- Column definitions ---
    # Each tuple: (header text, dict key, column width hint)
    columns = [
        ("Asset ID",             "asset_id",             12),
        ("Asset Name",           "asset_name",           22),
        ("Asset Type",           "asset_type",           16),
        ("Threat",               "threat",               30),
        ("Vulnerability",        "vulnerability",        30),
        ("Likelihood (1-5)",     "likelihood",           16),
        ("Impact (1-5)",         "impact",               14),
        ("Risk Rating",          "risk_rating",          14),
        ("Risk Level",           "risk_level",           14),
        ("Recommended Control",  "recommended_control",  35),
        ("Control Reference",    "control_reference",    20),
        ("Control Owner",        "control_owner",        20),
        ("Target Date",          "target_date",          16),
        ("Status",               "status",               16),
    ]

    # Write header row
    for col_idx, (header, _, _) in enumerate(columns, start=1):
        _style_header_cell(ws.cell(row=1, column=col_idx), header)

    # Set column widths from the hints above
    for col_idx, (_, _, width) in enumerate(columns, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Freeze the header row so it stays visible when scrolling down
    ws.freeze_panes = "A2"

    # Write data rows
    for row_idx, risk in enumerate(rows, start=2):
        is_even = (row_idx % 2 == 0)

        for col_idx, (_, key, _) in enumerate(columns, start=1):
            cell = ws.cell(row=row_idx, column=col_idx)
            value = risk.get(key, "")

            if key == "risk_level":
                # Risk Level column gets colour-coded fill
                cell.value = value
                _colour_risk_cell(cell, str(value))
            elif key in ("likelihood", "impact", "risk_rating"):
                # Numeric columns — centre-aligned
                cell.value = value
                cell.font      = _make_font()
                cell.fill      = _make_fill(GREY_HEX if is_even else WHITE_HEX)
                cell.alignment = _make_alignment(horizontal="center")
                cell.border    = _make_border()
            else:
                _style_data_cell(cell, value, row_even=is_even)

        # Set row height to allow text wrapping
        ws.row_dimensions[row_idx].height = 40

    # Add an empty placeholder row if no data provided
    if not rows:
        for col_idx in range(1, len(columns) + 1):
            _style_data_cell(ws.cell(row=2, column=col_idx), "", row_even=False)
        ws.row_dimensions[2].height = 40

    # Remove the default empty sheet openpyxl creates
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    return _wb_to_bytes(wb)


def export_audit_checklist(rows: list, company_profile: dict) -> bytes:
    """
    Generate an Audit Checklist Excel file for Module 3.

    Args:
        rows            : List of dicts from the LLM, each representing one control.
                          Keys: control_id, control_name, control_description,
                                evidence_required, responsible_owner, audit_method,
                                compliant, evidence_reference, auditor_notes, finding
        company_profile : Dict with company_name, industry, auditor_name, etc.

    Returns:
        bytes — ready for st.download_button()
    """
    wb = openpyxl.Workbook()

    # Cover sheet
    _add_cover_sheet(wb, "Audit Checklist", company_profile)

    # Main data sheet
    ws = wb.create_sheet("Audit Checklist")

    # --- Column definitions ---
    columns = [
        ("Control ID",          "control_id",          14),
        ("Control Name",        "control_name",        28),
        ("Control Description", "control_description", 40),
        ("Evidence Required",   "evidence_required",   35),
        ("Responsible Owner",   "responsible_owner",   22),
        ("Audit Method",        "audit_method",        28),
        ("Compliant",           "compliant",           14),
        ("Evidence Reference",  "evidence_reference",  28),
        ("Auditor Notes",       "auditor_notes",       35),
        ("Finding",             "finding",             35),
    ]

    # Header row
    for col_idx, (header, _, _) in enumerate(columns, start=1):
        _style_header_cell(ws.cell(row=1, column=col_idx), header)

    # Column widths
    for col_idx, (_, _, width) in enumerate(columns, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Freeze header
    ws.freeze_panes = "A2"

    # Data rows
    for row_idx, control in enumerate(rows, start=2):
        is_even = (row_idx % 2 == 0)

        for col_idx, (_, key, _) in enumerate(columns, start=1):
            cell = ws.cell(row=row_idx, column=col_idx)
            value = control.get(key, "")

            if key == "compliant":
                # Compliance status gets colour-coded fill
                cell.value = value
                _colour_compliance_cell(cell, str(value))
            else:
                _style_data_cell(cell, value, row_even=is_even)

        ws.row_dimensions[row_idx].height = 50

    # Placeholder if no data
    if not rows:
        for col_idx in range(1, len(columns) + 1):
            _style_data_cell(ws.cell(row=2, column=col_idx), "", row_even=False)
        ws.row_dimensions[2].height = 50

    # Remove default empty sheet
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    return _wb_to_bytes(wb)
