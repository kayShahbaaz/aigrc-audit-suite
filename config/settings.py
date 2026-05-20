"""
config/settings.py — AI GRC Audit Suite
==========================================
App-wide constants, model names, and configuration values.
Imported by modules and utilities — centralises all magic strings
so changing a model name or version only requires one edit here.
"""

# =============================================================
# APP IDENTITY
# =============================================================

APP_NAME = "AI GRC Audit Suite"
APP_VERSION = "1.0.0"
APP_TAGLINE = "AI-powered audit toolkit for the Saudi and Gulf compliance market"

# =============================================================
# REGION CONFIGURATION
# Phase 1: Saudi Arabia only. UAE and India show Coming Soon.
# =============================================================

REGIONS = {
    "Gulf": {
        "label": "🌍 Gulf",
        "countries": {
            "Saudi Arabia": {
                "label": "🇸🇦 Saudi Arabia",
                "status": "active",   # fully working
                "flag": "🇸🇦",
            },
            "UAE": {
                "label": "🇦🇪 UAE",
                "status": "coming_soon",
                "flag": "🇦🇪",
            },
        },
    },
    "India": {
        "label": "🇮🇳 India",
        "status": "coming_soon",
        "flag": "🇮🇳",
    },
}

# =============================================================
# LLM CONFIGURATION
# All model names defined once here — never hardcoded in modules.
# =============================================================

# Groq model for learning/development
GROQ_MODEL = "openai/gpt-oss-120b"

# Max tokens for Groq responses
# 4096 is safe for most outputs; report generation may use more
GROQ_MAX_TOKENS = 4096

# Temperature — 0.3 keeps outputs consistent and professional
# Low temperature = more deterministic = better for compliance docs
GROQ_TEMPERATURE = 0.3

# =============================================================
# EMBEDDING MODEL CONFIGURATION
# Used by Module 4 (Gap Assessment) for RAG
# =============================================================

EMBEDDING_MODEL = "all-mpnet-base-v2"

# =============================================================
# CHROMADB CONFIGURATION
# =============================================================

# Path to ChromaDB persistent storage — relative to project root
CHROMA_DB_PATH = "./data/chroma_db"

# Collection name prefix — each gap assessment gets its own collection
# Named by company + timestamp to avoid collisions
CHROMA_COLLECTION_PREFIX = "grc_gap_"

# Number of document chunks to retrieve per query
CHROMA_RETRIEVAL_K = 5

# =============================================================
# DOCUMENT CHUNKING CONFIGURATION
# Used when loading client documents in Module 4
# =============================================================

# Chunk size in characters — 1000 chars ≈ 200 words — good for policy docs
CHUNK_SIZE = 1000

# Overlap between chunks — ensures context is not lost at chunk boundaries
CHUNK_OVERLAP = 200

# =============================================================
# COMPANY PROFILE — DEFAULT VALUES
# Shown as placeholders in the UI
# =============================================================

COMPANY_SIZE_OPTIONS = ["Startup", "SME", "Enterprise"]

INDUSTRY_OPTIONS = [
    "Banking and Financial Services",
    "Insurance",
    "Healthcare",
    "Government and Public Sector",
    "Energy and Utilities",
    "Telecommunications",
    "Information Technology",
    "Retail and E-Commerce",
    "Real Estate",
    "Education",
    "Manufacturing",
    "Transportation and Logistics",
    "Media and Entertainment",
    "Consulting and Professional Services",
    "Other",
]

CITY_OPTIONS_SAUDI = [
    "Riyadh",
    "Jeddah",
    "Mecca",
    "Medina",
    "Dammam",
    "Al Khobar",
    "Dhahran",
    "Jubail",
    "Tabuk",
    "Abha",
    "Khamis Mushait",
    "Other",
]

# =============================================================
# MODULE CONFIGURATION
# =============================================================

# Risk rating matrix — Likelihood x Impact
# Rating = Likelihood * Impact
RISK_LEVELS = {
    (1, 5): "High",
    (2, 4): "High",
    (2, 5): "Critical",
    (3, 3): "Medium",
    (3, 4): "High",
    (3, 5): "Critical",
    (4, 4): "Critical",
    (5, 5): "Critical",
}

# Risk level thresholds (Risk Rating = Likelihood * Impact, max 25)
RISK_LEVEL_THRESHOLDS = {
    "Critical": (16, 25),   # Rating 16–25
    "High": (10, 15),       # Rating 10–15
    "Medium": (5, 9),       # Rating 5–9
    "Low": (1, 4),          # Rating 1–4
}

# Incident types for Module 6 — IR Playbook
INCIDENT_TYPES = [
    "Ransomware",
    "Data Breach",
    "Insider Threat",
    "DDoS Attack",
    "Phishing Campaign",
    "Unauthorized Access",
]

# Regulatory bodies for incident notification (Module 6)
REGULATORY_BODIES = [
    "NCA (National Cybersecurity Authority)",
    "SAMA (Saudi Central Bank)",
    "SDAIA / PDPL Regulator",
    "CITC (Communications and IT Commission)",
]

# =============================================================
# OUTPUT / EXPORT CONFIGURATION
# =============================================================

# Language options — used by language toggle in every module
LANGUAGE_OPTIONS = {
    "English": "English only (default)",
    "Bilingual": "English + Arabic summary page",
}

# Default document version for generated policies
DEFAULT_DOC_VERSION = "1.0"

# Document review cycle (used in policy documents)
DEFAULT_REVIEW_CYCLE = "Annual"

# =============================================================
# UI CONFIGURATION
# =============================================================

# Streamlit page config
PAGE_TITLE = "AI GRC Audit Suite"
PAGE_ICON = "🛡️"
PAGE_LAYOUT = "wide"

# Sidebar width hint
SIDEBAR_STATE = "collapsed"

# Success / warning / error colours (referenced in custom CSS if needed)
COLOR_SUCCESS = "#00C853"
COLOR_WARNING = "#FF6D00"
COLOR_ERROR = "#D50000"
COLOR_PRIMARY = "#1565C0"
