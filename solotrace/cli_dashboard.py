"""
solotrace dashboard  --  Static HTML dashboard generator

Reads out-before/ and out/ audit results and writes docs/index.html:
a single self-contained static HTML file with inline CSS/JS and embedded JSON.

Usage
-----
    python -m solotrace dashboard --before out-before --after out
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _count_test_functions(tests_dir: Path) -> int:
    """Count unique test function names defined in tests_dir/*.py."""
    import ast as _ast
    names: set[str] = set()
    if not tests_dir.exists():
        return 0
    for py_file in tests_dir.glob("test_*.py"):
        try:
            tree = _ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                if node.name.startswith("test"):
                    names.add(f"{py_file.name}::{node.name}")
    return len(names)


# ── HTML template ─────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SoloTrace — Compliance Dashboard</title>
<style>
/* ── CSS Custom Properties ─────────────────────────────────────────────────── */
:root {{
  --bg-page:     #161616;
  --bg-card:     #1e1e1e;
  --bg-card2:    #262626;
  --bg-header:   #0f0f0f;
  --border:      #393939;
  --text-main:   #f4f4f4;
  --text-muted:  #8d8d8d;
  --text-dim:    #6f6f6f;
  --ibm-blue:    #4589ff;
  --ibm-blue-dk: #0043ce;
  --green:       #42be65;
  --amber:       #f1c21b;
  --red:         #fa4d56;
  --purple:      #be95ff;
  --radius:      6px;
  --shadow:      0 2px 8px rgba(0,0,0,.45);
  --transition:  0.2s ease;
}}
@media (prefers-color-scheme: light) {{
  html:not([data-theme="dark"]) {{
    --bg-page:   #f4f4f4;
    --bg-card:   #ffffff;
    --bg-card2:  #f4f4f4;
    --bg-header: #ffffff;
    --border:    #e0e0e0;
    --text-main: #161616;
    --text-muted:#525252;
    --text-dim:  #8d8d8d;
    --shadow:    0 2px 8px rgba(0,0,0,.12);
  }}
}}
/* ── Reset & Base ─────────────────────────────────────────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif;
  background: var(--bg-page);
  color: var(--text-main);
  line-height: 1.6;
  min-height: 100vh;
}}
a {{ color: var(--ibm-blue); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
/* ── Layout ───────────────────────────────────────────────────────────────── */
.page-wrap {{ max-width: 1200px; margin: 0 auto; padding: 0 1.5rem 3rem; }}
/* ── Header ───────────────────────────────────────────────────────────────── */
.site-header {{
  background: var(--bg-header);
  border-bottom: 1px solid var(--border);
  padding: 1.25rem 1.5rem;
  position: sticky; top: 0; z-index: 100;
}}
.header-inner {{
  max-width: 1200px; margin: 0 auto;
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  flex-wrap: wrap;
}}
.logo {{ display: flex; align-items: center; gap: 0.75rem; }}
.logo-mark {{
  width: 36px; height: 36px; background: var(--ibm-blue);
  border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 0.85rem; color: #fff; flex-shrink: 0;
}}
.logo-text {{ font-size: 1.2rem; font-weight: 700; letter-spacing: -0.02em; }}
.logo-sub {{ font-size: 0.75rem; color: var(--text-muted); display: block; margin-top: -2px; }}
.header-meta {{ display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }}
.ibm-badge {{
  background: var(--ibm-blue-dk); color: #fff;
  padding: 0.3rem 0.85rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600;
  white-space: nowrap;
}}
.theme-btn {{
  background: none; border: 1px solid var(--border);
  color: var(--text-muted); padding: 0.3rem 0.7rem;
  border-radius: var(--radius); cursor: pointer; font-size: 0.8rem;
}}
.theme-btn:hover {{ border-color: var(--ibm-blue); color: var(--ibm-blue); }}
/* ── Hero ─────────────────────────────────────────────────────────────────── */
.hero {{
  padding: 3rem 0 2rem;
  text-align: center;
}}
.hero h1 {{
  font-size: clamp(1.8rem, 4vw, 2.8rem);
  font-weight: 700; margin-bottom: 0.5rem;
  letter-spacing: -0.03em;
}}
.hero h1 span {{ color: var(--ibm-blue); }}
.hero-sub {{ color: var(--text-muted); font-size: 1rem; margin-bottom: 2.5rem; }}
.score-compare {{
  display: flex; align-items: center; justify-content: center; gap: 1.5rem;
  flex-wrap: wrap; margin-bottom: 2rem;
}}
.score-box {{
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1.5rem 2rem; min-width: 160px;
  box-shadow: var(--shadow);
}}
.score-box .label {{ font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.35rem; }}
.score-box .value {{
  font-size: 2.5rem; font-weight: 800; letter-spacing: -0.04em; line-height: 1;
}}
.score-box.before .value {{ color: var(--red); }}
.score-box.after  .value {{ color: var(--green); }}
.score-arrow {{ font-size: 2rem; color: var(--ibm-blue); }}
.progress-wrap {{ max-width: 600px; margin: 0 auto; }}
.progress-label {{
  display: flex; justify-content: space-between;
  font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.4rem;
}}
.progress-bar {{ height: 10px; background: var(--bg-card2); border-radius: 999px; overflow: hidden; }}
.progress-fill {{
  height: 100%; background: linear-gradient(90deg, var(--ibm-blue), var(--green));
  border-radius: 999px; width: 0;
  transition: width 1.4s cubic-bezier(.22,.68,0,1.2);
}}
/* ── Stat Cards ───────────────────────────────────────────────────────────── */
.stat-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem; margin: 2.5rem 0;
}}
.stat-card {{
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1.25rem 1.5rem;
  box-shadow: var(--shadow);
  border-top: 3px solid var(--ibm-blue);
}}
.stat-card .n {{
  font-size: 2.2rem; font-weight: 800; letter-spacing: -0.03em;
  color: var(--ibm-blue); line-height: 1; margin-bottom: 0.3rem;
}}
.stat-card .desc {{ font-size: 0.85rem; color: var(--text-muted); }}
/* ── Section ──────────────────────────────────────────────────────────────── */
.section {{ margin: 2.5rem 0; }}
.section-title {{
  font-size: 1.15rem; font-weight: 700; margin-bottom: 1rem;
  display: flex; align-items: center; gap: 0.5rem;
}}
.section-title::before {{ content: ''; display: block; width: 4px; height: 1.2em; background: var(--ibm-blue); border-radius: 2px; }}
/* ── Pipeline Strip ───────────────────────────────────────────────────────── */
.pipeline {{
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1.5rem; overflow-x: auto;
  box-shadow: var(--shadow);
}}
.pipeline-steps {{
  display: flex; align-items: center; gap: 0; min-width: max-content;
}}
.pipeline-step {{
  display: flex; flex-direction: column; align-items: center;
  text-align: center; min-width: 110px;
}}
.step-icon {{
  width: 44px; height: 44px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem; margin-bottom: 0.5rem;
  border: 2px solid;
}}
.step-icon.bob    {{ background: rgba(69,137,255,.15); border-color: var(--ibm-blue); color: var(--ibm-blue); }}
.step-icon.auto   {{ background: rgba(66,190,101,.15); border-color: var(--green); color: var(--green); }}
.step-icon.human  {{ background: rgba(241,194,27,.15); border-color: var(--amber); color: var(--amber); }}
.step-label {{ font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-main); }}
.step-sub   {{ font-size: 0.65rem; color: var(--text-muted); margin-top: 2px; max-width: 100px; }}
.pipeline-arrow {{
  font-size: 1rem; color: var(--text-dim); margin: 0 0.25rem; padding-bottom: 1.5rem; flex-shrink: 0;
}}
/* ── Matrix Table ─────────────────────────────────────────────────────────── */
.filter-bar {{ display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem; }}
.filter-btn {{
  background: var(--bg-card); border: 1px solid var(--border);
  color: var(--text-muted); padding: 0.3rem 0.9rem;
  border-radius: 20px; cursor: pointer; font-size: 0.8rem; transition: var(--transition);
}}
.filter-btn:hover {{ border-color: var(--ibm-blue); color: var(--ibm-blue); }}
.filter-btn.active {{ background: var(--ibm-blue); border-color: var(--ibm-blue); color: #fff; }}
.table-wrap {{ overflow-x: auto; border-radius: var(--radius); border: 1px solid var(--border); }}
table {{
  width: 100%; border-collapse: collapse; font-size: 0.82rem;
  background: var(--bg-card);
}}
thead {{ background: var(--bg-card2); position: sticky; top: 60px; z-index: 10; }}
th {{
  padding: 0.7rem 1rem; text-align: left;
  font-size: 0.72rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--text-muted); white-space: nowrap;
  border-bottom: 1px solid var(--border);
}}
td {{ padding: 0.65rem 1rem; border-bottom: 1px solid var(--border); vertical-align: top; }}
tr:last-child td {{ border-bottom: none; }}
tr:hover td {{ background: rgba(69,137,255,.04); }}
.badge {{
  display: inline-flex; align-items: center; gap: 0.3em;
  padding: 0.18em 0.6em; border-radius: 20px;
  font-size: 0.72rem; font-weight: 600; white-space: nowrap;
}}
.badge-covered    {{ background: rgba(66,190,101,.15); color: var(--green); border: 1px solid rgba(66,190,101,.3); }}
.badge-untested   {{ background: rgba(241,194,27,.15); color: var(--amber); border: 1px solid rgba(241,194,27,.3); }}
.badge-contradicts{{ background: rgba(250,77,86,.15);  color: var(--red);   border: 1px solid rgba(250,77,86,.3); }}
.badge-missing    {{ background: rgba(250,77,86,.15);  color: var(--red);   border: 1px solid rgba(250,77,86,.3); }}
.badge-new        {{ background: rgba(190,149,255,.15); color: var(--purple); border: 1px solid rgba(190,149,255,.3); }}
.badge-changed    {{ background: rgba(241,194,27,.15); color: var(--amber); border: 1px solid rgba(241,194,27,.3); }}
.badge-none       {{ background: var(--bg-card2); color: var(--text-dim); border: 1px solid var(--border); }}
.badge-high       {{ background: rgba(250,77,86,.12); color: var(--red); }}
.badge-medium     {{ background: rgba(241,194,27,.12); color: var(--amber); }}
.badge-low        {{ background: rgba(66,190,101,.12); color: var(--green); }}
.evidence-snippet {{
  background: var(--bg-card2); border: 1px solid var(--border);
  border-radius: 4px; padding: 0.4rem 0.6rem;
  font-family: 'IBM Plex Mono', 'Fira Code', monospace;
  font-size: 0.72rem; color: var(--text-muted); white-space: pre-wrap;
  margin-top: 0.3rem; max-height: 120px; overflow-y: auto;
  display: none;
}}
.ev-toggle {{
  background: none; border: 1px solid var(--border);
  color: var(--text-muted); padding: 0.15rem 0.45rem;
  border-radius: 4px; cursor: pointer; font-size: 0.7rem;
  transition: var(--transition);
}}
.ev-toggle:hover {{ border-color: var(--ibm-blue); color: var(--ibm-blue); }}
.test-list {{ display: flex; flex-direction: column; gap: 2px; }}
.test-item {{
  font-size: 0.72rem; color: var(--text-muted);
  font-family: 'IBM Plex Mono', monospace;
}}
/* ── Evidence Verifier Panel ─────────────────────────────────────────────── */
.verifier-panel {{
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1.5rem; box-shadow: var(--shadow);
}}
.verifier-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 1rem; margin-bottom: 1.5rem;
}}
.verifier-stat {{
  background: var(--bg-card2); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1rem;
}}
.verifier-stat .n {{ font-size: 1.9rem; font-weight: 800; letter-spacing: -0.03em; }}
.verifier-stat.wrong .n {{ color: var(--red); }}
.verifier-stat.fixed .n {{ color: var(--green); }}
.verifier-stat.phantom .n {{ color: var(--amber); }}
.verifier-stat .d {{ font-size: 0.78rem; color: var(--text-muted); margin-top: 0.2rem; }}
.verifier-note {{ font-size: 0.82rem; color: var(--text-muted); line-height: 1.6; }}
/* ── Footer ───────────────────────────────────────────────────────────────── */
.site-footer {{
  border-top: 1px solid var(--border); padding: 1.5rem;
  text-align: center; color: var(--text-muted); font-size: 0.8rem; margin-top: 3rem;
}}
.site-footer a {{ color: var(--ibm-blue); }}
/* ── Responsive ───────────────────────────────────────────────────────────── */
@media (max-width: 600px) {{
  .score-compare {{ gap: 1rem; }}
  .score-box .value {{ font-size: 2rem; }}
  th, td {{ padding: 0.5rem 0.6rem; }}
}}
</style>
</head>
<body>

