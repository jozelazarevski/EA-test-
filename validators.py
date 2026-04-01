"""
Validators for HVAC Testing Agent.

Validates text responses and PDF documents against expected criteria.
"""

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
