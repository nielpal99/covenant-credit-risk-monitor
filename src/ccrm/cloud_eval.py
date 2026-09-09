import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


def _flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {_flatten(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    return str(value)


def _scalar(value: Any) -> Any:
    """Unwrap provider value objects while retaining them in the raw artifact."""
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _reducto_citation_evidence(item: Any, document_id: str, sec_url: str) -> list[dict[str, Any]]:
    """Turn Reducto citation blocks into review-only evidence objects."""
    found: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            citations = value.get("citations")
            if isinstance(citations, list):
                for citation in citations:
                    if not isinstance(citation, dict):
                        continue
                    excerpt = citation.get("content") or citation.get("text")
                    bbox = citation.get("bbox") or {}
                    page = bbox.get("page") if isinstance(bbox, dict) else None
                    if excerpt:
                        evidence = {
                            "document_id": document_id,
                            "sec_url": sec_url,
                            "locator": f"Reducto page {page}" if page else "Reducto citation",
                            "excerpt": str(excerpt).strip(),
                            "kind": "provider_citation",
                            "human_verified": False,
                        }
                        if evidence not in found:
                            found.append(evidence)
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(item)
    return found


def _normalize_reducto_provenance(value: Any, source_urls: dict[str, str]) -> Any:
    """Normalize only the comparison view; retain raw provider output on disk."""
    normalized = deepcopy(value)
    if not isinstance(normalized, list):
        return normalized
    for entry in normalized:
        if not isinstance(entry, dict) or entry.get("provider") != "reducto":
            continue
        document = str(entry.get("document") or "")
        document_id = Path(document).parent.name
        sec_url = source_urls.get(document_id, "")
        result = entry.get("result")
        if not isinstance(result, dict):
            continue
        for collection_name in ("debt_instruments", "covenants"):
            collection = result.get(collection_name)
            if not isinstance(collection, list):
                continue
            for item in collection:
                if not isinstance(item, dict) or item.get("evidence"):
                    continue
                item["evidence"] = _reducto_citation_evidence(item, document_id, sec_url)
        evidence = result.get("evidence")
        if isinstance(evidence, list):
            for item in evidence:
                if not isinstance(item, dict):
                    continue
                item["document_id"] = document_id
                item["sec_url"] = sec_url
                item.setdefault("kind", "provider_citation")
                item.setdefault("human_verified", False)
    return normalized


def _normalize_json_values(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return _normalize_json_values(json.loads(value))
        except json.JSONDecodeError:
            return value
    if isinstance(value, dict):
        return {key: _normalize_json_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_json_values(item) for item in value]
    return value


def _keyed_values(value: Any, keys: set[str]) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in keys:
                found.append(_flatten(item).lower())
            found.extend(_keyed_values(item, keys))
    elif isinstance(value, list):
        for item in value:
            found.extend(_keyed_values(item, keys))
    return found


def _is_reducto_bundle(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, dict) and item.get("provider") == "reducto" for item in value
    )


def _reducto_signal_checks(cloud: Any) -> list[dict[str, Any]]:
    """Use checks appropriate to Extract inputs, without weakening missing-hook failures."""
    flattened = re.sub(r"[^a-z0-9.]", "", _flatten(cloud).lower())
    commitment_found = "17500000000" in flattened or "17.5billion" in flattened
    return [
        {
            "signal": "ddtl_commitment",
            "expected_from_baseline": "$17.5 billion",
            "found_in_cloud_output": commitment_found,
            "applicable": True,
        },
        {
            "signal": "ddtl_outstanding",
            "expected_from_baseline": "$0",
            "found_in_cloud_output": False,
            "applicable": False,
            "reason": "Not in scope: the Reducto Extract input was the agreement, not the June 30, 2026 10-Q.",
        },
        {
            "signal": "no_financial_covenant",
            "expected_from_baseline": "no financial covenant",
            "found_in_cloud_output": False,
            "applicable": False,
            "reason": "Not asserted from absence of extracted definitions; requires direct agreement/filing review.",
        },
        {
            "signal": "revolving_amendment",
            "expected_from_baseline": "first amendment",
            "found_in_cloud_output": False,
            "applicable": True,
        },
        {
            "signal": "events_of_default",
            "expected_from_baseline": "events of default",
            "found_in_cloud_output": False,
            "applicable": True,
        },
        {
            "signal": "remedies",
            "expected_from_baseline": "remedies upon event of default",
            "found_in_cloud_output": False,
            "applicable": True,
        },
    ]


def _structured_evidence_gaps(value: Any) -> list[str]:
    gaps: list[str] = []
    if isinstance(value, dict):
        for collection_name in ("debt_instruments", "covenants"):
            collection = value.get(collection_name)
            if isinstance(collection, list):
                for index, item in enumerate(collection):
                    if isinstance(item, dict) and (
                        not item.get("evidence")
                        or not all(
                            isinstance(evidence, dict)
                            and _scalar(evidence.get("document_id"))
                            and str(_scalar(evidence.get("sec_url", ""))).startswith("https://www.sec.gov/")
                            and _scalar(evidence.get("locator"))
                            and _scalar(evidence.get("excerpt"))
                            for evidence in item.get("evidence", [])
                        )
                    ):
                        gaps.append(f"{collection_name}[{index}]")
        changes = value.get("changes_since_prior_period")
        if isinstance(changes, list):
            for index, item in enumerate(changes):
                if not isinstance(item, dict) or not item.get("description") or not item.get("change_type") or not item.get("evidence") or not all(
                    isinstance(evidence, dict)
                    and _scalar(evidence.get("document_id"))
                    and str(_scalar(evidence.get("sec_url", ""))).startswith("https://www.sec.gov/")
                    and _scalar(evidence.get("locator"))
                    and _scalar(evidence.get("excerpt"))
                    for evidence in item.get("evidence", [])
                ):
                    gaps.append(f"changes_since_prior_period[{index}]")
        financial_definitions = value.get("financial_definitions")
        if isinstance(financial_definitions, dict) and any(
            _scalar(item) for key, item in financial_definitions.items() if key != "evidence"
        ):
            evidence = financial_definitions.get("evidence")
            if not evidence or not all(
                isinstance(item, dict)
                and _scalar(item.get("document_id"))
                and str(_scalar(item.get("sec_url", ""))).startswith("https://www.sec.gov/")
                and _scalar(item.get("locator"))
                and _scalar(item.get("excerpt"))
                for item in evidence
            ):
                gaps.append("financial_definitions")
        risk_status = value.get("risk_status")
        if isinstance(risk_status, dict):
            risk_fields = ("events_of_default", "waivers", "amendments", "reporting_violations", "liquidity_concerns", "covenant_breaches")
            if any(risk_status.get(field) for field in risk_fields):
                evidence = risk_status.get("evidence")
                if not evidence or not all(
                    isinstance(item, dict)
                    and _scalar(item.get("document_id"))
                    and str(_scalar(item.get("sec_url", ""))).startswith("https://www.sec.gov/")
                    and _scalar(item.get("locator"))
                    and _scalar(item.get("excerpt"))
                    for item in evidence
                ):
                    gaps.append("risk_status")
        for item in value.values():
            gaps.extend(_structured_evidence_gaps(item))
    elif isinstance(value, list):
        for item in value:
            gaps.extend(_structured_evidence_gaps(item))
    return gaps


def _has_structured_report(value: Any) -> bool:
    if isinstance(value, dict):
        if isinstance(value.get("debt_instruments"), list) or isinstance(value.get("covenants"), list):
            return True
        return any(_has_structured_report(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_structured_report(item) for item in value)
    return False


def _evidence_provenance_gaps(value: Any, source_urls: dict[str, str], path: str = "") -> list[str]:
    gaps: list[str] = []
    if isinstance(value, dict):
        evidence = value.get("evidence")
        if isinstance(evidence, list):
            for index, item in enumerate(evidence):
                if not isinstance(item, dict):
                    gaps.append(f"{path}.evidence[{index}]")
                    continue
                document_id = _scalar(item.get("document_id"))
                sec_url = _scalar(item.get("sec_url"))
                if not document_id or document_id not in source_urls or sec_url != source_urls[document_id]:
                    gaps.append(f"{path}.evidence[{index}]")
        for key, item in value.items():
            gaps.extend(_evidence_provenance_gaps(item, source_urls, f"{path}.{key}" if path else key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            gaps.extend(_evidence_provenance_gaps(item, source_urls, f"{path}[{index}]"))
    return gaps


def compare_cloud_output(cloud_path: Path, deterministic_report: Path, output: Path, corpus_manifest: Path | None = None, parse_audit_path: Path | None = None) -> Path:
    """Compare cloud extraction text with the deterministic report; never changes the report."""
    baseline = json.loads(deterministic_report.read_text(encoding="utf-8"))
    source_urls: dict[str, str] = {}
    if corpus_manifest:
        manifest = json.loads(corpus_manifest.read_text(encoding="utf-8"))
        source_urls = {
            d.get("document_id") or d.get("filing", {}).get("accession_number"): d.get("sec_url") or d.get("filing", {}).get("source_url")
            for d in manifest.get("documents", [])
        }
    cloud = _normalize_json_values(json.loads(cloud_path.read_text(encoding="utf-8")))
    cloud = _normalize_reducto_provenance(cloud, source_urls)
    cloud_text = _flatten(cloud).lower().replace("_", " ")
    expected = {
        "ddtl_commitment": "$17.5 billion",
        "ddtl_outstanding": "$0",
        "no_financial_covenant": "no financial covenant",
        "revolving_amendment": "first amendment",
        "events_of_default": "events of default",
        "remedies": "remedies upon event of default",
    }
    if _is_reducto_bundle(cloud):
        checks = _reducto_signal_checks(cloud)
    else:
        checks = [
            {"signal": name, "expected_from_baseline": signal, "found_in_cloud_output": signal.lower() in cloud_text}
            for name, signal in expected.items()
        ]
    non_calculable = any(c.get("status") in {"not_calculable", "partially_calculable"} for c in baseline.get("covenants", []))
    headroom_tokens = re.findall(r"estimated[_ ]headroom\s*(?::|=|\s)\s*([^,}\]]+)", cloud_text)
    unsupported_headroom = non_calculable and any(token.strip().strip('"\'') not in {"null", "none", "not calculable"} for token in headroom_tokens)
    contradictions = []
    commitment_values = _keyed_values(cloud, {"commitment", "commitment_amount"})
    if commitment_values and not any("17.5" in value for value in commitment_values):
        contradictions.append({"field": "ddtl_commitment", "values": commitment_values})
    outstanding_values = _keyed_values(cloud, {"outstanding", "outstanding_amount"})
    if outstanding_values and not any(value.strip() in {"$0", "0", "0.0", "0.0 billion", "zero"} or "$0" in value for value in outstanding_values):
        contradictions.append({"field": "ddtl_outstanding", "values": outstanding_values})
    evidence_gaps = _structured_evidence_gaps(cloud)
    evidence_provenance_gaps: list[str] = []
    if corpus_manifest:
        evidence_provenance_gaps = _evidence_provenance_gaps(cloud, source_urls)
    parse_support: dict[str, list[dict[str, Any]]] = {}
    if parse_audit_path and parse_audit_path.is_file():
        audit = json.loads(parse_audit_path.read_text(encoding="utf-8"))
        for check in audit.get("checks", []):
            evidence = check.get("evidence")
            if evidence and check.get("passed"):
                parse_support.setdefault(check["check"], []).append(evidence)
    signal_to_parse_checks = {
        "revolving_amendment": "Amendment text",
        "events_of_default": "Section 8.01",
        "remedies": "Section 8.02",
    }
    for check in checks:
        audit_check = signal_to_parse_checks.get(check["signal"])
        if audit_check:
            check["parsed_text_support"] = bool(parse_support.get(audit_check))
            check["parsed_text_evidence"] = parse_support.get(audit_check, [])
    structured_report_present = _has_structured_report(cloud)
    provider = "Reducto" if _is_reducto_bundle(cloud) else "unknown provider"
    scope_note = (
        "Reducto Extract covered the three agreement exhibits only; period balances and filing-only covenant disclosures require the parsed 10-Q/8-K corpus."
        if provider == "Reducto"
        else "Provider input scope was not identified."
    )
    result = {
        "provider": provider,
        "scope_note": scope_note,
        "parse_audit": str(parse_audit_path) if parse_audit_path else None,
        "cloud_output": str(cloud_path),
        "deterministic_report": str(deterministic_report),
        "passed": all(not c.get("applicable", True) or c["found_in_cloud_output"] for c in checks) and not unsupported_headroom,
        "checks": checks,
        "unsupported_headroom": unsupported_headroom,
        "contradictions": contradictions,
        "structured_evidence_gaps": evidence_gaps,
        "evidence_provenance_gaps": evidence_provenance_gaps,
        "structured_report_present": structured_report_present,
        "note": "This is a comparison artifact only; deterministic SEC evidence remains authoritative until disagreements are reviewed.",
    }
    result["passed"] = result["passed"] and structured_report_present and not contradictions and not evidence_gaps and not evidence_provenance_gaps
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return output
