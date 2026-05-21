"""
utils/groq_client.py — AI GRC Audit Suite
============================================
Single entry point for ALL Groq API calls in the application.

Why this pattern matters:
- Every module imports generate() from here — never calls Groq directly
- If we switch models or providers, we change ONE file, not 7 modules
- Error handling, retries, and logging all live here in one place
- Easy to swap Groq for LM Studio (local) later without touching modules

Functions:
    generate(prompt, system, max_tokens)  — single-turn completion
    generate_structured(prompt, system)   — returns parsed JSON
    translate_to_arabic(text)             — translates English text for bilingual output
"""

import os
import json
import time

from groq import Groq
from dotenv import load_dotenv

# Load .env file so GROQ_API_KEY is available as an environment variable
# load_dotenv() looks for .env in the current directory and parent directories
load_dotenv()

# Import settings — model name and defaults live there, not here
from config.settings import GROQ_MODEL, GROQ_MAX_TOKENS, GROQ_TEMPERATURE


# =============================================================
# CLIENT INITIALISATION
# =============================================================

def _get_client() -> Groq:
    """
    Create and return a Groq client using the API key from .env.
    Called internally by every function in this file.
    Raises a clear error if the key is missing so the user knows exactly what to fix.
    """
    api_key = os.getenv("GROQ_API_KEY")

    # Give the user a helpful error message — not a cryptic KeyError
    if not api_key or api_key == "gsk_your-groq-key-here":
        raise EnvironmentError(
            "GROQ_API_KEY not found or still set to the placeholder value.\n"
            "Steps to fix:\n"
            "  1. Copy .env.example to .env\n"
            "  2. Get a free key at https://console.groq.com\n"
            "  3. Paste your key into .env as: GROQ_API_KEY=gsk_xxxx\n"
            "  4. Restart the app."
        )

    return Groq(api_key=api_key)


# =============================================================
# CORE GENERATE FUNCTION
# =============================================================

def generate(
    prompt: str,
    system: str = "",
    max_tokens: int = GROQ_MAX_TOKENS,
    temperature: float = GROQ_TEMPERATURE,
    retries: int = 3,
) -> str:
    """
    Send a prompt to Groq and return the response as a plain string.

    This is the primary function all modules use to call the LLM.
    It handles retries automatically — Groq's free tier occasionally
    rate-limits, so we wait and retry rather than crashing.

    Args:
        prompt      : The user/task message — what you want the AI to do
        system      : Optional system prompt — sets the AI's role and behaviour
        max_tokens  : Max tokens in the response (default from settings)
        temperature : 0.0 = deterministic, 1.0 = creative (default 0.3 for compliance docs)
        retries     : Number of times to retry on rate-limit errors

    Returns:
        The model's response as a plain string (whitespace stripped)

    Raises:
        EnvironmentError  if API key is missing
        RuntimeError      if all retries are exhausted
    """
    client = _get_client()

    # Build the messages list — system prompt is optional
    # If no system prompt is given, just send the user message
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # Retry loop — handles Groq rate limits gracefully
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            # Extract the text from the response object and return it
            return response.choices[0].message.content.strip()

        except Exception as e:
            error_str = str(e).lower()

            # Rate limit hit — wait and retry with exponential backoff
            # Backoff: 5s → 10s → 20s between attempts
            if "rate_limit" in error_str or "rate limit" in error_str or "429" in error_str:
                if attempt < retries - 1:
                    wait_seconds = 5 * (2 ** attempt)   # 5, 10, 20 seconds
                    time.sleep(wait_seconds)
                    continue  # Try again
                else:
                    raise RuntimeError(
                        f"Groq rate limit hit after {retries} attempts. "
                        "Wait a minute and try again, or reduce the number of controls being assessed."
                    ) from e

            # Authentication error — bad API key
            elif "authentication" in error_str or "api_key" in error_str or "401" in error_str:
                raise EnvironmentError(
                    "Groq rejected the API key. Check that GROQ_API_KEY in your .env file "
                    "is correct and active at https://console.groq.com"
                ) from e

            # Any other error — raise immediately with the original message
            else:
                raise RuntimeError(f"Groq API error: {e}") from e

    # Should never reach here due to the raise inside the loop, but just in case
    raise RuntimeError("generate() failed after all retries.")


# =============================================================
# STRUCTURED OUTPUT — returns parsed JSON dict
# =============================================================

