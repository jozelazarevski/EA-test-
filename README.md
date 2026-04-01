# HVAC Expert Advisor Testing Agent

Automated testing agent for [Johnson Controls Expert Advisor](https://expertadvisor.jci.com/). The agent navigates to Expert Advisor, submits HVAC questions across multiple categories, validates responses and PDF documents, and generates detailed test reports.

## Features

- **Browser automation** via Playwright — interacts with Expert Advisor like a real user
- **19 test cases** across 8 HVAC categories (chillers, AHUs, controls, refrigeration, energy, safety, documentation, edge cases)
- **Response validation** — checks keyword presence, minimum length, and content relevance
- **PDF validation** — downloads and inspects referenced PDFs for expected content
- **HTML + JSON reports** with per-test results, category breakdowns, and screenshots
- **CLI interface** — run all tests, specific IDs, or entire categories

## Prerequisites

- Python 3.9+
- You must be logged into Expert Advisor (OTP authentication) before running

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Usage

```bash
# Run all tests (browser visible — you must be logged in)
python run_agent.py

# Run in headless mode
python run_agent.py --headless

# Run specific test cases
python run_agent.py --tests CHILLER-001 AHU-001 CTRL-001

# Run an entire category
python run_agent.py --category "Chiller Systems"

# List all available test cases
python run_agent.py --list
```

## Test Categories

| Category              | Tests | Description                                      |
|-----------------------|-------|--------------------------------------------------|
| Chiller Systems       | 3     | Centrifugal chiller troubleshooting & maintenance |
| Air Handling Units    | 2     | AHU commissioning and VAV balancing               |
| Controls & BAS        | 2     | Metasys PID loops and BACnet networking           |
| Refrigeration         | 2     | Refrigerant types and leak testing                |
| Energy Efficiency     | 2     | Chiller plant optimization and VSD technology     |
| Fire & Safety         | 1     | HVAC fire safety requirements                     |
| Product Documentation | 2     | Installation guides and tech specs (PDF expected) |
| Edge Cases            | 3     | Off-topic questions, competitor comparisons, empty input |

## Reports

Reports are saved to the `reports/` directory:

- `report_<run_id>.html` — Visual HTML report with summary dashboard
- `report_<run_id>.json` — Machine-readable JSON with full details
- `screenshots_<run_id>/` — Screenshots captured at each step

## Configuration

Environment variables (or edit `config.py`):

| Variable   | Default | Description                        |
|------------|--------|------------------------------------|
| `HEADLESS` | false  | Run browser without visible window |
| `SLOW_MO`  | 500    | Milliseconds between browser actions |
| `TIMEOUT`  | 60000  | Default timeout for page operations (ms) |

## Project Structure

```
├── run_agent.py          # CLI entry point
├── agent.py              # Browser automation & test orchestration
├── hvac_test_cases.py    # Test case definitions & validation criteria
├── validators.py         # Response and PDF validation logic
├── report_generator.py   # HTML and JSON report generation
├── config.py             # Configuration settings
├── requirements.txt      # Python dependencies
└── reports/              # Generated reports (gitignored)
```

## Adding Test Cases

Edit `hvac_test_cases.py` and add entries to the `TEST_CASES` list:

```python
{
    "id": "CHILLER-004",
    "category": "Chiller Systems",
    "question": "Your HVAC question here?",
    "validation": {
        "must_contain": ["keyword1", "keyword2"],
        "must_not_contain": [],
        "min_length": 100,
        "expect_pdf": False,
        "pdf_keywords": [],
    },
}
```
