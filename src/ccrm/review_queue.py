"""Build a structured analyst queue from agent-reviewed exceptions."""

from __future__ import annotations

import json
from pathlib import Path


def build_review_queue(issuer_dir: Path, output: Path) -> Path:
    agent = json.loads((issuer_dir / "agent-review.json").read_text(encoding="utf-8"))
    rows = []
    for index, exception in enumerate(agent.get("exceptions", []), start=1):
        rows.append({
            "queue_id": f"EX-{index:03d}",
            "topic": exception.get("topic", "open item"),
            "severity": exception.get("severity", "review"),
            "status": "open",
            "owner": None,
            "agent_finding": exception.get("detail", ""),
            "evidence_ids": exception.get("evidence_ids", []),
            "human_disposition": None,
            "human_note": None,
        })
    result = {
        "issuer": issuer_dir.name,
        "report_period": json.loads((issuer_dir / "report.json").read_text(encoding="utf-8")).get("as_of"),
        "review_state": json.loads((issuer_dir / "review-state.json").read_text(encoding="utf-8")).get("status"),
        "human_approval_required": True,
        "items": rows,
        "workflow_note": "This queue organizes human work; agent findings do not change release readiness or approve the report.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return output