def generate_structured(
    prompt: str,
    system: str = "",
    max_tokens: int = GROQ_MAX_TOKENS,
) -> dict:
    """
    Like generate(), but the model is instructed to respond ONLY in JSON
    and the result is automatically parsed into a Python dict.

    Use this when you need structured data back — e.g. risk register rows,
    gap assessment scores, or vendor risk ratings — not free-form text.

    The system prompt is augmented to enforce JSON-only output.
    If the model adds markdown fences (```json ... ```) they are stripped.

    Args:
        prompt     : Task description — instruct the model what JSON to return
        system     : Optional base system prompt (JSON enforcement is appended)
        max_tokens : Max tokens (default from settings)

    Returns:
        Parsed dict or list (depends on what the model returns)

    Raises:
        ValueError   if the response cannot be parsed as JSON
        RuntimeError if the Groq call itself fails
    """

    # Tell the model explicitly to return only JSON — no preamble, no markdown
    json_instruction = (
        "\n\nIMPORTANT: You must respond with ONLY valid JSON. "
        "No preamble, no explanation, no markdown code fences. "
        "Your entire response must be parseable by Python's json.loads()."
    )

    full_system = (system or "") + json_instruction

    raw = generate(prompt=prompt, system=full_system, max_tokens=max_tokens, temperature=0.1)

    # Strip markdown fences if the model included them despite the instruction
    # Some models still wrap JSON in ```json ... ``` — this handles that case
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        cleaned = cleaned.split("\n", 1)[-1]
        # Remove closing fence
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    # First attempt — straightforward parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass  # fall through to repair pass below

    # --- Repair pass ---
    # LLMs frequently emit literal newlines/tabs inside JSON string values
    # (e.g. a long "classification" or "description" field that the model
    # wrote with actual line breaks instead of escaped \n). This is invalid
    # JSON — control characters (0x00-0x1F) are not allowed unescaped inside
    # a JSON string. We walk the text character by character, track whether
    # we are inside a string literal, and escape any raw control character
    # we find there. This does not touch whitespace between tokens (outside
    # strings), so the JSON structure itself is preserved.
    repaired = _escape_control_chars_in_json_strings(cleaned)

    try:
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Groq returned text that is not valid JSON, even after repair.\n"
            f"Error: {e}\n"
            f"Raw response (first 500 chars): {raw[:500]}"
        ) from e


def _escape_control_chars_in_json_strings(text: str) -> str:
    """
    Walk a JSON-like string and escape raw control characters (newline, tab,
    carriage return, etc.) that appear inside string literals.

    Why this is needed: JSON spec requires control characters (0x00-0x1F)
    inside string values to be escaped (\\n, \\t, ...). LLMs routinely violate
    this when generating long text fields with natural paragraph breaks,
    causing json.loads() to fail with "Invalid control character at...".

    This function tracks string boundaries (respecting escaped quotes \\")
    and only modifies characters found inside an open string literal —
    structural whitespace between JSON tokens is left untouched.

    Args:
        text : Raw text that should be JSON but may have unescaped control chars

    Returns:
        Text with control characters inside strings properly escaped
    """
    result = []
    in_string = False
    escape_next = False

    control_char_map = {
        "\n": "\\n",
        "\r": "\\r",
        "\t": "\\t",
        "\b": "\\b",
        "\f": "\\f",
    }

    for ch in text:
        if escape_next:
            # Previous char was a backslash — this char is already escaped,
            # pass it through untouched and clear the flag
            result.append(ch)
            escape_next = False
            continue

        if ch == "\\":
            result.append(ch)
            escape_next = True
            continue

        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue

        if in_string and ch in control_char_map:
            result.append(control_char_map[ch])
            continue

        # Any other control character inside a string (rare) — strip it
        if in_string and ord(ch) < 0x20:
            continue

        result.append(ch)

    return "".join(result)


# =============================================================
# ARABIC TRANSLATION — for bilingual document output
# =============================================================

def translate_to_arabic(text: str) -> str:
    """
    Translate a block of English text into Arabic.

    Used by the bilingual output feature — when the user selects
    'English + Arabic', this function translates the executive summary
    and key findings. The rest of the document stays in English.

    This is a genuine differentiator for the Saudi market — Arabic output
    makes the tool usable by Arabic-speaking stakeholders and boards.

    Args:
        text : English text to translate

    Returns:
        Arabic translation as a plain string

    Notes:
        - Keeps technical terms (NCA, SAMA, ECC, etc.) in English
        - Adds right-to-left marker at the start for correct rendering
    """

    system = (
        "You are a professional Arabic translator specialising in cybersecurity "
        "and regulatory compliance documents for the Saudi Arabian market. "
        "Translate the provided English text into formal Modern Standard Arabic (فصحى). "
        "Keep technical acronyms and framework names in English "
        "(e.g. NCA, SAMA, ECC, PDPL, ISO 27001). "
        "Your response must contain ONLY the Arabic translation — no English, "
        "no explanation, no preamble."
    )

    prompt = f"Translate the following text to Arabic:\n\n{text}"

    # Use slightly higher temperature for natural-sounding translation
    return generate(prompt=prompt, system=system, temperature=0.4)


