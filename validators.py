"""
Validators for HVAC Testing Agent.

Validates text responses and PDF documents against expected criteria.
Includes technical fact validation using authoritative reference data.
"""

import re
from pathlib import Path

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None


def validate_response(response_text: str, validation: dict) -> dict:
    """
    Validate a text response against the given criteria.

    Args:
        response_text: The response text from Expert Advisor
        validation: Dict with validation criteria

    Returns:
        Dict with 'pass' (bool), 'details' (str), and 'checks' (list of individual results)
    """
    checks = []
    all_pass = True

    # Check minimum length
    min_length = validation.get("min_length", 0)
    actual_length = len(response_text)
    length_pass = actual_length >= min_length
    checks.append({
        "check": "min_length",
        "pass": length_pass,
        "expected": f">= {min_length} chars",
        "actual": f"{actual_length} chars",
    })
    if not length_pass:
        all_pass = False

    # Check must_contain keywords
    for keyword in validation.get("must_contain", []):
        found = keyword.lower() in response_text.lower()
        checks.append({
            "check": "must_contain",
            "pass": found,
            "expected": f"Contains '{keyword}'",
            "actual": f"{'Found' if found else 'NOT found'}",
        })
        if not found:
            all_pass = False

    # Check must_not_contain keywords
    for keyword in validation.get("must_not_contain", []):
        not_found = keyword.lower() not in response_text.lower()
        checks.append({
            "check": "must_not_contain",
            "pass": not_found,
            "expected": f"Does NOT contain '{keyword}'",
            "actual": f"{'Not found (good)' if not_found else 'FOUND (bad)'}",
        })
        if not not_found:
            all_pass = False

    # Check for refusal/redirect if expected (edge case)
    if validation.get("expect_refusal_or_redirect"):
        # For off-topic questions, we expect the system to either refuse
        # or redirect to HVAC topics. We check if response mentions HVAC
        # or politely declines.
        hvac_redirect_keywords = [
            "hvac", "heating", "cooling", "chiller", "johnson controls",
            "building", "can help you with", "assist you with",
            "related to", "i'm designed", "i am designed",
        ]
        has_redirect = any(kw in response_text.lower() for kw in hvac_redirect_keywords)
        checks.append({
            "check": "expect_refusal_or_redirect",
            "pass": True,  # Informational - don't fail for this
            "expected": "Redirect to HVAC topics or polite refusal",
            "actual": f"{'Redirected/scoped response' if has_redirect else 'General response given'}",
        })

    details = "; ".join(
        f"{c['check']}: {'PASS' if c['pass'] else 'FAIL'} ({c['actual']})"
        for c in checks
    )

    return {
        "pass": all_pass,
        "details": details,
        "checks": checks,
    }


def validate_pdf(pdf_path: Path, expected_keywords: list) -> dict:
    """
    Validate a downloaded PDF file.

    Args:
        pdf_path: Path to the PDF file
        expected_keywords: Keywords expected in the PDF content

    Returns:
        Dict with 'pass' (bool), 'details' (str), and check results
    """
    result = {
        "pass": False,
        "file": str(pdf_path),
        "details": "",
        "checks": [],
    }

    # Check file exists and is non-empty
    if not pdf_path.exists():
        result["details"] = "PDF file does not exist"
        return result

    file_size = pdf_path.stat().st_size
    if file_size == 0:
        result["details"] = "PDF file is empty (0 bytes)"
        return result

    result["checks"].append({
        "check": "file_exists",
        "pass": True,
        "detail": f"File exists, size: {file_size} bytes",
    })

    # Try to read and validate PDF content
    if PdfReader is None:
        result["details"] = "PyPDF2 not installed - cannot validate PDF content"
        result["pass"] = True  # Pass on file existence alone
        return result

    try:
        reader = PdfReader(str(pdf_path))
        num_pages = len(reader.pages)

        result["checks"].append({
            "check": "pdf_readable",
            "pass": True,
            "detail": f"PDF is valid, {num_pages} pages",
        })

        # Extract text from all pages
        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

        result["checks"].append({
            "check": "has_text_content",
            "pass": len(full_text.strip()) > 0,
            "detail": f"Extracted {len(full_text)} chars of text",
        })

        # Check for expected keywords
        all_keywords_found = True
        for keyword in expected_keywords:
            found = keyword.lower() in full_text.lower()
            result["checks"].append({
                "check": f"keyword_{keyword}",
                "pass": found,
                "detail": f"Keyword '{keyword}': {'found' if found else 'NOT found'}",
            })
            if not found:
                all_keywords_found = False

        result["pass"] = all_keywords_found if expected_keywords else True
        result["details"] = f"PDF valid, {num_pages} pages, {len(full_text)} chars extracted"

    except Exception as e:
        result["details"] = f"Error reading PDF: {str(e)}"
        result["checks"].append({
            "check": "pdf_readable",
            "pass": False,
            "detail": f"Error: {str(e)}",
        })

    return result


