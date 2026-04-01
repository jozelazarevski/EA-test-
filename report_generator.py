"""
Report Generator for HVAC Testing Agent.

Generates HTML and JSON reports from test results.
"""

import json
from datetime import datetime
from pathlib import Path

from config import REPORTS_DIR


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
        passed = sum(
            1 for r in results if r["validation_results"]["overall_pass"]
        )
        failed = total - passed
        avg_response_time = (
            sum(r["response_time"] for r in results) / total if total > 0 else 0
        )

        # Group by category
        categories = {}
        for r in results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"total": 0, "passed": 0, "failed": 0}
            categories[cat]["total"] += 1
            if r["validation_results"]["overall_pass"]:
                categories[cat]["passed"] += 1
            else:
                categories[cat]["failed"] += 1

        errors = [
            {"test_id": r["test_id"], "error": r["error"]}
            for r in results
            if r.get("error")
        ]

        return {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{(passed / total * 100):.1f}%" if total > 0 else "N/A",
            "avg_response_time": f"{avg_response_time:.2f}s",
            "categories": categories,
            "errors": errors,
        }

    def _generate_html(self, results: list) -> Path:
        """Generate an HTML report."""
        summary = self._build_summary(results)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build category rows
        category_rows = ""
        for cat, stats in summary["categories"].items():
            cat_pass_rate = (
                f"{(stats['passed'] / stats['total'] * 100):.0f}%"
                if stats["total"] > 0 else "N/A"
            )
            category_rows += f"""
            <tr>
                <td>{cat}</td>
                <td>{stats['total']}</td>
                <td class="pass">{stats['passed']}</td>
                <td class="fail">{stats['failed']}</td>
                <td>{cat_pass_rate}</td>
            </tr>"""

        # Build test result rows
        test_rows = ""
        for r in results:
            status = "PASS" if r["validation_results"]["overall_pass"] else "FAIL"
            status_class = "pass" if status == "PASS" else "fail"

            validation_details = r["validation_results"]["text_validation"]
            if isinstance(validation_details, dict):
                details_html = validation_details.get("details", "")
            else:
                details_html = str(validation_details)

            # Truncate response for display
            response_preview = (r["response_text"] or "")[:300]
            if len(r["response_text"] or "") > 300:
                response_preview += "..."

            pdf_info = ""
            if r["pdf_links"]:
                pdf_info = f"<br><strong>PDFs found:</strong> {len(r['pdf_links'])}"
                for pdf in r["pdf_links"]:
                    pdf_info += f"<br>&nbsp;&nbsp;- {pdf.get('text', 'Unknown')}"

            error_html = ""
            if r.get("error"):
                error_html = f'<br><span class="error">Error: {r["error"]}</span>'

            test_rows += f"""
            <tr class="{status_class}-row">
                <td><strong>{r['test_id']}</strong></td>
                <td>{r['category']}</td>
                <td class="question">{r['question'][:100]}{'...' if len(r['question']) > 100 else ''}</td>
                <td class="{status_class}"><strong>{status}</strong></td>
                <td>{r['response_time']}s</td>
                <td class="details">
                    {details_html}
                    {pdf_info}
                    {error_html}
                </td>
                <td class="response-preview">{response_preview}</td>
            </tr>"""

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
        h1 {{
            color: #1a365d;
            margin-bottom: 5px;
            font-size: 24px;
        }}
        .subtitle {{
            color: #718096;
            margin-bottom: 30px;
            font-size: 14px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
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
        .summary-card .number {{
            font-size: 36px;
            font-weight: bold;
            color: #2d3748;
        }}
        .summary-card .label {{
            font-size: 13px;
            color: #718096;
            margin-top: 5px;
        }}
        .summary-card.pass-rate .number {{ color: #38a169; }}
        .summary-card.failures .number {{ color: #e53e3e; }}
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
        .pass-row {{ border-left: 4px solid #38a169; }}
        .fail-row {{ border-left: 4px solid #e53e3e; }}
        .error {{ color: #e53e3e; font-size: 12px; }}
        .question {{ max-width: 250px; }}
        .details {{ max-width: 300px; font-size: 12px; word-break: break-word; }}
        .response-preview {{
            max-width: 300px;
            font-size: 12px;
            color: #555;
            word-break: break-word;
        }}
        h2 {{
            color: #2d3748;
            margin-bottom: 15px;
            font-size: 18px;
        }}
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
            Target: expertadvisor.jci.com
        </p>

        <div class="summary-grid">
            <div class="summary-card">
                <div class="number">{summary['total_tests']}</div>
                <div class="label">Total Tests</div>
            </div>
            <div class="summary-card">
                <div class="number pass">{summary['passed']}</div>
                <div class="label">Passed</div>
            </div>
            <div class="summary-card failures">
                <div class="number">{summary['failed']}</div>
                <div class="label">Failed</div>
            </div>
            <div class="summary-card pass-rate">
                <div class="number">{summary['pass_rate']}</div>
                <div class="label">Pass Rate</div>
            </div>
            <div class="summary-card">
                <div class="number">{summary['avg_response_time']}</div>
                <div class="label">Avg Response Time</div>
            </div>
        </div>

        <h2>Results by Category</h2>
        <table>
            <thead>
                <tr>
                    <th>Category</th>
                    <th>Total</th>
                    <th>Passed</th>
                    <th>Failed</th>
                    <th>Pass Rate</th>
                </tr>
            </thead>
            <tbody>
                {category_rows}
            </tbody>
        </table>

        <h2>Detailed Test Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Test ID</th>
                    <th>Category</th>
                    <th>Question</th>
                    <th>Status</th>
                    <th>Time</th>
                    <th>Validation Details</th>
                    <th>Response Preview</th>
                </tr>
            </thead>
            <tbody>
                {test_rows}
            </tbody>
        </table>

        <div class="footer">
            HVAC Expert Advisor Testing Agent | Johnson Controls |
            Report generated automatically
        </div>
    </div>
</body>
</html>"""

        path = self.report_dir / f"report_{self.run_id}.html"
        with open(path, "w") as f:
            f.write(html)
        return path
