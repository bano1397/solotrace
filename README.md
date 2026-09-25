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
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run LedgerLite

```bash
source .venv/bin/activate
uvicorn ledgerlite.main:app --reload --port 8000
```

The API will be available at <http://localhost:8000>.
Interactive docs: <http://localhost:8000/docs>

## Run Tests

```bash
.venv/bin/pytest ledgerlite/tests/ -q
```