<!-- ── Header ─────────────────────────────────────────────────────────────── -->
<header class="site-header">
  <div class="header-inner">
    <div class="logo">
      <div class="logo-mark">ST</div>
      <div>
        <div class="logo-text">SoloTrace</div>
        <span class="logo-sub">Requirements Traceability Auditor</span>
      </div>
    </div>
    <div class="header-meta">
      <span class="ibm-badge">Built with IBM Bob 2.0</span>
      <button class="theme-btn" onclick="toggleTheme()">☀ / ☾</button>
    </div>
  </div>
</header>

<!-- ── Hero ───────────────────────────────────────────────────────────────── -->
<div class="page-wrap">
<section class="hero">
  <h1>Every requirement, <span>proven.</span></h1>
  <p class="hero-sub">Machine-verified traceability from specification to code to test.</p>

  <div class="score-compare">
    <div class="score-box before">
      <div class="label">Before (v1.0 audit)</div>
      <div class="value" id="score-before">{score_before}%</div>
    </div>
    <div class="score-arrow">→</div>
    <div class="score-box after">
      <div class="label">After (v2.0 fixed)</div>
      <div class="value" id="score-after">{score_after}%</div>
    </div>
  </div>

  <div class="progress-wrap">
    <div class="progress-label">
      <span>Compliance score</span>
      <span id="pct-label">{score_after}%</span>
    </div>
    <div class="progress-bar">
      <div class="progress-fill" id="prog-fill" data-target="{score_after}"></div>
    </div>
  </div>