def validate_technical_facts(
    response_text: str,
    expected_answer: dict,
) -> dict:
    """
    Validate a response against gold-standard expected answer reference data.

    Checks for:
    - Presence of required technical facts (from expected_facts / required_elements)
    - Presence of required safety warnings
    - Presence of forbidden content (automatic red flags)
    - Technical value ranges (numeric claims vs authoritative values)

    Args:
        response_text: The EA response text.
        expected_answer: Dict from references/expected_answers.yaml for this
                         scenario or test case.

    Returns:
        Dict with fact_checks, safety_checks, forbidden_checks, value_checks,
        and summary statistics.
    """
    lower = response_text.lower()
    fact_checks = []
    safety_checks = []
    forbidden_checks = []
    value_checks = []

    # 1. Check required facts / elements
    for section_key in ["required_elements", "expected_facts"]:
        data = expected_answer.get(section_key)
        if not data:
            continue

        items = []
        if isinstance(data, dict):
            for sub_key, sub_items in data.items():
                for item in sub_items:
                    items.append((sub_key, item))
        elif isinstance(data, list):
            items = [("facts", item) for item in data]

        for category, fact in items:
            # Extract key terms from the fact for matching
            key_terms = _extract_key_terms(fact)
            matched_terms = [t for t in key_terms if t in lower]
            match_ratio = len(matched_terms) / len(key_terms) if key_terms else 0

            fact_checks.append({
                "category": category,
                "expected_fact": fact,
                "key_terms": key_terms,
                "matched_terms": matched_terms,
                "match_ratio": round(match_ratio, 2),
                "present": match_ratio >= 0.3,  # Generous: 30% of key terms (allows paraphrasing)
            })

    # 2. Check safety warnings
    for safety_key in ["safety_warnings", "safety_notes"]:
        warnings = expected_answer.get(safety_key, [])
        for warning in warnings:
            key_terms = _extract_key_terms(warning)
            matched = [t for t in key_terms if t in lower]
            match_ratio = len(matched) / len(key_terms) if key_terms else 0
            safety_checks.append({
                "expected_warning": warning,
                "key_terms": key_terms,
                "matched_terms": matched,
                "match_ratio": round(match_ratio, 2),
                "present": match_ratio >= 0.25,  # Generous: safety concepts can be paraphrased
            })

    # 3. Check forbidden content
    for item in expected_answer.get("forbidden_content", []):
        key_terms = _extract_key_terms(item)
        found_terms = [t for t in key_terms if t in lower]
        is_present = len(found_terms) / len(key_terms) >= 0.6 if key_terms else False
        forbidden_checks.append({
            "forbidden": item,
            "detected": is_present,
            "matched_terms": found_terms,
        })

    # 4. Check technical values
    for values_key in ["technical_values", "expected_values"]:
        values = expected_answer.get(values_key, {})
        for key, expected_val in values.items():
            if isinstance(expected_val, (int, float)):
                found = _find_numeric_value_in_text(response_text, key, expected_val)
                value_checks.append(found)
            elif isinstance(expected_val, str) and "-" in str(expected_val):
                # Range like "118-128"
                found = _find_range_in_text(response_text, key, str(expected_val))
                value_checks.append(found)

    # Compute summary
    facts_present = sum(1 for f in fact_checks if f["present"])
    facts_total = len(fact_checks)
    safety_present = sum(1 for s in safety_checks if s["present"])
    safety_total = len(safety_checks)
    forbidden_found = sum(1 for f in forbidden_checks if f["detected"])
    values_matched = sum(1 for v in value_checks if v.get("match", False))
    values_total = len(value_checks)

    return {
        "fact_checks": fact_checks,
        "safety_checks": safety_checks,
        "forbidden_checks": forbidden_checks,
        "value_checks": value_checks,
        "summary": {
            "facts_coverage": f"{facts_present}/{facts_total}" if facts_total else "N/A",
            "facts_coverage_pct": round(facts_present / facts_total * 100, 1) if facts_total else 0,
            "safety_coverage": f"{safety_present}/{safety_total}" if safety_total else "N/A",
            "safety_coverage_pct": round(safety_present / safety_total * 100, 1) if safety_total else 0,
            "forbidden_violations": forbidden_found,
            "values_accuracy": f"{values_matched}/{values_total}" if values_total else "N/A",
        },
    }


