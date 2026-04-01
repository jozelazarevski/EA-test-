#!/usr/bin/env python3
"""
Generate a standalone HTML file for golden record validation.

The output is a single self-contained HTML file that can be emailed to
HVAC technicians. They open it in any browser, enter their name, then
walk through each golden record one at a time in a seamless wizard flow.

Every click auto-saves to localStorage so nothing is lost. When done,
download JSON results or copy to clipboard and send back.

Usage:
    python generate_validation_html.py
    # Creates: golden_record_review.html

    python generate_validation_html.py -o review_for_john.html
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).parent
REFERENCES_DIR = BASE_DIR / "references"


def load_golden_records() -> dict:
    path = REFERENCES_DIR / "expected_answers.yaml"
    if not path.exists():
        print(f"Error: {path} not found")
        sys.exit(1)
    with open(path) as f:
        return yaml.safe_load(f) or {}


def generate_standalone_validation_html(records: dict) -> str:
    """Generate a fully self-contained HTML validation wizard."""

    all_records = []
    for record_type in ["scenarios", "test_cases"]:
        items = records.get(record_type, {})
        for rec_id, rec_data in items.items():
            all_records.append({
                "id": rec_id,
                "type": record_type,
                "type_label": "Scenario" if record_type == "scenarios" else "Test Case",
                "data": rec_data,
            })

    records_json = json.dumps(all_records, indent=2, default=str)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HVAC Golden Record Review</title>
<style>
:root {{
    --bg: #f5f7fa; --card: #fff; --hover: #f0f4f8; --border: #d1d9e6;
    --text: #2d3748; --dim: #64748b; --bright: #1a202c;
    --accent: #2563eb; --green: #16a34a; --green-bg: rgba(22,163,74,0.08);
    --yellow: #ca8a04; --yellow-bg: rgba(202,138,4,0.08);
    --red: #dc2626; --red-bg: rgba(220,38,38,0.06); --orange: #ea580c;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif; background:var(--bg); color:var(--text); line-height:1.5; }}

/* ── Screens ─────────────────────────────────────── */
.screen {{ display:none; min-height:100vh; }}
.screen.active {{ display:flex; flex-direction:column; }}

/* ── Welcome screen ──────────────────────────────── */
#welcome {{
    align-items:center; justify-content:center; padding:40px;
}}
.welcome-box {{
    background:var(--card); border:1px solid var(--border); border-radius:16px;
    padding:48px; max-width:480px; width:100%; text-align:center;
    box-shadow:0 4px 24px rgba(0,0,0,0.06);
}}
.welcome-box h1 {{ font-size:28px; color:var(--bright); margin-bottom:8px; }}
.welcome-box p {{ color:var(--dim); margin-bottom:24px; font-size:15px; }}
.welcome-box input {{
    width:100%; padding:14px 18px; border:2px solid var(--border); border-radius:10px;
    font-size:18px; text-align:center; color:var(--text); margin-bottom:16px;
}}
.welcome-box input:focus {{ outline:none; border-color:var(--accent); }}

/* ── Progress bar ────────────────────────────────── */
.topbar {{
    background:var(--card); border-bottom:1px solid var(--border);
    padding:12px 24px; display:flex; align-items:center; gap:16px;
    position:sticky; top:0; z-index:10; box-shadow:0 1px 3px rgba(0,0,0,0.04);
}}
.topbar-name {{ font-weight:600; color:var(--bright); font-size:14px; }}
.topbar-progress {{ flex:1; }}
.pbar {{ height:8px; background:var(--border); border-radius:4px; overflow:hidden; }}
.pbar .fill {{ height:100%; background:var(--green); border-radius:4px; transition:width 0.4s ease; }}
.topbar-count {{ font-size:13px; color:var(--dim); font-weight:600; min-width:80px; text-align:right; }}

/* ── Review screen ───────────────────────────────── */
#review {{ padding-top:0; }}
.review-content {{ max-width:800px; margin:0 auto; padding:24px; flex:1; }}

.rec-title-bar {{
    display:flex; align-items:center; gap:10px; margin-bottom:16px; flex-wrap:wrap;
}}
.rec-title-bar h2 {{ font-size:20px; color:var(--bright); flex:1; }}
.tag {{ font-size:11px; padding:3px 10px; border-radius:6px; font-weight:600; }}
.tag-blue {{ background:rgba(37,99,235,0.08); color:var(--accent); }}
.tag-dim {{ background:rgba(148,163,184,0.1); color:var(--dim); }}

.section {{ margin-bottom:20px; }}
.section-hd {{
    font-size:11px; font-weight:700; text-transform:uppercase; color:var(--dim);
    letter-spacing:0.5px; margin-bottom:8px; padding-left:4px;
}}
.section-hd.safety {{ color:var(--red); }}
.section-hd.forbidden {{ color:var(--orange); }}

.el {{
    display:flex; align-items:flex-start; gap:8px;
    padding:10px 12px; border:1px solid var(--border); border-radius:8px;
    margin-bottom:4px; font-size:14px; transition:all 0.15s;
}}
.el:hover {{ background:var(--hover); }}
.el.safety {{ border-color:rgba(220,38,38,0.15); }}
.el.safety .el-txt {{ color:#b91c1c; }}
.el.forbidden {{ border-color:rgba(234,88,12,0.15); }}

.el-btns {{ display:flex; gap:2px; flex-shrink:0; margin-top:2px; }}
.vb {{
    width:28px; height:28px; border:1px solid var(--border); border-radius:6px;
    background:transparent; cursor:pointer; font-size:13px;
    display:flex; align-items:center; justify-content:center;
    transition:all 0.15s; color:var(--dim);
}}
.vb:hover {{ background:var(--hover); }}
.vb.ok.on {{ background:var(--green-bg); color:var(--green); border-color:var(--green); }}
.vb.no.on {{ background:var(--red-bg); color:var(--red); border-color:var(--red); }}
.vb.ed.on {{ background:var(--yellow-bg); color:var(--yellow); border-color:var(--yellow); }}
.el-txt {{ flex:1; }}
.el-note {{ width:100%; margin-top:6px; display:none; }}
.el.show-note .el-note {{ display:block; }}
.el-note textarea {{
    width:100%; min-height:32px; font-size:13px; padding:6px 10px;
    border:1px solid var(--border); border-radius:6px; resize:vertical; color:var(--text);
}}
.el-note textarea:focus {{ outline:none; border-color:var(--accent); }}

.val-tbl {{ width:100%; border-collapse:collapse; font-size:14px; }}
.val-tbl th {{ text-align:left; padding:6px 10px; color:var(--dim); font-size:11px; text-transform:uppercase; }}
.val-tbl td {{ padding:8px 10px; border-bottom:1px solid var(--border); }}
.val-tbl code {{ background:#f1f5f9; padding:2px 8px; border-radius:4px; font-size:13px; }}
.val-tbl input {{
    font-size:13px; padding:4px 8px; width:140px;
    border:1px solid var(--border); border-radius:6px; color:var(--text);
}}

.refs {{ margin-left:16px; font-size:13px; color:var(--dim); }}
.refs li {{ margin-bottom:3px; }}

.comment-section {{ margin-top:20px; }}
.comment-section label {{ font-size:13px; color:var(--dim); font-weight:600; display:block; margin-bottom:4px; }}
.comment-section textarea {{
    width:100%; min-height:60px; font-size:14px; padding:10px 14px;
    border:1px solid var(--border); border-radius:8px; resize:vertical; color:var(--text);
}}
.comment-section textarea:focus {{ outline:none; border-color:var(--accent); }}

.action-bar {{
    background:var(--card); border-top:1px solid var(--border);
    padding:16px 24px; display:flex; gap:10px; justify-content:center;
    position:sticky; bottom:0; box-shadow:0 -2px 8px rgba(0,0,0,0.04);
}}
.btn {{
    display:inline-flex; align-items:center; gap:6px;
    padding:12px 28px; border-radius:10px; font-size:15px; font-weight:600;
    border:none; cursor:pointer; transition:all 0.15s; color:white;
}}
.btn:hover {{ filter:brightness(0.92); }}
.btn-green {{ background:var(--green); }}
.btn-yellow {{ background:var(--yellow); color:#1a202c; }}
.btn-red {{ background:var(--red); }}
.btn-blue {{ background:var(--accent); }}
.btn-outline {{ background:var(--card); border:1px solid var(--border); color:var(--text); }}
.btn-sm {{ padding:8px 16px; font-size:13px; border-radius:8px; }}

/* ── Done screen ─────────────────────────────────── */
#done {{ align-items:center; justify-content:center; padding:40px; }}
.done-box {{
    background:var(--card); border:1px solid var(--border); border-radius:16px;
    padding:48px; max-width:560px; width:100%; text-align:center;
    box-shadow:0 4px 24px rgba(0,0,0,0.06);
}}
.done-box h1 {{ font-size:28px; color:var(--green); margin-bottom:8px; }}
.done-box p {{ color:var(--dim); margin-bottom:20px; }}
.done-stats {{ display:flex; gap:16px; justify-content:center; margin-bottom:24px; }}
.done-stat {{ text-align:center; }}
.done-stat .n {{ font-size:28px; font-weight:700; }}
.done-stat .l {{ font-size:11px; color:var(--dim); text-transform:uppercase; }}
.done-actions {{ display:flex; gap:10px; justify-content:center; flex-wrap:wrap; }}
.export-preview {{
    background:#f8fafc; border:1px solid var(--border); border-radius:8px;
    padding:10px; font-family:'SF Mono',monospace; font-size:11px;
    max-height:180px; overflow-y:auto; white-space:pre-wrap; word-break:break-all;
    text-align:left; margin-top:16px; display:none;
}}

/* ── Toast ────────────────────────────────────────── */
.toast-box {{ position:fixed; top:70px; right:20px; z-index:100; }}
.toast {{
    background:var(--card); border:1px solid var(--border); border-left:3px solid var(--green);
    border-radius:8px; padding:10px 14px; margin-bottom:6px; font-size:13px;
    box-shadow:0 4px 16px rgba(0,0,0,0.08); animation:slideIn 0.3s ease;
}}
@keyframes slideIn {{ from {{ transform:translateX(60px);opacity:0; }} to {{ transform:none;opacity:1; }} }}
</style>
</head>
<body>

<!-- ═══ SCREEN 1: Welcome ═══════════════════════════════════════ -->
<div class="screen active" id="welcome">
    <div class="welcome-box">
        <h1>Golden Record Review</h1>
        <p>Review and validate HVAC Expert Advisor expected answers.<br>Your feedback helps ensure testing accuracy.</p>
        <input type="text" id="name-input" placeholder="Enter your name" autofocus>
        <br>
        <button class="btn btn-blue" onclick="startReview()" style="width:100%;padding:14px;">
            Start Review
        </button>
        <p style="font-size:12px;color:var(--dim);margin-top:16px;">
            Progress is saved automatically. You can close and reopen anytime.
        </p>
    </div>
</div>

<!-- ═══ SCREEN 2: Review ════════════════════════════════════════ -->
<div class="screen" id="review">
    <div class="topbar">
        <div class="topbar-name" id="topbar-name"></div>
        <div class="topbar-progress">
            <div class="pbar"><div class="fill" id="pbar-fill" style="width:0%"></div></div>
        </div>
        <div class="topbar-count" id="topbar-count">0 / 0</div>
        <button class="btn-sm btn-outline" onclick="finishEarly()">Finish &amp; Export</button>
    </div>
    <div class="review-content" id="review-content"></div>
    <div class="action-bar">
        <button class="btn btn-outline" id="btn-skip" onclick="skipRecord()">Skip</button>
        <button class="btn btn-green" onclick="submitCurrent('approved')">&#10003; Approve</button>
        <button class="btn btn-yellow" onclick="submitCurrent('modified')">&#9998; Needs Changes</button>
        <button class="btn btn-red" onclick="submitCurrent('rejected')">&#10007; Reject</button>
    </div>
</div>

<!-- ═══ SCREEN 3: Done ══════════════════════════════════════════ -->
<div class="screen" id="done">
    <div class="done-box">
        <h1>Review Complete!</h1>
        <p>Thank you for your review. Please send the results back.</p>
        <div class="done-stats">
            <div class="done-stat"><div class="n" id="d-approved" style="color:var(--green)">0</div><div class="l">Approved</div></div>
            <div class="done-stat"><div class="n" id="d-modified" style="color:var(--yellow)">0</div><div class="l">Needs Changes</div></div>
            <div class="done-stat"><div class="n" id="d-rejected" style="color:var(--red)">0</div><div class="l">Rejected</div></div>
            <div class="done-stat"><div class="n" id="d-skipped" style="color:var(--dim)">0</div><div class="l">Skipped</div></div>
        </div>
        <div class="done-actions">
            <button class="btn btn-blue" onclick="downloadJSON()">Download Results (.json)</button>
            <button class="btn btn-outline" onclick="copyJSON()">Copy to Clipboard</button>
            <button class="btn btn-outline" onclick="emailJSON()">Email Results</button>
        </div>
        <pre class="export-preview" id="export-preview"></pre>
        <p style="font-size:12px;color:var(--dim);margin-top:16px;">
            <a href="#" onclick="backToReview();return false;">Go back to review remaining records</a>
        </p>
    </div>
</div>

<div class="toast-box" id="toasts"></div>

<script>
// ── Data ─────────────────────────────────────────────────────────
const RECORDS = {records_json};

const STORAGE_KEY = 'hvac_golden_review';
let state = loadState();

function loadState() {{
    try {{
        const s = localStorage.getItem(STORAGE_KEY);
        if (s) return JSON.parse(s);
    }} catch(e) {{}}
    return {{ reviewer: '', reviews: {{}}, currentIndex: 0 }};
}}

function save() {{
    try {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }} catch(e) {{}}
}}

// ── Navigation ───────────────────────────────────────────────────
function showScreen(id) {{
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(id).classList.add('active');
}}

function toast(msg) {{
    const t = document.createElement('div');
    t.className = 'toast';
    t.textContent = msg;
    document.getElementById('toasts').appendChild(t);
    setTimeout(() => t.remove(), 3000);
}}

// ── Welcome ──────────────────────────────────────────────────────
function startReview() {{
    const name = document.getElementById('name-input').value.trim();
    if (!name) {{ toast('Please enter your name'); return; }}
    state.reviewer = name;
    save();
    showScreen('review');
    showNextUnreviewed();
}}

// Restore session on load
if (state.reviewer) {{
    document.getElementById('name-input').value = state.reviewer;
}}

// Enter key on name input
document.getElementById('name-input').addEventListener('keydown', e => {{
    if (e.key === 'Enter') startReview();
}});

// ── Review flow ──────────────────────────────────────────────────
let currentRecId = null;

function getUnreviewedIndices() {{
    const indices = [];
    for (let i = 0; i < RECORDS.length; i++) {{
        if (!state.reviews[RECORDS[i].id]) indices.push(i);
    }}
    return indices;
}}

function showNextUnreviewed() {{
    const pending = getUnreviewedIndices();
    updateProgress();

    if (pending.length === 0) {{
        showDone();
        return;
    }}

    renderRecord(pending[0]);
}}

function updateProgress() {{
    const reviewed = Object.keys(state.reviews).length;
    const total = RECORDS.length;
    const pct = total > 0 ? (reviewed / total * 100) : 0;
    document.getElementById('pbar-fill').style.width = pct + '%';
    document.getElementById('topbar-count').textContent = `${{reviewed}} / ${{total}}`;
    document.getElementById('topbar-name').textContent = state.reviewer;
}}

function renderRecord(idx) {{
    const rec = RECORDS[idx];
    currentRecId = rec.id;
    const data = rec.data;
    const container = document.getElementById('review-content');

    let html = `
    <div class="rec-title-bar">
        <h2>${{data.title || data.question || rec.id}}</h2>
        <span class="tag tag-blue">${{rec.type_label}}</span>
        <span class="tag tag-dim">${{rec.id}}</span>
    </div>`;

    // Required Elements (scenarios)
    if (data.required_elements) {{
        for (const [section, items] of Object.entries(data.required_elements)) {{
            html += `<div class="section"><div class="section-hd">${{section.replace(/_/g, ' ')}}</div>`;
            items.forEach((item, i) => {{
                html += elHTML(`${{section}}:${{i}}`, item);
            }});
            html += '</div>';
        }}
    }}

    // Expected Facts (test cases)
    if (data.expected_facts) {{
        html += '<div class="section"><div class="section-hd">Expected Facts</div>';
        data.expected_facts.forEach((item, i) => {{
            html += elHTML(`facts:${{i}}`, item);
        }});
        html += '</div>';
    }}

    // Safety
    const safety = data.safety_warnings || data.safety_notes || [];
    if (safety.length) {{
        html += '<div class="section"><div class="section-hd safety">Safety Warnings</div>';
        safety.forEach((item, i) => {{
            html += elHTML(`safety:${{i}}`, item, 'safety');
        }});
        html += '</div>';
    }}

    // Technical Values
    const vals = data.technical_values || data.expected_values || {{}};
    if (Object.keys(vals).length) {{
        html += '<div class="section"><div class="section-hd">Technical Values</div><table class="val-tbl"><thead><tr><th></th><th>Parameter</th><th>Value</th><th>Correction</th></tr></thead><tbody>';
        for (const [k, v] of Object.entries(vals)) {{
            html += `<tr>
                <td><div class="el-btns" style="flex-direction:row">
                    <button class="vb ok" data-el="values:${{k}}" onclick="voteEl(this,'ok')">&#10003;</button>
                    <button class="vb no" data-el="values:${{k}}" onclick="voteEl(this,'no')">&#10007;</button>
                </div></td>
                <td style="font-weight:500;color:var(--bright)">${{k.replace(/_/g, ' ')}}</td>
                <td><code>${{v}}</code></td>
                <td><input class="val-fix" data-el="values:${{k}}" placeholder="Correct value..."></td>
            </tr>`;
        }}
        html += '</tbody></table></div>';
    }}

    // Forbidden
    if (data.forbidden_content) {{
        html += '<div class="section"><div class="section-hd forbidden">Forbidden Content</div>';
        data.forbidden_content.forEach((item, i) => {{
            html += elHTML(`forbidden:${{i}}`, item, 'forbidden');
        }});
        html += '</div>';
    }}

    // References
    if (data.references) {{
        html += '<div class="section"><div class="section-hd">References</div><ul class="refs">';
        data.references.forEach(r => html += `<li>${{r}}</li>`);
        html += '</ul></div>';
    }}

    // Comment
    html += `<div class="comment-section">
        <label>Overall Comments (optional)</label>
        <textarea id="rec-comment" placeholder="Missing elements, corrections, or general feedback..."></textarea>
    </div>`;

    container.innerHTML = html;
    window.scrollTo(0, 0);
}}

function elHTML(key, text, cls = '') {{
    return `<div class="el ${{cls}}">
        <div class="el-btns">
            <button class="vb ok" data-el="${{key}}" onclick="voteEl(this,'ok')" title="Correct">&#10003;</button>
            <button class="vb no" data-el="${{key}}" onclick="voteEl(this,'no')" title="Wrong">&#10007;</button>
            <button class="vb ed" data-el="${{key}}" onclick="voteEl(this,'edit')" title="Edit">&#9998;</button>
        </div>
        <div class="el-txt">${{text}}</div>
        <div class="el-note"><textarea data-el="${{key}}" placeholder="Suggest correction..."></textarea></div>
    </div>`;
}}

function voteEl(btn, type) {{
    const el = btn.closest('.el, tr');
    el.querySelectorAll('.vb').forEach(b => b.classList.remove('on'));
    btn.classList.add('on');
    if (type === 'edit' || type === 'no') el.classList.add('show-note');
    else el.classList.remove('show-note');
    // Auto-save element vote immediately
    autoSaveElementVotes();
}}

function autoSaveElementVotes() {{
    if (!currentRecId) return;
    const elReviews = collectElementVotes();
    if (!state.reviews[currentRecId]) {{
        state.reviews[currentRecId] = {{
            record_id: currentRecId,
            status: 'in_progress',
            reviewer: state.reviewer,
            element_reviews: {{}},
            comments: '',
            reviewed_at: new Date().toISOString(),
        }};
    }}
    state.reviews[currentRecId].element_reviews = elReviews;
    state.reviews[currentRecId].reviewed_at = new Date().toISOString();
    save();
}}

function collectElementVotes() {{
    const votes = {{}};
    document.querySelectorAll('.vb.on').forEach(btn => {{
        const key = btn.dataset.el;
        if (!key) return;
        let v = 'ok';
        if (btn.classList.contains('no')) v = 'rejected';
        else if (btn.classList.contains('ed')) v = 'needs_edit';
        // Find note
        const noteEl = document.querySelector(`textarea[data-el="${{key}}"], input.val-fix[data-el="${{key}}"]`);
        const note = noteEl ? noteEl.value.trim() : '';
        votes[key] = {{ vote: v, note }};
    }});
    return votes;
}}

function submitCurrent(status) {{
    if (!currentRecId) return;
    const comment = document.getElementById('rec-comment')?.value.trim() || '';
    const elReviews = collectElementVotes();
    const rec = RECORDS.find(r => r.id === currentRecId);

    state.reviews[currentRecId] = {{
        record_id: currentRecId,
        record_type: rec?.type || '',
        status,
        reviewer: state.reviewer,
        comments: comment,
        element_reviews: elReviews,
        reviewed_at: new Date().toISOString(),
    }};
    save();

    const labels = {{ approved: 'Approved', modified: 'Needs Changes', rejected: 'Rejected' }};
    toast(`${{currentRecId}}: ${{labels[status]}}`);
    showNextUnreviewed();
}}

function skipRecord() {{
    showNextUnreviewed();
}}

function finishEarly() {{
    showDone();
}}

function backToReview() {{
    showScreen('review');
    showNextUnreviewed();
}}

// ── Done screen ──────────────────────────────────────────────────
function showDone() {{
    showScreen('done');
    const reviews = Object.values(state.reviews).filter(r => r.status !== 'in_progress');
    const approved = reviews.filter(r => r.status === 'approved').length;
    const modified = reviews.filter(r => r.status === 'modified').length;
    const rejected = reviews.filter(r => r.status === 'rejected').length;
    const skipped = RECORDS.length - approved - modified - rejected;

    document.getElementById('d-approved').textContent = approved;
    document.getElementById('d-modified').textContent = modified;
    document.getElementById('d-rejected').textContent = rejected;
    document.getElementById('d-skipped').textContent = skipped;
}}

function buildExport() {{
    const completedReviews = Object.values(state.reviews).filter(r => r.status !== 'in_progress');
    const a = completedReviews.filter(r => r.status === 'approved').length;
    const m = completedReviews.filter(r => r.status === 'modified').length;
    const rej = completedReviews.filter(r => r.status === 'rejected').length;
    return JSON.stringify({{
        exported_at: new Date().toISOString(),
        reviewer: state.reviewer,
        summary: {{
            total: RECORDS.length,
            reviewed: completedReviews.length,
            approved: a,
            modified: m,
            rejected: rej,
            pending: RECORDS.length - completedReviews.length,
        }},
        reviews: completedReviews,
    }}, null, 2);
}}

function downloadJSON() {{
    const json = buildExport();
    const name = state.reviewer.replace(/\\s+/g, '_').toLowerCase() || 'reviewer';
    const fname = `golden_review_${{name}}_${{new Date().toISOString().slice(0,10)}}.json`;
    const blob = new Blob([json], {{ type: 'application/json' }});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = fname;
    a.click();
    URL.revokeObjectURL(a.href);
    toast('Downloaded ' + fname);
}}

function copyJSON() {{
    const json = buildExport();
    navigator.clipboard.writeText(json).then(() => {{
        toast('Copied to clipboard');
        const pre = document.getElementById('export-preview');
        pre.style.display = 'block';
        pre.textContent = json;
    }});
}}

function emailJSON() {{
    const json = buildExport();
    const p = JSON.parse(json);
    const s = p.summary;
    const subj = encodeURIComponent('Golden Record Review - ' + state.reviewer);
    const body = encodeURIComponent(
        'Golden Record Review from ' + state.reviewer + '\\n' +
        'Date: ' + new Date().toLocaleDateString() + '\\n\\n' +
        'Summary:\\n' +
        '  Approved: ' + s.approved + '\\n' +
        '  Needs Changes: ' + s.modified + '\\n' +
        '  Rejected: ' + s.rejected + '\\n' +
        '  Pending: ' + s.pending + '\\n\\n' +
        '--- Full JSON ---\\n\\n' + json
    );
    window.location.href = 'mailto:?subject=' + subj + '&body=' + body;
    toast('Opening email client...');
}}
</script>
</body>
</html>"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate standalone golden record validation HTML")
    parser.add_argument("-o", "--output", default="golden_record_review.html", help="Output file path")
    args = parser.parse_args()

    records = load_golden_records()
    html = generate_standalone_validation_html(records)

    out_path = Path(args.output)
    out_path.write_text(html)
    size_kb = out_path.stat().st_size // 1024
    print(f"Generated: {out_path} ({size_kb} KB)")
    print(f"Share via email. Technicians open in any browser, review, and send back JSON results.")