</section>

<!-- ── Stat Cards ──────────────────────────────────────────────────────────── -->
<div class="stat-grid">
  <div class="stat-card">
    <div class="n">{total_reqs}</div>
    <div class="desc">Requirements audited</div>
  </div>
  <div class="stat-card">
    <div class="n">{gaps_fixed}</div>
    <div class="desc">Gaps found &amp; fixed</div>
  </div>
  <div class="stat-card">
    <div class="n">+{tests_added}</div>
    <div class="desc">Test functions added ({tests_before} → {tests_after})</div>
  </div>
  <div class="stat-card">
    <div class="n">{evidence_entries}</div>
    <div class="desc">Evidence entries machine-verified</div>
  </div>
</div>

<!-- ── Pipeline Strip ─────────────────────────────────────────────────────── -->
<section class="section">
  <div class="section-title">Audit Pipeline</div>
  <div class="pipeline">
    <div class="pipeline-steps">
      <div class="pipeline-step">
        <div class="step-icon bob">📄</div>
        <div class="step-label">READ</div>
        <div class="step-sub">Document understanding<br><em>IBM Bob</em></div>
      </div>
      <div class="pipeline-arrow">›</div>
      <div class="pipeline-step">
        <div class="step-icon bob">🔍</div>
        <div class="step-label">AUDIT</div>
        <div class="step-sub">12 parallel subagents<br><em>IBM Bob</em></div>
      </div>
      <div class="pipeline-arrow">›</div>
      <div class="pipeline-step">
        <div class="step-icon human">✋</div>
        <div class="step-label">HUMAN SIGN-OFF</div>
        <div class="step-sub">Review verdicts<br>&amp; approve fixes</div>
      </div>
      <div class="pipeline-arrow">›</div>
      <div class="pipeline-step">
        <div class="step-icon bob">🔧</div>
        <div class="step-label">FIX</div>
        <div class="step-sub">Agent mode<br><em>IBM Bob</em></div>
      </div>
      <div class="pipeline-arrow">›</div>
      <div class="pipeline-step">
        <div class="step-icon auto">✅</div>
        <div class="step-label">VERIFY</div>
        <div class="step-sub">Anti-hallucination<br>evidence check</div>
      </div>
      <div class="pipeline-arrow">›</div>
      <div class="pipeline-step">
        <div class="step-icon auto">📊</div>
        <div class="step-label">REPORT</div>
        <div class="step-sub">Matrix + dashboard<br>generated</div>
      </div>
    </div>
  </div>
