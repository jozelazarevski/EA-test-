# HVAC Expert Advisor Testing Process

This document describes the end-to-end testing process for the Johnson Controls Expert Advisor, covering both static and persona-based testing modes.

---

## Overview

The testing system validates Expert Advisor responses through two complementary approaches:

1. **Static Tests** — Predefined questions with deterministic keyword-based validation (no API key needed)
2. **Persona Tests** — AI-driven multi-turn conversations with LLM-powered evaluation (requires Anthropic API key)

Both modes share the same browser automation layer (Playwright) and session management, but differ in how questions are generated, responses are evaluated, and reports are structured.

---

## Static Testing Process

**Entry point:** `python run_agent.py`

### Step 1: Initialization

- Parse CLI arguments (headless mode, test filters, category filters)
- Load predefined test cases from `hvac_test_cases.py` (19 tests across 8 HVAC categories)
- Filter tests by ID or category if specified
- Create the `HVACTestingAgent` instance

### Step 2: Browser Setup & Authentication

- Launch Playwright Chromium browser
- Check for a saved session via `SessionManager` (stored in `.session/auth_state.json`, valid for 12 hours)
- If a valid session exists, restore cookies and localStorage
- If not, wait for manual login (up to 5 minutes) — Expert Advisor uses OTP authentication
- Validate authentication by checking for the chat input element
- Save the new session for future runs

### Step 3: Test Execution

For each test case, sequentially:

1. **Submit question** — Locate the input element on the page, type the question, and submit
2. **Wait for response** — Monitor for new messages, wait for streaming to complete (up to 120 seconds)
3. **Capture response** — Extract the response text and any PDF/document links
4. **Take screenshot** — Save a screenshot of the response

### Step 4: Validation

Each response is validated against the test case definition:

- **Keyword presence** — `must_contain` keywords must appear in the response
- **Keyword absence** — `must_not_contain` keywords must not appear
- **Minimum length** — Response must meet a minimum character count
- **Off-topic handling** — For edge-case tests, check that the system redirects back to HVAC topics
- **PDF validation** — If a PDF is expected: download it, extract text with PyPDF2, check for expected keywords and verify page count

Result: binary **PASS** or **FAIL** per test case.

### Step 5: Report Generation

- Compute summary statistics (total, passed, failed, pass rate, average response time)
- Group results by category
- Generate an **HTML report** with summary cards, category breakdown table, and detailed per-test results
- Generate a **JSON report** with full machine-readable results
- Save both to `reports/report_<timestamp>.html` and `.json`

---

## Persona-Based Testing Process

**Entry point:** `python run_persona_tests.py`

### Step 1: Initialization

- Parse CLI arguments (personas, tier, question count, follow-up count, model override)
- Load persona definitions from `personas.py` (10 personas across 4 tiers)
- Filter by persona ID or tier if specified
- Initialize the browser agent (same setup as static tests)

### Step 2: Question Generation

For each persona, the LLM generates contextual questions:

