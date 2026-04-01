# HVAC Expert Advisor Testing Agent

Automated testing agent for [Johnson Controls Expert Advisor](https://expertadvisor.jci.com/). The agent navigates to Expert Advisor, submits HVAC questions across multiple categories, validates responses and PDF documents, and generates detailed test reports.

## Two Testing Modes

### 1. Static Test Cases (`run_agent.py`)
Predefined questions with keyword-based validation. Fast, deterministic, no API key needed.

### 2. LLM-Powered Persona Tests (`run_persona_tests.py`)
AI-driven testing with 10 realistic personas that generate contextual questions, conduct multi-turn conversations, and use Claude to intelligently evaluate response quality. Requires an Anthropic API key.

## Features

- **Browser automation** via Playwright — interacts with Expert Advisor like a real user
- **19 static test cases** across 8 HVAC categories
- **10 LLM-powered personas** across 4 tiers (technicians, engineers, management, adversarial)
- **AI question generation** — personas generate contextually realistic questions matching their expertise
- **Multi-turn conversations** — follow-up questions adapt based on previous responses
- **AI response evaluation** — Claude scores responses on 6 dimensions (accuracy, completeness, relevance, clarity, safety, persona-fit)
- **Conversation coherence analysis** — evaluates context retention across multi-turn exchanges
- **Adversarial testing** — off-topic handling, prompt injection resistance, competitor info boundaries
- **PDF validation** — downloads and inspects referenced PDFs for expected content
- **Rich HTML reports** with persona scorecards, dimension breakdowns, and conversation details

## Prerequisites

- Python 3.9+
- You must be logged into Expert Advisor (OTP authentication) before running
- For persona tests: `ANTHROPIC_API_KEY` environment variable

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# For persona tests — set your API key
export ANTHROPIC_API_KEY='your-key-here'
```

## Usage

### Static Tests

```bash
# Run all 19 tests (browser visible)
python run_agent.py

# Headless mode
python run_agent.py --headless

# Specific test cases
python run_agent.py --tests CHILLER-001 AHU-001 CTRL-001

# Run an entire category
python run_agent.py --category "Chiller Systems"

# List all test cases
python run_agent.py --list
```

### Persona Tests

```bash
# Run all 10 personas (3 questions each + 1 follow-up)
python run_persona_tests.py

# Run specific personas
python run_persona_tests.py --personas TECH-SENIOR ENG-MECHANICAL

# Run a tier
python run_persona_tests.py --tier technicians   # field techs only
python run_persona_tests.py --tier adversarial    # security/edge cases

# Control depth
python run_persona_tests.py --questions 5 --follow-ups 2

# Headless + custom model
python run_persona_tests.py --headless --model claude-sonnet-4-6

# List all personas
python run_persona_tests.py --list
```

## Personas

### Tier 1: Field Technicians
| ID | Name | Expertise | Focus |
|----|------|-----------|-------|
| `TECH-SENIOR` | Marcus — Senior Field Tech | Advanced (18y) | Chiller diagnostics, refrigerant circuits, VFDs |
| `TECH-JUNIOR` | Aisha — Junior Technician | Beginner (2y) | Basic operations, safety, learning terminology |
| `TECH-CONTROLS` | Raj — Controls Specialist | Advanced (10y) | Metasys, BACnet, DDC programming |

### Tier 2: Engineers
| ID | Name | Expertise | Focus |
|----|------|-----------|-------|
| `ENG-MECHANICAL` | Dr. Sarah Chen — Mech. Engineer | Expert (15y) | Equipment selection, ASHRAE standards, design |
| `ENG-ENERGY` | James — Energy Engineer | Advanced (8y) | Efficiency, decarbonization, lifecycle costs |

### Tier 3: Management
| ID | Name | Expertise | Focus |
|----|------|-----------|-------|
| `MGR-FACILITY` | Linda — Facility Manager | Intermediate (20y) | Budgets, comfort complaints, PM scheduling |
| `MGR-PROJECT` | Kevin — Construction PM | Intermediate (12y) | Lead times, commissioning, submittals |

### Tier 4: Adversarial
| ID | Name | Focus |
|----|------|-------|
| `ADV-OFFTOPIC` | Derek — Off-Topic User | Topic boundary testing, prompt injection |
| `ADV-COMPETITOR` | Tom — Competitor Analyst | Proprietary info extraction, competitive comparisons |
| `ADV-OVERLOAD` | StressBot — Stress Tester | Malformed inputs, XSS, system robustness |

## Evaluation Dimensions

Each response is scored 1-10 on:

| Dimension | What it measures |
|-----------|-----------------|
| **Accuracy** | Technical correctness of the response |
| **Completeness** | Whether the question was fully addressed |
| **Relevance** | Response stays on-topic and answers what was asked |
| **Clarity** | Writing quality appropriate for the persona's level |
| **Safety** | Proper safety warnings, no dangerous advice |
| **Persona Fit** | Response matches the user's expertise level and needs |

## Static Test Categories

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

- **Static tests:** `report_<run_id>.html` / `.json`
- **Persona tests:** `persona_report_<run_id>.html` / `.json`
- **Screenshots:** `screenshots_<run_id>/`

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required for persona tests |
| `HEADLESS` | false | Run browser without visible window |
| `SLOW_MO` | 500 | Milliseconds between browser actions |
| `TIMEOUT` | 60000 | Default timeout for page operations (ms) |

## Project Structure

```
├── run_agent.py               # Static test CLI entry point
├── run_persona_tests.py       # Persona test CLI entry point
├── agent.py                   # Browser automation & orchestration
├── personas.py                # 10 persona definitions with profiles
├── question_generator.py      # LLM-powered question generation
├── llm_evaluator.py           # LLM-powered response evaluation
├── hvac_test_cases.py         # Static test case definitions
├── validators.py              # Keyword & PDF validation
├── report_generator.py        # Static test HTML/JSON reports
├── report_generator_persona.py # Persona test HTML/JSON reports
├── config.py                  # Configuration settings
├── requirements.txt           # Python dependencies
└── reports/                   # Generated reports (gitignored)
```

## Adding a Custom Persona

Edit `personas.py` and add to the `PERSONAS` list:

```python
{
    "id": "CUSTOM-001",
    "name": "Your Persona Name",
    "role": "Job Title",
    "experience_years": 10,
    "expertise_level": "intermediate",  # none|beginner|intermediate|advanced|expert
    "background": "Detailed background...",
    "communication_style": {
        "tone": "description of tone",
        "vocabulary": "typical vocabulary",
        "typical_phrases": ["I usually say...", "Can you help with..."],
    },
    "question_domains": ["domain 1", "domain 2"],
    "follow_up_behavior": "How they follow up",
    "evaluation_focus": ["What matters for scoring"],
}
```
