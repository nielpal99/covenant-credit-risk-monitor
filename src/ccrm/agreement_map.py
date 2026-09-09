"""Normalize agreement review hooks from source-linked report evidence."""

from __future__ import annotations

import json
from pathlib import Path


def build_agreement_map(issuer_dir: Path, output: Path) -> Path:
    report = json.loads((issuer_dir / "report.json").read_text(encoding="utf-8"))
    audit_path = issuer_dir / "reducto-parse-audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.is_file() else {}
    parsed_checks = {(item.get("document_id"), item.get("check")) for item in audit.get("checks", []) if item.get("passed")}
    sections = []
    for evidence in report.get("risk_status", {}).get("evidence", []):
        locator = evidence.get("locator", "")
        if not (locator.startswith("Section ") or locator in {"First Amendment", "Exhibits 10.2 and 10.3"}):
            continue
        sections.append({
            "document_id": evidence.get("document_id"),
            "locator": locator,
            "evidence_id": evidence.get("evidence_id"),
            "sec_url": evidence.get("sec_url"),
            "excerpt": evidence.get("excerpt"),
            "parse_presence": (evidence.get("document_id"), locator) in parsed_checks or (evidence.get("document_id"), "Amendment text") in parsed_checks,
            "review_status": "human_review_required",
        })
    result = {
        "issuer": report.get("issuer"),
        "agreement_sections": sections,
        "section_count": len(sections),
        "human_review_required": True,
        "scope_note": "This is a review map, not a legal abstraction. It preserves source excerpts and does not infer baskets, capacity, or remedies beyond the cited text.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return output
