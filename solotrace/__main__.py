"""
Entry point for:  python -m solotrace <subcommand> [options]

Subcommands
-----------
verify    -- evidence verifier (anti-hallucination guard)
matrix    -- build traceability matrix from requirements + verdicts
report    -- write AUDIT_REPORT.md comparing before/after audit runs
dashboard -- generate docs/index.html static compliance dashboard
run       -- full post-audit pipeline (verify → matrix → report → dashboard)
"""
import argparse
import sys

from solotrace.cli_verify import cmd_verify
from solotrace.cli_matrix import cmd_matrix
from solotrace.cli_report import cmd_report
from solotrace.cli_dashboard import cmd_dashboard
from solotrace.cli_run import cmd_run


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m solotrace",
        description="SoloTrace requirements-traceability auditor CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── verify ────────────────────────────────────────────────────────────────
    p_verify = sub.add_parser(
        "verify",
        help="Anti-hallucination evidence verifier: check every code_evidence entry "
             "against the real source file and remove phantom test functions.",
    )
    p_verify.add_argument(
        "--out", default="out",
        help="Directory that contains verdicts/ (default: out)",
    )

    # ── matrix ────────────────────────────────────────────────────────────────
    p_matrix = sub.add_parser(
        "matrix",
        help="Build a traceability matrix from requirements.json + verdicts/.",
    )
    p_matrix.add_argument(
        "--out", default="out",
        help="Directory that contains requirements.json and verdicts/ (default: out)",
    )

    # ── report ────────────────────────────────────────────────────────────────
    p_report = sub.add_parser(
        "report",
        help="Write AUDIT_REPORT.md comparing a before/after pair of audit runs.",
    )
    p_report.add_argument(
        "--before", default="out-before",
        help="Directory of the pre-fix audit run (default: out-before)",
    )
    p_report.add_argument(
        "--after", default="out",
        help="Directory of the post-fix audit run (default: out)",
    )

    # ── dashboard ─────────────────────────────────────────────────────────────
    p_dash = sub.add_parser(
        "dashboard",
        help="Generate a self-contained static HTML compliance dashboard "
             "(docs/index.html) from before/after audit runs.",
    )
    p_dash.add_argument(
        "--before", default="out-before",
        help="Directory of the pre-fix audit run (default: out-before)",
    )
    p_dash.add_argument(
        "--after", default="out",
        help="Directory of the post-fix audit run (default: out)",
    )

    # ── run ───────────────────────────────────────────────────────────────────
    p_run = sub.add_parser(
        "run",
        help="Full post-audit pipeline: extract-check → verify → matrix → report → dashboard.",
    )
    p_run.add_argument(
        "--spec", default="demo-data/LedgerLite-Requirements-v2.0.pdf",
        help="Path to the PDF spec (display only; default: demo-data/LedgerLite-Requirements-v2.0.pdf)",
    )
    p_run.add_argument(
        "--out", default="out",
        help="Post-fix audit directory (default: out)",
    )
    p_run.add_argument(
        "--before", default="out-before",
        help="Pre-fix audit directory (default: out-before)",
    )

    args = parser.parse_args()

    if args.command == "verify":
        cmd_verify(args.out)
    elif args.command == "matrix":
        cmd_matrix(args.out)
    elif args.command == "report":
        cmd_report(args.before, args.after)
    elif args.command == "dashboard":
        cmd_dashboard(args.before, args.after)
    elif args.command == "run":
        cmd_run(spec=args.spec, out=args.out, before=args.before, after=args.out)


if __name__ == "__main__":
    main()
