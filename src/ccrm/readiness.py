"""Aggregate the persisted quality and review gates into one release signal."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_readiness(issuer_dir: Path, output: Path) -> Path:
    report = json.loads((issuer_dir / "report.json").read_text(encoding="utf-8"))
    evaluation = json.loads((issuer_dir / "evaluation.json").read_text(encoding="utf-8"))
    review = json.loads((issuer_dir / "review-state.json").read_text(encoding="utf-8"))
    comparison = json.loads((issuer_dir / "cloud-comparison.json").read_text(encoding="utf-8")) if (issuer_dir / "cloud-comparison.json").is_file() else None
    parse_audit = json.loads((issuer_dir / "reducto-parse-audit.json").read_text(encoding="utf-8")) if (issuer_dir / "reducto-parse-audit.json").is_file() else None
    agent_review = json.loads((issuer_dir / "agent-review.json").read_text(encoding="utf-8")) if (issuer_dir / "agent-review.json").is_file() else None
    run_manifests = list((issuer_dir / "runs").glob("*/run-manifest.json")) if (issuer_dir / "runs").is_dir() else []
    distinct_periods = set()
    for run_manifest in run_manifests:
        try:
            run = json.loads(run_manifest.read_text(encoding="utf-8"))
            distinct_periods.add((run.get("as_of"), run.get("prior_period")))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue

    gates: list[dict[str, Any]] = [
        {"name": "automated evaluation", "passed": evaluation.get("passed") is True, "artifact": "evaluation.json"},
        {"name": "human review", "passed": review.get("status") == "human_verified", "artifact": "review-state.json"},
        {"name": "provider comparison", "passed": comparison is None or comparison.get("passed") is True, "artifact": "cloud-comparison.json", "optional": True},
        {"name": "Parse audit", "passed": parse_audit is None or parse_audit.get("passed") is True, "artifact": "reducto-parse-audit.json", "optional": True},
        {"name": "agent review", "passed": agent_review is not None and agent_review.get("status") == "agent_reviewed", "artifact": "agent-review.json", "optional": True},
    ]
    blocking_items = [gate["name"] for gate in gates if not gate["passed"] and not gate.get("optional")]
    documented_gaps = [gate["name"] for gate in gates if not gate["passed"] and gate.get("optional")]
    if not evaluation.get("passed"):
        release_status = "blocked"
    elif review.get("status") == "human_verified":
        release_status = "customer_ready"
    else:
        release_status = "internal_review"
    expansion_blockers = []
    if review.get("status") != "human_verified":
        expansion_blockers.append("AMZN human review is not complete")
    if len(distinct_periods) < 2:
        expansion_blockers.append("fewer than two distinct immutable reporting periods exist")
    result = {
        "issuer": report.get("issuer", issuer_dir.name),
        "release_status": release_status,
        "customer_ready": release_status == "customer_ready",
        "gates": gates,
        "blocking_items": blocking_items,
        "documented_optional_gaps": documented_gaps,
        "expansion_ready": not expansion_blockers,
        "expansion_blockers": expansion_blockers,
        "next_action": "Complete the human review checklist and record all evidence/actions." if release_status == "internal_review" else "Repair failed automated gates before distribution." if release_status == "blocked" else "Maintain the evidence snapshot and review state for the next reporting period.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return output
