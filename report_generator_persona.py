"""
Persona-Based Report Generator for HVAC Testing Agent.

Generates rich HTML and JSON reports from persona-driven test results,
including:
- Five-tier quality scoring (Exemplary → Critical Failure)
- Weighted dimension breakdowns with reasoning
- Conversation trajectory analysis
- Clear verdict explanations for every evaluation
- Improvement suggestions
"""

import json
from datetime import datetime
from pathlib import Path

from config import REPORTS_DIR


# ---------------------------------------------------------------------------
# Tier rendering helpers
# ---------------------------------------------------------------------------

_TIER_CONFIG = {
    "exemplary":        {"label": "Exemplary",        "color": "#276749", "bg": "#c6f6d5", "icon": "&#9733;&#9733;"},
    "proficient":       {"label": "Proficient",       "color": "#38a169", "bg": "#e6ffed", "icon": "&#9733;"},
    "developing":       {"label": "Developing",       "color": "#d69e2e", "bg": "#fefcbf", "icon": "&#9684;"},
    "unsatisfactory":   {"label": "Unsatisfactory",   "color": "#dd6b20", "bg": "#feebc8", "icon": "&#9661;"},
    "critical_failure": {"label": "Critical Failure",  "color": "#c53030", "bg": "#fed7d7", "icon": "&#10006;"},
}

_WEIGHT_LABELS = {
    "critical": {"label": "CRITICAL", "color": "#c53030"},
    "high":     {"label": "HIGH",     "color": "#dd6b20"},
    "medium":   {"label": "MEDIUM",   "color": "#d69e2e"},
    "low":      {"label": "LOW",      "color": "#718096"},
}

