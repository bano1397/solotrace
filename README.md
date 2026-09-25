# SoloTrace

> Automated API auditing — traces requirements through to implementation and verdicts.

## Structure

| Path | Description |
|------|-------------|
| `solotrace/` | SoloTrace auditing tool (Python package) |
| `ledgerlite/` | Sample banking API audited by SoloTrace |
| `demo-data/` | Requirement documents (PDF) |
| `out/` | SoloTrace outputs (`requirements.json`, `verdicts/`, `matrix.json`) |
| `docs/` | Static dashboard served by GitHub Pages |
| `bob_sessions/` | PNG screenshots of every Bob task session summary |
| `.bob/` | Bob custom modes and rules |

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
