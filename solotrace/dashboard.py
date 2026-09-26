"""
solotrace dashboard — a self-contained static page (docs/index.html) for GitHub Pages.

No external requests: CSS, JavaScript, data and the favicon are inline; the only
other files are Bob session screenshots copied to docs/assets/.  Data is embedded
as JSON with ``<`` escaped, and the page renders it with textContent only, so no
verdict text can inject markup.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from solotrace import __version__

REPO_URL = "https://github.com/bano1397/solotrace"
PAGES_URL = "https://bano1397.github.io/solotrace/"

BOB_CONFIG = [
    (".bob/custom_modes.yaml", "SoloTrace Auditor custom mode: auditor role, tool groups, subagents"),
    (".bob/rules-solotrace/01-audit-rules.md", "Evidence rules: cite file:line, four verdicts, no edits during an audit"),
    (".bob/skills/solotrace-audit/SKILL.md", "Reusable skill: Read → Audit → Prove → Report on any repo and spec"),
    ("AGENTS.md", "Project map loaded automatically by every Bob task"),
]


def _load(path: Path) -> Any | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _stage(key: str, label: str, matrix: dict | None, verification: dict | None, extra: dict) -> dict | None:
    if not matrix:
        return None
    s = matrix["summary"]
    audit = matrix.get("audit", {})
    tests = s.get("tests_run") or {}
    v = (verification or {}).get("totals", {})
    return {
        "key": key,
        "label": label,
        "task": audit.get("bob_task"),
        "auditor": audit.get("auditor"),
        "audited_at": audit.get("audited_at"),
        "commit": (audit.get("code_commit") or "")[:7],
        "total": s["total"],
        "ai_covered": s["ai"]["covered"],
        "evidence_ok": s["statuses"]["proven"] + s["statuses"]["covered"],
        "proven": s["statuses"]["proven"] if s["mutation_testing"] else None,
        "mutation_testing": s["mutation_testing"],
        "mutations_killed": s["mutations_killed"],
        "mutations_total": s["mutations_total"],
        "citations_verified": s["citations_verified"],
        "citations_total": s["citations_total"],
        "not_verbatim": v.get("not_found", 0),
        "too_short": v.get("too_short", 0),
        "tests_passed": tests.get("passed"),
        "tests_failed": tests.get("failed"),
        "statuses": {r["id"]: r["status"] for r in matrix["rows"]},
        **extra,
    }


def _count_test_functions(commit: str | None) -> int | None:
    """Number of test functions in ledgerlite/tests at *commit* (None = working tree)."""
    import ast

    def count(text: str) -> int:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return 0
        return sum(1 for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test"))

    if commit is None:
        return sum(count(p.read_text(encoding="utf-8")) for p in Path("ledgerlite/tests").glob("test_*.py"))
    try:
        names = subprocess.run(["git", "ls-tree", "--name-only", f"{commit}:ledgerlite/tests"],
                               capture_output=True, text=True, check=True).stdout.split()
        total = 0
        for name in names:
            if name.startswith("test_") and name.endswith(".py"):
                total += count(subprocess.run(["git", "show", f"{commit}:ledgerlite/tests/{name}"],
                                              capture_output=True, text=True, check=True).stdout)
        return total
    except (subprocess.CalledProcessError, OSError):
        return None


def _downscale(src: Path, dest: Path, max_px: int = 1400) -> bool:
    """Shrink a screenshot for the web with macOS `sips` when available (originals stay in bob_sessions/)."""
    if not shutil.which("sips"):
        return False
    result = subprocess.run(["sips", "-Z", str(max_px), str(src), "--out", str(dest)],
                            capture_output=True, text=True, check=False)
    return result.returncode == 0 and dest.exists()


def _screenshots(docs: Path) -> list[dict[str, str]]:
    source = Path("bob_sessions")
    target = docs / "assets" / "bob"
    target.mkdir(parents=True, exist_ok=True)
    shots = []
    for png in sorted(source.glob("solotrace_*.png")):
        dest = target / png.name
        if not _downscale(png, dest):
            shutil.copyfile(png, dest)
        caption = png.stem.replace("solotrace_", "").replace("_", " ")
        shots.append({"src": f"assets/bob/{png.name}", "caption": caption})
    return shots


def collect(before: str, round1: str, after: str, docs: Path, video_url: str | None) -> dict[str, Any]:
    stages_raw = [
        ("baseline", "Baseline audit", Path(before)),
        ("round1", "Round 1 — after Bob's fixes", Path(round1)),
        ("final", "Round 2 — final", Path(after)),
    ]
    stages = []
    for key, label, d in stages_raw:
        st = _stage(key, label, _load(d / "matrix.json"), _load(d / "verification.json"), {})
        if st:
            stages.append(st)

    final = _load(Path(after) / "matrix.json")
    prove = _load(Path(after) / "prove.json") or {}
    first_commit = next((s["commit"] for s in stages if s["key"] == "baseline"), None)
    rows = []
    for r in final["rows"]:
        rows.append({
            **{k: r[k] for k in ("id", "title", "text", "acceptance_criteria", "risk", "change",
                                 "ai_status", "status", "reason", "evidence", "tests", "checks")},
            "history": [{"stage": s["key"], "status": s["statuses"].get(r["id"])} for s in stages],
            "mutations": prove.get("requirements", {}).get(r["id"], {}).get("mutations", []),
        })
    sessions = (_load(Path("bob_sessions") / "sessions.json") or {}).get("sessions", [])
    audit = final.get("audit", {})
    return {
        "version": __version__,
        "project": audit.get("project", "the audited project"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo_url": REPO_URL,
        "pages_url": PAGES_URL,
        "report_url": f"{REPO_URL}/blob/main/AUDIT_REPORT.md",
        "video_url": video_url,
        "spec": {**audit.get("spec", {}), "url": f"{REPO_URL}/blob/main/{audit.get('spec', {}).get('path', '')}"},
        "stages": stages,
        "rows": rows,
        "tests_functions": {"before": _count_test_functions(first_commit), "after": _count_test_functions(None)},
        "sessions": sessions,
        "subagents_total": sum(s["subagents"]["count"] for s in sessions),
        "bobcoins_total": round(sum(s["bobcoins"] for s in sessions), 2),
        "signoffs": (_load(Path("bob_sessions") / "signoffs.json") or {}).get("signoffs", []),
        "bob_config": [{"path": p, "what": w, "url": f"{REPO_URL}/blob/main/{p}"} for p, w in BOB_CONFIG],
        "screenshots": _screenshots(docs),
    }


def render(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    # Fill the fixed placeholders first and the data last, so data can never be rewritten.
    page = TEMPLATE.replace("__PAGES_URL__", data["pages_url"]).replace("__VERSION__", data["version"])
    return page.replace("__DATA__", payload)


def cmd_dashboard(before: str, round1: str, after: str, out: str = "docs/index.html", video_url: str | None = None) -> int:
    docs = Path(out).parent
    docs.mkdir(parents=True, exist_ok=True)
    if not (Path(after) / "matrix.json").exists():
        print(f"ERROR: {after}/matrix.json not found — run `python -m solotrace matrix --out {after}` first.")
        return 1
    if video_url and not video_url.startswith("https://"):
        print("ERROR: --video-url must be an https:// link")
        return 1
    data = collect(before, round1, after, docs, video_url)
    cover = Path("docs/assets/cover.png")
    Path(out).write_text(render(data), encoding="utf-8")
    print(f"Dashboard written: {out} ({len(data['rows'])} requirements, {len(data['stages'])} audit rounds"
          f"{', cover image present' if cover.exists() else ''})")
    return 0


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" data-theme="auto">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SoloTrace — Every requirement, proven</title>
<meta name="description" content="SoloTrace turns IBM Bob into a compliance auditor: it reads the spec, proves every requirement in code and tests, and does not trust green tests until they catch deliberate sabotage.">
<meta property="og:title" content="SoloTrace — Every requirement, proven">
<meta property="og:description" content="Requirements-to-code traceability audits run by IBM Bob 2.0, proven by evidence verification and mutation testing.">
<meta property="og:type" content="website">
<meta property="og:url" content="__PAGES_URL__">
<meta property="og:image" content="__PAGES_URL__assets/cover.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%230f62fe'/%3E%3Cpath d='M9 16.5l4.5 4.5L23 11' fill='none' stroke='white' stroke-width='3.2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<style>
:root {
  --bg:#ffffff; --layer:#f4f4f4; --layer-2:#e8e8e8; --border:#d6d6d6; --text:#161616; --muted:#525252;
  --accent:#0f62fe; --accent-text:#ffffff; --accent-soft:#e5edff;
  --proven:#198038; --proven-soft:#defbe6; --covered:#0f62fe; --covered-soft:#e5edff;
  --weak:#ba4e00; --weak-soft:#fff2e8; --warn:#8e6a00; --warn-soft:#fcf4d6;
  --bad:#da1e28; --bad-soft:#fff1f1; --missing:#9f1853; --missing-soft:#fff0f7;
  --bob:#6929c4; --bob-soft:#f6f2ff; --human:#005d5d; --human-soft:#d9fbfb;
  --shadow:0 1px 2px rgba(0,0,0,.06),0 8px 24px rgba(0,0,0,.06);
  --radius:14px; --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --sans:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
:root[data-theme="dark"] {
  --bg:#0e1117; --layer:#161b24; --layer-2:#1f2633; --border:#2c3444; --text:#f2f4f8; --muted:#aab2c0;
  --accent:#4589ff; --accent-text:#0e1117; --accent-soft:#16264a;
  --proven:#42be65; --proven-soft:#10291a; --covered:#78a9ff; --covered-soft:#16264a;
  --weak:#ff832b; --weak-soft:#33200f; --warn:#f1c21b; --warn-soft:#2e2808;
  --bad:#ff8389; --bad-soft:#3a1316; --missing:#ff7eb6; --missing-soft:#3a1227;
  --bob:#be95ff; --bob-soft:#261a3d; --human:#3ddbd9; --human-soft:#0c2b2b;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px rgba(0,0,0,.35);
}
@media (prefers-color-scheme: dark) {
  :root[data-theme="auto"] {
    --bg:#0e1117; --layer:#161b24; --layer-2:#1f2633; --border:#2c3444; --text:#f2f4f8; --muted:#aab2c0;
    --accent:#4589ff; --accent-text:#0e1117; --accent-soft:#16264a;
    --proven:#42be65; --proven-soft:#10291a; --covered:#78a9ff; --covered-soft:#16264a;
    --weak:#ff832b; --weak-soft:#33200f; --warn:#f1c21b; --warn-soft:#2e2808;
    --bad:#ff8389; --bad-soft:#3a1316; --missing:#ff7eb6; --missing-soft:#3a1227;
    --bob:#be95ff; --bob-soft:#261a3d; --human:#3ddbd9; --human-soft:#0c2b2b;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px rgba(0,0,0,.35);
  }
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 var(--sans)}
a{color:var(--accent)}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px}
header.top{border-bottom:1px solid var(--border)}
.top .wrap{display:flex;align-items:center;gap:14px;min-height:64px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:18px;text-decoration:none;color:var(--text)}
.logo{width:30px;height:30px;border-radius:8px;background:var(--accent);display:grid;place-items:center}
.logo svg{width:18px;height:18px}
.spacer{flex:1}
.pill{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:4px 10px;font-size:13px;font-weight:600;white-space:nowrap}
.pill.bob{background:var(--bob-soft);color:var(--bob)}
.theme-btn{border:1px solid var(--border);background:var(--layer);color:var(--text);border-radius:10px;padding:7px 11px;font:inherit;font-size:14px;cursor:pointer}
.theme-btn:focus-visible,.btn:focus-visible,.chip:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
section{padding:44px 0}
h1{font-size:clamp(32px,5vw,52px);line-height:1.08;margin:0 0 14px;letter-spacing:-.02em}
h1 .hl{color:var(--accent)}
h2{font-size:clamp(22px,3vw,30px);margin:0 0 6px;letter-spacing:-.01em}
.lede{font-size:clamp(17px,2vw,20px);color:var(--muted);max-width:760px;margin:0 0 10px}
.sub{color:var(--muted);margin:0 0 22px;max-width:780px}
.cta{display:flex;gap:10px;flex-wrap:wrap;margin-top:22px}
.btn{display:inline-flex;align-items:center;gap:8px;padding:10px 16px;border-radius:10px;font-weight:600;text-decoration:none;border:1px solid var(--border);color:var(--text);background:var(--layer)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-text)}
.hero{padding-top:52px}
.journey{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:8px}
.stage{background:var(--layer);border:1px solid var(--border);border-radius:var(--radius);padding:20px;box-shadow:var(--shadow);position:relative}
.stage.final{border-color:var(--proven);box-shadow:0 0 0 1px var(--proven),var(--shadow)}
.stage .kicker{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:700}
.stage h3{margin:4px 0 14px;font-size:18px}
.meter{margin:10px 0}
.meter .row{display:flex;justify-content:space-between;align-items:baseline;gap:8px;font-size:14px;color:var(--muted)}
.meter .val{font-size:28px;font-weight:700;color:var(--text);font-variant-numeric:tabular-nums}
.meter .val.ai{color:var(--covered)} .meter .val.pr{color:var(--proven)} .meter .val.lo{color:var(--weak)}
.bar{height:8px;border-radius:99px;background:var(--layer-2);overflow:hidden;margin-top:6px}
.bar i{display:block;height:100%;width:0;border-radius:99px;transition:width 1.1s cubic-bezier(.2,.8,.2,1)}
.bar i.ai{background:var(--covered)} .bar i.pr{background:var(--proven)} .bar i.lo{background:var(--weak)}
.stage ul{margin:12px 0 0;padding-left:18px;color:var(--muted);font-size:14px}
.stage li{margin:3px 0}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}
.kpi{background:var(--layer);border:1px solid var(--border);border-radius:12px;padding:16px}
.kpi b{display:block;font-size:26px;line-height:1.1;font-variant-numeric:tabular-nums}
.kpi span{color:var(--muted);font-size:13px}
.flow{display:grid;grid-template-columns:repeat(7,1fr);gap:10px;counter-reset:step}
.step{background:var(--layer);border:1px solid var(--border);border-radius:12px;padding:14px;position:relative}
.step b{display:block;font-size:14px;letter-spacing:.04em}
.step p{margin:6px 0 10px;font-size:13px;color:var(--muted)}
.actor{font-size:11px;font-weight:700;border-radius:99px;padding:2px 8px;display:inline-block}
.actor.bob{background:var(--bob-soft);color:var(--bob)} .actor.code{background:var(--accent-soft);color:var(--accent)} .actor.human{background:var(--human-soft);color:var(--human)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}
.chip{border:1px solid var(--border);background:var(--layer);color:var(--text);border-radius:99px;padding:6px 12px;font:inherit;font-size:14px;cursor:pointer}
.chip[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--accent-text)}
table.matrix{width:100%;border-collapse:collapse;font-size:14px}
.matrix th,.matrix td{text-align:left;padding:10px 8px;border-bottom:1px solid var(--border);vertical-align:top}
.matrix th{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.matrix td.id{font-family:var(--mono);white-space:nowrap;font-weight:600}
.matrix tr.row{cursor:pointer} .matrix tr.row:hover td{background:var(--layer)}
.status{display:inline-flex;align-items:center;gap:6px;border-radius:99px;padding:2px 9px;font-size:12.5px;font-weight:700;white-space:nowrap}
.s-proven{background:var(--proven-soft);color:var(--proven)} .s-covered{background:var(--covered-soft);color:var(--covered)}
.s-weak{background:var(--weak-soft);color:var(--weak)} .s-unverified,.s-untested{background:var(--warn-soft);color:var(--warn)}
.s-contradicts{background:var(--bad-soft);color:var(--bad)} .s-missing{background:var(--missing-soft);color:var(--missing)} .s-none{color:var(--muted)}
.tag{font-size:11px;font-weight:700;border-radius:6px;padding:1px 6px;margin-left:6px;vertical-align:middle}
.tag.new{background:var(--proven-soft);color:var(--proven)} .tag.changed{background:var(--warn-soft);color:var(--warn)}
.tag.high{background:var(--bad-soft);color:var(--bad)} .tag.medium{background:var(--layer-2);color:var(--muted)}
.detail td{background:var(--layer);padding:0}
.detail .box{padding:18px 18px 22px}
.detail h4{margin:16px 0 6px;font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.detail h4:first-child{margin-top:0}
.quote{border-left:3px solid var(--accent);padding:4px 12px;margin:0;color:var(--text)}
.ev{display:flex;gap:10px;align-items:flex-start;margin:6px 0;font-size:13.5px}
.ev code{font-family:var(--mono);font-size:12.5px;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:2px 6px;overflow-wrap:anywhere;white-space:pre-wrap}
.ev .loc{font-family:var(--mono);font-size:12.5px;color:var(--muted);white-space:nowrap}
.ok{color:var(--proven);font-weight:700} .no{color:var(--bad);font-weight:700}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.card{background:var(--layer);border:1px solid var(--border);border-radius:var(--radius);padding:18px}
.card h3{margin:0 0 8px;font-size:17px}
.verif{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.verif .card b{font-size:24px}
.sessions{display:grid;gap:10px}
.sess{display:grid;grid-template-columns:120px 1fr auto;gap:12px;align-items:center;background:var(--layer);border:1px solid var(--border);border-radius:12px;padding:12px 14px}
.sess .t{font-family:var(--mono);font-weight:700}
.sess .meta{color:var(--muted);font-size:13px}
.sess .cost{font-weight:700;color:var(--bob);white-space:nowrap}
.shots{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.shots a{display:block;background:var(--layer);border:1px solid var(--border);border-radius:10px;overflow:hidden;text-decoration:none;color:var(--muted);font-size:12.5px}
.shots img{display:block;width:100%;height:130px;object-fit:cover;object-position:top}
.shots span{display:block;padding:8px 10px}
.config li{margin:6px 0}
.config code{font-family:var(--mono);font-size:13px}
footer{border-top:1px solid var(--border);padding:28px 0 40px;color:var(--muted);font-size:14px}
.muted{color:var(--muted)}
.only-mobile{display:none}
.small{font-size:13px}
@media (max-width:1000px){ .flow{grid-template-columns:repeat(4,1fr)} .kpis{grid-template-columns:repeat(3,1fr)} .shots{grid-template-columns:repeat(3,1fr)} }
@media (max-width:760px){
  section{padding:34px 0}
  .journey,.two,.verif{grid-template-columns:1fr}
  .flow{grid-template-columns:repeat(2,1fr)}
  .kpis{grid-template-columns:repeat(2,1fr)}
  .shots{grid-template-columns:repeat(2,1fr)}
  .matrix .col-req,.matrix .col-base,.matrix .col-r1{display:none}
  .only-mobile{display:block}
  .sess{grid-template-columns:1fr auto}
  .sess .meta{grid-column:1 / -1}
  .ev{flex-direction:column;gap:4px}
}
@media (prefers-reduced-motion:reduce){ .bar i{transition:none} }
</style>
</head>
<body>
<noscript><p style="padding:20px">This dashboard needs JavaScript. The same results are in the audit report: AUDIT_REPORT.md in the repository.</p></noscript>
<header class="top"><div class="wrap">
  <a class="brand" href="#top"><span class="logo" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.2 4.2L19 7" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg></span>SoloTrace</a>
  <span class="pill bob">Built with IBM Bob 2.0</span>
  <span class="spacer"></span>
  <button class="theme-btn" id="theme" type="button" aria-label="Switch colour theme">◐ Theme</button>
</div></header>
<main id="top">
  <section class="hero"><div class="wrap" id="hero"></div></section>
  <section><div class="wrap">
    <h2>From "the AI says 100%" to "proven"</h2>
    <p class="sub">Three audit rounds of the same code base against the same spec. Green tests are not enough: SoloTrace only counts a requirement once its tests catch deliberate sabotage.</p>
    <p class="muted small" id="journey-sub"></p>
    <div class="journey" id="journey"></div>
  </div></section>
  <section><div class="wrap"><div class="kpis" id="kpis"></div></div></section>
  <section><div class="wrap">
    <h2>How an audit runs</h2>
    <p class="sub">IBM Bob does the reading, auditing and fixing. SoloTrace's code checks every claim. A human signs off before any code changes.</p>
    <div class="flow" id="flow"></div>
  </div></section>
  <section id="matrix-section"><div class="wrap">
    <h2>Traceability matrix</h2>
    <p class="sub">Select a requirement to see its text, acceptance criteria, verified code evidence, tests and the sabotage attempts its tests caught.</p>
    <div class="chips" id="filters" role="group" aria-label="Filter requirements"></div>
    <table class="matrix" aria-describedby="matrix-section">
      <thead><tr><th>ID</th><th class="col-req">Requirement</th><th class="col-base">Baseline</th><th class="col-r1">Round 1</th><th>Final</th></tr></thead>
      <tbody id="matrix"></tbody>
    </table>
    <p class="muted small" id="empty" hidden>No requirement matches this filter.</p>
  </div></section>
  <section><div class="wrap">
    <h2>The evidence verifier</h2>
    <p class="sub">AI auditors cite code. SoloTrace re-finds every citation in the audited commit and rejects anything that is not really there.</p>
    <div class="verif" id="verif"></div>
  </div></section>
  <section><div class="wrap">
    <h2>How IBM Bob runs SoloTrace</h2>
    <p class="sub">Every stage below ran inside IBM Bob IDE. Times, Bobcoins and subagent counts come from Bob's own task history.</p>
    <div class="two">
      <div class="card"><h3>Bob sessions</h3><div class="sessions" id="sessions"></div></div>
      <div class="card config"><h3>Bob-native configuration</h3><ul id="config"></ul><h3 style="margin-top:18px">Human sign-offs</h3><ul id="signoffs"></ul></div>
    </div>
    <h3 style="margin:26px 0 10px">Task session summaries</h3>
    <div class="shots" id="shots"></div>
  </div></section>
</main>
<footer><div class="wrap" id="foot"></div></footer>
<script id="data" type="application/json">__DATA__</script>
<script>
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("data").textContent);
  var LABEL = {proven:"Proven", covered:"Covered", weak:"Weak tests", unverified:"Unverified", untested:"Untested", contradicts:"Contradicts spec", missing:"Missing"};
  var ICON = {proven:"✓", covered:"✓", weak:"!", unverified:"?", untested:"!", contradicts:"✕", missing:"–"};

  function h(tag, attrs, kids) {
    var el = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (k === "class") el.className = attrs[k];
      else if (k === "text") el.textContent = attrs[k];
      else if (attrs[k] !== null && attrs[k] !== undefined) el.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c !== null && c !== undefined) el.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return el;
  }
  function pct(n, d) { return d ? Math.round(n / d * 100) : 0; }
  function status(s) { return h("span", {class: "status s-" + (s || "none"), text: s ? ICON[s] + " " + LABEL[s] : "—"}); }
  function link(text, href, cls) { return h("a", {class: cls || null, href: href, target: "_blank", rel: "noopener"}, [text]); }

  // theme
  var root = document.documentElement, btn = document.getElementById("theme");
  try { var saved = localStorage.getItem("solotrace-theme"); if (saved) root.setAttribute("data-theme", saved); } catch (e) {}
  function current() { var t = root.getAttribute("data-theme"); if (t === "auto") t = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; return t; }
  function label() { btn.textContent = current() === "dark" ? "☀ Light" : "☾ Dark"; }
  btn.addEventListener("click", function () { var n = current() === "dark" ? "light" : "dark"; root.setAttribute("data-theme", n); try { localStorage.setItem("solotrace-theme", n); } catch (e) {} label(); });
  label();

  var stages = D.stages, final = stages[stages.length - 1];

  // hero
  var hero = document.getElementById("hero");
  hero.appendChild(h("h1", null, ["Every requirement, ", h("span", {class: "hl", text: "proven."})]));
  hero.appendChild(h("p", {class: "lede", text: "SoloTrace turns IBM Bob into a compliance auditor. It reads your requirements document, proves each requirement in code and tests with verified file:line evidence, and does not trust green tests until they catch deliberate sabotage."}));
  hero.appendChild(h("p", {class: "sub", text: "Built for engineering and compliance teams in banking, insurance and healthcare, who must show auditors that every written requirement is implemented and tested before each release."}));
  var cta = h("div", {class: "cta"});
  if (D.video_url) cta.appendChild(link("▶ Watch the 3-minute demo", D.video_url, "btn primary"));
  cta.appendChild(link("Read the audit report", D.report_url, D.video_url ? "btn" : "btn primary"));
  cta.appendChild(link("Requirements spec (PDF)", D.spec.url, "btn"));
  cta.appendChild(link("Source on GitHub", D.repo_url, "btn"));
  hero.appendChild(cta);

  // journey
  var bars = [];
  var journey = document.getElementById("journey");
  var jsub = document.getElementById("journey-sub");
  if (jsub) jsub.textContent = "Audited project: " + D.project + " · specification v" + (D.spec.version || "?") + ".";
  stages.forEach(function (s) {
    var card = h("div", {class: "stage" + (s.key === "final" ? " final" : "")});
    card.appendChild(h("div", {class: "kicker", text: (s.task ? "IBM Bob " + s.task.replace("task0", "task ") : "") + (s.commit ? " · commit " + s.commit : "")}));
    card.appendChild(h("h3", {text: s.label}));
    function meter(name, value, total, cls, note) {
      var i = h("i", {class: cls});
      bars.push([i, pct(value, total)]);
      return h("div", {class: "meter"}, [
        h("div", {class: "row"}, [h("span", {text: name}), h("span", {class: "val " + cls, text: pct(value, total) + "%"})]),
        h("div", {class: "bar", role: "img", "aria-label": name + ": " + value + " of " + total}, [i]),
        note ? h("div", {class: "muted small", text: note}) : null
      ]);
    }
    card.appendChild(meter("AI verdicts say covered", s.ai_covered, s.total, "ai", s.ai_covered + " of " + s.total + " requirements"));
    if (s.mutation_testing) {
      card.appendChild(meter("SoloTrace proves", s.proven, s.total, s.proven === s.total ? "pr" : "lo", s.proven + " of " + s.total + " requirements"));
    } else {
      card.appendChild(meter("Evidence verified", s.evidence_ok, s.total, "lo", "no mutation testing yet"));
    }
    var facts = [];
    facts.push(s.citations_verified + " of " + s.citations_total + " code citations verified");
    if (s.not_verbatim) facts.push(s.not_verbatim + " citations could not be found in the audited code");
    if (s.tests_passed !== null && s.tests_passed !== undefined) facts.push(s.tests_passed + " tests passing" + (s.tests_failed ? ", " + s.tests_failed + " failing" : ""));
    if (s.mutation_testing) facts.push(s.mutations_killed + " of " + s.mutations_total + " sabotage attempts caught" + (s.mutations_total - s.mutations_killed ? " — " + (s.mutations_total - s.mutations_killed) + " slipped through" : ""));
    card.appendChild(h("ul", null, facts.map(function (f) { return h("li", {text: f}); })));
    journey.appendChild(card);
  });

  // KPIs
  var tf = D.tests_functions || {};
  var kpis = [
    [final.total, "requirements traced"],
    [final.citations_verified + "/" + final.citations_total, "code citations verified"],
    [final.mutations_total ? final.mutations_killed + "/" + final.mutations_total : "—", "sabotage attempts caught"],
    [final.tests_passed, "tests passing" + (tf.before && tf.after ? " (" + tf.before + " → " + tf.after + " test functions)" : "")],
    [D.subagents_total, "Bob subagents run in parallel"],
    [D.bobcoins_total, "Bobcoins, whole build"]
  ];
  var kbox = document.getElementById("kpis");
  kpis.forEach(function (k) { kbox.appendChild(h("div", {class: "kpi"}, [h("b", {text: String(k[0])}), h("span", {text: k[1]})])); });

  // flow
  var steps = [
    ["READ", "Bob reads the spec PDF and extracts requirements with acceptance criteria.", "bob", "IBM Bob"],
    ["AUDIT", "12 subagents, one per requirement, in parallel, each citing file:line evidence.", "bob", "IBM Bob"],
    ["VERIFY", "Every citation is re-found in the audited commit; paraphrases and unsafe paths are rejected.", "code", "SoloTrace"],
    ["SIGN-OFF", "A compliance officer approves the fix plan before any code changes.", "human", "Human"],
    ["FIX", "Bob writes a failing test for each gap, then the fix, then runs the whole suite.", "bob", "IBM Bob"],
    ["PROVE", "Each requirement is sabotaged on purpose; its tests must catch every attempt.", "code", "SoloTrace"],
    ["REPORT", "Traceability matrix, audit report and this dashboard.", "code", "SoloTrace"]
  ];
  var flow = document.getElementById("flow");
  steps.forEach(function (s, i) { flow.appendChild(h("div", {class: "step"}, [h("b", {text: (i + 1) + " · " + s[0]}), h("p", {text: s[1]}), h("span", {class: "actor " + s[2], text: s[3]})])); });

  // matrix
  var filters = [
    ["all", "All"], ["proven", "Proven"], ["new", "New in v2.0"], ["changed", "Changed in v2.0"], ["weak-before", "Weak in round 1"]
  ];
  var active = "all", tbody = document.getElementById("matrix"), empty = document.getElementById("empty");
  var fbox = document.getElementById("filters");
  filters.forEach(function (f) {
    var b = h("button", {class: "chip", type: "button", "aria-pressed": f[0] === active ? "true" : "false", text: f[1]});
    b.addEventListener("click", function () { active = f[0]; Array.prototype.forEach.call(fbox.children, function (c) { c.setAttribute("aria-pressed", "false"); }); b.setAttribute("aria-pressed", "true"); draw(); });
    fbox.appendChild(b);
  });
  function histStatus(r, key) { var x = (r.history || []).filter(function (e) { return e.stage === key; })[0]; return x ? x.status : null; }
  function match(r) {
    if (active === "all") return true;
    if (active === "proven") return r.status === "proven";
    if (active === "new" || active === "changed") return r.change === active;
    if (active === "weak-before") return histStatus(r, "round1") === "weak";
    return true;
  }
  function detail(r) {
    var box = h("div", {class: "box"});
    box.appendChild(h("h4", {text: "Requirement"}));
    box.appendChild(h("p", {class: "quote", text: r.text}));
    box.appendChild(h("h4", {text: "Acceptance criteria"}));
    box.appendChild(h("ul", null, r.acceptance_criteria.map(function (a) { return h("li", {text: a}); })));
    box.appendChild(h("h4", {text: "Auditor's reasoning"}));
    box.appendChild(h("p", {text: r.reason}));
    box.appendChild(h("h4", {text: "Code evidence (" + r.checks.citations_verified + "/" + r.checks.citations_total + " verified)"}));
    r.evidence.forEach(function (e) {
      box.appendChild(h("div", {class: "ev"}, [
        h("span", {class: e.verified ? "ok" : "no", text: e.verified ? "✓" : "✕", "aria-label": e.verified ? "verified" : "not verified"}),
        h("span", {class: "loc", text: e.file + ":" + e.line}),
        h("code", {text: String(e.snippet).trim()})
      ]));
    });
    box.appendChild(h("h4", {text: "Tests (" + r.checks.tests_passing + "/" + r.checks.tests_cited + " passing)"}));
    r.tests.forEach(function (t) {
      box.appendChild(h("div", {class: "ev"}, [
        h("span", {class: t.passed ? "ok" : "no", text: t.passed ? "✓" : "✕"}),
        h("code", {text: t.test_name}),
        h("span", {class: "loc", text: t.file})
      ]));
    });
    if (r.mutations && r.mutations.length) {
      box.appendChild(h("h4", {text: "Sabotage attempts (" + r.mutations.filter(function (m) { return m.outcome === "killed"; }).length + "/" + r.mutations.length + " caught)"}));
      r.mutations.forEach(function (m) {
        var caught = m.outcome === "killed";
        var by = m.killed_by ? m.killed_by.split("::").pop() : "";
        box.appendChild(h("div", {class: "ev"}, [
          h("span", {class: caught ? "ok" : "no", text: caught ? "✓" : "✕"}),
          h("span", {text: m.description + (caught ? " — caught by " : " — NOT caught")}),
          by ? h("code", {text: by}) : null
        ]));
      });
    }
    return box;
  }
  function draw() {
    tbody.textContent = "";
    var shown = 0;
    D.rows.forEach(function (r) {
      if (!match(r)) return;
      shown++;
      var id = "d-" + r.id;
      var titleCell = h("td", {class: "col-req"}, [r.title,
        r.change !== "none" ? h("span", {class: "tag " + r.change, text: r.change.toUpperCase()}) : null,
        h("span", {class: "tag " + r.risk.toLowerCase(), text: r.risk})]);
      var idCell = h("td", {class: "id"}, [h("button", {class: "chip", type: "button", "aria-expanded": "false", "aria-controls": id, text: r.id})]);
      var tr = h("tr", {class: "row"}, [idCell, titleCell,
        h("td", {class: "col-base"}, [status(histStatus(r, "baseline"))]),
        h("td", {class: "col-r1"}, [status(histStatus(r, "round1"))]),
        h("td", null, [status(r.status), h("div", {class: "muted small only-mobile", text: r.title})])]);
      var dr = h("tr", {class: "detail", id: id, hidden: ""}, [h("td", {colspan: "5"}, [detail(r)])]);
      function toggle() {
        var open = dr.hasAttribute("hidden");
        if (open) dr.removeAttribute("hidden"); else dr.setAttribute("hidden", "");
        idCell.firstChild.setAttribute("aria-expanded", open ? "true" : "false");
      }
      tr.addEventListener("click", toggle);
      tbody.appendChild(tr); tbody.appendChild(dr);
    });
    empty.hidden = shown !== 0;
  }
  draw();

  // verifier
  var vbox = document.getElementById("verif");
  stages.forEach(function (s) {
    var bad = s.citations_total - s.citations_verified;
    vbox.appendChild(h("div", {class: "card"}, [
      h("div", {class: "muted small", text: s.label}),
      h("b", {text: s.citations_verified + " / " + s.citations_total}),
      h("div", {text: "code citations verified in commit " + s.commit}),
      h("div", {class: "muted small", text: bad ? bad + " rejected: " + (s.not_verbatim ? s.not_verbatim + " not found in the code" : "") + (s.not_verbatim && s.too_short ? ", " : "") + (s.too_short ? s.too_short + " too short to prove anything" : "") : "no citation rejected"})
    ]));
  });

  // Bob sessions
  var sbox = document.getElementById("sessions");
  D.sessions.forEach(function (s) {
    var sub = s.subagents.count ? " · " + s.subagents.count + " parallel subagents (" + s.subagents.parallel_wall_clock_s + " s)" : "";
    sbox.appendChild(h("div", {class: "sess"}, [
      h("span", {class: "t", text: s.task.replace("task0", "Task ")}),
      h("span", {class: "meta", text: s.title}),
      h("span", {class: "cost", text: s.bobcoins + " coins"}),
      h("span", {class: "meta", text: s.started_at.replace("T", " ").slice(0, 16) + " PKT · " + s.duration_min + " min" + sub})
    ]));
  });
  var cfg = document.getElementById("config");
  D.bob_config.forEach(function (c) { cfg.appendChild(h("li", null, [link(c.path, c.url), h("div", {class: "muted small", text: c.what})])); });
  var so = document.getElementById("signoffs");
  if (!D.signoffs.length) so.appendChild(h("li", {class: "muted", text: "No sign-off recorded yet."}));
  D.signoffs.forEach(function (s) { so.appendChild(h("li", null, [h("b", {text: "“" + s.statement + "”"}), h("div", {class: "muted small", text: s.approved_at.replace("T", " ").slice(0, 19) + " PKT · IBM Bob " + s.task.replace("task0", "task ")})])); });
  var shots = document.getElementById("shots");
  D.screenshots.forEach(function (s) {
    shots.appendChild(h("a", {href: s.src, target: "_blank", rel: "noopener"}, [h("img", {src: s.src, alt: "IBM Bob " + s.caption, loading: "lazy"}), h("span", {text: s.caption})]));
  });

  // footer
  var foot = document.getElementById("foot");
  foot.appendChild(h("p", null, ["SoloTrace " + D.version + " · built for the lablab.ai IBM Bob 2.0 Hackathon (September 2026) · MIT licence · ",
    link("GitHub", D.repo_url), " · ", link("Audit report", D.report_url)]));
  foot.appendChild(h("p", {class: "small", text: "Spec " + (D.spec.path || "") + " · SHA-256 " + (D.spec.sha256 || "n/a").slice(0, 16) + "… · generated " + D.generated_at}));

  // animate bars
  requestAnimationFrame(function () { bars.forEach(function (b) { b[0].style.width = b[1] + "%"; }); });
})();
</script>
</body>
</html>
"""
