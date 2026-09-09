"""Build a source-only issuer coverage inventory from a Filing Radar export."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def build_issuer_coverage(filing_radar: Path, issuer: str, output: Path) -> Path:
    issuer = issuer.upper()
    root = filing_radar / "data" / issuer
    if not root.is_dir():
        raise FileNotFoundError(root)
    documents = []
    for manifest_path in sorted(root.glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        filing = manifest.get("filing", {})
        source_value = manifest.get("source_file")
        source = Path(source_value) if source_value and Path(source_value).is_absolute() else (filing_radar / source_value if source_value else None)
        documents.append({
            "accession": filing.get("accession_number", manifest_path.parent.name),
            "form": filing.get("form"),
            "filing_date": filing.get("filing_date"),
            "report_date": filing.get("report_date"),
            "source_url": filing.get("source_url"),
            "source_available": bool(source and source.is_file()),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest() if source and source.is_file() else None,
        })
    report_dates = sorted({item["report_date"] for item in documents if item.get("report_date")}, reverse=True)
    result = {
        "issuer": issuer,
        "status": "source_scoped",
        "customer_ready": False,
        "report_dates": report_dates,
        "document_count": len(documents),
        "documents": documents,
        "scope_note": "Source inventory only. No debt, covenant, headroom, or customer-ready conclusion is inferred from coverage alone.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return output