</section>

<!-- ── Traceability Matrix ─────────────────────────────────────────────────── -->
<section class="section">
  <div class="section-title">Traceability Matrix</div>
  <div class="filter-bar" id="filter-bar">
    <button class="filter-btn active" data-filter="all" onclick="filterMatrix('all',this)">All ({total_reqs})</button>
    <button class="filter-btn" data-filter="covered" onclick="filterMatrix('covered',this)">✅ Covered ({n_covered})</button>
    <button class="filter-btn" data-filter="untested" onclick="filterMatrix('untested',this)">⚠ Untested ({n_untested})</button>
    <button class="filter-btn" data-filter="contradicts" onclick="filterMatrix('contradicts',this)">✗ Contradicts ({n_contradicts})</button>
    <button class="filter-btn" data-filter="missing" onclick="filterMatrix('missing',this)">● Missing ({n_missing})</button>
  </div>
  <div class="table-wrap">
    <table id="matrix-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Requirement</th>
          <th>Risk</th>
          <th>Change</th>
          <th>Before</th>
          <th>After</th>
          <th>Code Evidence</th>
          <th>Tests</th>
        </tr>
      </thead>
      <tbody id="matrix-body">
      </tbody>
    </table>
  </div>
</section>

<!-- ── Evidence Verifier Panel ───────────────────────────────────────────── -->
<section class="section">
  <div class="section-title">Evidence Verifier</div>
  <div class="verifier-panel">
    <div class="verifier-grid">
      <div class="verifier-stat wrong">
        <div class="n" id="vstat-wrong">{verif_before_corrected}</div>
        <div class="d">Wrong line numbers in baseline audit</div>
      </div>
      <div class="verifier-stat wrong">
        <div class="n" id="vstat-paraphrase">{verif_before_replaced}</div>
        <div class="d">Paraphrased quotes (not real code)</div>
      </div>
      <div class="verifier-stat phantom">
        <div class="n" id="vstat-phantom">{verif_before_phantom}</div>
        <div class="d">Phantom tests (not found in AST)</div>
      </div>
      <div class="verifier-stat fixed">
        <div class="n" id="vstat-ok">{verif_after_ok}</div>
        <div class="d">Evidence entries verified OK (after)</div>
      </div>
    </div>
    <p class="verifier-note">
      The SoloTrace evidence verifier runs after every audit pass.  It parses each
      cited source file at the cited line number, checks that the quoted snippet
      actually appears there (±5 lines), and removes any <code>test_evidence</code>
      entry whose function name cannot be found in the file's AST.  Numbers above
      are read from <code>out-before/verification.json</code> vs
      <code>out/verification.json</code>.
    </p>
  </div>
