"""
Report Generator for HVAC Testing Agent.

Generates HTML and JSON reports from LLM-evaluated test results.
"""

import json
from datetime import datetime
from pathlib import Path

from config import REPORTS_DIR


# Tier styling
TIER_COLORS = {
    "exemplary": ("#276749", "#c6f6d5"),
    "proficient": ("#38a169", "#e6ffed"),
    "developing": ("#d69e2e", "#fefcbf"),
    "unsatisfactory": ("#dd6b20", "#feebc8"),
    "critical_failure": ("#c53030", "#fed7d7"),
}
TIER_ICONS = {
    "exemplary": "★★",
    "proficient": "★",
    "developing": "◐",
    "unsatisfactory": "▽",
    "critical_failure": "✖",
}
DIMENSION_LABELS = {
    "safety": ("Safety", "CRITICAL", "#c53030"),
    "accuracy": ("Accuracy", "HIGH", "#d69e2e"),
    "completeness": ("Completeness", "MEDIUM", "#3182ce"),
    "relevance": ("Relevance", "STD", "#718096"),
    "clarity": ("Clarity", "LOW", "#a0aec0"),
    "persona_fit": ("Persona Fit", "LOW", "#a0aec0"),
}


class ReportGenerator:
    """Generates test execution reports in HTML and JSON formats."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.report_dir = REPORTS_DIR
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, results: list) -> Path:
        """Generate both HTML and JSON reports. Returns path to HTML report."""
        json_path = self._generate_json(results)
        html_path = self._generate_html(results)
        print(f"[Report] JSON report: {json_path}")
        print(f"[Report] HTML report: {html_path}")
        return html_path

    def _generate_json(self, results: list) -> Path:
        """Generate a JSON report."""
        report = {
            "run_id": self.run_id,
            "timestamp": datetime.now().isoformat(),
            "summary": self._build_summary(results),
            "results": results,
        }
        path = self.report_dir / f"report_{self.run_id}.json"
        with open(path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        return path

    def _build_summary(self, results: list) -> dict:
        """Build a summary of test results."""
        total = len(results)
        scores = [r["evaluation"].get("overall_score", 0) for r in results]
        avg_score = sum(scores) / len(scores) if scores else 0
        passed = sum(1 for s in scores if s >= 6)
        failed = total - passed
        avg_response_time = (
            sum(r["response_time"] for r in results) / total if total > 0 else 0
        )

        # Tier distribution
        tiers = {}
        for r in results:
            tier = r["evaluation"].get("quality_tier", "unknown")
            tiers[tier] = tiers.get(tier, 0) + 1

        # Group by category
        categories = {}
        for r in results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"total": 0, "scores": [], "tiers": {}}
            categories[cat]["total"] += 1
            categories[cat]["scores"].append(
                r["evaluation"].get("overall_score", 0)
            )
            tier = r["evaluation"].get("quality_tier", "unknown")
            categories[cat]["tiers"][tier] = categories[cat]["tiers"].get(tier, 0) + 1

        # Compute category averages
        for cat, data in categories.items():
            data["avg_score"] = round(sum(data["scores"]) / len(data["scores"]), 1) if data["scores"] else 0
            data["passed"] = sum(1 for s in data["scores"] if s >= 6)
            data["failed"] = data["total"] - data["passed"]

        # Red flags
        red_flags = []
        for r in results:
            for flag in r["evaluation"].get("red_flags", []):
                red_flags.append({"test_id": r["test_id"], "flag": flag})

        errors = [
            {"test_id": r["test_id"], "error": r["error"]}
            for r in results
            if r.get("error")
        ]

        return {
            "total_tests": total,
            "avg_score": round(avg_score, 1),
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{(passed / total * 100):.1f}%" if total > 0 else "N/A",
            "avg_response_time": f"{avg_response_time:.2f}s",
            "tier_distribution": tiers,
            "categories": categories,
            "red_flags": red_flags,
            "errors": errors,
        }

    def _generate_html(self, results: list) -> Path:
        """Generate an HTML report with LLM evaluation details."""
        summary = self._build_summary(results)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build tier distribution bar
        tier_bar_html = self._build_tier_bar(summary["tier_distribution"], len(results))

        # Build category rows
        category_rows = ""
        for cat, stats in summary["categories"].items():
            category_rows += f"""
            <tr>
                <td>{cat}</td>
                <td>{stats['total']}</td>
                <td><strong>{stats['avg_score']}</strong>/10</td>
                <td class="pass">{stats['passed']}</td>
                <td class="fail">{stats['failed']}</td>
            </tr>"""

        # Build test result cards
        test_cards = ""
        for r in results:
            test_cards += self._build_test_card(r)

        # Red flags section
        red_flags_html = ""
        if summary["red_flags"]:
            flags = "".join(
                f'<li><strong>{f["test_id"]}:</strong> {f["flag"]}</li>'
                for f in summary["red_flags"]
            )
            red_flags_html = f"""
            <div class="red-flags">
                <h2>Red Flags</h2>
                <ul>{flags}</ul>
            </div>"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HVAC Expert Advisor Test Report - {self.run_id}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f7fa;
            color: #333;
            padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #1a365d; margin-bottom: 5px; font-size: 24px; }}
        .subtitle {{ color: #718096; margin-bottom: 30px; font-size: 14px; }}
        h2 {{ color: #2d3748; margin: 25px 0 15px; font-size: 18px; }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .summary-card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .summary-card .number {{ font-size: 36px; font-weight: bold; color: #2d3748; }}
        .summary-card .label {{ font-size: 13px; color: #718096; margin-top: 5px; }}
        .summary-card.score .number {{ color: #2b6cb0; }}

        .tier-bar {{
            display: flex;
            height: 32px;
            border-radius: 6px;
            overflow: hidden;
            margin-bottom: 30px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .tier-bar .segment {{
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 600;
            color: white;
            min-width: 40px;
        }}

        table {{
            width: 100%;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-collapse: collapse;
            margin-bottom: 30px;
            font-size: 13px;
        }}
        th {{
            background: #2d3748;
            color: white;
            padding: 12px 10px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #e2e8f0;
            vertical-align: top;
        }}
        tr:hover {{ background: #f7fafc; }}
        .pass {{ color: #38a169; font-weight: 600; }}
        .fail {{ color: #e53e3e; font-weight: 600; }}

        .test-card {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            overflow: hidden;
        }}
        .test-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 20px;
            cursor: pointer;
        }}
        .test-card-header:hover {{ background: #f7fafc; }}
        .test-card-header .left {{ display: flex; align-items: center; gap: 15px; }}
        .test-card-header .test-id {{ font-weight: 700; font-size: 14px; color: #2d3748; }}
        .test-card-header .category {{ font-size: 12px; color: #718096; }}
        .test-card-header .question-preview {{
            font-size: 13px; color: #4a5568; max-width: 500px;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }}

        .tier-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
        }}
        .score-display {{
            font-size: 20px;
            font-weight: 700;
            margin-right: 10px;
        }}

        .test-card-body {{
            display: none;
            padding: 0 20px 20px;
            border-top: 1px solid #e2e8f0;
        }}
        .test-card.open .test-card-body {{ display: block; }}

        .dimensions-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 12px;
            margin: 15px 0;
        }}
        .dim-item {{
            background: #f7fafc;
            border-radius: 6px;
            padding: 12px;
        }}
        .dim-item .dim-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }}
        .dim-item .dim-name {{ font-weight: 600; font-size: 13px; }}
        .dim-item .dim-weight {{ font-size: 11px; padding: 2px 6px; border-radius: 3px; }}
        .dim-item .dim-bar {{
            height: 6px;
            background: #e2e8f0;
            border-radius: 3px;
            overflow: hidden;
        }}
        .dim-item .dim-bar .fill {{
            height: 100%;
            border-radius: 3px;
            transition: width 0.3s;
        }}
        .dim-item .dim-score {{ font-size: 12px; color: #4a5568; margin-top: 4px; }}
        .dim-item .dim-feedback {{ font-size: 12px; color: #718096; margin-top: 4px; }}

        .verdict {{
            padding: 12px 16px;
            border-radius: 6px;
            border-left: 4px solid;
            margin: 15px 0;
            font-size: 13px;
            line-height: 1.5;
        }}

        .reasoning {{ margin: 10px 0; }}
        .reasoning summary {{ cursor: pointer; font-weight: 600; font-size: 13px; color: #4a5568; }}
        .reasoning ol {{ margin: 8px 0 0 20px; font-size: 12px; color: #4a5568; }}
        .reasoning ol li {{ margin-bottom: 4px; }}

        .strengths-weaknesses {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin: 10px 0;
        }}
        .sw-list {{ font-size: 12px; }}
        .sw-list h4 {{ font-size: 13px; margin-bottom: 6px; }}
        .sw-list ul {{ margin: 0; padding-left: 18px; }}
        .sw-list li {{ margin-bottom: 3px; color: #4a5568; }}

        .response-preview {{
            background: #f7fafc;
            border-radius: 6px;
            padding: 12px;
            font-size: 12px;
            color: #555;
            max-height: 200px;
            overflow-y: auto;
            margin-top: 10px;
            white-space: pre-wrap;
        }}

        .red-flags {{
            background: #fff5f5;
            border: 1px solid #fc8181;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
        }}
        .red-flags h2 {{ color: #c53030; margin-bottom: 10px; }}
        .red-flags ul {{ margin-left: 20px; }}
        .red-flags li {{ margin-bottom: 6px; color: #742a2a; font-size: 13px; }}

        .error {{ color: #e53e3e; font-size: 12px; }}
        .footer {{
            text-align: center;
            color: #a0aec0;
            font-size: 12px;
            margin-top: 30px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>HVAC Expert Advisor - Test Report</h1>
        <p class="subtitle">
            Run ID: {self.run_id} | Generated: {timestamp} |
            Target: expertadvisor.jci.com | Evaluation: LLM-powered
        </p>

        <div class="summary-grid">
            <div class="summary-card">
                <div class="number">{summary['total_tests']}</div>
                <div class="label">Total Tests</div>
            </div>
            <div class="summary-card score">
                <div class="number">{summary['avg_score']}/10</div>
                <div class="label">Average Score</div>
            </div>
            <div class="summary-card">
                <div class="number pass">{summary['passed']}</div>
                <div class="label">Passed (≥6)</div>
            </div>
            <div class="summary-card">
                <div class="number fail">{summary['failed']}</div>
                <div class="label">Failed (&lt;6)</div>
            </div>
            <div class="summary-card">
                <div class="number">{summary['pass_rate']}</div>
                <div class="label">Pass Rate</div>
            </div>
            <div class="summary-card">
                <div class="number">{summary['avg_response_time']}</div>
                <div class="label">Avg Response Time</div>
            </div>
        </div>

        <h2>Quality Tier Distribution</h2>
        {tier_bar_html}

        {red_flags_html}

        <h2>Results by Category</h2>
        <table>
            <thead>
                <tr>
                    <th>Category</th>
                    <th>Tests</th>
                    <th>Avg Score</th>
                    <th>Passed</th>
                    <th>Failed</th>
                </tr>
            </thead>
            <tbody>
                {category_rows}
            </tbody>
        </table>

        <h2>Detailed Test Results</h2>
        <p style="font-size:13px;color:#718096;margin-bottom:15px;">Click a test to expand evaluation details.</p>
        {test_cards}

        <div class="footer">
            HVAC Expert Advisor Testing Agent | Johnson Controls |
            Report generated automatically | LLM evaluation
        </div>
    </div>

    <script>
        document.querySelectorAll('.test-card-header').forEach(header => {{
            header.addEventListener('click', () => {{
                header.closest('.test-card').classList.toggle('open');
            }});
        }});
    </script>
</body>
</html>"""

        path = self.report_dir / f"report_{self.run_id}.html"
        with open(path, "w") as f:
            f.write(html)
        return path

    # ------------------------------------------------------------------
    # HTML helpers
    # ------------------------------------------------------------------

    def _build_tier_bar(self, tier_dist: dict, total: int) -> str:
        if total == 0:
            return ""
        segments = ""
        for tier_name in ["exemplary", "proficient", "developing", "unsatisfactory", "critical_failure"]:
            count = tier_dist.get(tier_name, 0)
            if count == 0:
                continue
            pct = count / total * 100
            color, _ = TIER_COLORS.get(tier_name, ("#718096", "#eee"))
            icon = TIER_ICONS.get(tier_name, "")
            label = tier_name.replace("_", " ").title()
            segments += (
                f'<div class="segment" style="width:{pct:.1f}%;background:{color};" '
                f'title="{label}: {count}">{icon} {count}</div>'
            )
        return f'<div class="tier-bar">{segments}</div>'

    def _build_test_card(self, r: dict) -> str:
        ev = r.get("evaluation", {})
        score = ev.get("overall_score", 0)
        tier = ev.get("quality_tier", "unknown")
        color, bg = TIER_COLORS.get(tier, ("#718096", "#edf2f7"))
        icon = TIER_ICONS.get(tier, "?")
        label = tier.replace("_", " ").title()

        question_preview = (r["question"] or "(empty)")[:100]
        if len(r.get("question", "")) > 100:
            question_preview += "..."

        # Dimensions
        dims_html = ""
        dimensions = ev.get("dimensions", {})
        for dim_key in ["safety", "accuracy", "completeness", "relevance", "clarity", "persona_fit"]:
            dim_data = dimensions.get(dim_key, {})
            dim_score = dim_data.get("score", 0)
            dim_label, weight_label, weight_color = DIMENSION_LABELS.get(
                dim_key, (dim_key.title(), "STD", "#718096"))
            bar_color = self._score_color(dim_score)
            feedback = dim_data.get("feedback", "")
            dims_html += f"""
            <div class="dim-item">
                <div class="dim-header">
                    <span class="dim-name">{dim_label}</span>
                    <span class="dim-weight" style="background:{weight_color}20;color:{weight_color};">{weight_label}</span>
                </div>
                <div class="dim-bar"><div class="fill" style="width:{dim_score*10}%;background:{bar_color};"></div></div>
                <div class="dim-score">{dim_score}/10</div>
                <div class="dim-feedback">{feedback}</div>
            </div>"""

        # Reasoning chain
        chain = ev.get("reasoning_chain", [])
        reasoning_html = ""
        if chain:
            items = "".join(f"<li>{step}</li>" for step in chain)
            reasoning_html = f"""
            <details class="reasoning">
                <summary>Reasoning Chain ({len(chain)} steps)</summary>
                <ol>{items}</ol>
            </details>"""

        # Verdict
        verdict = ev.get("verdict_explanation", "")
        verdict_html = ""
        if verdict:
            verdict_html = f'<div class="verdict" style="border-color:{color};background:{bg};">{verdict}</div>'

        # Strengths / weaknesses
        strengths = ev.get("strengths", [])
        weaknesses = ev.get("weaknesses", [])
        sw_html = ""
        if strengths or weaknesses:
            s_items = "".join(f"<li>{s}</li>" for s in strengths)
            w_items = "".join(f"<li>{w}</li>" for w in weaknesses)
            sw_html = f"""
            <div class="strengths-weaknesses">
                <div class="sw-list"><h4 style="color:#38a169;">Strengths</h4><ul>{s_items}</ul></div>
                <div class="sw-list"><h4 style="color:#e53e3e;">Weaknesses</h4><ul>{w_items}</ul></div>
            </div>"""

        # Reference comparison
        ref_cmp = ev.get("reference_comparison", {})
        ref_html = ""
        if ref_cmp:
            confirmed = ref_cmp.get("facts_confirmed", [])
            missing = ref_cmp.get("facts_missing", [])
            incorrect = ref_cmp.get("facts_incorrect", [])
            if confirmed or missing or incorrect:
                parts = []
                if confirmed:
                    items = "".join(f"<li style='color:#38a169;'>&#10003; {f}</li>" for f in confirmed)
                    parts.append(f"<strong>Confirmed:</strong><ul>{items}</ul>")
                if missing:
                    items = "".join(f"<li style='color:#d69e2e;'>&#9888; {f}</li>" for f in missing)
                    parts.append(f"<strong>Missing:</strong><ul>{items}</ul>")
                if incorrect:
                    items = "".join(f"<li style='color:#e53e3e;'>&#10007; {f}</li>" for f in incorrect)
                    parts.append(f"<strong>Incorrect:</strong><ul>{items}</ul>")
                ref_html = f"""
                <details class="reasoning" style="margin-top:10px;">
                    <summary>Reference Comparison</summary>
                    <div style="font-size:12px;margin-top:8px;">{''.join(parts)}</div>
                </details>"""

        # Error
        error_html = ""
        if r.get("error"):
            error_html = f'<p class="error" style="margin-top:10px;">Error: {r["error"]}</p>'

        # Response preview
        response_preview = (r.get("response_text") or "")[:500]

        return f"""
        <div class="test-card">
            <div class="test-card-header">
                <div class="left">
                    <span class="test-id">{r['test_id']}</span>
                    <span class="category">{r['category']}</span>
                    <span class="question-preview">{question_preview}</span>
                </div>
                <div style="display:flex;align-items:center;">
                    <span class="score-display" style="color:{color};">{score}/10</span>
                    <span class="tier-badge" style="background:{bg};color:{color};">{icon} {label}</span>
                </div>
            </div>
            <div class="test-card-body">
                <h3 style="font-size:14px;margin:15px 0 5px;">Dimension Scores</h3>
                <div class="dimensions-grid">{dims_html}</div>
                {verdict_html}
                {reasoning_html}
                {sw_html}
                {ref_html}
                {error_html}
                <p style="font-size:12px;color:#718096;margin-top:10px;">Response time: {r['response_time']}s</p>
                <div class="response-preview">{response_preview}</div>
            </div>
        </div>"""

    @staticmethod
    def _score_color(score: float) -> str:
        if score >= 9:
            return "#276749"
        elif score >= 7:
            return "#38a169"
        elif score >= 5:
            return "#d69e2e"
        elif score >= 3:
            return "#dd6b20"
        else:
            return "#c53030"
