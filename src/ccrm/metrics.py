"""Persist conservative workflow metrics for product-value evaluation."""

from __future__ import annotations

import json
from pathlib import Path


def build_workflow_metrics(issuer_dir: Path, output: Path) -> Path:
    report = json.loads((issuer_dir / "report.json").read_text(encoding="utf-8"))
    review = json.loads((issuer_dir / "review-state.json").read_text(encoding="utf-8"))
    agent = json.loads((issuer_dir / "agent-review.json").read_text(encoding="utf-8"))
    evidence_items = len(review.get("evidence_items", {}))
    exceptions = len(agent.get("exceptions", []))
    result = {
        "issuer": report.get("issuer"),
        "report_period": report.get("as_of"),
        "agent_review_status": agent.get("status"),
        "evidence_items_in_review_state": evidence_items,
        "agent_checks": len(agent.get("checks", [])),
        "agent_exceptions": exceptions,
        "human_review_focus_ratio": round(exceptions / evidence_items, 4) if evidence_items else None,
        "interpretation": "The agent narrows human attention to explicit exceptions; this is a workflow-compression measure, not a measured time-saved claim.",
        "time_saved_measured": False,
        "human_approval_status": review.get("status"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return output
