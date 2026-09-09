import json
import hashlib
import re
from decimal import Decimal
from pathlib import Path

from bs4 import BeautifulSoup

from .schema import Change, Covenant, DebtInstrument, Evidence, FinancialDefinitions, Report, RiskStatus
from .compare import classify_amzn_changes, extract_amzn_snapshot


def _text(path: Path) -> str:
    return BeautifulSoup(path.read_bytes(), "html.parser").get_text(" ", strip=True)


def _normalized_text(path: Path) -> str:
    return re.sub(r"\s+", " ", _text(path)).strip()


def _agreement_sections(path: Path, codes: set[str]) -> dict[str, str]:
    """Extract section text from the agreement HTML while retaining section locators."""
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    paragraphs = soup.find_all(["p", "td"])
    found: dict[str, list[str]] = {}
    current: str | None = None
    for node in paragraphs:
        value = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        match = re.match(r"^(\d+\.\d+)\s+", value)
        if match:
            code = match.group(1)
            if code in codes:
                current = code
                found[current] = [value]
            else:
                current = None
        elif current and value:
            found[current].append(value)
        if current and len(" ".join(found[current])) > 2600:
            current = None
    return {code: " ".join(values)[:2600] for code, values in found.items()}


def _required_agreement_sections(sections: dict[str, str], required: set[str]) -> dict[str, str]:
    missing = sorted(required - set(sections))
    if missing:
        raise ValueError(f"Required agreement sections missing; refusing to build an incomplete report: {', '.join(missing)}")
    return sections


def _required_filing_metadata(manifest: dict, accession: str, form: str, report_date: str) -> dict:
    record = next((d for d in manifest.get("documents", []) if d.get("filing", {}).get("accession_number") == accession), None)
    filing = record.get("filing", {}) if record else {}
    if not record or filing.get("form") != form or filing.get("report_date") != report_date:
        raise ValueError(f"Required filing metadata missing or mismatched for {accession}; refusing to build a period-inaccurate report")
    return record


def _ev(document_id: str, url: str, locator: str, excerpt: str, kind: str = "reported") -> Evidence:
    if not url.startswith("https://www.sec.gov/"):
        raise ValueError(f"Evidence URL must be an HTTPS SEC URL: {url}")
    excerpt = excerpt[:700]
    evidence_id = "E-" + hashlib.sha256(f"{kind}|{document_id}|{url}|{locator}|{excerpt}".encode()).hexdigest()[:12]
    return Evidence(evidence_id=evidence_id, kind=kind, document_id=document_id, sec_url=url, locator=locator, excerpt=excerpt)


def _required_excerpt(match: re.Match[str] | None, label: str) -> str:
    if match is None:
        raise ValueError(f"Required SEC evidence not found for {label}; refusing to fabricate a reported fact")
    return match.group(0)


def _markdown_evidence_links(evidence: list[Evidence]) -> str:
    return " ".join(f"[{item.kind} / {item.locator}]({item.sec_url})" for item in evidence)


