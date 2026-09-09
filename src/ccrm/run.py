"""Create immutable, self-contained report snapshots for a reporting period."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .cloud_eval import compare_cloud_output
from .evaluate import evaluate_report
from .readiness import build_readiness
from .reducto_audit import audit_reducto_parse
from .report import build_report
from .review import build_review_checklist, build_review_summary, initialize_review_state, record_agent_review
from .agent_review import build_agent_review
from .brief import build_decision_brief
from .approval import build_approval_packet
from .metrics import build_workflow_metrics
from .agreement_map import build_agreement_map


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_source(path: Path, issuer_dir: Path) -> Path:
    if path.is_absolute() and path.is_file():
        return path
    candidates = [path, issuer_dir.parent.parent / path, issuer_dir / path]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(path)


def _rewrite_snapshot_manifest(issuer_dir: Path, corpus: Path, run_dir: Path) -> Path:
    source_manifest = issuer_dir / "corpus-manifest.json"
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    for document in manifest.get("documents", []):
        source_value = document.get("source_file")
        if not source_value:
            continue
        source = _resolve_source(Path(source_value), issuer_dir)
        relative = source.relative_to(corpus.resolve())
        # Snapshot manifests use absolute paths so both the report builder and
        # the evaluator resolve the copied corpus unambiguously.
        document["source_file"] = str((run_dir / "corpus" / relative).resolve())
    output = run_dir / "corpus-manifest.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output


def _copy_optional(source: Path, destination: Path) -> None:
    if source.is_file():
        shutil.copy2(source, destination)


def create_run_snapshot(issuer_dir: Path) -> Path:
    """Snapshot the current issuer artifacts without mutating the working report."""
    report_path = issuer_dir / "report.json"
    manifest_path = issuer_dir / "corpus-manifest.json"
    review_path = issuer_dir / "review-state.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    run_seed = "|".join([
        report.get("issuer", issuer_dir.name),
        report.get("as_of", ""),
        report.get("prior_period", ""),
        _sha256(manifest_path),
        _sha256(report_path),
        _sha256(review_path),
    ])
    run_id = "run-" + hashlib.sha256(run_seed.encode("utf-8")).hexdigest()[:16]
    run_dir = issuer_dir / "runs" / run_id
    run_manifest_path = run_dir / "run-manifest.json"
    if run_manifest_path.is_file():
        return run_manifest_path
    run_dir.mkdir(parents=True, exist_ok=False)
    source_corpus = issuer_dir / "corpus"
    shutil.copytree(source_corpus, run_dir / "corpus")
    snapshot_manifest = _rewrite_snapshot_manifest(issuer_dir, source_corpus, run_dir)

    # Rebuild all derived artifacts inside the snapshot so their hashes and
    # references cannot depend on the mutable working directory.
    build_report(run_dir / "corpus", run_dir / "report")
    for name in ("reducto-extract.json",):
        _copy_optional(issuer_dir / name, run_dir / name)
    audit_reducto_parse(run_dir / "corpus", snapshot_manifest, run_dir / "reducto-parse-audit.json")
    if (run_dir / "reducto-extract.json").is_file():
        compare_cloud_output(run_dir / "reducto-extract.json", run_dir / "report.json", run_dir / "cloud-comparison.json", snapshot_manifest, run_dir / "reducto-parse-audit.json")
    for name in ("xbrl-corroboration.json",):
        _copy_optional(issuer_dir / name, run_dir / name)
    evaluate_report(run_dir / "report.json", run_dir / "evaluation.json", snapshot_manifest, run_dir / "xbrl-corroboration.json")
    checklist = build_review_checklist(run_dir / "report.json", run_dir / "human-review-checklist.md", run_dir / "cloud-comparison.json", run_dir / "reducto-parse-audit.json")
    state = initialize_review_state(run_dir / "report.json", checklist, run_dir / "review-state.json", run_dir / "cloud-comparison.json", run_dir / "reducto-parse-audit.json", run_dir / "xbrl-corroboration.json")
    build_review_summary(run_dir / "report.json", run_dir / "cloud-comparison.json", run_dir / "reducto-parse-audit.json", state, run_dir / "review-summary.md")
    agent_review = build_agent_review(run_dir, run_dir / "agent-review.json")
    record_agent_review(state, agent_review)
    build_decision_brief(run_dir / "report.json", run_dir / "agent-review.json", run_dir / "decision-brief.md")
    build_approval_packet(run_dir, run_dir / "human-approval-packet.md")
    build_workflow_metrics(run_dir, run_dir / "workflow-metrics.json")
    build_agreement_map(run_dir, run_dir / "agreement-map.json")
    readiness = build_readiness(run_dir, run_dir / "readiness.json")

    artifact_hashes: dict[str, str] = {}
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path.name != "run-manifest.json":
            artifact_hashes[str(path.relative_to(run_dir))] = _sha256(path)
    result: dict[str, Any] = {
        "run_id": run_id,
        "issuer": report.get("issuer"),
        "as_of": report.get("as_of"),
        "prior_period": report.get("prior_period"),
        "release_status": json.loads(readiness.read_text(encoding="utf-8")).get("release_status"),
        "immutable": True,
        "corpus_snapshot": "corpus/",
        "artifact_sha256": artifact_hashes,
        "artifact_count": len(artifact_hashes),
    }
    run_manifest_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return run_manifest_path


def verify_run_snapshot(run_manifest_path: Path) -> dict[str, Any]:
    """Verify every hash recorded by an immutable run manifest."""
    manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    checks = []
    run_dir = run_manifest_path.parent
    for relative, expected in manifest.get("artifact_sha256", {}).items():
        path = run_dir / relative
        actual = _sha256(path) if path.is_file() else None
        checks.append({"artifact": relative, "passed": actual == expected})
    return {"run_id": manifest.get("run_id"), "passed": bool(checks) and all(check["passed"] for check in checks), "checks": checks}


def _evidence_ids(item: dict[str, Any]) -> list[str]:
    return [e["evidence_id"] for e in item.get("evidence", []) if e.get("evidence_id")]


def compare_run_snapshots(prior_manifest_path: Path, current_manifest_path: Path, output: Path) -> Path:
    """Compare two verified immutable runs without modifying either run."""
    prior_verification = verify_run_snapshot(prior_manifest_path)
    current_verification = verify_run_snapshot(current_manifest_path)
    prior_dir, current_dir = prior_manifest_path.parent, current_manifest_path.parent
    prior_run = json.loads(prior_manifest_path.read_text(encoding="utf-8"))
    current_run = json.loads(current_manifest_path.read_text(encoding="utf-8"))
    issuer_match = prior_run.get("issuer") == current_run.get("issuer")
    prior_report = json.loads((prior_dir / "report.json").read_text(encoding="utf-8"))
    current_report = json.loads((current_dir / "report.json").read_text(encoding="utf-8"))
    prior_corpus = json.loads((prior_dir / "corpus-manifest.json").read_text(encoding="utf-8"))
    current_corpus = json.loads((current_dir / "corpus-manifest.json").read_text(encoding="utf-8"))

    prior_instruments = {item["name"]: item for item in prior_report.get("debt_instruments", [])}
    current_instruments = {item["name"]: item for item in current_report.get("debt_instruments", [])}
    instrument_changes = []
    fields = ("instrument_type", "agreement_version", "principal_amount", "outstanding_amount", "commitment_amount", "maturity_date", "interest_rate_or_spread", "rate_type", "secured_status", "priority", "recent_change")
    for name in sorted(set(prior_instruments) | set(current_instruments)):
        before, after = prior_instruments.get(name), current_instruments.get(name)
        if before is None or after is None:
            instrument_changes.append({"name": name, "change": "added" if after else "removed", "before": before, "after": after, "evidence_ids": _evidence_ids(after or before)})
            continue
        changed = {field: {"prior": before.get(field), "current": after.get(field)} for field in fields if before.get(field) != after.get(field)}
        if changed:
            instrument_changes.append({"name": name, "change": "changed", "fields": changed, "evidence_ids": _evidence_ids(after)})

    prior_covenants = {item["name"]: item for item in prior_report.get("covenants", [])}
    current_covenants = {item["name"]: item for item in current_report.get("covenants", [])}
    covenant_changes = []
    for name in sorted(set(prior_covenants) | set(current_covenants)):
        before, after = prior_covenants.get(name), current_covenants.get(name)
        if before is None or after is None:
            covenant_changes.append({"name": name, "change": "added" if after else "removed", "before": before, "after": after, "evidence_ids": _evidence_ids(after or before)})
            continue
        changed = {field: {"prior": before.get(field), "current": after.get(field)} for field in ("covenant_type", "threshold", "testing_date_or_frequency", "calculated_value", "estimated_headroom", "status", "maintenance_or_incurrence", "agreement_section") if before.get(field) != after.get(field)}
        if changed:
            covenant_changes.append({"name": name, "change": "changed", "fields": changed, "evidence_ids": _evidence_ids(after)})

    def corpus_index(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {d.get("document_id") or d.get("filing", {}).get("accession_number"): d for d in manifest.get("documents", [])}

    prior_docs, current_docs = corpus_index(prior_corpus), corpus_index(current_corpus)
    corpus_changes = []
    for document_id in sorted(set(prior_docs) | set(current_docs)):
        before, after = prior_docs.get(document_id), current_docs.get(document_id)
        if before is None or after is None:
            corpus_changes.append({"document_id": document_id, "change": "added" if after else "removed"})
        elif before.get("source_sha256") != after.get("source_sha256"):
            corpus_changes.append({"document_id": document_id, "change": "source_changed", "prior_sha256": before.get("source_sha256"), "current_sha256": after.get("source_sha256")})

    same_reporting_period = prior_run.get("as_of") == current_run.get("as_of") and prior_run.get("prior_period") == current_run.get("prior_period")
    same_corpus = not corpus_changes
    same_report_content = not instrument_changes and not covenant_changes and prior_report.get("changes_since_prior_period", []) == current_report.get("changes_since_prior_period", [])

    result = {
        "prior_run_id": prior_run.get("run_id"),
        "current_run_id": current_run.get("run_id"),
        "issuer": current_run.get("issuer"),
        "prior_period": prior_run.get("as_of"),
        "current_period": current_run.get("as_of"),
        "passed": prior_verification["passed"] and current_verification["passed"] and issuer_match,
        "identical": same_reporting_period and same_corpus and same_report_content,
        "same_reporting_period": same_reporting_period,
        "verification": {"prior": prior_verification, "current": current_verification},
        "corpus_changes": corpus_changes,
        "instrument_changes": instrument_changes,
        "covenant_changes": covenant_changes,
        "declared_current_run_changes": current_report.get("changes_since_prior_period", []),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return output
