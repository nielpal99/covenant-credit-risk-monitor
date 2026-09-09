"""Turn source-only coverage into a reviewable issuer configuration draft."""

from __future__ import annotations

import json
from pathlib import Path


def build_issuer_config(coverage: Path, output: Path) -> Path:
    """Create a configuration draft without promoting source coverage to credit analysis."""
    inventory = json.loads(coverage.read_text(encoding="utf-8"))
    documents = inventory.get("documents", [])
    quarterly = sorted(
        (item for item in documents if item.get("form") == "10-Q" and item.get("report_date")),
        key=lambda item: item["report_date"],
        reverse=True,
    )
    annual = sorted(
        (item for item in documents if item.get("form") == "10-K" and item.get("report_date")),
        key=lambda item: item["report_date"],
        reverse=True,
    )
    result = {
        "issuer": inventory.get("issuer"),
        "status": "configuration_draft",
        "source_coverage_status": inventory.get("status"),
        "credit_report_enabled": False,
        "customer_ready": False,
        "requires_human_configuration_review": True,
        "selected_latest_10q": quarterly[0] if quarterly else None,
        "selected_prior_10q": quarterly[1] if len(quarterly) > 1 else None,
        "latest_10k": annual[0] if annual else None,
        "available_10q_count": len(quarterly),
        "available_10k_count": len(annual),
        "configuration_gaps": [
            "instrument families and governing agreements are not mapped",
            "issuer-specific report vocabulary is not configured",
            "covenant definitions and calculation inputs are not configured",
            "human review is required before enabling credit conclusions",
        ],
        "scope_note": "This draft organizes genuine SEC sources only. It does not infer debt, covenants, headroom, risk, or customer readiness.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return output
