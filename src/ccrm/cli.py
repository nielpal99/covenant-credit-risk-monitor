import argparse
import json
import os
from pathlib import Path

from .ingest import ingest_amzn
from .llama import extract_report, parse_document
from .report import build_report
from .evaluate import evaluate_report
from .llama_plan import bounded_agreement_parsed_documents, bounded_source_documents, build_llama_plan
from .cloud_eval import compare_cloud_output
from .review import build_review_checklist, build_review_summary, initialize_review_state, record_agent_review, transition_review_state
from . import reducto
from .reducto_audit import audit_reducto_parse
from .xbrl import build_xbrl_corroboration
from .readiness import build_readiness
from .agent_review import build_agent_review
from .brief import build_decision_brief
from .approval import build_approval_packet
from .metrics import build_workflow_metrics
from .periods import build_period_registry
from .agreement_map import build_agreement_map
from .run import compare_run_snapshots, create_run_snapshot, verify_run_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(prog="ccrm")
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest-amzn")
    ingest.add_argument("--filing-radar", type=Path, required=True)
    ingest.add_argument("--output", type=Path, default=Path("data"))
    report = sub.add_parser("report")
    report.add_argument("--issuer", default="AMZN")
    report.add_argument("--output", type=Path, default=Path("data"))
    parse = sub.add_parser("parse")
    parse.add_argument("--issuer", default="AMZN")
    parse.add_argument("--output", type=Path, default=Path("data"))
    parse.add_argument("--force", action="store_true")
    extract = sub.add_parser("extract")
    extract.add_argument("--issuer", default="AMZN")
    extract.add_argument("--output", type=Path, default=Path("data"))
    extract.add_argument("--force", action="store_true")
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--issuer", default="AMZN")
    evaluate.add_argument("--output", type=Path, default=Path("data"))
    llama_plan = sub.add_parser("llama-plan")
    llama_plan.add_argument("--issuer", default="AMZN")
    llama_plan.add_argument("--output", type=Path, default=Path("data"))
    cloud_eval = sub.add_parser("compare-cloud")
    cloud_eval.add_argument("--issuer", default="AMZN")
    cloud_eval.add_argument("--output", type=Path, default=Path("data"))
    cloud_eval.add_argument("--cloud-output", type=Path, required=True)
    review = sub.add_parser("review-checklist")
    review.add_argument("--issuer", default="AMZN")
    review.add_argument("--output", type=Path, default=Path("data"))
    review_state = sub.add_parser("review-state")
    review_state.add_argument("--issuer", default="AMZN")
    review_state.add_argument("--output", type=Path, default=Path("data"))
    review_state.add_argument("--status", choices=("machine_assembled", "partially_reviewed", "human_verified"), default="machine_assembled")
    review_state.add_argument("--reviewer", default="")
    review_state.add_argument("--date", default="")
    review_state.add_argument("--complete-action", action="append", default=[])
    review_state.add_argument("--complete-evidence-id", action="append", default=[])
    review_summary = sub.add_parser("review-summary")
    review_summary.add_argument("--issuer", default="AMZN")
    review_summary.add_argument("--output", type=Path, default=Path("data"))
    agent_review = sub.add_parser("agent-review")
    agent_review.add_argument("--issuer", default="AMZN")
    agent_review.add_argument("--output", type=Path, default=Path("data"))
    decision_brief = sub.add_parser("decision-brief")
    decision_brief.add_argument("--issuer", default="AMZN")
    decision_brief.add_argument("--output", type=Path, default=Path("data"))
    approval_packet = sub.add_parser("approval-packet")
    approval_packet.add_argument("--issuer", default="AMZN")
    approval_packet.add_argument("--output", type=Path, default=Path("data"))
    workflow_metrics = sub.add_parser("workflow-metrics")
    workflow_metrics.add_argument("--issuer", default="AMZN")
    workflow_metrics.add_argument("--output", type=Path, default=Path("data"))
    period_registry = sub.add_parser("period-registry")
    period_registry.add_argument("--issuer", default="AMZN")
    period_registry.add_argument("--output", type=Path, default=Path("data"))
    agreement_map = sub.add_parser("agreement-map")
    agreement_map.add_argument("--issuer", default="AMZN")
    agreement_map.add_argument("--output", type=Path, default=Path("data"))
    reducto_parse = sub.add_parser("reducto-parse")
    reducto_parse.add_argument("--issuer", default="AMZN")
    reducto_parse.add_argument("--output", type=Path, default=Path("data"))
    reducto_parse.add_argument("--force", action="store_true")
    reducto_extract = sub.add_parser("reducto-extract")
    reducto_extract.add_argument("--issuer", default="AMZN")
    reducto_extract.add_argument("--output", type=Path, default=Path("data"))
    reducto_extract.add_argument("--force", action="store_true")
    reducto_audit = sub.add_parser("reducto-audit")
    reducto_audit.add_argument("--issuer", default="AMZN")
    reducto_audit.add_argument("--output", type=Path, default=Path("data"))
    readiness = sub.add_parser("readiness")
    readiness.add_argument("--issuer", default="AMZN")
    readiness.add_argument("--output", type=Path, default=Path("data"))
    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("--issuer", default="AMZN")
    snapshot.add_argument("--output", type=Path, default=Path("data"))
    verify_snapshot = sub.add_parser("verify-snapshot")
    verify_snapshot.add_argument("--run-manifest", type=Path, required=True)
    compare_runs = sub.add_parser("compare-runs")
    compare_runs.add_argument("--prior-run", type=Path, required=True)
    compare_runs.add_argument("--current-run", type=Path, required=True)
    compare_runs.add_argument("--output", type=Path, required=True)
    xbrl = sub.add_parser("xbrl-corroborate")
    xbrl.add_argument("--issuer", default="AMZN")
    xbrl.add_argument("--output", type=Path, default=Path("data"))
    args = parser.parse_args()
    issuer_commands = {"report", "parse", "extract", "evaluate", "llama-plan", "compare-cloud", "review-checklist", "review-state", "review-summary", "agent-review", "decision-brief", "approval-packet", "workflow-metrics", "period-registry", "agreement-map", "reducto-parse", "reducto-extract", "reducto-audit", "readiness", "snapshot", "xbrl-corroborate"}
    if args.command in issuer_commands and args.issuer.upper() != "AMZN":
        raise SystemExit("Prototype currently supports AMZN only")
    if args.command == "ingest-amzn":
        print(ingest_amzn(args.filing_radar, args.output))
    elif args.command == "report":
        print(build_report(args.output / "AMZN" / "corpus", args.output / "AMZN" / "report"))
    elif args.command == "parse":
        corpus = args.output / args.issuer.upper() / "corpus"
        sources = bounded_source_documents(corpus)
        for source in sources:
            print(parse_document(source, source.parent / "parsed", force=args.force))
    elif args.command == "extract":
        corpus = args.output / args.issuer.upper() / "corpus"
        parsed = bounded_agreement_parsed_documents(corpus)
        print(extract_report(parsed, args.output / args.issuer.upper() / "llama-extract.json", force=args.force))
    elif args.command == "evaluate":
        report_path = args.output / args.issuer.upper() / "report.json"
        evaluation_path = evaluate_report(report_path, args.output / args.issuer.upper() / "evaluation.json", args.output / args.issuer.upper() / "corpus-manifest.json", args.output / args.issuer.upper() / "xbrl-corroboration.json")
        print(evaluation_path)
        if not json.loads(evaluation_path.read_text(encoding="utf-8"))["passed"]:
            raise SystemExit(1)
    elif args.command == "llama-plan":
        print(build_llama_plan(args.output / "AMZN" / "corpus", args.output / "AMZN" / "llama-plan.json"))
    elif args.command == "compare-cloud":
        comparison_path = compare_cloud_output(args.cloud_output, args.output / "AMZN" / "report.json", args.output / "AMZN" / "cloud-comparison.json", args.output / "AMZN" / "corpus-manifest.json", args.output / "AMZN" / "reducto-parse-audit.json")
        print(comparison_path)
        if not json.loads(comparison_path.read_text(encoding="utf-8"))["passed"]:
            raise SystemExit(1)
    elif args.command == "review-checklist":
        print(build_review_checklist(args.output / "AMZN" / "report.json", args.output / "AMZN" / "human-review-checklist.md", args.output / "AMZN" / "cloud-comparison.json", args.output / "AMZN" / "reducto-parse-audit.json"))
    elif args.command == "review-state":
        issuer_dir = args.output / args.issuer.upper()
        state_path = issuer_dir / "review-state.json"
        checklist_path = issuer_dir / "human-review-checklist.md"
        if not state_path.exists():
            print(initialize_review_state(issuer_dir / "report.json", checklist_path, state_path, issuer_dir / "cloud-comparison.json", issuer_dir / "reducto-parse-audit.json", issuer_dir / "xbrl-corroboration.json"))
        elif args.status == "machine_assembled":
            print(state_path)
        else:
            if not args.reviewer or not args.date:
                raise SystemExit("--reviewer and --date are required for a review-state transition")
            print(transition_review_state(state_path, args.status, args.reviewer, args.date, args.complete_action, issuer_dir / "report.json", checklist_path, issuer_dir / "cloud-comparison.json", issuer_dir / "reducto-parse-audit.json", issuer_dir / "xbrl-corroboration.json", args.complete_evidence_id))
    elif args.command == "review-summary":
        issuer_dir = args.output / args.issuer.upper()
        print(build_review_summary(issuer_dir / "report.json", issuer_dir / "cloud-comparison.json", issuer_dir / "reducto-parse-audit.json", issuer_dir / "review-state.json", issuer_dir / "review-summary.md"))
    elif args.command == "agent-review":
        issuer_dir = args.output / args.issuer.upper()
        agent_review_path = build_agent_review(issuer_dir, issuer_dir / "agent-review.json")
        print(record_agent_review(issuer_dir / "review-state.json", agent_review_path))
    elif args.command == "decision-brief":
        issuer_dir = args.output / args.issuer.upper()
        print(build_decision_brief(issuer_dir / "report.json", issuer_dir / "agent-review.json", issuer_dir / "decision-brief.md"))
    elif args.command == "approval-packet":
        issuer_dir = args.output / args.issuer.upper()
        print(build_approval_packet(issuer_dir, issuer_dir / "human-approval-packet.md"))
    elif args.command == "workflow-metrics":
        issuer_dir = args.output / args.issuer.upper()
        print(build_workflow_metrics(issuer_dir, issuer_dir / "workflow-metrics.json"))
    elif args.command == "period-registry":
        issuer_dir = args.output / args.issuer.upper()
        print(build_period_registry(issuer_dir, issuer_dir / "period-registry.json"))
    elif args.command == "agreement-map":
        issuer_dir = args.output / args.issuer.upper()
        print(build_agreement_map(issuer_dir, issuer_dir / "agreement-map.json"))
    elif args.command == "readiness":
        print(build_readiness(args.output / args.issuer.upper(), args.output / args.issuer.upper() / "readiness.json"))
    elif args.command == "snapshot":
        print(create_run_snapshot(args.output / args.issuer.upper()))
    elif args.command == "verify-snapshot":
        result = verify_run_snapshot(args.run_manifest)
        print(json.dumps(result, indent=2))
        if not result["passed"]:
            raise SystemExit(1)
    elif args.command == "compare-runs":
        print(compare_run_snapshots(args.prior_run, args.current_run, args.output))
    elif args.command == "reducto-parse":
        corpus = args.output / args.issuer.upper() / "corpus"
        for source in bounded_source_documents(corpus):
            print(reducto.parse_document(source, source.parent / "reducto-parsed", force=args.force))
    elif args.command == "reducto-extract":
        corpus = args.output / args.issuer.upper() / "corpus"
        agreements = [corpus / folder / "agreement.htm" for folder in sorted(reducto.AGREEMENT_FOLDERS)]
        print(reducto.extract_report(agreements, args.output / args.issuer.upper() / "reducto-extract.json", force=args.force))
    elif args.command == "reducto-audit":
        issuer_dir = args.output / args.issuer.upper()
        print(audit_reducto_parse(issuer_dir / "corpus", issuer_dir / "corpus-manifest.json", issuer_dir / "reducto-parse-audit.json"))
    elif args.command == "xbrl-corroborate":
        issuer_dir = args.output / args.issuer.upper()
        manifest = json.loads((issuer_dir / "corpus-manifest.json").read_text(encoding="utf-8"))
        record = next(d for d in manifest["documents"] if d.get("filing", {}).get("accession_number") == "0001018724-26-000026")
        print(build_xbrl_corroboration(Path(record["source_file"]), record["filing"]["source_url"], issuer_dir / "xbrl-corroboration.json", issuer_dir / "report.json"))


if __name__ == "__main__":
    main()