</section>

</div><!-- .page-wrap -->

<!-- ── Footer ─────────────────────────────────────────────────────────────── -->
<footer class="site-footer">
  <a href="https://github.com/bano1397/solotrace" target="_blank" rel="noopener">GitHub: bano1397/solotrace</a>
  &nbsp;·&nbsp;
  <a href="AUDIT_REPORT.md" target="_blank">AUDIT_REPORT.md</a>
  &nbsp;·&nbsp;
  <span>Generated {generated_at}</span>
</footer>

<!-- ── Embedded Data ───────────────────────────────────────────────────────── -->
<script>
const MATRIX_DATA = {matrix_json};
const BEFORE_MAP  = {before_map_json};

function statusBadge(s) {{
  const m = {{
    covered:    ['badge-covered',    '✅ covered'],
    untested:   ['badge-untested',   '⚠ untested'],
    contradicts:['badge-contradicts','✗ contradicts'],
    missing:    ['badge-missing',    '● missing'],
  }};
  const [cls, label] = m[s] || ['', s];
  return `<span class="badge ${{cls}}">${{label}}</span>`;
}}
function changeBadge(c) {{
  const m = {{ new:'badge-new', changed:'badge-changed', none:'badge-none' }};
  return `<span class="badge ${{m[c]||'badge-none'}}">${{c}}</span>`;
}}
function riskBadge(r) {{
  const m = {{ High:'badge-high', Medium:'badge-medium', Low:'badge-low' }};
  return `<span class="badge ${{m[r]||''}}">${{r}}</span>`;
}}

