"""
HVAC Testing Agent — Web UI Application

Flask-based web interface for configuring, running, and reviewing
HVAC Expert Advisor tests without using the command line.

Usage:
    python web_app.py
    # Open http://localhost:5000 in your browser
"""

import asyncio
import json
import logging
import os
import queue
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    Response,
    url_for,
)

from config import (
    ANTHROPIC_API_KEY,
    BASE_DIR,
    HEADLESS,
    LLM_MODEL,
    MAX_WAIT_FOR_RESPONSE,
    REPORTS_DIR,
    SESSION_PERSIST,
    TARGET_URL,
)
from hvac_test_cases import TEST_CASES
from personas import PERSONAS

logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.secret_key = os.urandom(24)

# ---------------------------------------------------------------------------
# In-memory run tracker (keyed by run_id)
# ---------------------------------------------------------------------------

_runs: dict[str, dict] = {}
_run_lock = threading.Lock()


def _get_run(run_id: str) -> dict | None:
    with _run_lock:
        return _runs.get(run_id)


def _set_run(run_id: str, data: dict):
    with _run_lock:
        _runs[run_id] = data


# ---------------------------------------------------------------------------
# Routes — Pages
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    """Dashboard home page."""
    # Gather recent reports
    reports = _list_reports()
    categories = sorted({tc["category"] for tc in TEST_CASES})
    persona_tiers = {
        "technicians": [p for p in PERSONAS if p["id"].startswith("TECH")],
        "engineers": [p for p in PERSONAS if p["id"].startswith("ENG")],
        "management": [p for p in PERSONAS if p["id"].startswith("MGR")],
        "adversarial": [p for p in PERSONAS if p["id"].startswith("ADV")],
    }
    has_api_key = bool(ANTHROPIC_API_KEY)
    return render_template(
        "dashboard.html",
        test_cases=TEST_CASES,
        categories=categories,
        personas=PERSONAS,
        persona_tiers=persona_tiers,
        reports=reports[:20],
        has_api_key=has_api_key,
        target_url=TARGET_URL,
        llm_model=LLM_MODEL,
        active_runs=_get_active_runs(),
    )


@app.route("/reports")
def reports_page():
    """Browse all past reports."""
    reports = _list_reports()
    return render_template("reports.html", reports=reports)


@app.route("/reports/<path:filename>")
def serve_report(filename):
    """Serve a generated report file."""
    report_path = REPORTS_DIR / filename
    if not report_path.exists() or not str(report_path.resolve()).startswith(
        str(REPORTS_DIR.resolve())
    ):
        return "Report not found", 404
    return report_path.read_text(), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/settings")
def settings_page():
    """Settings and configuration page."""
    env_path = BASE_DIR / ".env"
    env_content = ""
    if env_path.exists():
        env_content = env_path.read_text()
    return render_template(
        "settings.html",
        target_url=TARGET_URL,
        llm_model=LLM_MODEL,
        headless=HEADLESS,
        max_wait=MAX_WAIT_FOR_RESPONSE,
        session_persist=SESSION_PERSIST,
        has_api_key=bool(ANTHROPIC_API_KEY),
        env_content=env_content,
    )


@app.route("/run/<run_id>")
def run_detail(run_id):
    """Live view of a running or completed test run."""
    run = _get_run(run_id)
    if not run:
        return "Run not found", 404
    return render_template("run_detail.html", run_id=run_id, run=run)


# ---------------------------------------------------------------------------
# Routes — API
# ---------------------------------------------------------------------------


@app.route("/api/run/static", methods=["POST"])
def api_run_static():
    """Start a static test run."""
    data = request.json or {}
    test_ids = data.get("test_ids", [])
    category = data.get("category")
    headless = data.get("headless", True)

    # Resolve test IDs
    if category:
        test_ids = [tc["id"] for tc in TEST_CASES if tc["category"] == category]
    elif not test_ids:
        test_ids = [tc["id"] for tc in TEST_CASES]

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    event_queue = queue.Queue()

    run_data = {
        "run_id": run_id,
        "type": "static",
        "status": "starting",
        "started_at": datetime.now().isoformat(),
        "test_ids": test_ids,
        "headless": headless,
        "events": event_queue,
        "progress": 0,
        "total": len(test_ids),
        "results": [],
        "report_path": None,
        "error": None,
    }
    _set_run(run_id, run_data)

    thread = threading.Thread(
        target=_run_static_tests,
        args=(run_id, test_ids, headless),
        daemon=True,
    )
    thread.start()

    return jsonify({"run_id": run_id, "total": len(test_ids)})