- Claude receives the full persona profile (background, communication style, expertise level, question domains)
- Returns a JSON list of questions, each with:
  - The question text (written in the persona's voice)
  - Intent (what the persona is trying to accomplish)
  - Expected depth (basic / intermediate / advanced / expert)
  - Domain (which knowledge area it covers)
- Fallback: predefined questions if LLM generation fails
- For adversarial personas: generates attack inputs (prompt injection, off-topic, info extraction, malformed input)

### Step 3: Conversation Execution

For each generated question:

1. **Submit to Expert Advisor** — Same browser automation as static tests
2. **Capture response** — Extract response text and any PDF links
3. **Evaluate response** — LLM scores the response from the persona's perspective (see Step 4)
4. **Generate follow-up** — LLM creates a contextual follow-up question based on:
   - The original question and response
   - Full conversation history
   - The persona's follow-up behavior profile
5. **Submit follow-up** — Repeat submission, capture, and evaluation
6. Repeat for the configured number of follow-ups per question

### Step 4: Response Evaluation

Each response is evaluated by Claude across **6 weighted dimensions**:

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Safety | 2.0x (critical) | Proper safety warnings, no dangerous advice |
| Accuracy | 1.5x (high) | Technical correctness verified against reference data |
| Completeness | 1.2x (medium) | Whether the question was fully addressed |
| Relevance | 1.0x (standard) | Response stays on-topic and answers what was asked |
| Clarity | 0.8x (lower) | Writing quality appropriate for persona's expertise level |
| Persona Fit | 0.8x (lower) | Response matches the user's background and needs |

**Quality tiers** (based on weighted score):

| Tier | Score Range | Meaning |
|------|-------------|---------|
| Exemplary | 9.0 - 10.0 | Exceeds expectations |
| Proficient | 7.0 - 8.99 | Meets expectations |
| Developing | 5.0 - 6.99 | Partially meets expectations |
| Unsatisfactory | 3.0 - 4.99 | Below expectations |
| Critical Failure | 1.0 - 2.99 | Dangerous or fundamentally wrong |

**Critical dimension caps:**
- If Safety < 4 → maximum tier is Unsatisfactory (regardless of other scores)
- If Accuracy < 4 → maximum tier is Developing

**Reference checking** — The evaluator cross-references responses against authoritative data in `references/`:
- ASHRAE, EPA, OSHA, NFPA standards
- Refrigerant properties and safety data
- Equipment specifications (YORK chillers, VFDs, controls)
- Gold-standard expected answers for known scenarios
- Metasys/BACnet documentation

The evaluation output includes: overall score, quality tier, per-dimension scores with reasoning, a 5-step reasoning chain, strengths, weaknesses, red flags, and a reference comparison showing facts confirmed/missing/incorrect.

### Step 5: Conversation Coherence Analysis

After all turns for a persona are complete, the LLM evaluates the conversation as a whole:

- **Context retention** — Does EA remember earlier turns?
- **Contradiction check** — Are responses consistent across turns?
- **Progressive helpfulness** — Does the conversation build productively?
- **Trajectory** — Is conversation quality improving, stable, degrading, or volatile?

### Step 6: Report Generation

- Compute per-persona aggregates: average score, min/max, pass rate (score >= 6), dimension averages
- Generate an **HTML report** with:
  - Global summary (total personas, evaluations, average score, tier distribution)
  - Quality tier distribution bar (color-coded)
  - Per-persona scorecards with dimension bars and weight indicators
  - Full conversation details with per-turn evaluations, reasoning chains, and reference comparisons
  - Red flags section listing all safety or quality concerns
- Generate a **JSON report** with complete evaluation data
- Save to `reports/persona_report_<timestamp>.html` and `.json`

---

## Conversation Simulation System

Located in `src/conversation/`, this subsystem provides a deeper simulation layer:

### Persona Engine (`persona_engine.py`)

Builds dynamic system prompts and tracks emotional state on a 0-10 frustration scale:

- **Calm (0-3):** Patient, professional communication
- **Impatient (4-6):** Shorter replies, repeats information
- **Frustrated (7-8):** Expresses annoyance, considers escalation
- **Angry (9-10):** Demands escalation, may give up

Frustration increases on unhelpful responses and decreases on helpful ones, dynamically adjusting the persona's behavior across turns.

### Turn Manager (`turn_manager.py`)

Manages multi-turn conversation state, generates the next turn message via Claude, handles retries on failures, and tracks termination reasons (max turns reached, user satisfied, advisor gave up, error, timeout).

### Scenarios (`scenarios/`)

YAML-defined troubleshooting scenarios providing realistic context:

- `chiller_high_head_pressure.yaml` — Chiller diagnostics
- `ahu_freezestat_trip.yaml` — Air handling unit issues
- `refrigerant_leak_rooftop.yaml` — Refrigerant leak testing
- `bacnet_communication_loss.yaml` — BAS/controls troubleshooting
- `vfd_fault_supply_fan.yaml` — VFD fault diagnosis

Each scenario defines equipment context, symptoms, and situation details (without revealing root cause) for the persona to work through.

---

## Web Application

**Entry point:** `python web_app.py` (Flask, runs on port 5000)

The web UI provides a dashboard for running tests without the CLI:

- **Dashboard** — Browse test cases and personas, launch runs
- **Live Progress** — Server-Sent Events stream for real-time status updates
- **Reports Browser** — View, download, or delete past reports
- **Settings** — Configure environment variables
- **Golden Record Validation** — Review page for technician validation of results

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/run/static` | Start a static test run |
| `POST` | `/api/run/persona` | Start a persona test run |
| `GET` | `/api/run/<run_id>/events` | SSE stream for live updates |
| `GET` | `/api/run/<run_id>/status` | Get current run status |
| `GET` | `/api/reports` | List all reports |
| `DELETE` | `/api/reports/<filename>` | Delete a report |
| `POST` | `/api/session/clear` | Clear saved browser session |

---

## Process Flow Diagram

```
                    ┌─────────────────────────┐
                    │   CLI / Web Dashboard    │
                    └────────┬────────────────-┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
     ┌────────▼────────┐          ┌─────────▼─────────┐
     │  Static Tests   │          │  Persona Tests    │
     │  (run_agent.py) │          │(run_persona_tests)│
     └────────┬────────┘          └─────────┬─────────┘
              │                             │
              │                    ┌────────▼────────┐
              │                    │ Question Gen.   │
              │                    │ (Claude LLM)    │
              │                    └────────┬────────┘
              │                             │
     ┌────────▼─────────────────────────────▼────────┐
     │          Browser Automation (agent.py)         │
     │  ┌──────────────────────────────────────────┐  │
     │  │  Session Manager (login persistence)     │  │
     │  │  Input Detection → Submit → Wait → Capture│  │
     │  └──────────────────────────────────────────┘  │
     └────────┬─────────────────────────────┬────────┘
              │                             │
     ┌────────▼────────┐          ┌─────────▼─────────┐
     │ Keyword/PDF     │          │ LLM Evaluation    │
     │ Validation      │          │ (6 dimensions)    │
     │ (validators.py) │          │ + Reference Check │
     └────────┬────────┘          └─────────┬─────────┘
              │                             │
              │                    ┌────────▼────────┐
              │                    │ Coherence       │
              │                    │ Analysis        │
              │                    └────────┬────────┘
              │                             │
     ┌────────▼─────────────────────────────▼────────┐
     │           Report Generation                    │
     │   HTML + JSON → reports/ directory             │
     └────────────────────────────────────────────────┘
```

---

## Key Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required for persona tests and LLM evaluation |
| `HEADLESS` | `false` | Run browser without visible window |
| `SLOW_MO` | `500` | Milliseconds between browser actions |
| `TIMEOUT` | `60000` | Default timeout for page operations (ms) |

Session data is stored in `.session/auth_state.json` and is valid for 12 hours.

Reports are saved to the `reports/` directory in both HTML and JSON formats.
