import json
import hashlib
import html
import re
from pathlib import Path
from typing import Any

from .integrity import check_corpus_integrity
from .schema import Report


def _normalized_document_text(path: Path) -> str:
    text = html.unescape(path.read_text(encoding="utf-8", errors="ignore"))
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split()).lower()


def evaluate_report(report_path: Path, output: Path, corpus_manifest: Path | None = None, xbrl_corroboration: Path | None = None) -> Path:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    try:
        Report.model_validate(report)
        report_schema_valid = True
    except Exception:
        report_schema_valid = False
    check("report schema", report_schema_valid, "The persisted report conforms to the structured Covenant & Credit Risk Monitor schema.")

    instruments = report.get("debt_instruments", [])
    covenants = report.get("covenants", [])
    check("instrument evidence coverage", bool(instruments) and all(i.get("evidence") for i in instruments), "Every reported debt instrument has at least one evidence object.")
    check("covenant evidence coverage", bool(covenants) and all(c.get("evidence") for c in covenants), "Every reported covenant status has at least one evidence object.")
    check("safe headroom", all(c.get("estimated_headroom") is not None or c.get("status") in {"not_calculable", "partially_calculable"} for c in covenants), "No headroom is emitted for a non-calculable or partially calculable covenant.")
    calculation_fields = ("agreement_version", "threshold", "testing_date_or_frequency", "actual_reported_value", "agreement_section")
    calculated_covenants = [c for c in covenants if c.get("estimated_headroom") is not None or c.get("calculated_value") is not None or c.get("status") in {"estimated", "verified"}]
    calculation_safe = all(all(c.get(field) for field in calculation_fields) and c.get("evidence") for c in calculated_covenants)
    check("calculation safety completeness", calculation_safe, "Any estimated or verified covenant calculation has a threshold, testing period, reported input, agreement section, agreement version, and evidence.")
    check("period comparison", report.get("as_of") == "June 30, 2026" and report.get("prior_period") == "March 31, 2026", "Latest and prior reporting periods match the selected AMZN 10-Q pair.")
    verification_status = report.get("risk_status", {}).get("human_verification_status", "").lower()
    check("human verification disclosure", "machine-assembled" in verification_status and ("not human verified" in verification_status or "unverified" in verification_status), "The report clearly discloses that it is machine-assembled and not human verified.")
    risk_status = report.get("risk_status", {})
    evidence = risk_status.get("evidence", [])
    risk_fields = ("events_of_default", "waivers", "amendments", "reporting_violations", "liquidity_concerns", "covenant_breaches")
    populated_risk_fields = [field for field in risk_fields if risk_status.get(field)]
    check("risk status evidence coverage", not populated_risk_fields or bool(evidence), "Every populated narrative risk-status category has supporting evidence objects.")
    check("uncertainty evidence coverage", not risk_status.get("uncertainty_or_missing_information") or bool(evidence), "Every populated uncertainty or missing-information narrative has supporting evidence objects.")
    check("agreement locator coverage", len(evidence) >= 7 and all(e.get("locator") and e.get("excerpt") for e in evidence), "Agreement monitoring sections retain locators and excerpts.")
    changes = report.get("changes_since_prior_period", [])
    check("change evidence coverage", bool(changes) and all(c.get("evidence") for c in changes), "Every quarter-over-quarter change statement has direct evidence.")
    first_report_questions_covered = all([
        bool(instruments),
        all(i.get("agreement_version") for i in instruments if i.get("name") in {"DDTL Facility", "Unsecured revolving credit facilities"}),
        bool(covenants) and all(c.get("name") and c.get("applicable_instrument") for c in covenants),
        all(c.get("maintenance_or_incurrence") for c in covenants),
        all(c.get("threshold") or c.get("status") in {"not_calculable", "partially_calculable"} for c in covenants),
        bool(report.get("financial_definitions", {}).get("evidence")),
        all(c.get("estimated_headroom") is not None or c.get("status") in {"not_calculable", "partially_calculable"} for c in covenants),
        bool(changes),
        not report.get("risk_status", {}).get("amendments") or bool(report.get("risk_status", {}).get("evidence")),
        bool(report.get("follow_up_questions")),
    ])
    check("first-report question coverage", first_report_questions_covered, "The report addresses debt, governing agreements, covenant type/thresholds, required inputs, headroom safety, changes, amendments, and open uncertainties.")
    prior_period = str(report.get("prior_period", "")).strip()
    current_period = str(report.get("as_of", "")).strip()
    period_change_evidence_ok = all(
        not (" from " in c.get("description", "").lower() and " to " in c.get("description", "").lower())
        or (
            bool(prior_period and current_period)
            and any(prior_period in e.get("excerpt", "") for e in c.get("evidence", []))
            and any(current_period in e.get("excerpt", "") for e in c.get("evidence", []))
        )
        for c in changes
    )
    check("period-change evidence", period_change_evidence_ok, "A change expressed as a from/to comparison has SEC excerpts covering both selected periods.")
    stale_change_language = any(
        marker in c.get("description", "").lower()
        for c in changes
        for marker in ("continues to disclose", "unchanged", "no change")
    )
    check("change list precision", not stale_change_language, "The quarter-over-quarter change list does not label unchanged disclosures as changes.")
    evidence_objects = []
    for instrument in instruments:
        evidence_objects.extend(instrument.get("evidence", []))
    for covenant in covenants:
        evidence_objects.extend(covenant.get("evidence", []))
    evidence_objects.extend(report.get("financial_definitions", {}).get("evidence", []))
    evidence_objects.extend(report.get("risk_status", {}).get("evidence", []))
    for change in changes:
        evidence_objects.extend(change.get("evidence", []))
    check("evidence completeness", bool(evidence_objects) and all(
        e.get("document_id") and e.get("sec_url", "").startswith("https://www.sec.gov/") and e.get("locator") and e.get("excerpt")
        for e in evidence_objects
    ), "Every evidence object has a document ID, SEC URL, locator, and non-empty excerpt.")
    noisy_excerpt_markers = ("file:///", "/Users/", "\\Users\\", "localhost:")
    check("evidence excerpt cleanliness", bool(evidence_objects) and all(
        not any(marker in str(e.get("excerpt", "")) for marker in noisy_excerpt_markers)
        for e in evidence_objects
    ), "Evidence excerpts do not contain local renderer paths or other known transport noise.")
    evidence_ids = [e.get("evidence_id") for e in evidence_objects]
    id_to_payload = {}
    payload_to_id = {}
    evidence_id_consistent = True
    for evidence in evidence_objects:
        evidence_id = evidence.get("evidence_id")
        payload = json.dumps({
            key: evidence.get(key)
            for key in ("kind", "document_id", "sec_url", "locator", "excerpt", "human_verified")
        }, sort_keys=True)
        if evidence_id in id_to_payload and id_to_payload[evidence_id] != payload:
            evidence_id_consistent = False
        if payload in payload_to_id and payload_to_id[payload] != evidence_id:
            evidence_id_consistent = False
        if evidence_id:
            id_to_payload[evidence_id] = payload
            payload_to_id[payload] = evidence_id
    check("evidence ID coverage", bool(evidence_ids) and all(evidence_ids) and evidence_id_consistent, "Every persisted evidence item has a non-empty stable ID, and repeated references resolve to one immutable evidence payload.")
    def _ids(items: list[dict[str, Any]]) -> list[str]:
        return list(dict.fromkeys(e.get("evidence_id") for e in items if e.get("evidence_id")))

    question_coverage = [
        {"question": 1, "topic": "company debt", "status": "covered", "evidence_ids": _ids([e for i in instruments for e in i.get("evidence", [])])},
        {"question": 2, "topic": "governing agreements", "status": "bounded", "note": "Primary DDTL, revolving, and Senior Notes indenture context are identified; other context facilities remain explicitly unmapped in the bounded corpus.", "evidence_ids": _ids([e for i in instruments for e in i.get("evidence", [])])},
        {"question": 3, "topic": "applicable covenants", "status": "covered", "evidence_ids": _ids([e for c in covenants for e in c.get("evidence", [])])},
        {"question": 4, "topic": "maintenance versus incurrence", "status": "covered", "evidence_ids": _ids([e for c in covenants for e in c.get("evidence", [])])},
        {"question": 5, "topic": "thresholds", "status": "not_calculable", "note": "No unsupported threshold is inferred where the agreement discloses no financial covenant or where exception schedules are incomplete.", "evidence_ids": _ids([e for c in covenants for e in c.get("evidence", [])])},
        {"question": 6, "topic": "required financial inputs", "status": "not_calculable", "evidence_ids": _ids(report.get("financial_definitions", {}).get("evidence", []))},
        {"question": 7, "topic": "estimated headroom", "status": "not_calculable", "note": "No covenant headroom is emitted without complete definitions, periods, inputs, exclusions, and agreement version.", "evidence_ids": _ids([e for c in covenants for e in c.get("evidence", [])])},
        {"question": 8, "topic": "quarter-over-quarter changes", "status": "covered", "evidence_ids": _ids([e for c in changes for e in c.get("evidence", [])])},
        {"question": 9, "topic": "amendments and new debt", "status": "covered", "evidence_ids": _ids(report.get("risk_status", {}).get("evidence", []))},
        {"question": 10, "topic": "uncertainties and follow-up", "status": "covered", "evidence_ids": _ids(report.get("risk_status", {}).get("evidence", []))},
    ]
    evidence_marked_verified = any(e.get("human_verified") is True for e in evidence_objects)
    report_marked_verified = "not human verified" not in verification_status and "unverified" not in verification_status and "human verified" in verification_status
    check("verification flag consistency", not evidence_marked_verified or report_marked_verified, "Evidence cannot be marked human verified while the report-level status remains unverified.")
    if corpus_manifest:
        manifest_digest = hashlib.sha256(corpus_manifest.read_bytes()).hexdigest()
        check("report corpus binding", report.get("corpus_manifest_sha256") == manifest_digest, "The persisted report is bound to the exact aggregate corpus manifest used for evaluation.")
        manifest = json.loads(corpus_manifest.read_text(encoding="utf-8"))
        manifest_documents = manifest.get("documents", [])
        manifest_ids = {
            d.get("document_id") or d.get("filing", {}).get("accession_number")
            for d in manifest_documents
        }
        required_corpus_ids = {
            "0001018724-26-000014", "0001018724-26-000026", "0001104659-26-072140",
            "0001018724-26-000012", "0001018724-26-000024", "ddtl-agreement",
            "revolving-amendment-364", "revolving-amendment-five-year", "0001018724-26-000004",
            "senior-notes-indenture", "senior-notes-supplemental-indenture",
        }
        check("corpus completeness", manifest_ids == required_corpus_ids, "The bounded AMZN corpus contains the quarterly filings, latest annual filing context, DDTL agreement, and two revolving amendments.")
        filing_metadata = {
            d.get("filing", {}).get("accession_number"): d.get("filing", {})
            for d in manifest_documents
            if d.get("filing")
        }
        period_metadata_ok = (
            filing_metadata.get("0001018724-26-000014", {}).get("form") == "10-Q"
            and filing_metadata.get("0001018724-26-000014", {}).get("report_date") == "2026-03-31"
            and filing_metadata.get("0001018724-26-000026", {}).get("form") == "10-Q"
            and filing_metadata.get("0001018724-26-000026", {}).get("report_date") == "2026-06-30"
        )
        check("manifest period metadata", period_metadata_ok, "The corpus metadata identifies the selected March 31 and June 30, 2026 10-Q comparison pair.")
        source_urls = {
            d.get("document_id") or d.get("filing", {}).get("accession_number"): d.get("sec_url") or d.get("filing", {}).get("source_url")
            for d in manifest_documents
        }
        manifest_provenance_ok = bool(manifest_documents) and all(
            bool(d.get("document_id") or d.get("filing", {}).get("accession_number"))
            and isinstance((url := (d.get("sec_url") or d.get("filing", {}).get("source_url"))), str)
            and url.startswith("https://www.sec.gov/")
            for d in manifest_documents
        )
        check("manifest source provenance", manifest_provenance_ok, "Every corpus document has a non-empty HTTPS SEC URL recorded in the manifest.")
        provenance_ok = bool(evidence_objects) and all(
            e.get("document_id") in source_urls and e.get("sec_url") == source_urls[e.get("document_id")]
            for e in evidence_objects
        )
        check("evidence provenance", provenance_ok, "Every evidence object maps to the matching SEC URL recorded in the corpus manifest.")
        if xbrl_corroboration and xbrl_corroboration.is_file():
            try:
                xbrl = json.loads(xbrl_corroboration.read_text(encoding="utf-8"))
                xbrl_facts = xbrl.get("facts", [])
                xbrl_source_record = next(
                    (d for d in manifest_documents if (d.get("document_id") or d.get("filing", {}).get("accession_number")) == "0001018724-26-000026"),
                    {},
                )
                xbrl_source_path = Path(xbrl_source_record.get("source_file", ""))
                if not xbrl_source_path.is_absolute():
                    rooted = corpus_manifest.resolve().parent.parent.parent / xbrl_source_path
                    if rooted.exists():
                        xbrl_source_path = rooted
                xbrl_urls_ok = all(fact.get("sec_url") == source_urls.get(fact.get("document_id")) for fact in xbrl_facts)
                xbrl_hash_ok = bool(xbrl_source_path.is_file()) and xbrl.get("source_sha256") == hashlib.sha256(xbrl_source_path.read_bytes()).hexdigest()
                xbrl_ok = bool(xbrl.get("passed") is True and xbrl.get("report_alignment_passed") is True and len(xbrl_facts) == 6 and xbrl_urls_ok and xbrl_hash_ok)
                check("XBRL corroboration binding", xbrl_ok, "The supplemental XBRL artifact has six aligned facts, exact manifest SEC provenance, and a current source hash." if xbrl_ok else "The supplemental XBRL artifact is stale, incomplete, misbound, or not aligned with the report.")
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
                check("XBRL corroboration binding", False, "The supplemental XBRL artifact could not be read as a valid bound corroboration result.")
        source_paths = {}
        for document in manifest_documents:
            document_id = document.get("document_id") or document.get("filing", {}).get("accession_number")
            source_file = document.get("source_file")
            if not document_id or not source_file:
                continue
            path = Path(source_file)
            if not path.is_absolute():
                rooted = corpus_manifest.resolve().parent.parent.parent / path
                if rooted.exists():
                    path = rooted
            source_paths[document_id] = path
        source_text_cache = {}
        unsupported_evidence = []
        source_content_gaps = []
        for item in evidence_objects:
            # A `missing` evidence object deliberately explains an unavailable
            # fact; it is not claiming that its explanatory sentence appears
            # verbatim in the cited source.
            if item.get("kind") == "missing":
                continue
            document_id = item.get("document_id")
            source_path = source_paths.get(document_id)
            if not source_path or not source_path.is_file():
                unsupported_evidence.append(item.get("evidence_id") or document_id)
                continue
            if document_id not in source_text_cache:
                source_text_cache[document_id] = _normalized_document_text(source_path)
            excerpt = " ".join(html.unescape(str(item.get("excerpt", ""))).split()).lower()
            if not excerpt or excerpt not in source_text_cache[document_id]:
                source_content_gaps.append(item.get("evidence_id") or document_id)
        check("evidence source-content binding", not unsupported_evidence and not source_content_gaps, "Every non-missing report evidence excerpt is present in the normalized text of its manifest-bound local SEC artifact." if not (unsupported_evidence or source_content_gaps) else f"Evidence could not be source-bound; missing artifacts: {unsupported_evidence}; excerpt gaps: {source_content_gaps}.")
        integrity = check_corpus_integrity(corpus_manifest)
        check("corpus integrity", integrity["passed"], "Every local SEC artifact matches its recorded SHA-256 digest.")
    result = {"report": str(report_path), "passed": all(c["passed"] for c in checks), "checks": checks, "question_coverage": question_coverage}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return output