function buildMatrix(filter) {{
  const tbody = document.getElementById('matrix-body');
  const rows  = MATRIX_DATA.rows;
  const html  = [];
  rows.forEach((row, i) => {{
    if (filter !== 'all' && row.status !== filter) return;
    const beforeStatus = BEFORE_MAP[row.id] || 'missing';
    const ev = row.evidence || [];
    const evId = `ev-${{i}}`;
    const evHtml = ev.length
      ? `<button class="ev-toggle" onclick="toggleEvidence('${{evId}}')">Show ${{ev.length}}</button>
         <div class="evidence-snippet" id="${{evId}}">${{ev.map(e=>escHtml(e)).join('\\n')}}</div>`
      : '<span style="color:var(--text-dim)">—</span>';

    const tests = row.tests || [];
    const testHtml = tests.length
      ? `<div class="test-list">${{tests.map(t => `<span class="test-item">${{escHtml(t.split(' (')[0])}}</span>`).join('')}}</div>`
      : '<span style="color:var(--text-dim)">—</span>';

    html.push(`<tr data-status="${{row.status}}">
      <td><strong>${{row.id}}</strong></td>
      <td>${{escHtml(row.title)}}</td>
      <td>${{riskBadge(row.risk)}}</td>
      <td>${{changeBadge(row.change)}}</td>
      <td>${{statusBadge(beforeStatus)}}</td>
      <td>${{statusBadge(row.status)}}</td>
      <td>${{evHtml}}</td>
      <td>${{testHtml}}</td>
    </tr>`);
  }});
  tbody.innerHTML = html.join('');
}}

function filterMatrix(filter, btn) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  buildMatrix(filter);
}}

function toggleEvidence(id) {{
  const el = document.getElementById(id);
  if (!el) return;
  el.style.display = el.style.display === 'block' ? 'none' : 'block';
}}

function escHtml(s) {{
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}}

function toggleTheme() {{
  const html = document.documentElement;
  html.dataset.theme = html.dataset.theme === 'dark' ? 'light' : 'dark';
}}

