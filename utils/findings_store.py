"""
utils/findings_store.py — AI GRC Audit Suite
==============================================
Shared findings store — passes findings between modules via session state.

Each module (2-6) writes its key findings here after generation.
Module 7 reads everything and pre-fills the findings textarea automatically.

Why session state:
- Streamlit re-runs the whole script on every interaction
- session_state is the only way to share data between tabs/modules
- No file I/O needed — lives purely in memory for the session

Data format stored under st.session_state["module_findings"]:
    List of dicts:
    {
        "source":         "Module 2 — Risk Register",
        "severity":       "High",
        "title":          "Finding title",
        "description":    "What was found.",
        "recommendation": "What to do about it.",
    }

Public functions:
    add_finding(source, severity, title, description, recommendation)
    get_all_findings()         → list of finding dicts
    format_for_module7()       → pre-formatted string for Module 7 textarea
    clear_findings()
    get_findings_count()       → int
"""

import streamlit as st

# Session state key — shared across all modules
_STATE_KEY = "module_findings"

# Valid severity levels
SEVERITIES = ["Critical", "High", "Medium", "Low", "Informational"]


def add_finding(
    source: str,
    severity: str,
    title: str,
    description: str,
    recommendation: str,
) -> None:
    """
    Add a single finding to the shared store.

    Called by Modules 2-6 whenever they generate results that
    represent audit findings worth carrying into the final report.

    Args:
        source         : Which module produced this — e.g. "Module 2 — Risk Register"
        severity       : One of Critical / High / Medium / Low / Informational
        title          : Short finding title — e.g. "Critical Risk: Ransomware Exposure"
        description    : What was found and why it matters
        recommendation : Specific remediation action
    """
    if _STATE_KEY not in st.session_state:
        st.session_state[_STATE_KEY] = []

    # Normalise severity
    if severity not in SEVERITIES:
        severity = "Medium"

    st.session_state[_STATE_KEY].append({
        "source":         source,
        "severity":       severity,
        "title":          title[:120],
        "description":    description[:400],
        "recommendation": recommendation[:400],
    })


def add_findings_bulk(source: str, findings: list) -> None:
    """
    Add multiple findings at once from a single module.

    Args:
        source   : Module name string
        findings : List of dicts with keys: severity, title, description, recommendation
    """
    for f in findings:
        add_finding(
            source         = source,
            severity       = f.get("severity", "Medium"),
            title          = f.get("title", "Finding"),
            description    = f.get("description", ""),
            recommendation = f.get("recommendation", ""),
        )


def get_all_findings() -> list:
    """
    Return all findings stored so far, in insertion order.
    Returns empty list if no findings have been stored yet.
    """
    return st.session_state.get(_STATE_KEY, [])


def get_findings_count() -> int:
    """Return the total number of findings stored."""
    return len(get_all_findings())


def format_for_module7() -> str:
    """
    Format all stored findings as the text string Module 7 expects.

    Produces the exact format the _parse_findings_text() function
    in modules/report.py can parse:

        Finding Title
        Severity: High
        Description: What was found.
        Recommendation: What to do.

        ---

        Next Finding...

    Returns empty string if no findings stored.
    """
    findings = get_all_findings()
    if not findings:
        return ""

    blocks = []
    for f in findings:
        block = (
            f"{f['title']}\n"
            f"Severity: {f['severity']}\n"
            f"Description: {f['description']}\n"
            f"Recommendation: {f['recommendation']}"
        )
        blocks.append(block)

    return "\n\n---\n\n".join(blocks)


def clear_findings() -> None:
    """Clear all stored findings — used when starting a new engagement."""
    st.session_state[_STATE_KEY] = []


def get_findings_summary() -> dict:
    """
    Return a count breakdown by severity.
    Used by Module 7 to show what's been collected before generating.
    """
    findings = get_all_findings()
    summary  = {s: 0 for s in SEVERITIES}
    sources  = set()
    for f in findings:
        summary[f.get("severity", "Medium")] += 1
        sources.add(f.get("source", "Unknown"))
    summary["total"]   = len(findings)
    summary["sources"] = sorted(sources)
    return summary
