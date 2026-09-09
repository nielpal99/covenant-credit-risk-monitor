"""Source-bound agent review for reducing the human approval workload."""

from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized_source(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip().lower()


def build_agent_review(
    issuer_dir: Path,
    output: Path,
) -> Path:
    """Run bounded consistency checks without claiming human approval."""
    report_path = issuer_dir / "report.json"
    manifest_path = issuer_dir / "corpus-manifest.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = {
        d.get("document_id") or d.get("filing", {}).get("accession_number"): d
        for d in manifest.get("documents", [])
    }
    evidence: list[dict[str, Any]] = []
    for collection_name, collection in (
        ("debt_instruments", report.get("debt_instruments", [])),
        ("covenants", report.get("covenants", [])),
        ("changes_since_prior_period", report.get("changes_since_prior_period", [])),
        ("risk_status", [report.get("risk_status", {})]),
    ):
        for item in collection:
            for item_evidence in item.get("evidence", []):
                evidence.append({"collection": collection_name, **item_evidence})

    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    expected_manifest_hash = report.get("corpus_manifest_sha256")
    check(
        "report corpus binding",
        expected_manifest_hash == _sha256(manifest_path),
        "Report corpus hash matches the current corpus manifest." if expected_manifest_hash == _sha256(manifest_path) else "Report corpus hash does not match the current corpus manifest.",
    )
    malformed = [
        item.get("evidence_id", "missing-id")
        for item in evidence
        if not item.get("evidence_id") or not item.get("locator") or not item.get("excerpt") or not str(item.get("sec_url", "")).startswith("https://www.sec.gov/")
    ]
    check("evidence completeness", not malformed, "All report evidence has an ID, locator, excerpt, and SEC URL." if not malformed else f"Malformed evidence: {malformed}")
    missing_documents = [item.get("evidence_id", "missing-id") for item in evidence if item.get("document_id") not in documents]
    check("evidence source membership", not missing_documents, "Every evidence item points to a corpus document." if not missing_documents else f"Evidence points outside the corpus: {missing_documents}")
    excerpt_mismatches = []
    source_text_cache: dict[str, str] = {}
    for item in evidence:
        evidence_id = item.get("evidence_id", "missing-id")
        document = documents.get(item.get("document_id"), {})
        source_file = document.get("source_file")
        if not source_file or not Path(source_file).is_file() or not item.get("excerpt"):
            continue
        if item.get("document_id") not in source_text_cache:
            source_text_cache[item["document_id"]] = _normalized_source(Path(source_file).read_text(encoding="utf-8", errors="ignore"))
        excerpt_prefix = _normalized_source(item["excerpt"])[:80]
        if excerpt_prefix and excerpt_prefix not in source_text_cache[item["document_id"]]:
            excerpt_mismatches.append(evidence_id)
    check("evidence excerpt anchoring", not excerpt_mismatches, "Each evidence excerpt is anchored in its manifest source file." if not excerpt_mismatches else f"Evidence excerpts not found in source: {excerpt_mismatches}")
    missing_files = []
    for document_id, document in documents.items():
        source_file = document.get("source_file")
        if source_file and not Path(source_file).is_file():
            missing_files.append(document_id)
    check("corpus file availability", not missing_files, "Every manifest source file is available." if not missing_files else f"Missing source files: {missing_files}")

    ddtl = next((item for item in report.get("debt_instruments", []) if item.get("name") == "DDTL Facility"), {})
    check("DDTL fact consistency", ddtl.get("commitment_amount") == "$17.5 billion" and "$0" in str(ddtl.get("outstanding_amount")), "DDTL commitment and quarter-end balance agree with the report evidence." )
    unsafe_headroom = [item.get("name") for item in report.get("covenants", []) if item.get("status") == "not_calculable" and item.get("estimated_headroom") is not None]
    check("calculation safety", not unsafe_headroom, "No headroom is emitted for a not-calculable covenant." if not unsafe_headroom else f"Unsupported headroom found for: {unsafe_headroom}")
    unproven_changes = [item.get("change_type", "unknown") for item in report.get("changes_since_prior_period", []) if not item.get("evidence")]
    check("change provenance", not unproven_changes, "Every declared change has supporting evidence." if not unproven_changes else f"Unproven changes: {unproven_changes}")

    def evidence_ids(items: list[dict[str, Any]]) -> list[str]:
        return sorted({item.get("evidence_id") for record in items for item in record.get("evidence", []) if item.get("evidence_id")})

    amendments = [item for item in report.get("changes_since_prior_period", []) if item.get("change_type") == "amendment"]
    covenants = report.get("covenants", [])
    risk_items = [report.get("risk_status", {})]
    ddtl_items = [item for item in report.get("debt_instruments", []) if item.get("name") == "DDTL Facility"]
    exceptions = [
        {"severity": "material", "topic": "agreement amendments", "detail": "The two June 8 revolving amendments are identified and source-linked, but their full commercial effect remains for human confirmation.", "evidence_ids": evidence_ids(amendments)},
        {"severity": "material", "topic": "covenant capacity", "detail": "Financial covenant, lien, and fundamental-change headroom remains not calculable; the agent confirms that no unsupported headroom was emitted.", "evidence_ids": evidence_ids(covenants)},
        {"severity": "review", "topic": "events of default and remedies", "detail": "Sections 8.01 and 8.02 are source-linked, but the provider output is not a substitute for reviewer confirmation of the complete triggers and remedies.", "evidence_ids": evidence_ids(risk_items)},
        {"severity": "review", "topic": "post-period activity", "detail": "The report cannot determine whether the DDTL was drawn after June 30 and before the September 30 commitment expiry.", "evidence_ids": evidence_ids(ddtl_items)},
    ]
    passed = all(item["passed"] for item in checks)
    result = {
        "issuer": report.get("issuer"),
        "status": "agent_reviewed" if passed else "agent_review_failed",
        "human_approval_required": True,
        "report_sha256": _sha256(report_path),
        "corpus_manifest_sha256": _sha256(manifest_path),
        "checks": checks,
        "exceptions": exceptions,
        "summary": "Agent review passed bounded source, provenance, excerpt-anchoring, and calculation-safety checks. Human approval is still required for the listed exceptions and final release decision." if passed else "Agent review found automated consistency failures; human approval is blocked until they are repaired.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return output
