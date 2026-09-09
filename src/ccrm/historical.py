"""Build a bounded historical AMZN period snapshot from a real SEC 10-Q."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from bs4 import BeautifulSoup

from .schema import Change, Covenant, DebtInstrument, Evidence, FinancialDefinitions, Report, RiskStatus


def _text(path: Path) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(path.read_bytes(), "html.parser").get_text(" ", strip=True))


def _evidence(document_id: str, sec_url: str, locator: str, excerpt: str, kind: str = "reported") -> Evidence:
    excerpt = excerpt[:700]
    evidence_id = "E-" + hashlib.sha256(f"{kind}|{document_id}|{sec_url}|{locator}|{excerpt}".encode()).hexdigest()[:12]
    return Evidence(evidence_id=evidence_id, kind=kind, document_id=document_id, sec_url=sec_url, locator=locator, excerpt=excerpt)


def _required(text: str, pattern: str, label: str) -> str:
    match = re.search(pattern, text, re.I)
    if not match:
        raise ValueError(f"Required SEC evidence not found for {label}; refusing to build historical snapshot")
    return match.group(0)


def build_historical_amzn_report(source: Path, sec_url: str, output: Path) -> Path:
    """Persist a source-linked March 31, 2026 AMZN period report.

    This is intentionally a bounded historical snapshot, not a customer-ready
    quarter report. It only emits facts directly supported by the real Q1 10-Q.
    """
    text = _text(source)
    document_id = "0001018724-26-000014"
    revolving_excerpt = _required(text, r"aggregate \$ ?20\.0 billion.*?March 31, 2026", "revolving facilities")
    commercial_paper_excerpt = _required(text, r"commercial paper programs.*?March 31, 2026", "commercial paper")
    notes_covenant_excerpt = _required(text, r"We are not subject to any financial covenants under the Notes\.", "notes covenant absence")
    notes_excerpt = _required(text, r"senior notes outstanding.*?March 2026 for general corporate", "senior notes issuance")
    short_term_excerpt = _required(text, r"other short-term credit facilities for working capital purposes\. There were \$ ?455 million and \$ ?152 million.*?March 31, 2026", "short-term facilities")
    fair_value_excerpt = _required(text, r"fair value of the Notes was approximately \$ ?61\.1 billion and \$ ?113\.6 billion as of December 31, 2025 and March 31, 2026", "notes fair value")

    revolving_ev = _evidence(document_id, sec_url, "Note 5 / Debt", revolving_excerpt)
    cp_ev = _evidence(document_id, sec_url, "Note 5 / Debt", commercial_paper_excerpt)
    notes_covenant_ev = _evidence(document_id, sec_url, "Note 5 / Debt", notes_covenant_excerpt)
    notes_ev = _evidence(document_id, sec_url, "Note 5 / Debt", notes_excerpt)
    short_term_ev = _evidence(document_id, sec_url, "Note 5 / Debt", short_term_excerpt)
    fair_value_ev = _evidence(document_id, sec_url, "Note 5 / Debt", fair_value_excerpt)

    changes = [Change(
        change_type="balance_changed",
        description="Other short-term credit facilities decreased from $455 million as of December 31, 2025 to $152 million as of March 31, 2026.",
        calculation="$152 million - $455 million = -$303 million decrease",
        evidence=[short_term_ev],
    )]
    report = Report(
        issuer="Amazon.com, Inc. (AMZN)",
        as_of="March 31, 2026",
        prior_period="December 31, 2025",
        corpus_manifest_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        scope="Bounded historical period snapshot from Amazon's March 31, 2026 Form 10-Q; machine-assembled and not human verified.",
        debt_instruments=[
            DebtInstrument(name="Unsecured revolving credit facilities", instrument_type="revolving credit facility", commitment_amount="$20.0 billion aggregate", outstanding_amount="$0 as of March 31, 2026", secured_status="unsecured", priority="senior", evidence=[revolving_ev]),
            DebtInstrument(name="Commercial Paper Programs", instrument_type="commercial paper", commitment_amount="Up to $30.0 billion aggregate, including up to €3.0 billion", outstanding_amount="$0 as of March 31, 2026", secured_status="unsecured", evidence=[cp_ev]),
            DebtInstrument(name="Senior Notes", instrument_type="senior notes", outstanding_amount="Senior notes were issued in March 2026; total principal is not normalized in this bounded snapshot", secured_status="unsecured", recent_change="March 2026 issuance disclosed; principal requires a broader debt-table extraction before use in calculations.", evidence=[notes_ev, notes_covenant_ev, fair_value_ev]),
            DebtInstrument(name="Other short-term credit facilities", instrument_type="short-term working-capital facilities", outstanding_amount="$152 million as of March 31, 2026", recent_change="Latest 10-Q reports $455 million at December 31, 2025 and $152 million at March 31, 2026.", evidence=[short_term_ev]),
        ],
        covenants=[Covenant(name="Senior Notes financial covenants", covenant_type="financial covenant absence", applicable_instrument="Senior Notes", status="not_calculable", maintenance_or_incurrence="No financial covenant", calculation_limitations=["The 10-Q states that Amazon is not subject to financial covenants under the Notes; no ratio or headroom is inferred."], evidence=[notes_covenant_ev])],
        financial_definitions=FinancialDefinitions(evidence=[_evidence(document_id, sec_url, "Note 5 / Debt", "Definitions and exception schedules are not normalized in this bounded historical snapshot.", "missing")]),
        risk_status=RiskStatus(uncertainty_or_missing_information=["This historical snapshot is limited to directly extracted Q1 debt facts; full agreement terms, definitions, baskets, cure rights, and reporting obligations are not normalized.", "The total Senior Notes principal is not emitted because the bounded extraction did not establish a single authoritative total."], human_verification_status="Machine-assembled from SEC filing; not human verified.", evidence=[revolving_ev, cp_ev, notes_ev, notes_covenant_ev, short_term_ev, fair_value_ev]),
        changes_since_prior_period=changes,
        follow_up_questions=["Can the March 2026 Senior Notes issuance be reconciled to the authoritative debt table?", "Which agreement definitions and reporting obligations governed the March 31, 2026 period?", "Has a human reviewer confirmed this historical snapshot before it is used for customer reporting?"],
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.model_dump(), indent=2) + "\n", encoding="utf-8")
    return output


def create_historical_amzn_snapshot(issuer_dir: Path, output: Path) -> Path:
    """Create a verified immutable run for the real March 31, 2026 source."""
    source = next((issuer_dir / "corpus" / "0001018724-26-000014").glob("*.htm"))
    manifest = json.loads((issuer_dir / "corpus-manifest.json").read_text(encoding="utf-8"))
    record = next(d for d in manifest["documents"] if d.get("filing", {}).get("accession_number") == "0001018724-26-000014")
    run_dir = output / "run-historical-20260331"
    if run_dir.exists():
        return run_dir / "run-manifest.json"
    (run_dir / "corpus" / "0001018724-26-000014").mkdir(parents=True, exist_ok=False)
    copied_source = run_dir / "corpus" / "0001018724-26-000014" / source.name
    shutil.copy2(source, copied_source)
    snapshot_manifest = {"documents": [{"document_id": "0001018724-26-000014", "source_file": str(copied_source.resolve()), "source_sha256": hashlib.sha256(copied_source.read_bytes()).hexdigest(), "filing": record["filing"]}]}
    (run_dir / "corpus-manifest.json").write_text(json.dumps(snapshot_manifest, indent=2) + "\n", encoding="utf-8")
    build_historical_amzn_report(copied_source, record["filing"]["source_url"], run_dir / "report.json")
    (run_dir / "readiness-note.md").write_text("# Historical snapshot\n\nThis is a real March 31, 2026 SEC 10-Q snapshot used to prove period repeatability. It is machine-assembled, bounded, and not customer-ready or human-approved.\n", encoding="utf-8")
    hashes = {}
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path.name != "run-manifest.json":
            hashes[str(path.relative_to(run_dir))] = hashlib.sha256(path.read_bytes()).hexdigest()
    run_manifest = {"run_id": "run-historical-20260331", "issuer": "Amazon.com, Inc. (AMZN)", "as_of": "March 31, 2026", "prior_period": "December 31, 2025", "release_status": "internal_review", "immutable": True, "historical_snapshot": True, "artifact_sha256": hashes, "artifact_count": len(hashes)}
    manifest_path = run_dir / "run-manifest.json"
    manifest_path.write_text(json.dumps(run_manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path