_TRAJECTORY_CONFIG = {
    "improving":  {"label": "Improving",  "icon": "&#8599;", "color": "#38a169"},
    "stable":     {"label": "Stable",     "icon": "&#8594;", "color": "#3182ce"},
    "degrading":  {"label": "Degrading",  "icon": "&#8600;", "color": "#e53e3e"},
    "volatile":   {"label": "Volatile",   "icon": "&#8597;", "color": "#d69e2e"},
}


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
        """Generate a comprehensive HTML report with tiered scoring and reasoning."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ── Global stats ─────────────────────────────────────────────
        total_personas = len(results)
        total_turns = sum(r["aggregate_scores"].get("total_turns", 0) for r in results)
        all_scores = [r["aggregate_scores"]["avg_score"] for r in results if r["aggregate_scores"].get("avg_score")]
        global_avg = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0

        # Tier distribution
        tier_counts = {"exemplary": 0, "proficient": 0, "developing": 0, "unsatisfactory": 0, "critical_failure": 0}
        total_evals = 0
        all_red_flags = []
        for r in results:
            all_red_flags.extend(r["aggregate_scores"].get("red_flags", []))
            for conv in r.get("conversations", []):
                for ev in conv.get("evaluations", []):
                    total_evals += 1
                    tier = ev.get("quality_tier", self._score_to_tier(ev.get("overall_score", 0)))
                    if tier in tier_counts:
                        tier_counts[tier] += 1

        # ── Tier distribution bar ────────────────────────────────────
        tier_bar_html = self._build_tier_distribution_bar(tier_counts, total_evals)

        # ── Persona cards ────────────────────────────────────────────
        persona_cards = ""
        for r in results:
            persona_cards += self._build_persona_card(r)

        # ── Conversation details ─────────────────────────────────────
        conversation_html = ""
        for r in results:
            conversation_html += self._build_conversation_detail(r)

        # ── Red flags section ────────────────────────────────────────
        red_flags_section = ""
        if all_red_flags:
            flags_list = "".join(f"<li>{self._escape(f)}</li>" for f in all_red_flags)
            red_flags_section = f"""
            <div class="red-flags-global">
                <h2>Red Flags ({len(all_red_flags)})</h2>
                <ul>{flags_list}</ul>
            </div>"""

        # ── Assemble HTML ────────────────────────────────────────────
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HVAC EA Persona Test Report — {self.run_id}</title>
    <style>{self._css()}</style>
</head>
<body>
<div class="container">
    <h1>HVAC Expert Advisor — Persona Test Report</h1>
    <p class="subtitle">Run: {self.run_id} | Generated: {timestamp} | Target: expertadvisor.jci.com</p>

    <!-- Global Stats -->
    <div class="summary-grid">
        <div class="stat-card"><div class="number">{total_personas}</div><div class="label">Personas</div></div>
        <div class="stat-card"><div class="number">{total_evals}</div><div class="label">Evaluations</div></div>
        <div class="stat-card"><div class="number" style="color:{self._score_color(global_avg)}">{global_avg}</div><div class="label">Avg Score /10</div></div>
        <div class="stat-card"><div class="number" style="color:#276749">{tier_counts['exemplary'] + tier_counts['proficient']}</div><div class="label">Proficient+</div></div>
        <div class="stat-card"><div class="number" style="color:#dd6b20">{tier_counts['unsatisfactory']}</div><div class="label">Unsatisfactory</div></div>
        <div class="stat-card"><div class="number" style="color:#c53030">{tier_counts['critical_failure']}</div><div class="label">Critical Failures</div></div>
    </div>

    <!-- Tier Distribution -->
    <h2>Quality Tier Distribution</h2>
    {tier_bar_html}

    {red_flags_section}

    <!-- Persona Scorecards -->
    <h2>Persona Scorecards</h2>
    {persona_cards}

    <!-- Conversation Details -->
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

    # ──────────────────────────────────────────────────────────────────
    # Section builders
    # ──────────────────────────────────────────────────────────────────

    def _build_tier_distribution_bar(self, tier_counts: dict, total: int) -> str:
        if total == 0:
            return '<div class="tier-bar"><div class="tier-segment" style="width:100%;background:#edf2f7">No data</div></div>'

        segments = ""
        legend_items = ""
        for tier_key in ["exemplary", "proficient", "developing", "unsatisfactory", "critical_failure"]:
            count = tier_counts.get(tier_key, 0)
            pct = count / total * 100 if total else 0
            cfg = _TIER_CONFIG.get(tier_key, {})
            if count > 0:
                segments += (
                    f'<div class="tier-segment" style="width:{pct:.1f}%;background:{cfg["color"]}" '
                    f'title="{cfg["label"]}: {count} ({pct:.0f}%)">'
                    f'{count}</div>'
                )
            legend_items += (
                f'<span class="tier-legend-item">'
                f'<span class="tier-dot" style="background:{cfg["color"]}"></span>'
                f'{cfg["label"]}: {count} ({pct:.0f}%)</span>'
            )

        return f"""
        <div class="tier-bar">{segments}</div>
        <div class="tier-legend">{legend_items}</div>"""

    def _build_persona_card(self, r: dict) -> str:
        p = r["persona"]
        agg = r["aggregate_scores"]
        avg_score = agg.get("avg_score", 0)
        score_color = self._score_color(avg_score)
        tier_key = self._score_to_tier(avg_score)
        tier_cfg = _TIER_CONFIG.get(tier_key, _TIER_CONFIG["developing"])

        # Dimension bars with weights
        dims = agg.get("dimension_averages", {})
        dim_weights = {"safety": "critical", "accuracy": "high", "completeness": "medium",
                       "relevance": "medium", "clarity": "low", "persona_fit": "low"}
        dim_bars = ""
        for dim_name in ["safety", "accuracy", "completeness", "relevance", "clarity", "persona_fit"]:
            dim_score = dims.get(dim_name, 0)
            bar_width = dim_score * 10
            bar_color = self._score_color(dim_score)
            weight_key = dim_weights.get(dim_name, "medium")
            weight_cfg = _WEIGHT_LABELS.get(weight_key, _WEIGHT_LABELS["medium"])
            dim_bars += f"""
                <div class="dim-row">
                    <span class="dim-label">{dim_name.title()}</span>
                    <span class="weight-badge" style="color:{weight_cfg['color']}">{weight_cfg['label']}</span>
                    <div class="dim-bar-bg">
                        <div class="dim-bar" style="width:{bar_width}%;background:{bar_color}"></div>
                    </div>
                    <span class="dim-score">{dim_score}</span>
                </div>"""

        # Red flags
        flags_html = ""
        if agg.get("red_flags"):
            flags_list = "".join(f"<li>{self._escape(f)}</li>" for f in agg["red_flags"][:5])
            flags_html = f'<div class="red-flags"><strong>Red Flags:</strong><ul>{flags_list}</ul></div>'

        return f"""
        <div class="persona-card">
            <div class="persona-header">
                <div class="persona-score" style="border-color:{score_color}">
                    <span style="color:{score_color}">{avg_score}</span>
                    <small>/10</small>
                </div>
                <div class="persona-info">
                    <h3>{self._escape(p['name'])}</h3>
                    <p class="persona-role">{self._escape(p['role'])} &mdash; {p['experience_years']}y exp, {p['expertise_level']}</p>
                    <div class="tier-badge" style="background:{tier_cfg['bg']};color:{tier_cfg['color']}">
                        {tier_cfg['icon']} {tier_cfg['label']}
                    </div>
                    <p class="persona-meta">
                        {agg.get('total_turns', 0)} evaluations &bull;
                        Range: {agg.get('min_score', 0)}-{agg.get('max_score', 0)}/10
                    </p>
                </div>
            </div>
            <div class="dimensions">{dim_bars}</div>
            {flags_html}
        </div>"""

    def _build_conversation_detail(self, r: dict) -> str:
        p = r["persona"]
        html = f'<h2 class="persona-section-title">{self._escape(p["name"])}</h2>'

        for c_idx, conv in enumerate(r.get("conversations", [])):
            q_data = conv.get("question_data", {})
            html += f"""
            <div class="conversation">
                <div class="conv-header">
                    <span class="conv-label">Conversation {c_idx + 1}</span>
                    <span class="conv-domain">{self._escape(q_data.get('domain', ''))}</span>
                    <span class="conv-intent">{self._escape(q_data.get('intent', ''))}</span>
                </div>"""

            for t_idx, turn in enumerate(conv.get("turns", [])):
                eval_data = conv["evaluations"][t_idx] if t_idx < len(conv.get("evaluations", [])) else {}
                html += self._build_turn_html(turn, eval_data, t_idx)

            # Coherence evaluation
            if r.get("coherence_evaluation"):
                html += self._build_coherence_html(r["coherence_evaluation"])

            html += "</div>"  # .conversation

        return html

    def _build_turn_html(self, turn: dict, eval_data: dict, t_idx: int) -> str:
        turn_score = eval_data.get("overall_score", "?")
        tier_key = eval_data.get("quality_tier", self._score_to_tier(turn_score if isinstance(turn_score, (int, float)) else 0))
        tier_cfg = _TIER_CONFIG.get(tier_key, _TIER_CONFIG["developing"])
        is_followup = t_idx > 0

        # ── Tier badge (replaces binary pass/fail) ────────────────
        tier_badge = (
            f'<span class="tier-badge-sm" style="background:{tier_cfg["bg"]};color:{tier_cfg["color"]}">'
            f'{tier_cfg["icon"]} {turn_score}/10 {tier_cfg["label"]}</span>'
        )

        # ── Reasoning chain (the "why") ───────────────────────────
        reasoning_html = ""
        reasoning_chain = eval_data.get("reasoning_chain", [])
        if reasoning_chain:
            steps = "".join(f"<li>{self._escape(step)}</li>" for step in reasoning_chain)
            reasoning_html = f"""
            <details class="reasoning-section">
                <summary>Reasoning Chain ({len(reasoning_chain)} steps)</summary>
                <ol class="reasoning-chain">{steps}</ol>
            </details>"""

        # ── Verdict explanation ───────────────────────────────────
        verdict_html = ""
        verdict = eval_data.get("verdict_explanation", "") or eval_data.get("summary", "")
        if verdict:
            verdict_html = f'<div class="verdict-box" style="border-left-color:{tier_cfg["color"]}">{self._escape(verdict)}</div>'

        # ── Dimension details with weight + reasoning ─────────────
        eval_html = ""
        if eval_data.get("dimensions"):
            eval_html = '<div class="eval-details">'
            for dim, data in eval_data["dimensions"].items():
                s = data.get("score", 0)
                weight = data.get("weight", "medium")
                weight_cfg = _WEIGHT_LABELS.get(weight, _WEIGHT_LABELS["medium"])
                dim_color = self._score_color(s)
                reasoning = data.get("reasoning", "")

                eval_html += f"""
                <div class="eval-dim">
                    <div class="eval-dim-header">
                        <strong style="color:{dim_color}">{dim}:</strong>
                        <span class="eval-dim-score" style="color:{dim_color}">{s}/10</span>
                        <span class="weight-badge-sm" style="color:{weight_cfg['color']}">{weight_cfg['label']}</span>
                    </div>
                    <div class="eval-dim-feedback">{self._escape(data.get("feedback", ""))}</div>
                    {"<div class='eval-dim-reasoning'>Why: " + self._escape(reasoning) + "</div>" if reasoning else ""}
                </div>"""
            eval_html += "</div>"

        # ── Strengths / weaknesses ────────────────────────────────
        sw_html = ""
        strengths = eval_data.get("strengths", [])
        weaknesses = eval_data.get("weaknesses", [])
        if strengths or weaknesses:
            sw_html = '<div class="sw-grid">'
            if strengths:
                items = "".join(f"<li>{self._escape(s)}</li>" for s in strengths)
                sw_html += f'<div class="sw-col sw-strengths"><strong>Strengths</strong><ul>{items}</ul></div>'
            if weaknesses:
                items = "".join(f"<li>{self._escape(w)}</li>" for w in weaknesses)
                sw_html += f'<div class="sw-col sw-weaknesses"><strong>Weaknesses</strong><ul>{items}</ul></div>'
            sw_html += '</div>'

        # ── Improvement suggestions ───────────────────────────────
        suggestions_html = ""
        suggestions = eval_data.get("improvement_suggestions", [])
        if suggestions:
            items = "".join(f"<li>{self._escape(s)}</li>" for s in suggestions)
            suggestions_html = f'<div class="suggestions"><strong>Improvement suggestions:</strong><ul>{items}</ul></div>'

        # ── Follow-up metadata ────────────────────────────────────
        fu_meta = ""
        if is_followup and turn.get("follow_up_metadata"):
            fm = turn["follow_up_metadata"]
            fu_meta = f"""
            <div class="fu-meta">
                Follow-up type: {self._escape(fm.get('follow_up_type', ''))} &bull;
                Satisfaction: {self._escape(fm.get('satisfaction_with_previous', ''))} &bull;
                Reason: {self._escape(fm.get('reason', ''))}
            </div>"""

        # ── Error ─────────────────────────────────────────────────
        error_html = ""
        if turn.get("error"):
            error_html = f'<div class="turn-error">Error: {self._escape(turn["error"])}</div>'

        return f"""
        <div class="turn {'turn-followup' if is_followup else ''}">
            <div class="turn-header">
                <span class="turn-label">{'Follow-up' if is_followup else 'Question'}</span>
                {tier_badge}
                <span class="response-time">{turn.get('response_time', 0)}s</span>
            </div>
            {fu_meta}
            <div class="turn-question"><strong>Q:</strong> {self._escape(turn.get('question', ''))}</div>
            <div class="turn-response">
                <strong>A:</strong> {self._escape((turn.get('response') or '')[:800])}
                {'...' if len(turn.get('response') or '') > 800 else ''}
            </div>
            {error_html}
            {verdict_html}
            {eval_html}
            {reasoning_html}
            {sw_html}
            {suggestions_html}
        </div>"""

    def _build_coherence_html(self, ce: dict) -> str:
        tier_key = ce.get("quality_tier", self._score_to_tier(ce.get("overall_conversation_score", 0)))
        tier_cfg = _TIER_CONFIG.get(tier_key, _TIER_CONFIG["developing"])

        traj_key = ce.get("trajectory", "stable")
        traj_cfg = _TRAJECTORY_CONFIG.get(traj_key, _TRAJECTORY_CONFIG["stable"])

        dimensions_html = ""
        for dim_key, dim_label in [
            ("coherence_score", "Coherence"),
            ("context_retention", "Context Retention"),
            ("contradiction_check", "No Contradictions"),
            ("progressive_helpfulness", "Progressive Help"),
        ]:
            score = ce.get(dim_key, "?")
            reasoning = ce.get(f"{dim_key}_reasoning", "")
            color = self._score_color(score if isinstance(score, (int, float)) else 0)
            dimensions_html += f"""
            <div class="coherence-dim">
                <strong>{dim_label}:</strong>
                <span style="color:{color}">{score}/10</span>
                {"<br><span class='coherence-reasoning'>" + self._escape(reasoning) + "</span>" if reasoning else ""}
            </div>"""

        # Improvement suggestions
        suggestions_html = ""
        suggestions = ce.get("improvement_suggestions", [])
        if suggestions:
            items = "".join(f"<li>{self._escape(s)}</li>" for s in suggestions)
            suggestions_html = f'<div class="suggestions"><strong>Suggestions:</strong><ul>{items}</ul></div>'

        # Issues
        issues_html = ""
        issues = ce.get("issues", [])
        if issues:
            items = "".join(f"<li>{self._escape(i)}</li>" for i in issues)
            issues_html = f'<div class="coherence-issues"><strong>Issues found:</strong><ul>{items}</ul></div>'

        return f"""
        <div class="coherence-eval">
            <div class="coherence-header">
                <strong>Conversation Coherence</strong>
                <span class="tier-badge-sm" style="background:{tier_cfg['bg']};color:{tier_cfg['color']}">
                    {tier_cfg['icon']} {ce.get('overall_conversation_score', '?')}/10 {tier_cfg['label']}
                </span>
                <span class="trajectory-badge" style="color:{traj_cfg['color']}">
                    {traj_cfg['icon']} {traj_cfg['label']}
                </span>
            </div>
            {dimensions_html}
            {"<div class='coherence-traj-reasoning'>" + self._escape(ce.get('trajectory_reasoning', '')) + "</div>" if ce.get('trajectory_reasoning') else ""}
            <div class="coherence-summary">{self._escape(ce.get('summary', ''))}</div>
            {issues_html}
            {suggestions_html}
        </div>"""

    # ──────────────────────────────────────────────────────────────────
    # Utilities
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _score_color(score) -> str:
        try:
            score = float(score)
        except (ValueError, TypeError):
            return "#a0aec0"
        if score >= 8:
            return "#276749"
        elif score >= 6:
            return "#38a169"
        elif score >= 4:
            return "#d69e2e"
        elif score >= 2:
            return "#dd6b20"
        else:
            return "#c53030"

    @staticmethod
    def _score_to_tier(score) -> str:
        try:
            score = float(score)
        except (ValueError, TypeError):
            return "critical_failure"
        if score >= 9:
            return "exemplary"
        elif score >= 7:
            return "proficient"
        elif score >= 5:
            return "developing"
        elif score >= 3:
            return "unsatisfactory"
        else:
            return "critical_failure"

    @staticmethod
    def _escape(text) -> str:
        if not text:
            return ""
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    @staticmethod
    def _css() -> str:
        return """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; color: #1a202c; padding: 24px; line-height: 1.5; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { font-size: 26px; color: #1a365d; margin-bottom: 4px; }
        .subtitle { color: #718096; margin-bottom: 24px; font-size: 14px; }

        /* Summary grid */
        .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 30px; }
        .stat-card { background: white; border-radius: 10px; padding: 18px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
        .stat-card .number { font-size: 32px; font-weight: 700; }
        .stat-card .label { font-size: 12px; color: #718096; margin-top: 2px; }

        /* Tier distribution bar */
        .tier-bar { display: flex; height: 32px; border-radius: 8px; overflow: hidden; margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .tier-segment { display: flex; align-items: center; justify-content: center; color: white; font-weight: 700; font-size: 13px; min-width: 24px; transition: width 0.3s; }
        .tier-legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 12px; color: #4a5568; margin-bottom: 24px; }
        .tier-legend-item { display: flex; align-items: center; gap: 4px; }
        .tier-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }

        /* Tier badges */
        .tier-badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 700; margin-top: 4px; }
        .tier-badge-sm { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 700; }

        /* Trajectory */
        .trajectory-badge { font-size: 13px; font-weight: 700; margin-left: 8px; }

        /* Persona cards */
        .persona-card { background: white; border-radius: 10px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
        .persona-header { display: flex; align-items: center; gap: 16px; margin-bottom: 14px; }
        .persona-score { width: 64px; height: 64px; border-radius: 50%; border: 4px solid; display: flex; flex-direction: column; align-items: center; justify-content: center; flex-shrink: 0; }
        .persona-score span { font-size: 22px; font-weight: 700; }
        .persona-score small { font-size: 10px; color: #a0aec0; }
        .persona-info h3 { font-size: 16px; margin-bottom: 2px; }
        .persona-role { font-size: 13px; color: #4a5568; }
        .persona-meta { font-size: 12px; color: #a0aec0; margin-top: 4px; }

        /* Dimensions */
        .dimensions { margin-top: 8px; }
        .dim-row { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
        .dim-label { width: 90px; font-size: 12px; color: #4a5568; text-align: right; }
        .weight-badge { font-size: 9px; font-weight: 700; width: 56px; text-align: center; }
        .dim-bar-bg { flex: 1; height: 8px; background: #edf2f7; border-radius: 4px; overflow: hidden; }
        .dim-bar { height: 100%; border-radius: 4px; transition: width 0.3s; }
        .dim-score { width: 28px; font-size: 12px; font-weight: 600; color: #2d3748; }

        /* Red flags */
        .red-flags, .red-flags-global { background: #fff5f5; border: 1px solid #feb2b2; border-radius: 8px; padding: 12px; margin-top: 10px; font-size: 13px; color: #c53030; }
        .red-flags ul, .red-flags-global ul { margin-left: 18px; margin-top: 4px; }
        .red-flags-global { margin-bottom: 20px; }
        .red-flags-global h2 { color: #c53030; font-size: 16px; margin-bottom: 6px; }

        h2 { font-size: 18px; color: #2d3748; margin: 24px 0 12px; }
        .persona-section-title { margin-top: 32px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; }

        /* Conversations */
        .conversation { background: white; border-radius: 10px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
        .conv-header { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; font-size: 13px; }
        .conv-label { font-weight: 700; color: #2d3748; }
        .conv-domain { background: #ebf8ff; color: #2b6cb0; padding: 2px 8px; border-radius: 4px; }
        .conv-intent { color: #718096; font-style: italic; }

        /* Turns */
        .turn { border-left: 3px solid #e2e8f0; padding: 10px 14px; margin-bottom: 12px; }
        .turn-followup { border-left-color: #bee3f8; background: #fafcff; }
        .turn-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; flex-wrap: wrap; }
        .turn-label { font-weight: 600; font-size: 12px; color: #4a5568; }
        .response-time { font-size: 11px; color: #a0aec0; }
        .fu-meta { font-size: 11px; color: #718096; margin-bottom: 6px; background: #f7fafc; padding: 4px 8px; border-radius: 4px; }
        .turn-question { font-size: 13px; margin-bottom: 6px; }
        .turn-response { font-size: 13px; color: #4a5568; margin-bottom: 8px; white-space: pre-wrap; }
        .turn-error { color: #e53e3e; font-size: 12px; margin-bottom: 6px; }

        /* Verdict box */
        .verdict-box { border-left: 4px solid #a0aec0; padding: 8px 12px; margin: 8px 0; font-size: 13px; color: #2d3748; background: #f7fafc; border-radius: 0 6px 6px 0; font-style: italic; }

        /* Evaluation details */
        .eval-details { font-size: 12px; margin-bottom: 8px; }
        .eval-dim { margin-bottom: 6px; padding: 4px 0; border-bottom: 1px solid #f0f2f5; }
        .eval-dim-header { display: flex; align-items: center; gap: 8px; }
        .eval-dim-score { font-weight: 700; }
        .weight-badge-sm { font-size: 9px; font-weight: 700; }
        .eval-dim-feedback { color: #4a5568; margin-top: 2px; }
        .eval-dim-reasoning { color: #718096; font-style: italic; margin-top: 2px; font-size: 11px; }

        /* Reasoning chain */
        .reasoning-section { margin: 8px 0; font-size: 12px; }
        .reasoning-section summary { cursor: pointer; color: #3182ce; font-weight: 600; padding: 4px 0; }
        .reasoning-section summary:hover { text-decoration: underline; }
        .reasoning-chain { margin-left: 18px; margin-top: 6px; color: #4a5568; }
        .reasoning-chain li { margin-bottom: 3px; }

        /* Strengths / weaknesses grid */
        .sw-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 8px 0; font-size: 12px; }
        .sw-col { padding: 8px; border-radius: 6px; }
        .sw-col ul { margin-left: 16px; margin-top: 4px; }
        .sw-strengths { background: #f0fff4; color: #276749; }
        .sw-weaknesses { background: #fff5f5; color: #9b2c2c; }

        /* Suggestions */
        .suggestions { background: #ebf8ff; border-radius: 6px; padding: 8px 12px; margin: 6px 0; font-size: 12px; color: #2b6cb0; }
        .suggestions ul { margin-left: 16px; margin-top: 4px; }

        /* Coherence evaluation */
        .coherence-eval { background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; margin-top: 12px; }
        .coherence-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
        .coherence-dim { margin-bottom: 4px; font-size: 13px; }
        .coherence-reasoning { color: #718096; font-size: 11px; font-style: italic; }
        .coherence-traj-reasoning { color: #4a5568; font-size: 12px; margin: 6px 0; font-style: italic; }
        .coherence-summary { font-size: 13px; color: #2d3748; margin-top: 6px; padding-top: 6px; border-top: 1px solid #e2e8f0; }
        .coherence-issues { font-size: 12px; color: #c53030; margin-top: 6px; }
        .coherence-issues ul { margin-left: 16px; margin-top: 4px; }

        .footer { text-align: center; color: #a0aec0; font-size: 12px; margin-top: 40px; }
        """