// Animate progress bar on load
window.addEventListener('load', () => {{
  buildMatrix('all');
  setTimeout(() => {{
    const fill = document.getElementById('prog-fill');
    if (fill) fill.style.width = fill.dataset.target + '%';
  }}, 300);
}});
</script>
</body>
</html>
"""


# ── public command ─────────────────────────────────────────────────────────────

def cmd_dashboard(before_dir: str, after_dir: str) -> None:
    """Generate docs/index.html from before/after audit directories."""
    before = Path(before_dir)
    after  = Path(after_dir)

    m_before = _load_json(before / "matrix.json") or {}
    m_after  = _load_json(after  / "matrix.json") or {}

    if not m_after:
        print(f"ERROR: matrix.json not found in {after_dir}. "
              "Run `python -m solotrace matrix` first.", file=sys.stderr)
        sys.exit(1)

    summary_before = m_before.get("summary", {})
    summary_after  = m_after.get("summary",  {})

    score_before = summary_before.get("score_percent", 0.0)
    score_after  = summary_after.get("score_percent",  0.0)

    # Format scores: show one decimal only when non-integer
    def fmt_pct(v: float) -> str:
        return str(int(v)) if v == int(v) else f"{v:.1f}"

    total_reqs    = summary_after.get("total", 0)
    n_covered     = summary_after.get("covered", 0)
    n_untested    = summary_after.get("untested", 0)
    n_contradicts = summary_after.get("contradicts", 0)
    n_missing     = summary_after.get("missing", 0)

    # Gaps fixed = requirements that were NOT covered before and ARE covered after
    rows_before_by_id = {r["id"]: r for r in m_before.get("rows", [])}
    rows_after        = m_after.get("rows", [])
    gaps_fixed = sum(
        1 for r in rows_after
        if r["status"] == "covered"
        and rows_before_by_id.get(r["id"], {}).get("status", "missing") != "covered"
    )

    # Test function counts
    tests_dir = Path("ledgerlite/tests")
    tests_after = _count_test_functions(tests_dir)

    # Count test functions referenced in before matrix (unique names)
    tests_before_names: set[str] = set()
    for row in m_before.get("rows", []):
        for t in row.get("tests", []):
            name = t.split(" (")[0]
            tests_before_names.add(name)
    tests_before = len(tests_before_names)
    tests_added  = max(0, tests_after - tests_before)

    # Evidence entries
    verif_after  = _load_json(after  / "verification.json") or {}
    verif_before = _load_json(before / "verification.json") or {}
    evidence_entries     = verif_after.get("totals",  {}).get("checked", 0)
    verif_before_corrected = verif_before.get("totals", {}).get("corrected", 0)
    verif_before_replaced  = verif_before.get("totals", {}).get("replaced",  0)
    verif_before_phantom   = verif_before.get("totals", {}).get("tests_removed", 0)
    verif_after_ok         = verif_after.get("totals",  {}).get("ok", 0)

    # Build before-status map for the table
    before_map = {r["id"]: r.get("status", "missing") for r in m_before.get("rows", [])}

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html = _HTML_TEMPLATE.format(
        score_before=fmt_pct(score_before),
        score_after=fmt_pct(score_after),
        total_reqs=total_reqs,
        gaps_fixed=gaps_fixed,
        tests_before=tests_before,
        tests_after=tests_after,
        tests_added=tests_added,
        evidence_entries=evidence_entries,
        n_covered=n_covered,
        n_untested=n_untested,
        n_contradicts=n_contradicts,
        n_missing=n_missing,
        verif_before_corrected=verif_before_corrected,
        verif_before_replaced=verif_before_replaced,
        verif_before_phantom=verif_before_phantom,
        verif_after_ok=verif_after_ok,
        matrix_json=json.dumps(m_after),
        before_map_json=json.dumps(before_map),
        generated_at=generated_at,
    )

    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)
    out_path = docs_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Dashboard written: {out_path}")
    print(f"  Before score : {fmt_pct(score_before)}%")
    print(f"  After score  : {fmt_pct(score_after)}%")
    print(f"  Requirements : {total_reqs}")
    print(f"  Tests added  : +{tests_added}  ({tests_before} → {tests_after})")