# =============================================================
# CONVENIENCE WRAPPERS
# Pre-built system prompts for the most common use cases.
# Modules call these instead of crafting their own system prompts.
# =============================================================

def generate_policy(prompt: str) -> str:
    """
    Generate a professional compliance policy document section.
    Uses a system prompt tuned for formal, regulatory-compliant language.
    Called by modules/policy.py.
    """
    system = (
        "You are a senior cybersecurity GRC consultant with deep expertise in Saudi Arabian "
        "compliance frameworks including NCA ECC, SAMA CSF, and SDAIA PDPL. "
        "You write professional, clear, and enforceable compliance policy documents. "
        "Your language is formal but accessible. You follow ISO 27001 policy structure conventions. "
        "Always write in complete sentences. Never use bullet points in policy body text — "
        "use numbered clauses instead. Include specific, actionable requirements."
    )
    return generate(prompt=prompt, system=system)


def generate_risk_items(prompt: str) -> dict:
    """
    Generate risk register rows as structured JSON.
    Called by modules/risk.py.
    Returns a dict with a 'risks' list.
    """
    system = (
        "You are a senior cybersecurity risk analyst specialising in Saudi Arabian "
        "compliance frameworks. You produce structured risk register entries that are "
        "specific, realistic, and mapped to the correct framework controls. "
        "Always base risk ratings on industry-standard likelihood × impact methodology."
    )
    return generate_structured(prompt=prompt, system=system)


def generate_checklist_items(prompt: str) -> dict:
    """
    Generate audit checklist rows as structured JSON.
    Called by modules/checklist.py.
    Returns a dict with a 'controls' list.
    """
    system = (
        "You are a senior cybersecurity auditor with deep knowledge of Saudi Arabian "
        "compliance frameworks. You produce detailed audit checklists with specific, "
        "verifiable evidence requirements. Your audit methods are practical and aligned "
        "to what an auditor can realistically test during an engagement."
    )
    return generate_structured(prompt=prompt, system=system)


def generate_gap_verdict(prompt: str) -> dict:
    """
    Assess whether a framework control is Met / Partially Met / Not Met
    based on document evidence. Returns a structured JSON verdict.
    Called by modules/gap.py for each control during RAG assessment.
    """
    system = (
        "You are a senior cybersecurity GRC auditor assessing compliance evidence. "
        "Given a framework control requirement and extracted document text, "
        "determine if the control is: Met, Partially Met, or Not Met. "
        "Be conservative — if evidence is unclear or incomplete, mark Partially Met. "
        "Only mark Met if the evidence clearly and fully satisfies the control requirement."
    )
    return generate_structured(prompt=prompt, system=system)


def generate_vendor_assessment(prompt: str) -> dict:
    """
    Generate a vendor risk assessment as structured JSON.
    Called by modules/vendor.py.
    """
    system = (
        "You are a cybersecurity third-party risk analyst specialising in vendor "
        "assessments for Saudi Arabian financial and corporate entities. "
        "You identify red flags, assess risk levels, and recommend contractual "
        "safeguards based on SAMA CSF and NCA ECC third-party requirements."
    )
    return generate_structured(prompt=prompt, system=system)


def generate_ir_playbook(prompt: str) -> str:
    """
    Generate an incident response playbook section.
    Called by modules/playbook.py.
    """
    system = (
        "You are a senior cybersecurity incident response specialist with expertise "
        "in Saudi Arabian regulatory requirements including NCA incident reporting, "
        "SAMA CSF resilience requirements, and PDPL breach notification obligations. "
        "You write clear, actionable IR playbooks that teams can follow under pressure. "
        "Use numbered steps. Be specific about timelines and responsible roles."
    )
    return generate(prompt=prompt, system=system)


def generate_audit_report_section(prompt: str) -> str:
    """
    Generate a section of the final audit report.
    Called by modules/report.py.
    Uses the most formal, board-level language.
    """
    system = (
        "You are a senior cybersecurity auditor producing a formal audit report "
        "for a board of directors and senior management. "
        "Your language is professional, precise, and objective. "
        "Findings are evidence-based. Recommendations are specific and prioritised. "
        "You follow professional audit report standards. "
        "Never use casual language. Write in third person where appropriate."
    )
    return generate(prompt=prompt, system=system)