@app.route("/api/run/persona", methods=["POST"])
def api_run_persona():
    """Start a persona-based test run."""
    if not ANTHROPIC_API_KEY:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured. Set it in Settings."}), 400

    data = request.json or {}
    persona_ids = data.get("persona_ids", [])
    tier = data.get("tier")
    questions = data.get("questions_per_persona", 3)
    follow_ups = data.get("follow_ups_per_question", 1)
    headless = data.get("headless", True)
    model = data.get("model") or LLM_MODEL

    # Resolve personas
    if tier:
        prefix_map = {
            "technicians": "TECH",
            "engineers": "ENG",
            "management": "MGR",
            "adversarial": "ADV",
        }
        prefix = prefix_map.get(tier, "")
        selected = [p for p in PERSONAS if p["id"].startswith(prefix)]
    elif persona_ids:
        id_set = set(persona_ids)
        selected = [p for p in PERSONAS if p["id"] in id_set]
    else:
        selected = PERSONAS

    if not selected:
        return jsonify({"error": "No personas selected"}), 400

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    event_queue = queue.Queue()

    total_evals = len(selected) * questions * (1 + follow_ups)
    run_data = {
        "run_id": run_id,
        "type": "persona",
        "status": "starting",
        "started_at": datetime.now().isoformat(),
        "personas": [p["id"] for p in selected],
        "questions_per_persona": questions,
        "follow_ups_per_question": follow_ups,
        "model": model,
        "headless": headless,
        "events": event_queue,
        "progress": 0,
        "total": total_evals,
        "results": [],
        "report_path": None,
        "error": None,
    }
    _set_run(run_id, run_data)

    thread = threading.Thread(
        target=_run_persona_tests,
        args=(run_id, selected, questions, follow_ups, headless, model),
        daemon=True,
    )
    thread.start()

    return jsonify({"run_id": run_id, "total": total_evals, "personas": len(selected)})


@app.route("/api/run/<run_id>/events")
def api_run_events(run_id):
    """Server-Sent Events stream for live run updates."""
    run = _get_run(run_id)
    if not run:
        return "Run not found", 404

    def generate():
        q = run["events"]
        # Send current state
        yield _sse_data({
            "type": "status",
            "status": run["status"],
            "progress": run["progress"],
            "total": run["total"],
        })

        while True:
            try:
                event = q.get(timeout=30)
                yield _sse_data(event)
                if event.get("type") == "complete" or event.get("type") == "error":
                    break
            except queue.Empty:
                yield _sse_data({"type": "heartbeat"})

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/run/<run_id>/status")
def api_run_status(run_id):
    """Get current run status."""
    run = _get_run(run_id)
    if not run:
        return jsonify({"error": "Run not found"}), 404
    return jsonify({
        "run_id": run_id,
        "type": run["type"],
        "status": run["status"],
        "progress": run["progress"],
        "total": run["total"],
        "report_path": run.get("report_path"),
        "error": run.get("error"),
    })


@app.route("/api/reports")
def api_reports():
    """List all reports."""
    return jsonify(_list_reports())


@app.route("/api/reports/<path:filename>", methods=["DELETE"])
def api_delete_report(filename):
    """Delete a report file."""
    report_path = REPORTS_DIR / filename
    if report_path.exists() and str(report_path.resolve()).startswith(
        str(REPORTS_DIR.resolve())
    ):
        report_path.unlink()
        # Also delete companion JSON
        json_path = report_path.with_suffix(".json")
        if json_path.exists():
            json_path.unlink()
        return jsonify({"deleted": filename})
    return jsonify({"error": "Not found"}), 404


