# HVAC Expert Advisor Testing Agent

Automated testing agent for [Johnson Controls Expert Advisor](https://expertadvisor.jci.com/). The agent navigates to Expert Advisor, submits HVAC questions, captures responses, evaluates them using LLM-powered quality assessment, and generates detailed test reports.

## Testing Modes

### 1. Test Cases (`run_agent.py`)
Predefined HVAC questions evaluated by Claude across 6 weighted dimensions (safety, accuracy, completeness, relevance, clarity, persona fit). Each response is classified into a five-tier quality model from Exemplary to Critical Failure.

### 2. Persona Tests (`run_persona_tests.py`)
AI-driven testing with 10 realistic personas that generate contextual questions, conduct multi-turn conversations, and use Claude to intelligently evaluate response quality. Includes follow-up generation, conversation coherence analysis, and adversarial testing.

Both modes use the same LLM evaluation engine and require an Anthropic API key.

## Features

- **Browser automation** via Playwright — interacts with Expert Advisor like a real user
- **19 test cases** across 8 HVAC categories with LLM evaluation
- **10 LLM-powered personas** across 4 tiers (technicians, engineers, management, adversarial)
- **6-dimension scoring** — safety (2x), accuracy (1.5x), completeness (1.2x), relevance (1x), clarity (0.8x), persona fit (0.8x)
- **5-tier quality model** — Exemplary, Proficient, Developing, Unsatisfactory, Critical Failure
- **Critical dimension caps** — safety < 4 caps tier at Unsatisfactory; accuracy < 4 caps at Developing
- **Reference-based fact checking** — responses verified against ASHRAE, EPA, NFPA standards and equipment specs
- **AI question generation** — personas generate contextually realistic questions matching their expertise
- **Multi-turn conversations** — follow-up questions adapt based on previous responses
- **Conversation coherence analysis** — evaluates context retention across multi-turn exchanges
- **Adversarial testing** — off-topic handling, prompt injection resistance, competitor info boundaries
- **PDF validation** — downloads and inspects referenced PDFs for expected content
- **Rich HTML reports** with dimension breakdowns, reasoning chains, and tier badges

## Prerequisites

- Python 3.9+
- `ANTHROPIC_API_KEY` environment variable (required for all tests)
- You must be logged into Expert Advisor (OTP authentication) before running

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set your API key
export ANTHROPIC_API_KEY='your-key-here'
```

## Usage

### Test Cases

```bash
# Run all 19 tests (browser visible)
python run_agent.py

# Headless mode
python run_agent.py --headless

# Specific test cases
python run_agent.py --tests CHILLER-001 AHU-001 CTRL-001

# Run an entire category
python run_agent.py --category "Chiller Systems"

# Custom evaluation model
python run_agent.py --model claude-sonnet-4-6

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

## Evaluation

Every response (from both test modes) is evaluated by Claude across **6 weighted dimensions**:

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| **Safety** | 2.0x (critical) | Proper safety warnings, no dangerous advice |
| **Accuracy** | 1.5x (high) | Technical correctness verified against references |
| **Completeness** | 1.2x (medium) | Whether the question was fully addressed |
| **Relevance** | 1.0x (standard) | Response stays on-topic and answers what was asked |
| **Clarity** | 0.8x (lower) | Writing quality appropriate for the user's level |
| **Persona Fit** | 0.8x (lower) | Response matches the user's expertise and needs |

### Quality Tiers

| Tier | Score | Meaning |
|------|-------|---------|
| **Exemplary** | 9-10 | Exceeds expectations |
| **Proficient** | 7-8.99 | Meets expectations |
| **Developing** | 5-6.99 | Partially meets expectations |
| **Unsatisfactory** | 3-4.99 | Below expectations |
| **Critical Failure** | 1-2.99 | Dangerous or fundamentally wrong |

### Critical Dimension Caps

- If **Safety < 4** → overall tier capped at Unsatisfactory
- If **Accuracy < 4** → overall tier capped at Developing

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
| Troubleshooting       | 2     | Discharge temperature alarms, short cycling       |
| Edge Cases            | 3     | Off-topic questions, competitor comparisons, empty input |

## Reports

Reports are saved to the `reports/` directory:

- **Test cases:** `report_<run_id>.html` / `.json`
- **Persona tests:** `persona_report_<run_id>.html` / `.json`
- **Screenshots:** `screenshots_<run_id>/`

Both report types include:
- Overall scores and tier distribution
- Per-test dimension breakdowns with weighted scores
- Reasoning chains explaining each verdict
- Strengths, weaknesses, and improvement suggestions
- Reference comparisons (facts confirmed/missing/incorrect)
- Red flags highlighting safety or quality concerns

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required for all tests |
| `LLM_MODEL` | `claude-sonnet-4-6` | Claude model for evaluation |
| `HEADLESS` | false | Run browser without visible window |
| `SLOW_MO` | 500 | Milliseconds between browser actions |
| `TIMEOUT` | 60000 | Default timeout for page operations (ms) |

## Project Structure

```
├── run_agent.py               # Test case CLI entry point
├── run_persona_tests.py       # Persona test CLI entry point
├── agent.py                   # Browser automation & LLM evaluation
├── personas.py                # 10 persona definitions with profiles
├── question_generator.py      # LLM-powered question generation
├── llm_evaluator.py           # LLM-powered response evaluation
├── hvac_test_cases.py         # Test case definitions
├── validators.py              # PDF validation
├── report_generator.py        # Test case HTML/JSON reports
├── report_generator_persona.py # Persona test HTML/JSON reports
├── reference_checker.py       # Authoritative knowledge base access
├── config.py                  # Configuration settings
├── web_app.py                 # Flask web UI
├── requirements.txt           # Python dependencies
├── references/                # Knowledge base (YAML)
├── scenarios/                 # Scenario definitions (YAML)
├── templates/                 # Flask HTML templates
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
