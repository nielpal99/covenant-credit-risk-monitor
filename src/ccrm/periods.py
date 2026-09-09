"""Inventory immutable reporting periods without fabricating missing history."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

def build_period_registry(issuer_dir: Path, output: Path) -> Path:
    from .run import verify_run_snapshot
    groups: dict[str, list[dict]] = defaultdict(list)
    invalid_runs = []
    for manifest_path in sorted((issuer_dir / "runs").glob("*/run-manifest.json")) if (issuer_dir / "runs").is_dir() else []:
        verification = verify_run_snapshot(manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        key = f"{manifest.get('as_of')}|{manifest.get('prior_period')}"
        record = {"run_id": manifest.get("run_id"), "path": str(manifest_path), "as_of": manifest.get("as_of"), "prior_period": manifest.get("prior_period"), "verified": verification.get("passed") is True}
        groups[key].append(record)
        if not record["verified"]:
            invalid_runs.append(record["run_id"])
    periods = [{"period_key": key, "as_of": rows[0]["as_of"], "prior_period": rows[0]["prior_period"], "run_count": len(rows), "runs": rows} for key, rows in sorted(groups.items())]
    duplicate_runs = [run["run_id"] for period in periods if period["run_count"] > 1 for run in period["runs"][1:]]
    result = {
        "issuer": issuer_dir.name,
        "periods": periods,
        "distinct_period_count": len(periods),
        "verified_run_count": sum(run["verified"] for period in periods for run in period["runs"]),
        "duplicate_runs": duplicate_runs,
        "invalid_runs": invalid_runs,
        "historical_comparison_ready": len(periods) >= 2 and not invalid_runs,
        "note": "Only distinct verified reporting periods count toward repeatability; duplicate rebuilds are retained for audit but do not count as history.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return output
