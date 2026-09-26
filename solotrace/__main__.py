"""
python -m solotrace <command>

  run        full evidence pipeline: requirements → test → verify → prove → matrix → report → dashboard
  verify     re-find every code citation of the AI verdicts in the audited commit
  test       run the test suite and record every result
  prove      mutation testing: sabotage each requirement, its tests must catch it
  matrix     traceability matrix scored on evidence
  report     write AUDIT_REPORT.md
  dashboard  write docs/index.html (static, for GitHub Pages)

The judgement stages (READ the spec, AUDIT with one subagent per requirement,
FIX after human sign-off) run inside IBM Bob: SoloTrace Auditor mode +
solotrace-audit skill.  See AGENTS.md.
"""
from __future__ import annotations

import argparse
import sys

from solotrace import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m solotrace", description="SoloTrace — every requirement, proven.")
    parser.add_argument("--version", action="version", version=f"SoloTrace {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="full evidence pipeline")
    p.add_argument("--spec", default="demo-data/LedgerLite-Requirements-v2.0.pdf", help="requirements PDF")
    p.add_argument("--out", default="out", help="audit directory (verdicts/, mutations/, outputs)")
    p.add_argument("--before", default="out-before", help="baseline audit directory")
    p.add_argument("--round1", default="out-round1", help="round-1 audit directory")
    p.add_argument("--tests", default="ledgerlite/tests", help="test suite path")
    p.add_argument("--no-prove", action="store_true", help="skip mutation testing")
    p.add_argument("--workers", type=int, default=4, help="parallel mutation workers")
    p.add_argument("--auditor", help="who produced the verdicts (recorded in audit.json)")
    p.add_argument("--bob-task", help="IBM Bob task that produced the verdicts")
    p.add_argument("--video-url", help="demo video link for the dashboard")
    p.add_argument("--strict", action="store_true", help="exit 2 unless every requirement is proven")

    p = sub.add_parser("verify", help="evidence verifier")
    p.add_argument("--out", default="out")
    p.add_argument("--source-commit", help="verify against this git commit instead of the working tree")
    p.add_argument("--check", action="store_true", help="read-only; exit 1 if any citation is unverified")

    p = sub.add_parser("test", help="run the test suite and record results")
    p.add_argument("--out", default="out")
    p.add_argument("--tests", default="ledgerlite/tests")

    p = sub.add_parser("prove", help="mutation testing")
    p.add_argument("--out", default="out")
    p.add_argument("--tests", default="ledgerlite/tests")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--timeout", type=int, default=300, help="seconds per mutation")

    p = sub.add_parser("matrix", help="traceability matrix")
    p.add_argument("--out", default="out")

    p = sub.add_parser("report", help="write AUDIT_REPORT.md")
    p.add_argument("--before", default="out-before")
    p.add_argument("--round1", default="out-round1")
    p.add_argument("--after", default="out")
    p.add_argument("--output", default="AUDIT_REPORT.md")

    p = sub.add_parser("dashboard", help="write docs/index.html")
    p.add_argument("--before", default="out-before")
    p.add_argument("--round1", default="out-round1")
    p.add_argument("--after", default="out")
    p.add_argument("--output", default="docs/index.html")
    p.add_argument("--video-url")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        from solotrace.pipeline import cmd_run
        return cmd_run(args.spec, args.out, args.before, args.round1, args.tests, prove=not args.no_prove,
                       workers=args.workers, auditor=args.auditor, bob_task=args.bob_task,
                       video_url=args.video_url, strict=args.strict)
    if args.command == "verify":
        from solotrace.verify import cmd_verify
        return cmd_verify(args.out, args.source_commit, args.check)
    if args.command == "test":
        from solotrace.testrun import cmd_test
        return cmd_test(args.out, args.tests)
    if args.command == "prove":
        from solotrace.prove import cmd_prove
        return cmd_prove(args.out, args.tests, args.workers, args.timeout)
    if args.command == "matrix":
        from solotrace.matrix import cmd_matrix
        return cmd_matrix(args.out)
    if args.command == "report":
        from solotrace.report import cmd_report
        return cmd_report(args.before, args.round1, args.after, args.output)
    if args.command == "dashboard":
        from solotrace.dashboard import cmd_dashboard
        return cmd_dashboard(args.before, args.round1, args.after, args.output, args.video_url)
    return 1


if __name__ == "__main__":
    sys.exit(main())