@app.route("/api/session/clear", methods=["POST"])
def api_clear_session():
    """Clear saved browser session."""
    try:
        from session_manager import SessionManager
        SessionManager().clear()
        return jsonify({"status": "Session cleared"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    """Save .env settings."""
    data = request.json or {}
    env_content = data.get("env_content", "")
    env_path = BASE_DIR / ".env"
    env_path.write_text(env_content)
    return jsonify({"status": "Settings saved. Restart the app to apply changes."})


# ---------------------------------------------------------------------------
# Background test runners
# ---------------------------------------------------------------------------


def _emit(run_id: str, event: dict):
    """Push an event to the run's event queue."""
    run = _get_run(run_id)
    if run and run.get("events"):
        run["events"].put(event)


def _run_static_tests(run_id: str, test_ids: list, headless: bool):
    """Run static tests in a background thread."""
    from agent import HVACTestingAgent

    run = _get_run(run_id)
    run["status"] = "running"
    _emit(run_id, {"type": "status", "status": "running", "message": "Launching browser..."})

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        agent = HVACTestingAgent(headless=headless, test_ids=test_ids, persist_session=SESSION_PERSIST)
        loop.run_until_complete(agent.setup())
        _emit(run_id, {"type": "status", "status": "running", "message": "Browser ready. Running tests..."})

        for i, test_id in enumerate(test_ids):
            tc = next((t for t in TEST_CASES if t["id"] == test_id), None)
            if not tc:
                continue

            _emit(run_id, {
                "type": "test_start",
                "test_id": test_id,
                "question": tc["question"][:100],
                "progress": i,
                "total": len(test_ids),
            })

            result = loop.run_until_complete(agent.run_test_case(tc))
            passed = result.get("validation_results", {}).get("overall_pass", False)

            run["progress"] = i + 1
            run["results"].append(result)

            _emit(run_id, {
                "type": "test_result",
                "test_id": test_id,
                "passed": passed,
                "score": "PASS" if passed else "FAIL",
                "response_time": result.get("response_time", 0),
                "progress": i + 1,
                "total": len(test_ids),
            })

        # Generate report
        _emit(run_id, {"type": "status", "status": "generating_report", "message": "Generating report..."})
        from report_generator import ReportGenerator
        gen = ReportGenerator(run_id)
        report_path = gen.generate(agent.results)

        run["status"] = "complete"
        run["report_path"] = str(report_path.name)

        _emit(run_id, {
            "type": "complete",
            "report_path": str(report_path.name),
            "total_tests": len(test_ids),
            "passed": sum(1 for r in agent.results if r.get("validation_results", {}).get("overall_pass")),
        })

        loop.run_until_complete(agent.teardown())

    except Exception as e:
        logger.exception("Static test run failed")
        run["status"] = "error"
        run["error"] = str(e)
        _emit(run_id, {"type": "error", "message": str(e)})
    finally:
        loop.close()


def _run_persona_tests(
    run_id: str,
    personas: list,
    questions: int,
    follow_ups: int,
    headless: bool,
    model: str,
):
    """Run persona tests in a background thread."""
    from agent import HVACTestingAgent
    from question_generator import generate_questions, generate_follow_up, generate_adversarial_inputs
    from llm_evaluator import evaluate_response, evaluate_conversation_coherence
    from report_generator_persona import PersonaReportGenerator

    run = _get_run(run_id)
    run["status"] = "running"
    _emit(run_id, {"type": "status", "status": "running", "message": "Launching browser..."})

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        agent = HVACTestingAgent(headless=headless, persist_session=SESSION_PERSIST)
        loop.run_until_complete(agent.setup())
        _emit(run_id, {"type": "status", "status": "running", "message": "Browser ready. Running persona tests..."})

        all_results = []
        eval_count = 0

        for p_idx, persona in enumerate(personas):
            _emit(run_id, {
                "type": "persona_start",
                "persona_id": persona["id"],
                "persona_name": persona["name"],
                "persona_idx": p_idx + 1,
                "total_personas": len(personas),
            })

            persona_result = {
                "persona": persona,
                "conversations": [],
                "coherence_evaluation": None,
                "aggregate_scores": {},
            }

            # Generate questions
            is_adversarial = "ADV" in persona["id"]
            if is_adversarial:
                adversarial_inputs = generate_adversarial_inputs(persona, questions, model=model)
                q_list = [
                    {"question": inp["input"], "intent": inp["expected_behavior"],
                     "expected_depth": "basic", "domain": inp["attack_type"]}
                    for inp in adversarial_inputs
                ]
            else:
                q_list = generate_questions(persona, questions, model=model)

            if not q_list:
                q_list = [
                    {"question": d, "intent": "fallback", "expected_depth": "basic", "domain": "general"}
                    for d in persona["question_domains"][:questions]
                ]

            for q_idx, q_data in enumerate(q_list):
                question = q_data["question"]
                _emit(run_id, {
                    "type": "question_start",
                    "persona_id": persona["id"],
                    "question": question[:120],
                    "q_idx": q_idx + 1,
                    "total_q": len(q_list),
                })

                conversation = {"question_data": q_data, "turns": [], "evaluations": []}

                # Send question
                response = loop.run_until_complete(agent.send_question(question))
                response_text = response["response_text"]

                conversation["turns"].append({
                    "question": question,
                    "response": response_text,
                    "response_time": response["response_time"],
                    "pdf_links": response["pdf_links"],
                    "error": response.get("error"),
                })

                # Evaluate
                evaluation = evaluate_response(persona, question, response_text, model=model)
                conversation["evaluations"].append(evaluation)
                eval_count += 1
                run["progress"] = eval_count

                score = evaluation.get("overall_score", 0)
                tier = evaluation.get("quality_tier", "unknown")
                _emit(run_id, {
                    "type": "evaluation",
                    "persona_id": persona["id"],
                    "score": score,
                    "tier": tier,
                    "progress": eval_count,
                    "total": run["total"],
                })

                # Follow-ups
                history = [{"question": question, "response": response_text}]
                for fu_idx in range(follow_ups):
                    if response.get("error"):
                        break
                    fu_data = generate_follow_up(
                        persona, question, response_text,
                        conversation_history=history, model=model,
                    )
                    fu_q = fu_data.get("follow_up", "")
                    if not fu_q:
                        break

                    fu_resp = loop.run_until_complete(agent.send_question(fu_q))
                    conversation["turns"].append({
                        "question": fu_q,
                        "response": fu_resp["response_text"],
                        "response_time": fu_resp["response_time"],
                        "pdf_links": fu_resp["pdf_links"],
                        "error": fu_resp.get("error"),
                        "follow_up_metadata": fu_data,
                    })

                    fu_eval = evaluate_response(
                        persona, fu_q, fu_resp["response_text"],
                        conversation_history=history, model=model,
                    )
                    conversation["evaluations"].append(fu_eval)
                    eval_count += 1
                    run["progress"] = eval_count

                    _emit(run_id, {
                        "type": "evaluation",
                        "persona_id": persona["id"],
                        "score": fu_eval.get("overall_score", 0),
                        "tier": fu_eval.get("quality_tier", "unknown"),
                        "is_followup": True,
                        "progress": eval_count,
                        "total": run["total"],
                    })

                    history.append({"question": fu_q, "response": fu_resp["response_text"]})
                    loop.run_until_complete(asyncio.sleep(2))

                persona_result["conversations"].append(conversation)
                loop.run_until_complete(asyncio.sleep(3))

            # Coherence
            if len(persona_result["conversations"]) > 1:
                all_turns = []
                for conv in persona_result["conversations"]:
                    all_turns.extend(conv["turns"])
                if len(all_turns) >= 2:
                    coherence = evaluate_conversation_coherence(persona, all_turns, model=model)
                    persona_result["coherence_evaluation"] = coherence

            # Aggregate
            all_evals = []
            for conv in persona_result["conversations"]:
                all_evals.extend(conv["evaluations"])
            if all_evals:
                scores = [e.get("overall_score", 0) for e in all_evals]
                passes = sum(1 for e in all_evals if e.get("pass"))
                dims = {}
                for dim in ["accuracy", "completeness", "relevance", "clarity", "safety", "persona_fit"]:
                    ds = [e["dimensions"][dim]["score"] for e in all_evals
                          if "dimensions" in e and dim in e.get("dimensions", {})]
                    if ds:
                        dims[dim] = round(sum(ds) / len(ds), 1)
                red_flags = []
                for e in all_evals:
                    red_flags.extend(e.get("red_flags", []))

                persona_result["aggregate_scores"] = {
                    "avg_score": round(sum(scores) / len(scores), 1),
                    "min_score": min(scores),
                    "max_score": max(scores),
                    "pass_rate": f"{passes / len(scores) * 100:.0f}%",
                    "passed": passes,
                    "failed": len(scores) - passes,
                    "total_turns": len(scores),
                    "dimension_averages": dims,
                    "red_flags": red_flags,
                }

            all_results.append(persona_result)

            _emit(run_id, {
                "type": "persona_complete",
                "persona_id": persona["id"],
                "avg_score": persona_result.get("aggregate_scores", {}).get("avg_score", 0),
            })

        # Report
        _emit(run_id, {"type": "status", "status": "generating_report", "message": "Generating report..."})
        gen = PersonaReportGenerator(run_id)
        report_path = gen.generate(all_results)

        run["status"] = "complete"
        run["report_path"] = str(report_path.name)
        run["results"] = all_results

        _emit(run_id, {
            "type": "complete",
            "report_path": str(report_path.name),
            "total_evals": eval_count,
        })

        loop.run_until_complete(agent.teardown())

    except Exception as e:
        logger.exception("Persona test run failed")
        run["status"] = "error"
        run["error"] = str(e)
        _emit(run_id, {"type": "error", "message": str(e)})
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _list_reports() -> list[dict]:
    """List all report files sorted by modification time (newest first)."""
    reports = []
    if REPORTS_DIR.exists():
        for f in sorted(REPORTS_DIR.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = f.stat()
            # Determine type
            rtype = "persona" if "persona" in f.name else "static"
            json_companion = f.with_suffix(".json")
            reports.append({
                "filename": f.name,
                "type": rtype,
                "size_kb": round(stat.st_size / 1024, 1),
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "has_json": json_companion.exists(),
            })
    return reports


def _get_active_runs() -> list[dict]:
    """Get all currently active runs."""
    with _run_lock:
        return [
            {"run_id": rid, "type": r["type"], "status": r["status"],
             "progress": r["progress"], "total": r["total"]}
            for rid, r in _runs.items()
            if r["status"] in ("starting", "running", "generating_report")
        ]


def _sse_data(data: dict) -> str:
    """Format data as SSE message."""
    return f"data: {json.dumps(data)}\n\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("\n" + "=" * 60)
    print("  HVAC Testing Agent — Web UI")
    print("  Open http://localhost:5000 in your browser")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