def _extract_key_terms(text: str) -> list[str]:
    """Extract meaningful technical terms from a reference fact string.

    Only extracts the most distinctive technical terms (nouns, numbers,
    abbreviations) so that paraphrased answers can still match.
    """
    # Broad stop words — be generous so only truly distinctive terms remain
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "must", "can", "could", "of", "in", "to",
        "for", "with", "on", "at", "from", "by", "about", "as", "into",
        "through", "during", "before", "after", "above", "below", "between",
        "and", "but", "or", "nor", "not", "if", "then", "than", "that",
        "this", "these", "those", "it", "its", "they", "them", "their",
        "we", "our", "you", "your", "he", "she", "his", "her",
        # Additional common verbs/adjectives that don't help matching
        "ensure", "check", "verify", "make", "sure", "use", "using", "used",
        "need", "needs", "needed", "provide", "provides", "provided",
        "include", "includes", "including", "such", "like", "also",
        "when", "where", "how", "what", "which", "who", "only",
        "all", "any", "each", "every", "both", "either", "neither",
        "more", "most", "less", "least", "very", "much", "many",
        "always", "never", "often", "usually", "sometimes",
        "required", "recommended", "important", "necessary", "proper",
        "appropriate", "correct", "specific", "based", "within",
        "per", "follow", "following", "according", "typically",
    }
    words = re.findall(r"[a-z][a-z0-9/°\-]+", text.lower())
    terms = [w for w in words if w not in stop_words and len(w) > 2]
    # Limit to most distinctive terms (cap at 6) to avoid over-penalizing
    return terms[:6]


def _find_numeric_value_in_text(
    text: str,
    key: str,
    expected: float,
    tolerance_pct: float = 15.0,
) -> dict:
    """Check if a numeric value close to 'expected' appears in the text."""
    # Find all numbers in the text
    numbers = re.findall(r"[\d]+\.?\d*", text)
    label = key.replace("_", " ").title()

    for num_str in numbers:
        try:
            val = float(num_str)
            if expected != 0:
                diff_pct = abs(val - expected) / abs(expected) * 100
            else:
                diff_pct = abs(val)

            if diff_pct <= tolerance_pct:
                return {
                    "label": label,
                    "expected": expected,
                    "found": val,
                    "match": True,
                    "detail": f"Found {val} (expected ~{expected}, within {tolerance_pct}%)",
                }
        except ValueError:
            continue

    return {
        "label": label,
        "expected": expected,
        "found": None,
        "match": False,
        "detail": f"Value ~{expected} not found in response",
    }


def _find_range_in_text(text: str, key: str, expected_range: str) -> dict:
    """Check if a value range like '118-128' appears in the text."""
    label = key.replace("_", " ").title()

    # Try to parse the expected range
    parts = expected_range.split("-")
    if len(parts) != 2:
        return {"label": label, "expected": expected_range, "found": None, "match": False,
                "detail": f"Could not parse range: {expected_range}"}

    try:
        lo, hi = float(parts[0].strip()), float(parts[1].strip())
    except ValueError:
        return {"label": label, "expected": expected_range, "found": None, "match": False,
                "detail": f"Could not parse range: {expected_range}"}

    # Check if the range or any value within it appears
    numbers = re.findall(r"[\d]+\.?\d*", text)
    for num_str in numbers:
        try:
            val = float(num_str)
            if lo * 0.85 <= val <= hi * 1.15:
                return {
                    "label": label,
                    "expected": expected_range,
                    "found": val,
                    "match": True,
                    "detail": f"Found {val} (within range {expected_range})",
                }
        except ValueError:
            continue

    return {
        "label": label,
        "expected": expected_range,
        "found": None,
        "match": False,
        "detail": f"No value in range {expected_range} found in response",
    }
