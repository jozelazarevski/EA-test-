"""
Persona-Based Report Generator for HVAC Testing Agent.

Generates rich HTML and JSON reports from persona-driven test results,
including LLM evaluation scores, dimension breakdowns, and conversation flows.
"""

import json
from datetime import datetime
from pathlib import Path

from config import REPORTS_DIR


class PersonaReportGenerator:
    """Generates detailed reports from persona-based test results."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.report_dir = REPORTS_DIR
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, results: list) -> Path:
        """Generate both HTML and JSON reports."""
        self._generate_json(results)
        html_path = self._generate_html(results)
        print(f"[Report] Persona report: {html_path}")
        return html_path

    def _generate_json(self, results: list) -> Path:
        """Save raw results as JSON."""
        path = self.report_dir / f"persona_report_{self.run_id}.json"
        report = {
            "run_id": self.run_id,
            "timestamp": datetime.now().isoformat(),
            "results": results,
        }
        with open(path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        return path

    def _generate_html(self, results: list) -> Path:
        """Generate a comprehensive HTML report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Compute global stats
        total_personas = len(results)
        total_turns = sum(r["aggregate_scores"].get("total_turns", 0) for r in results)
        all_scores = [r["aggregate_scores"]["avg_score"] for r in results if r["aggregate_scores"].get("avg_score")]
        global_avg = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
        total_pass = sum(r["aggregate_scores"].get("passed", 0) for r in results)
        total_fail = sum(r["aggregate_scores"].get("failed", 0) for r in results)
        global_pass_rate = f"{(total_pass / (total_pass + total_fail) * 100):.0f}%" if (total_pass + total_fail) > 0 else "N/A"
        all_red_flags = []
        for r in results:
            all_red_flags.extend(r["aggregate_scores"].get("red_flags", []))

        # Build persona summary cards
        persona_cards = ""
        for r in results:
            p = r["persona"]
            agg = r["aggregate_scores"]
            score_color = self._score_color(agg.get("avg_score", 0))
            dims = agg.get("dimension_averages", {})
            dim_bars = ""
            for dim_name, dim_score in dims.items():
                bar_width = dim_score * 10
                bar_color = self._score_color(dim_score)
                dim_bars += f"""
                <div class="dim-row">
                    <span class="dim-label">{dim_name.title()}</span>
                    <div class="dim-bar-bg">
                        <div class="dim-bar" style="width:{bar_width}%;background:{bar_color}"></div>
                    </div>
                    <span class="dim-score">{dim_score}</span>
                </div>"""

            flags_html = ""
            if agg.get("red_flags"):
                flags_html = '<div class="red-flags"><strong>Red Flags:</strong><ul>'
                for flag in agg["red_flags"][:5]:
                    flags_html += f"<li>{self._escape(flag)}</li>"
                flags_html += "</ul></div>"

            persona_cards += f"""
            <div class="persona-card">
                <div class="persona-header">
                    <div class="persona-score" style="border-color:{score_color}">
                        <span style="color:{score_color}">{agg.get('avg_score', 0)}</span>
                        <small>/10</small>
                    </div>
                    <div class="persona-info">
                        <h3>{self._escape(p['name'])}</h3>
                        <p class="persona-role">{self._escape(p['role'])} &mdash; {p['experience_years']}y exp, {p['expertise_level']}</p>
                        <p class="persona-meta">
                            {agg.get('total_turns', 0)} evaluations &bull;
                            {agg.get('pass_rate', 'N/A')} pass rate &bull;
                            Range: {agg.get('min_score', 0)}-{agg.get('max_score', 0)}/10
                        </p>
                    </div>
                </div>
                <div class="dimensions">
                    {dim_bars}
                </div>
                {flags_html}
            </div>"""

        # Build conversation details
        conversation_html = ""
        for r in results:
            p = r["persona"]
            conversation_html += f'<h2 class="persona-section-title">{self._escape(p["name"])}</h2>'

            for c_idx, conv in enumerate(r["conversations"]):
                q_data = conv["question_data"]
                conversation_html += f"""
                <div class="conversation">
                    <div class="conv-header">
                        <span class="conv-label">Conversation {c_idx + 1}</span>
                        <span class="conv-domain">{self._escape(q_data.get('domain', ''))}</span>
                        <span class="conv-intent">{self._escape(q_data.get('intent', ''))}</span>
                    </div>"""

                for t_idx, turn in enumerate(conv["turns"]):
                    eval_data = conv["evaluations"][t_idx] if t_idx < len(conv["evaluations"]) else {}
                    turn_score = eval_data.get("overall_score", "?")
                    turn_pass = eval_data.get("pass", False)
                    score_badge_class = "badge-pass" if turn_pass else "badge-fail"
                    is_followup = t_idx > 0

                    # Evaluation details
                    eval_html = ""
                    if eval_data.get("dimensions"):
                        eval_html += '<div class="eval-details">'
                        for dim, data in eval_data["dimensions"].items():
                            s = data.get("score", 0)
                            eval_html += f'<div class="eval-dim"><strong>{dim}:</strong> {s}/10 — {self._escape(data.get("feedback", ""))}</div>'
                        eval_html += "</div>"

                    strengths_html = ""
                    if eval_data.get("strengths"):
                        strengths_html = "<strong>Strengths:</strong> " + ", ".join(self._escape(s) for s in eval_data["strengths"])

                    weaknesses_html = ""
                    if eval_data.get("weaknesses"):
                        weaknesses_html = "<strong>Weaknesses:</strong> " + ", ".join(self._escape(w) for w in eval_data["weaknesses"])

                    fu_meta = ""
                    if is_followup and turn.get("follow_up_metadata"):
                        fm = turn["follow_up_metadata"]
                        fu_meta = f"""
                        <div class="fu-meta">
                            Follow-up type: {self._escape(fm.get('follow_up_type', ''))} &bull;
                            Satisfaction: {self._escape(fm.get('satisfaction_with_previous', ''))} &bull;
                            Reason: {self._escape(fm.get('reason', ''))}
                        </div>"""

                    error_html = ""
                    if turn.get("error"):
                        error_html = f'<div class="turn-error">Error: {self._escape(turn["error"])}</div>'

                    conversation_html += f"""
                    <div class="turn {'turn-followup' if is_followup else ''}">
                        <div class="turn-header">
                            <span class="turn-label">{'Follow-up' if is_followup else 'Question'}</span>
                            <span class="score-badge {score_badge_class}">{turn_score}/10</span>
                            <span class="response-time">{turn.get('response_time', 0)}s</span>
                        </div>
                        {fu_meta}
                        <div class="turn-question">
                            <strong>Q:</strong> {self._escape(turn['question'])}
                        </div>
                        <div class="turn-response">
                            <strong>A:</strong> {self._escape((turn.get('response') or '')[:800])}
                            {'...' if len(turn.get('response') or '') > 800 else ''}
                        </div>
                        {error_html}
                        {eval_html}
                        <div class="eval-summary">
                            {strengths_html}
                            {('<br>' if strengths_html and weaknesses_html else '') + weaknesses_html}
                        </div>
                        {'<div class="eval-verdict">' + self._escape(eval_data.get("summary", "")) + '</div>' if eval_data.get("summary") else ''}
                    </div>"""

                # Coherence evaluation
                if r.get("coherence_evaluation"):
                    ce = r["coherence_evaluation"]
                    conversation_html += f"""
                    <div class="coherence-eval">
                        <strong>Conversation Coherence:</strong>
                        Score: {ce.get('overall_conversation_score', '?')}/10 &bull;
                        Context Retention: {ce.get('context_retention', '?')}/10 &bull;
                        No Contradictions: {ce.get('contradiction_check', '?')}/10
                        <br>{self._escape(ce.get('summary', ''))}
                    </div>"""

                conversation_html += "</div>"  # .conversation

        # Red flags section
        red_flags_section = ""
        if all_red_flags:
            red_flags_section = """
            <div class="red-flags-global">
                <h2>Red Flags</h2>
                <ul>"""
            for flag in all_red_flags:
                red_flags_section += f"<li>{self._escape(flag)}</li>"
            red_flags_section += "</ul></div>"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HVAC EA Persona Test Report — {self.run_id}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; color: #1a202c; padding: 24px; line-height: 1.5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ font-size: 26px; color: #1a365d; margin-bottom: 4px; }}
        .subtitle {{ color: #718096; margin-bottom: 24px; font-size: 14px; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 30px; }}
        .stat-card {{ background: white; border-radius: 10px; padding: 18px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
        .stat-card .number {{ font-size: 32px; font-weight: 700; }}
        .stat-card .label {{ font-size: 12px; color: #718096; margin-top: 2px; }}

        .persona-card {{ background: white; border-radius: 10px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
        .persona-header {{ display: flex; align-items: center; gap: 16px; margin-bottom: 14px; }}
        .persona-score {{ width: 64px; height: 64px; border-radius: 50%; border: 4px solid; display: flex; flex-direction: column; align-items: center; justify-content: center; flex-shrink: 0; }}
        .persona-score span {{ font-size: 22px; font-weight: 700; }}
        .persona-score small {{ font-size: 10px; color: #a0aec0; }}
        .persona-info h3 {{ font-size: 16px; margin-bottom: 2px; }}
        .persona-role {{ font-size: 13px; color: #4a5568; }}
        .persona-meta {{ font-size: 12px; color: #a0aec0; margin-top: 2px; }}

        .dimensions {{ margin-top: 8px; }}
        .dim-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }}
        .dim-label {{ width: 90px; font-size: 12px; color: #4a5568; text-align: right; }}
        .dim-bar-bg {{ flex: 1; height: 8px; background: #edf2f7; border-radius: 4px; overflow: hidden; }}
        .dim-bar {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
        .dim-score {{ width: 28px; font-size: 12px; font-weight: 600; color: #2d3748; }}

        .red-flags, .red-flags-global {{ background: #fff5f5; border: 1px solid #feb2b2; border-radius: 8px; padding: 12px; margin-top: 10px; font-size: 13px; color: #c53030; }}
        .red-flags ul, .red-flags-global ul {{ margin-left: 18px; margin-top: 4px; }}
        .red-flags-global {{ margin-bottom: 20px; }}
        .red-flags-global h2 {{ color: #c53030; font-size: 16px; margin-bottom: 6px; }}

        h2 {{ font-size: 18px; color: #2d3748; margin: 24px 0 12px; }}
        .persona-section-title {{ margin-top: 32px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; }}

        .conversation {{ background: white; border-radius: 10px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
        .conv-header {{ display: flex; gap: 12px; align-items: center; margin-bottom: 12px; font-size: 13px; }}
        .conv-label {{ font-weight: 700; color: #2d3748; }}
        .conv-domain {{ background: #ebf8ff; color: #2b6cb0; padding: 2px 8px; border-radius: 4px; }}
        .conv-intent {{ color: #718096; font-style: italic; }}

        .turn {{ border-left: 3px solid #e2e8f0; padding: 10px 14px; margin-bottom: 12px; }}
        .turn-followup {{ border-left-color: #bee3f8; background: #fafcff; }}
        .turn-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }}
        .turn-label {{ font-weight: 600; font-size: 12px; color: #4a5568; }}
        .score-badge {{ padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 700; }}
        .badge-pass {{ background: #c6f6d5; color: #276749; }}
        .badge-fail {{ background: #fed7d7; color: #9b2c2c; }}
        .response-time {{ font-size: 11px; color: #a0aec0; }}

        .fu-meta {{ font-size: 11px; color: #718096; margin-bottom: 6px; background: #f7fafc; padding: 4px 8px; border-radius: 4px; }}
        .turn-question {{ font-size: 13px; margin-bottom: 6px; }}
        .turn-response {{ font-size: 13px; color: #4a5568; margin-bottom: 8px; white-space: pre-wrap; }}
        .turn-error {{ color: #e53e3e; font-size: 12px; margin-bottom: 6px; }}

        .eval-details {{ font-size: 12px; margin-bottom: 6px; }}
        .eval-dim {{ margin-bottom: 3px; color: #4a5568; }}
        .eval-summary {{ font-size: 12px; color: #4a5568; }}
        .eval-verdict {{ font-size: 13px; font-style: italic; color: #2d3748; margin-top: 6px; padding-top: 6px; border-top: 1px solid #edf2f7; }}

        .coherence-eval {{ background: #ebf8ff; border-radius: 8px; padding: 12px; margin-top: 8px; font-size: 13px; color: #2b6cb0; }}

        .footer {{ text-align: center; color: #a0aec0; font-size: 12px; margin-top: 40px; }}
    </style>
</head>
<body>
<div class="container">
    <h1>HVAC Expert Advisor — Persona Test Report</h1>
    <p class="subtitle">Run: {self.run_id} | Generated: {timestamp} | Target: expertadvisor.jci.com</p>

    <div class="summary-grid">
        <div class="stat-card"><div class="number">{total_personas}</div><div class="label">Personas</div></div>
        <div class="stat-card"><div class="number">{total_turns}</div><div class="label">Evaluations</div></div>
        <div class="stat-card"><div class="number" style="color:{self._score_color(global_avg)}">{global_avg}</div><div class="label">Avg Score /10</div></div>
        <div class="stat-card"><div class="number" style="color:#38a169">{total_pass}</div><div class="label">Passed</div></div>
        <div class="stat-card"><div class="number" style="color:#e53e3e">{total_fail}</div><div class="label">Failed</div></div>
        <div class="stat-card"><div class="number">{global_pass_rate}</div><div class="label">Pass Rate</div></div>
    </div>

    {red_flags_section}

    <h2>Persona Scorecards</h2>
    {persona_cards}

    <h2>Conversation Details</h2>
    {conversation_html}

    <div class="footer">HVAC Expert Advisor Persona Testing Agent | Automated Report</div>
</div>
</body>
</html>"""

        path = self.report_dir / f"persona_report_{self.run_id}.html"
        with open(path, "w") as f:
            f.write(html)
        return path

    @staticmethod
    def _score_color(score: float) -> str:
        if score >= 8:
            return "#38a169"
        elif score >= 6:
            return "#d69e2e"
        elif score >= 4:
            return "#dd6b20"
        else:
            return "#e53e3e"

    @staticmethod
    def _escape(text: str) -> str:
        if not text:
            return ""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