def _millions(value: str) -> Decimal:
    match = re.fullmatch(r"\$\s*([\d.]+)\s+million", value.strip(), re.I)
    if match is None:
        raise ValueError(f"Expected a dollar amount expressed in millions, got: {value}")
    return Decimal(match.group(1))


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def build_report(corpus: Path, output: Path) -> Path:
    manifest_path = corpus.parent / "corpus-manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    _required_filing_metadata(manifest, "0001018724-26-000014", "10-Q", "2026-03-31")
    _required_filing_metadata(manifest, "0001018724-26-000026", "10-Q", "2026-06-30")
    by_id = {Path(d.get("source_file", "")).parent.name: d for d in manifest["documents"] if d.get("source_file")}
    agreement = corpus / "ddtl-agreement" / "agreement.htm"
    eight_k = corpus / "0001104659-26-072140" / Path(by_id["0001104659-26-072140"]["source_file"]).name
    q1 = corpus / "0001018724-26-000014" / Path(by_id["0001018724-26-000014"]["source_file"]).name
    q2 = corpus / "0001018724-26-000026" / Path(by_id["0001018724-26-000026"]["source_file"]).name
    e8 = _normalized_text(eight_k)
    q1t, q2t = _normalized_text(q1), _normalized_text(q2)
    eight_excerpt = re.search(r"The DDTL Credit Agreement provides.*?does not contain financial covenants\.", e8, re.I)
    excerpt = _required_excerpt(eight_excerpt, "DDTL financial-covenant absence")
    agreement_record = next(d for d in manifest["documents"] if d.get("document_id") == "ddtl-agreement")
    agreement_url = agreement_record["sec_url"]
    eight_url = by_id["0001104659-26-072140"]["filing"]["source_url"]
    q2_url = by_id["0001018724-26-000026"]["filing"]["source_url"]
    q1_url = by_id["0001018724-26-000014"]["filing"]["source_url"]
    annual_record = next(d for d in manifest["documents"] if d.get("filing", {}).get("accession_number") == "0001018724-26-000004")
    annual_path = Path(annual_record["source_file"])
    annual_text = _normalized_text(annual_path)
    annual_url = annual_record["filing"]["source_url"]
    indenture_excerpt = _required_excerpt(re.search(r"4\.1 Indenture, dated as of November 29, 2012.*?Current Report on Form 8-K, filed November 29, 2012\)", annual_text, re.I), "senior-notes indenture reference")
    supplemental_excerpt = _required_excerpt(re.search(r"4\.2 Supplemental Indenture, dated as of April 13, 2022.*?successor trustee.*?containing Form of 2\.730% Note", annual_text, re.I), "senior-notes supplemental indenture reference")
    notes_indenture = _ev("0001018724-26-000004", annual_url, "Exhibit Index, Items 4.1–4.2", indenture_excerpt)
    notes_supplemental = _ev("0001018724-26-000004", annual_url, "Exhibit Index, Items 4.1–4.2", supplemental_excerpt)
    no_cov = _ev("0001104659-26-072140", eight_url, "Item 1.01 / Item 2.03", excerpt)
    facility_excerpt = re.search(r"On June 8, 2026, Amazon\.com, Inc\..*?Borrowings under the DDTL Facility will be used for general corporate purposes\.", e8, re.I)
    facility_ev = _ev("0001104659-26-072140", eight_url, "Item 1.01 / Item 2.03", _required_excerpt(facility_excerpt, "DDTL facility creation"))
    expiry_excerpt = re.search(r"The DDTL Credit Agreement provides.*?unless fully borrowed prior to such date\.", e8, re.I)
    expiry_ev = _ev("0001104659-26-072140", eight_url, "Item 1.01 / Item 2.03 — commitment expiry", _required_excerpt(expiry_excerpt, "DDTL commitment expiry"))
    no_draw_excerpt = re.search(r"There were no borrowings outstanding under the Term Loan as of June 30, 2026\.", q2t, re.I)
    no_draw = _ev("0001018724-26-000026", q2_url, "Note 7, Debt", _required_excerpt(no_draw_excerpt, "DDTL outstanding balance"))
    previous_snapshot = extract_amzn_snapshot(q1t, "March 31, 2026")
    current_snapshot = extract_amzn_snapshot(q2t, "June 30, 2026")
    detected_changes = classify_amzn_changes(previous_snapshot, current_snapshot)
    sections = _required_agreement_sections(_agreement_sections(agreement, {"6.01", "6.02", "6.03", "7.01", "7.02", "8.01", "8.02"}), {"6.01", "6.02", "6.03", "7.01", "7.02", "8.01", "8.02"})
    nonpayment_excerpt = _required_excerpt(re.search(r"\(a\) Non-Payment.*?any other amount payable hereunder or under any other Loan Document", sections["8.01"], re.I), "event-of-default non-payment cure language")
    agreement_evidence = [
        _ev("ddtl-agreement", agreement_url, f"Section {code}", text, "agreement_defined")
        for code, text in sections.items()
    ]
    revolving_match = re.search(r"We have an aggregate \$ ?20\.0 billion.*?There were no borrowings outstanding under the Credit Agreement and the Short-Term Credit Agreement as of December 31, 2025 and June 30, 2026\.", q2t, re.I)
    commercial_paper_match = re.search(r"We have U\.S\. Dollar and Euro commercial paper programs.*?There were no borrowings outstanding under the Commercial Paper Programs as of December 31, 2025 and June 30, 2026\.", q2t, re.I)
    notes_match = re.search(r"We are not subject to any financial covenants under the Notes\.", q2t, re.I)
    notes_outstanding_match = re.search(r"As of June 30, 2026, we had \$ ?132\.1 billion of unsecured senior notes outstanding", q2t, re.I)
    prior_short_term_match = re.search(r"other short-term credit facilities for working capital purposes\. There were \$ ?455 million and \$ ?152 million of borrowings outstanding under these facilities as of December 31, 2025 and March 31, 2026", q1t, re.I)
    short_term_match = re.search(r"other short-term credit facilities for working capital purposes\. There were \$ ?455 million and \$ ?325 million of borrowings outstanding under these facilities as of December 31, 2025 and June 30, 2026", q2t, re.I)
    notes_fair_value_match = re.search(r"The estimated fair value of the Notes was approximately \$ ?61\.1 billion and \$ ?123\.8 billion as of December 31, 2025 and June 30, 2026", q2t, re.I)
    revolving_ev = _ev("0001018724-26-000026", q2_url, "Note 7, Debt", _required_excerpt(revolving_match, "revolving credit facilities"))
    commercial_paper_ev = _ev("0001018724-26-000026", q2_url, "Note 7, Debt", _required_excerpt(commercial_paper_match, "commercial paper programs"))
    notes_ev = _ev("0001018724-26-000026", q2_url, "Note 7, Debt", _required_excerpt(notes_match, "Notes covenant status"))
    notes_outstanding_ev = _ev("0001018724-26-000026", q2_url, "Note 7, Debt", _required_excerpt(notes_outstanding_match, "Senior Notes outstanding balance"))
    prior_short_term_ev = _ev("0001018724-26-000014", q1_url, "Note 7, Debt", _required_excerpt(prior_short_term_match, "prior-quarter other short-term borrowings"))
    short_term_ev = _ev("0001018724-26-000026", q2_url, "Note 7, Debt", _required_excerpt(short_term_match, "other short-term borrowings"))
    notes_fair_value_ev = _ev("0001018724-26-000026", q2_url, "Note 7, Debt", _required_excerpt(notes_fair_value_match, "Notes fair value"))
    amendment_364 = next(d for d in manifest["documents"] if d.get("document_id") == "revolving-amendment-364")
    amendment_five_year = next(d for d in manifest["documents"] if d.get("document_id") == "revolving-amendment-five-year")
    amendment_excerpt = _required_excerpt(re.search(r"10\.2 Amended and Restated 364-Day Revolving Credit Agreement, dated as of October 29, 2025, as amended by the First Amendment thereto, dated as of June 8, 2026.*?10\.3 Five-Year Revolving Credit Agreement, dated as of November 1, 2023, as amended by the First Amendment thereto, dated as of June 8, 2026, among Amazon\.com, Inc\., Citibank N\.A\., as administrative agent, and the lenders party thereto\.", q2t, re.I), "10-Q revolving amendment exhibit descriptions")
    amendment_364_text = _normalized_text(corpus / "revolving-amendment-364" / "agreement.htm")
    amendment_five_year_text = _normalized_text(corpus / "revolving-amendment-five-year" / "agreement.htm")
    amendment_364_title = _required_excerpt(re.search(r"FIRST AMENDMENT dated as of June 8, 2026.*?as Administrative Agent\.", amendment_364_text, re.I), "364-day revolving amendment title")
    amendment_five_year_title = _required_excerpt(re.search(r"FIRST AMENDMENT dated as of June 8, 2026.*?as Administrative Agent\.", amendment_five_year_text, re.I), "five-year revolving amendment title")
    amendment_evidence = [
        _ev("0001018724-26-000026", q2_url, "Exhibits 10.2 and 10.3", amendment_excerpt),
        _ev(amendment_364["document_id"], amendment_364["sec_url"], "First Amendment", amendment_364_title, "agreement_defined"),
        _ev(amendment_five_year["document_id"], amendment_five_year["sec_url"], "First Amendment", amendment_five_year_title, "agreement_defined"),
    ]
    ddtl = DebtInstrument(
        name="DDTL Facility",
        instrument_type="senior unsecured delayed-draw term loan facility",
        agreement_version="June 8, 2026 DDTL Credit Agreement, filed as Exhibit 10.1 to the June 10, 2026 Form 8-K",
        commitment_amount="$17.5 billion",
        maturity_date="Three-year anniversary of each borrowing",
        interest_rate_or_spread="Alternate Base Rate + 0%; Term SOFR + 0.625% to 0.875% based on credit ratings",
        rate_type="floating",
        secured_status="unsecured",
        priority="senior",
        outstanding_amount="$0 as of June 30, 2026",
        recent_change="Entered into June 8, 2026; commitments expire September 30, 2026 unless fully borrowed earlier. No borrowings were outstanding as of June 30, 2026.",
        evidence=[facility_ev, expiry_ev, no_cov, no_draw],
    )
    covenant = Covenant(
        name="Financial covenants",
        covenant_type="financial covenant absence",
        applicable_instrument="DDTL Facility",
        agreement_version="June 8, 2026 DDTL Credit Agreement, filed as Exhibit 10.1 to the June 10, 2026 Form 8-K",
        status="not_calculable",
        maintenance_or_incurrence="No financial covenant",
        calculation_limitations=["The filed 8-K states the facility contains customary covenants but does not contain financial covenants; no leverage or coverage threshold is available to test."],
        evidence=[no_cov, no_draw],
    )
    agreement_evidence_by_locator = {item.locator: item for item in agreement_evidence}
    liens_exception_match = re.search(r"Liens existing on the date hereof.*?listed on Schedule 7\.01", sections["7.01"], re.I)
    fundamental_exception_match = re.search(r"Merge or consolidate.*?documentation reasonably satisfactory to the Administrative Agent", sections["7.02"], re.I)
    negative_covenants = [
        Covenant(
            name="Liens",
            covenant_type="negative covenant",
            applicable_instrument="DDTL Facility",
            agreement_version="June 8, 2026 DDTL Credit Agreement, filed as Exhibit 10.1 to the June 10, 2026 Form 8-K",
            status="not_calculable",
            maintenance_or_incurrence="Negative / incurrence covenant",
            agreement_section="Section 7.01",
            exceptions=[liens_exception_match.group(0)] if liens_exception_match else [],
            calculation_limitations=["The agreement contains additional exceptions and baskets; no complete exception schedule or capacity calculation has been normalized."],
            evidence=[agreement_evidence_by_locator["Section 7.01"]],
        ),
        Covenant(
            name="Fundamental Changes",
            covenant_type="negative covenant",
            applicable_instrument="DDTL Facility",
            agreement_version="June 8, 2026 DDTL Credit Agreement, filed as Exhibit 10.1 to the June 10, 2026 Form 8-K",
            status="not_calculable",
            maintenance_or_incurrence="Negative / incurrence covenant",
            agreement_section="Section 7.02",
            exceptions=[fundamental_exception_match.group(0)] if fundamental_exception_match else [],
            calculation_limitations=["The agreement contains additional conditions and exceptions; no complete transaction-permission analysis has been normalized."],
            evidence=[agreement_evidence_by_locator["Section 7.02"]],
        ),
    ]
    definitions = FinancialDefinitions(
        evidence=[_ev("ddtl-agreement", agreement_url, "Agreement; definitions not summarized in public 8-K", "The 8-K qualifies its description in its entirety by the terms of the agreement.", "missing")]
    )
    changes = []
    if "new_ddtl_facility" in detected_changes:
        changes.append(Change(change_type="facility_added", description="New $17.5 billion DDTL Facility entered into June 8, 2026 and disclosed in the June 10, 2026 8-K.", evidence=[facility_ev]))
    if "ddtl_outstanding_balance_reported" in detected_changes:
        changes.append(Change(change_type="balance_reported", description="The latest 10-Q reports no borrowings outstanding under the DDTL Facility as of June 30, 2026.", evidence=[no_draw]))
    if "short_term_outstanding_changed" in detected_changes:
        prior_amount = _millions(previous_snapshot.short_term_outstanding or "")
        current_amount = _millions(current_snapshot.short_term_outstanding or "")
        delta = current_amount - prior_amount
        changes.append(Change(change_type="balance_changed", description="Borrowings under other short-term credit facilities increased from $152 million as of March 31, 2026 to $325 million as of June 30, 2026.", calculation=f"${_decimal_text(current_amount)} million - ${_decimal_text(prior_amount)} million = ${_decimal_text(delta)} million increase", evidence=[prior_short_term_ev, short_term_ev]))
    if "amendment_reported" in detected_changes:
        changes.append(Change(change_type="amendment", description="The latest 10-Q identifies First Amendments dated June 8, 2026 to both revolving credit agreements; the amendment terms require human review.", evidence=amendment_evidence))
    risk = RiskStatus(
        events_of_default=[f"Section 8.01 provides that principal non-payment is due when required, while interest, fees, and other amounts have a five-Business-Day cure period. Other triggers and remedies require agreement review. Source: {nonpayment_excerpt[:600]}"],
        amendments=["First Amendments dated June 8, 2026 identified for the Amended and Restated 364-Day Revolving Credit Agreement and the Five-Year Revolving Credit Agreement; terms not yet human verified."], waivers=[], reporting_violations=[], liquidity_concerns=[], covenant_breaches=[],
        uncertainty_or_missing_information=["The DDTL Facility's outstanding balance is reported as zero at June 30, 2026; subsequent draw activity before the September 30 commitment expiry is outside this quarter-end snapshot.", "Section-level agreement excerpts are machine-segmented; full definitions, baskets, cure rights, and reporting obligations have not been human verified in this prototype report."],
        human_verification_status="Machine-assembled from SEC filings; not human verified.",
        evidence=agreement_evidence + amendment_evidence,
    )
    context_instruments = [
        DebtInstrument(name="Unsecured revolving credit facilities", instrument_type="revolving credit facility", agreement_version="Amended and Restated 364-Day Revolving Credit Agreement dated October 29, 2025, as amended June 8, 2026; Five-Year Revolving Credit Agreement dated November 1, 2023, as amended June 8, 2026", commitment_amount="$20.0 billion aggregate ($15.0 billion Credit Agreement plus $5.0 billion 364-day facility)", maturity_date="November 2028 for the Credit Agreement; October 2026 for the Short-Term Credit Agreement", interest_rate_or_spread="Benchmark/SOFR + 0.45%; 0.03% commitment fee on undrawn portion", rate_type="floating", secured_status="unsecured", outstanding_amount="$0 as of June 30, 2026", recent_change="First Amendments dated June 8, 2026 identified in the latest 10-Q; amendment terms require human review.", evidence=[revolving_ev, *amendment_evidence]),
        DebtInstrument(name="Commercial Paper Programs", instrument_type="commercial paper", commitment_amount="Up to $30.0 billion aggregate, including up to €3.0 billion", maturity_date="Individual maturities not exceeding 397 days", secured_status="unsecured", outstanding_amount="$0 as of June 30, 2026", recent_change="Context instrument disclosed in the latest 10-Q.", evidence=[commercial_paper_ev]),
        DebtInstrument(name="Senior Notes", instrument_type="senior notes", agreement_version="2012 Indenture and 2022 Supplemental Indenture, incorporated by reference in the latest 10-K", secured_status="unsecured", outstanding_amount="$132.1 billion as of June 30, 2026; fair value approximately $123.8 billion", recent_change="Latest 10-Q states the Notes have no financial covenants.", evidence=[notes_outstanding_ev, notes_ev, notes_fair_value_ev, notes_indenture, notes_supplemental]),
        DebtInstrument(name="Other short-term credit facilities", instrument_type="short-term working-capital facilities", outstanding_amount="$325 million as of June 30, 2026", secured_status="not specified in selected excerpt", recent_change="Latest 10-Q reports $455 million at December 31, 2025 and $325 million at June 30, 2026.", evidence=[short_term_ev]),
    ]
    report = Report(
        issuer="Amazon.com, Inc. (AMZN)", as_of="June 30, 2026", prior_period="March 31, 2026", corpus_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        scope="SEC-only prototype: DDTL Facility as the primary monitored family, with other debt families shown as latest-quarter context.",
        debt_instruments=[ddtl] + context_instruments, covenants=[covenant] + negative_covenants, financial_definitions=definitions, risk_status=risk,
        changes_since_prior_period=changes,
        follow_up_questions=["Did any borrowing occur after June 30, 2026 and before the September 30, 2026 commitment expiry?", "Which exceptions in Sections 7.01 and 7.02 are material to the company's debt capacity?", "Which exact reporting certificate and notice periods apply under Sections 6.01–6.03?", "Has a human reviewer confirmed the agreement version and all amendments?"],
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md = ["# Covenant & Credit Risk Monitor — AMZN", "", "## Executive conclusion", "", "The selected DDTL Facility is a $17.5 billion senior unsecured delayed-draw term loan facility. The filed 8-K says it has no financial covenants, so covenant headroom is **not calculable**, not zero and not verified.", "", f"- The commitment is undrawn at the latest quarter-end and expires September 30, 2026 unless fully borrowed earlier; this is a time-bounded availability observation, not a forecast. [reported / commitment expiry]({eight_url}) [DDTL agreement]({agreement_url})", "", "## First-report coverage", "", "The ten required first-report questions are addressed below. Status describes the answer boundary, not human verification.", "", "| # | Required question | Status | Boundary |", "|---:|---|---|---|", "| 1 | What debt does the company have? | covered | Latest-quarter debt context is listed below. |", "| 2 | Which agreements govern it? | bounded | DDTL, revolving, and Senior Notes indenture context are identified; other context facilities remain unmapped. |", "| 3 | What covenants apply? | covered | DDTL financial-covenant absence and selected negative covenants are listed. |", "| 4 | Maintenance or incurrence? | covered | Covenant records distinguish no financial covenant from negative/incurrence covenants. |", "| 5 | What are the thresholds? | not calculable | No threshold is inferred where disclosures or exception schedules are incomplete. |", "| 6 | What financial inputs are required? | not calculable | Agreement definitions and required inputs are not fully normalized. |", "| 7 | What is estimated headroom? | not calculable | No unsupported covenant ratio or headroom is emitted. |", "| 8 | What changed since the prior quarter? | covered | New facility, balances, short-term debt change, and amendments are linked below. |", "| 9 | Were there amendments, waivers, or new debt? | covered | New DDTL debt and revolving amendments are identified; no waiver is reported. |", "| 10 | What uncertainties remain? | covered | Follow-up questions and human-review boundaries are listed below. |", "", "## Debt instruments", "", f"- **DDTL Facility (primary monitored family):** commitment {ddtl.commitment_amount}; outstanding {ddtl.outstanding_amount}; {ddtl.secured_status}; {ddtl.interest_rate_or_spread}. [SEC 8-K]({eight_url}) [Latest 10-Q]({q2_url})", "", "### Other latest-quarter debt context", ""]
    for instrument in context_instruments:
        governing = instrument.agreement_version or "governing agreement not specified in the bounded corpus"
        md.append(f"- **{instrument.name}:** {instrument.commitment_amount or instrument.instrument_type}; outstanding {instrument.outstanding_amount or 'not reported in selected excerpt'}; governing agreement: {governing}. {_markdown_evidence_links(instrument.evidence)}")
    md += ["", "## Covenant status", "", f"- **Financial covenant:** None disclosed for the DDTL Facility. Status: **Not calculable**. [reported / Item 1.01 / Item 2.03]({eight_url})"]
    for nonfinancial in negative_covenants:
        exception_text = f" Exception noted: {nonfinancial.exceptions[0]}" if nonfinancial.exceptions else ""
        md.append(f"- **{nonfinancial.name}:** {nonfinancial.maintenance_or_incurrence}; status **{nonfinancial.status}**; no unsupported threshold or headroom is presented.{exception_text} {_markdown_evidence_links(nonfinancial.evidence)}")
    md += [f"- The agreement description is qualified by the full Exhibit 10.1 agreement, so definitions, baskets, cure rights, grace periods, and non-financial covenants remain human-review items. [missing / agreement qualification]({agreement_url})", "", "## Evidence classification", "", "- **reported:** directly stated in an SEC filing", "- **agreement_defined:** stated in a filed credit agreement or amendment", "- **calculated:** derived from sourced inputs", "- **estimate:** approximate or judgmental value", "- **interpretation:** analytical reading of sourced material", "- **missing:** not available or not yet verified", "- **human verification:** reviewer status is stated separately and does not convert machine output into a verified conclusion", "", "## What changed since March 31, 2026", ""]
    md += [f"- **{c.change_type}:** {c.description}" + (f" Calculation: `{c.calculation}`." if c.calculation else "") + f" {_markdown_evidence_links(c.evidence)}" for c in changes]
    md += ["", "## Default and remedy observations", "", f"- {risk.events_of_default[0]} [agreement_defined / Section 8.01 source]({agreement_url})", "", "## Agreement monitoring hooks", "", "The agreement contains operative affirmative-covenant, negative-covenant, and event-of-default sections. These excerpts are machine-segmented and require human verification:", ""]
    for code in sorted(sections):
        label = {"6.01": "Financial statements", "6.02": "Certificates and other information", "6.03": "Notices", "7.01": "Liens", "7.02": "Fundamental changes", "8.01": "Events of default", "8.02": "Remedies upon event of default"}.get(code, "Agreement section")
        md.append(f"- **Section {code} — {label}:** {sections[code][:700]} [agreement_defined / Section {code}]({agreement_url})")
    md += ["", "## Uncertainties and follow-up", ""] + [f"- {q}" for q in report.follow_up_questions]
    md += ["", "## Source register", "", "The report uses this bounded SEC corpus (quarterly filings, the latest annual filing as context, the DDTL agreement, and two revolving-credit amendments):"]
    source_roles = {
        "0001018724-26-000014": "prior comparison period",
        "0001018724-26-000026": "latest comparison period and debt context",
        "0001104659-26-072140": "DDTL facility disclosure",
        "0001018724-26-000012": "SEC filing context",
        "0001018724-26-000024": "SEC filing context",
        "0001018724-26-000004": "latest annual context; not used for the quarter-over-quarter calculations",
        "senior-notes-indenture": "governing Senior Notes indenture context",
        "senior-notes-supplemental-indenture": "supplemental Senior Notes indenture context",
        "ddtl-agreement": "governing DDTL agreement",
        "revolving-amendment-364": "amended revolving agreement",
        "revolving-amendment-five-year": "amended revolving agreement",
    }
    for source in manifest["documents"]:
        source_id = source.get("document_id") or source.get("filing", {}).get("accession_number")
        role = source_roles.get(source_id, "corpus source")
        filing = source.get("filing")
        if filing:
            md.append(f"- **{filing.get('form', 'SEC filing')} — {filing.get('report_date', 'date not recorded')} ({role}):** accession `{filing.get('accession_number')}` [SEC filing]({filing.get('source_url')})")
        else:
            md.append(f"- **{source.get('document_id')} ({role}):** [SEC exhibit]({source.get('sec_url')})")
    md += ["", "## Evidence and status", "", "This report is machine-assembled from SEC filings and the linked SEC exhibit. It is not human verified and is not investment advice.", "", f"Corpus manifest SHA-256: `{report.corpus_manifest_sha256}`", f"Prior-quarter 10-Q: [SEC filing]({q1_url})", f"Latest-quarter 10-Q: [SEC filing]({q2_url})"]
    xbrl_path = output.parent / "xbrl-corroboration.json"
    if xbrl_path.is_file():
        try:
            xbrl_result = json.loads(xbrl_path.read_text(encoding="utf-8"))
            fact_count = len(xbrl_result.get("facts", []))
            xbrl_status = "passed" if xbrl_result.get("passed") else "unresolved"
            md += ["", "## Supplemental SEC inline-XBRL corroboration", "", f"The companion `xbrl-corroboration.json` artifact reports **{xbrl_status}** for {fact_count} selected latest-quarter debt facts and alignment with this report. It is machine corroboration only; it does not establish covenant definitions, headroom, remedies, or human verification."]
        except (OSError, UnicodeError, json.JSONDecodeError):
            md += ["", "## Supplemental SEC inline-XBRL corroboration", "", "A companion XBRL artifact exists but could not be read for report display; the deterministic SEC report remains authoritative."]
    output.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return output.with_suffix(".md")
