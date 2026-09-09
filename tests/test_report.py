import hashlib
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

from ccrm.evaluate import evaluate_report
from ccrm.compare import classify_amzn_changes, extract_amzn_snapshot
from ccrm.llama_plan import bounded_agreement_parsed_documents, bounded_source_documents, build_llama_plan, validate_llama_plan
from ccrm.report import _ev, _required_excerpt, _required_agreement_sections, _required_filing_metadata
from ccrm.cloud_eval import compare_cloud_output
from ccrm.review import build_review_checklist, build_review_summary, initialize_review_state, record_agent_review, transition_review_state
from ccrm.integrity import check_corpus_integrity
from ccrm.reducto_audit import audit_reducto_parse
from ccrm.xbrl import build_xbrl_corroboration
from ccrm.readiness import build_readiness
from ccrm.run import compare_run_snapshots, create_run_snapshot, verify_run_snapshot
from ccrm.agent_review import build_agent_review
from ccrm.brief import build_decision_brief
from ccrm.approval import build_approval_packet
from ccrm.metrics import build_workflow_metrics
from ccrm.periods import build_period_registry
from ccrm.agreement_map import build_agreement_map


def test_report_captures_zero_ddtl_draw_at_latest_quarter():
    report = json.loads(Path("data/AMZN/report.json").read_text())
    instrument = report["debt_instruments"][0]
    assert instrument["outstanding_amount"] == "$0 as of June 30, 2026"
    assert any("no borrowings outstanding" in e["excerpt"].lower() for e in instrument["evidence"])
    assert "June 8, 2026 DDTL Credit Agreement" in instrument["agreement_version"]


def test_report_does_not_invent_headroom():
    report = json.loads(Path("data/AMZN/report.json").read_text())
    assert all(c["estimated_headroom"] is None for c in report["covenants"])
    assert all(c["status"] == "not_calculable" for c in report["covenants"])
    assert report["covenants"][0]["agreement_version"]
    assert {i["name"] for i in report["debt_instruments"]} >= {"DDTL Facility", "Senior Notes", "Commercial Paper Programs", "Other short-term credit facilities"}
    assert report["debt_instruments"][-1]["outstanding_amount"] == "$325 million as of June 30, 2026"


def test_report_captures_reported_senior_notes_principal():
    report = json.loads(Path("data/AMZN/report.json").read_text())
    notes = next(i for i in report["debt_instruments"] if i["name"] == "Senior Notes")
    assert notes["outstanding_amount"].startswith("$132.1 billion")
    assert any("132.1 billion" in e["excerpt"] for e in notes["evidence"])


def test_markdown_explicitly_discloses_missing_context_agreement_mapping():
    text = Path("data/AMZN/report.md").read_text()
    assert text.count("governing agreement: governing agreement not specified in the bounded corpus") == 2
    assert "2012 Indenture and 2022 Supplemental Indenture" in text


def test_inline_xbrl_corroboration_covers_selected_debt_facts(tmp_path: Path):
    output = build_xbrl_corroboration(
        Path("data/AMZN/corpus/0001018724-26-000026/0001018724-26-000026-amzn-20260630.htm"),
        "https://www.sec.gov/Archives/edgar/data/1018724/000101872426000026/amzn-20260630.htm",
        tmp_path / "xbrl.json",
        Path("data/AMZN/report.json"),
    )
    result = json.loads(output.read_text())
    assert result["passed"] is True
    assert len(result["facts"]) == 6
    assert result["human_verified"] is False
    assert result["report_alignment_passed"] is True
    assert len(result["report_alignment"]) == 6
    assert any(f["label"] == "Senior Notes principal" and f["display_value"] == "$132.1 billion" and f["period"] == "2026-06-30" for f in result["facts"])
    assert any(f["label"] == "Senior Notes principal" and f["numeric_value"] == "132100000000" for f in result["facts"])


def test_evaluation_binds_current_xbrl_corroboration(tmp_path: Path):
    result = json.loads(evaluate_report(
        Path("data/AMZN/report.json"),
        tmp_path / "evaluation.json",
        Path("data/AMZN/corpus-manifest.json"),
        Path("data/AMZN/xbrl-corroboration.json"),
    ).read_text())
    check = next(c for c in result["checks"] if c["name"] == "XBRL corroboration binding")
    assert check["passed"] is True


def test_evaluation_rejects_stale_xbrl_source_hash(tmp_path: Path):
    xbrl = json.loads(Path("data/AMZN/xbrl-corroboration.json").read_text())
    xbrl["source_sha256"] = "0" * 64
    xbrl_path = tmp_path / "xbrl.json"
    xbrl_path.write_text(json.dumps(xbrl), encoding="utf-8")
    result = json.loads(evaluate_report(
        Path("data/AMZN/report.json"),
        tmp_path / "evaluation.json",
        Path("data/AMZN/corpus-manifest.json"),
        xbrl_path,
    ).read_text())
    check = next(c for c in result["checks"] if c["name"] == "XBRL corroboration binding")
    assert check["passed"] is False


def test_report_surfaces_agreement_monitoring_sections():
    report = json.loads(Path("data/AMZN/report.json").read_text())
    locators = {e["locator"] for e in report["risk_status"]["evidence"]}
    assert all("/000110465926072140/" in e["sec_url"] for e in report["risk_status"]["evidence"] if e["document_id"] == "ddtl-agreement")
    assert "Section 6.01" in locators
    assert "Section 7.01" in locators
    assert "Section 8.01" in locators
    section_603 = next(e["excerpt"] for e in report["risk_status"]["evidence"] if e["locator"] == "Section 6.03")
    assert "6.04 Payment of Taxes" not in section_603


def test_report_structures_negative_covenants_without_inventing_headroom():
    report = json.loads(Path("data/AMZN/report.json").read_text())
    negative = {item["name"]: item for item in report["covenants"] if item["covenant_type"] == "negative covenant"}
    assert set(negative) == {"Liens", "Fundamental Changes"}
    assert all(item["status"] == "not_calculable" and item["estimated_headroom"] is None for item in negative.values())
    assert negative["Liens"]["agreement_section"] == "Section 7.01"
    assert negative["Fundamental Changes"]["agreement_section"] == "Section 7.02"
    text = Path("data/AMZN/report.md").read_text()
    assert "**Liens:**" in text
    assert "**Fundamental Changes:**" in text


def test_negative_covenants_surface_bounded_exception_language():
    report = json.loads(Path("data/AMZN/report.json").read_text())
    negative = {item["name"]: item for item in report["covenants"] if item["covenant_type"] == "negative covenant"}
    assert "Schedule 7.01" in negative["Liens"]["exceptions"][0]
    assert "no Default exists" in negative["Fundamental Changes"]["exceptions"][0]


def test_new_debt_change_has_new_debt_evidence():
    report = json.loads(Path("data/AMZN/report.json").read_text())
    change = report["changes_since_prior_period"][0]
    assert "New $17.5 billion" in change["description"]
    assert "$17.5 billion" in change["evidence"][0]["excerpt"]
    assert change["change_type"] == "facility_added"


def test_report_surfaces_real_revolving_agreement_amendments():
    report = json.loads(Path("data/AMZN/report.json").read_text())
    amendment = next(c for c in report["changes_since_prior_period"] if "First Amendments" in c["description"])
    assert len(amendment["evidence"]) == 3
    assert amendment["evidence"][0]["excerpt"].startswith("10.2 Amended and Restated 364-Day Revolving Credit Agreement")
    assert "FIRST AMENDMENT dated as of June 8, 2026" in amendment["evidence"][1]["excerpt"]
    assert "FIRST AMENDMENT dated as of June 8, 2026" in amendment["evidence"][2]["excerpt"]
    assert "June 8, 2026" in amendment["description"]
    assert len(report["risk_status"]["amendments"]) == 1
    assert not any("continues to disclose" in c["description"] for c in report["changes_since_prior_period"])


def test_revolving_context_is_bound_to_amended_agreements():
    report = json.loads(Path("data/AMZN/report.json").read_text())
    revolving = next(i for i in report["debt_instruments"] if i["name"] == "Unsecured revolving credit facilities")
    assert "364-Day Revolving Credit Agreement" in revolving["agreement_version"]
    assert "Five-Year Revolving Credit Agreement" in revolving["agreement_version"]
    assert len(revolving["evidence"]) == 4
    assert any(e["document_id"] == "revolving-amendment-five-year" for e in revolving["evidence"])


def test_short_term_change_carries_both_periods_evidence():
    report = json.loads(Path("data/AMZN/report.json").read_text())
    change = next(c for c in report["changes_since_prior_period"] if "short-term credit facilities increased" in c["description"])
    assert [e["document_id"] for e in change["evidence"]] == ["0001018724-26-000014", "0001018724-26-000026"]
    assert "March 31, 2026" in change["evidence"][0]["excerpt"]
    assert "June 30, 2026" in change["evidence"][1]["excerpt"]
    assert change["change_type"] == "balance_changed"
    assert change["calculation"] == "$325 million - $152 million = $173 million increase"
    assert "Calculation: `$325 million - $152 million = $173 million increase`." in Path("data/AMZN/report.md").read_text()


def test_markdown_default_observation_links_section_801():
    text = Path("data/AMZN/report.md").read_text()
    assert "Section 8.01 source" in text
    assert "tm2613616d4_ex10-1.htm" in text


def test_markdown_executive_conclusion_surfaces_commitment_expiry():
    text = Path("data/AMZN/report.md").read_text()
    assert "expires September 30, 2026" in text
    assert "time-bounded availability observation" in text
    assert "reported / commitment expiry" in text


def test_markdown_exposes_first_report_coverage_table():
    text = Path("data/AMZN/report.md").read_text()
    assert "## First-report coverage" in text
    assert text.count("| 10 |") == 1
    assert "No unsupported covenant ratio or headroom is emitted." in text


def test_ddtl_commitment_expiry_has_dedicated_evidence():
    report = json.loads(Path("data/AMZN/report.json").read_text())
    ddtl = report["debt_instruments"][0]
    expiry = next(e for e in ddtl["evidence"] if e["locator"].endswith("commitment expiry"))
    assert "September 30, 2026" in expiry["excerpt"]


def test_markdown_source_register_lists_bounded_corpus():
    text = Path("data/AMZN/report.md").read_text()
    assert "## Source register" in text
    assert "0001018724-26-000014" in text
    assert "0001018724-26-000026" in text
    assert "ddtl-agreement" in text
    assert "revolving-amendment-364" in text
    assert "prior comparison period" in text
    assert "latest comparison period and debt context" in text
    assert "0001018724-26-000004" in text
    assert "latest annual context; not used for the quarter-over-quarter calculations" in text
    assert "governing DDTL agreement" in text
    assert "amended revolving agreement" in text
    assert "Corpus manifest SHA-256:" in text


def test_markdown_exposes_evidence_classification():
    text = Path("data/AMZN/report.md").read_text()
    assert "## Evidence classification" in text
    assert "**reported:** directly stated in an SEC filing" in text
    assert "**agreement_defined:** stated in a filed credit agreement or amendment" in text
    assert "**missing:** not available or not yet verified" in text
    assert "**balance_changed:**" in text
    assert "[reported / Note 7, Debt]" in text


def test_markdown_surfaces_supplemental_xbrl_boundary():
    text = Path("data/AMZN/report.md").read_text()
    assert "Supplemental SEC inline-XBRL corroboration" in text
    assert "6 selected latest-quarter debt facts" in text
    assert "does not establish covenant definitions" in text


def test_product_status_is_durable_and_matches_current_boundary():
    text = Path("STATUS.md").read_text()
    assert "AMZN" in text
    assert "June 30, 2026 versus March 31, 2026" in text
    assert "not calculable" in text
    assert "26/26 checks passed" in text
    assert "105 tests passed" in text
    assert "Active blockers" in text
    assert "Additional Reducto usage requires explicit cost authorization" in text


def test_review_summary_exposes_durable_progress_counts():
    text = Path("data/AMZN/review-summary.md").read_text()
    assert "Evidence review progress:" in text
    assert "0/24" in text
    assert "Action progress:" in text
    assert "0/5" in text


def test_persisted_evaluation_passes(tmp_path: Path):
    result_path = evaluate_report(Path("data/AMZN/report.json"), tmp_path / "evaluation.json")
    result = json.loads(result_path.read_text())
    assert result["passed"] is True
    assert len(result["checks"]) == 18


def test_evaluation_rejects_one_sided_period_change_evidence(tmp_path: Path):
    report = json.loads(Path("data/AMZN/report.json").read_text())
    change = next(c for c in report["changes_since_prior_period"] if "short-term credit facilities increased" in c["description"])
    change["evidence"] = [change["evidence"][1]]
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result = json.loads(evaluate_report(report_path, tmp_path / "evaluation.json").read_text())
    check = next(c for c in result["checks"] if c["name"] == "period-change evidence")
    assert check["passed"] is False


def test_period_change_gate_fails_closed_when_period_metadata_is_blank(tmp_path: Path):
    report = json.loads(Path("data/AMZN/report.json").read_text())
    report["prior_period"] = ""
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result = json.loads(evaluate_report(report_path, tmp_path / "evaluation.json").read_text())
    check = next(c for c in result["checks"] if c["name"] == "period-change evidence")
    assert check["passed"] is False


def test_evaluation_rejects_incomplete_verified_calculation(tmp_path: Path):
    report = json.loads(Path("data/AMZN/report.json").read_text())
    report["covenants"][0].update({"status": "verified", "estimated_headroom": "17.5x"})
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result_path = evaluate_report(report_path, tmp_path / "evaluation.json")
    result = json.loads(result_path.read_text())
    check = next(c for c in result["checks"] if c["name"] == "calculation safety completeness")
    assert check["passed"] is False


def test_manifest_evidence_provenance_gate_passes_for_current_report(tmp_path: Path):
    result_path = evaluate_report(
        Path("data/AMZN/report.json"),
        tmp_path / "evaluation.json",
        Path("data/AMZN/corpus-manifest.json"),
    )
    result = json.loads(result_path.read_text())
    provenance = next(c for c in result["checks"] if c["name"] == "evidence provenance")
    assert provenance["passed"] is True
    completeness = next(c for c in result["checks"] if c["name"] == "corpus completeness")
    assert completeness["passed"] is True
    period_metadata = next(c for c in result["checks"] if c["name"] == "manifest period metadata")
    assert period_metadata["passed"] is True
    binding = next(c for c in result["checks"] if c["name"] == "report corpus binding")
    assert binding["passed"] is True


def test_persisted_evaluation_records_ten_question_coverage_rows(tmp_path: Path):
    result = json.loads(evaluate_report(Path("data/AMZN/report.json"), tmp_path / "evaluation.json").read_text())
    coverage = result["question_coverage"]
    assert [row["question"] for row in coverage] == list(range(1, 11))
    assert all(row["status"] in {"covered", "bounded", "not_calculable"} for row in coverage)
    assert coverage[6]["status"] == "not_calculable"


def test_readiness_artifact_keeps_current_report_internal_review(tmp_path: Path):
    output = build_readiness(Path("data/AMZN"), tmp_path / "readiness.json")
    readiness = json.loads(output.read_text())
    assert readiness["release_status"] == "internal_review"
    assert readiness["customer_ready"] is False
    assert "human review" in readiness["blocking_items"]
    assert "provider comparison" in readiness["documented_optional_gaps"]
    assert "agent review" not in readiness["documented_optional_gaps"]
    assert readiness["expansion_ready"] is False
    assert "fewer than two distinct immutable reporting periods exist" in readiness["expansion_blockers"]


def test_agent_review_passes_bounded_checks_and_preserves_exceptions(tmp_path: Path):
    output = build_agent_review(Path("data/AMZN"), tmp_path / "agent-review.json")
    review = json.loads(output.read_text())
    assert review["status"] == "agent_reviewed"
    assert review["human_approval_required"] is True
    assert all(check["passed"] for check in review["checks"])
    assert any(check["name"] == "evidence excerpt anchoring" for check in review["checks"])
    assert {item["topic"] for item in review["exceptions"]} == {"agreement amendments", "covenant capacity", "events of default and remedies", "post-period activity"}


def test_agent_review_is_bound_to_durable_review_state(tmp_path: Path):
    report = Path("data/AMZN/report.json")
    checklist = build_review_checklist(report, tmp_path / "review.md")
    state = initialize_review_state(report, checklist, tmp_path / "review-state.json", Path("data/AMZN/cloud-comparison.json"))
    agent = build_agent_review(Path("data/AMZN"), tmp_path / "agent-review.json")
    record_agent_review(state, agent)
    durable = json.loads(state.read_text())
    assert durable["status"] == "agent_reviewed"
    assert durable["agent_review_status"] == "agent_reviewed"
    assert durable["agent_review_sha256"]


def test_decision_brief_surfaces_customer_value_and_boundaries(tmp_path: Path):
    output = build_decision_brief(Path("data/AMZN/report.json"), Path("data/AMZN/agent-review.json"), tmp_path / "decision-brief.md")
    text = output.read_text()
    assert "$17.5 billion senior unsecured DDTL facility" in text
    assert "undrawn at quarter-end" in text
    assert "headroom" in text
    assert "June 8 revolving-credit amendments" in text
    assert "human approval still required" in text


def test_approval_packet_focuses_human_on_agent_exceptions(tmp_path: Path):
    output = build_approval_packet(Path("data/AMZN"), tmp_path / "approval.md")
    text = output.read_text()
    assert "Agent checks:" in text
    assert "Agreement Amendments" in text
    assert "Covenant Capacity" in text
    assert "Post-Period Activity" in text
    assert "does not itself change readiness" in text


def test_workflow_metrics_are_conservative_and_durable(tmp_path: Path):
    output = build_workflow_metrics(Path("data/AMZN"), tmp_path / "workflow-metrics.json")
    metrics = json.loads(output.read_text())
    assert metrics["agent_review_status"] == "agent_reviewed"
    assert metrics["evidence_items_in_review_state"] == 24
    assert metrics["agent_exceptions"] == 4
    assert metrics["time_saved_measured"] is False
    assert metrics["human_review_focus_ratio"] == 0.1667


def test_period_registry_does_not_count_duplicate_rebuilds_as_history(tmp_path: Path):
    output = build_period_registry(Path("data/AMZN"), tmp_path / "period-registry.json")
    registry = json.loads(output.read_text())
    assert registry["distinct_period_count"] == 1
    assert registry["historical_comparison_ready"] is False
    assert registry["duplicate_runs"]
    assert registry["invalid_runs"] == []


def test_agreement_map_preserves_review_hooks_and_source_boundaries(tmp_path: Path):
    output = build_agreement_map(Path("data/AMZN"), tmp_path / "agreement-map.json")
    mapping = json.loads(output.read_text())
    assert mapping["section_count"] == 10
    assert {row["locator"] for row in mapping["agreement_sections"]} >= {"Section 7.01", "Section 8.01", "Section 8.02", "First Amendment"}
    assert all(row["review_status"] == "human_review_required" for row in mapping["agreement_sections"])
    assert mapping["human_review_required"] is True


def test_snapshot_is_immutable_and_idempotent():
    first = create_run_snapshot(Path("data/AMZN"))
    second = create_run_snapshot(Path("data/AMZN"))
    assert first == second
    snapshot = json.loads(first.read_text())
    assert snapshot["immutable"] is True
    assert snapshot["artifact_count"] > 0
    assert snapshot["issuer"] == "Amazon.com, Inc. (AMZN)"
    run_dir = first.parent
    evaluation = json.loads((run_dir / "evaluation.json").read_text())
    assert evaluation["passed"] is True
    assert json.loads((run_dir / "readiness.json").read_text())["release_status"] == "internal_review"
    verification = verify_run_snapshot(first)
    assert verification["passed"] is True


def test_run_comparison_verifies_and_handles_identical_snapshot(tmp_path: Path):
    run_manifest = next(Path("data/AMZN/runs").glob("*/run-manifest.json"))
    output = compare_run_snapshots(run_manifest, run_manifest, tmp_path / "run-comparison.json")
    comparison = json.loads(output.read_text())
    assert comparison["passed"] is True
    assert comparison["identical"] is True
    assert comparison["same_reporting_period"] is True
    assert comparison["corpus_changes"] == []
    assert comparison["instrument_changes"] == []
    assert comparison["covenant_changes"] == []


def test_run_comparison_surfaces_verified_changes_between_runs(tmp_path: Path):
    def write_run(name: str, outstanding: str, source_sha: str) -> Path:
        run_dir = tmp_path / name
        run_dir.mkdir()
        report = {
            "debt_instruments": [{"name": "Facility", "outstanding_amount": outstanding, "evidence": [{"evidence_id": "E-1"}]}],
            "covenants": [],
            "changes_since_prior_period": [{"change_type": "balance_changed", "description": outstanding}],
        }
        corpus = {"documents": [{"document_id": "doc-1", "source_sha256": source_sha}]}
        for filename, payload in (("report.json", report), ("corpus-manifest.json", corpus)):
            (run_dir / filename).write_text(json.dumps(payload), encoding="utf-8")
        hashes = {filename: hashlib.sha256((run_dir / filename).read_bytes()).hexdigest() for filename in ("report.json", "corpus-manifest.json")}
        manifest = {"run_id": name, "issuer": "Amazon.com, Inc. (AMZN)", "as_of": name, "artifact_sha256": hashes}
        path = run_dir / "run-manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    prior = write_run("prior", "$1", "old")
    current = write_run("current", "$2", "new")
    comparison = json.loads(compare_run_snapshots(prior, current, tmp_path / "comparison.json").read_text())
    assert comparison["passed"] is True
    assert comparison["identical"] is False
    assert comparison["corpus_changes"] == [{"document_id": "doc-1", "change": "source_changed", "prior_sha256": "old", "current_sha256": "new"}]
    assert comparison["instrument_changes"][0]["fields"]["outstanding_amount"] == {"prior": "$1", "current": "$2"}


def test_evaluation_rejects_non_sec_manifest_source_url(tmp_path: Path):
    manifest = json.loads(Path("data/AMZN/corpus-manifest.json").read_text())
    manifest["documents"][0]["filing"]["source_url"] = "https://example.com/not-sec"
    manifest_path = tmp_path / "corpus-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = json.loads(evaluate_report(Path("data/AMZN/report.json"), tmp_path / "evaluation.json", manifest_path).read_text())
    check = next(c for c in result["checks"] if c["name"] == "manifest source provenance")
    assert check["passed"] is False


def test_evaluation_rejects_report_bound_to_different_manifest(tmp_path: Path):
    report = json.loads(Path("data/AMZN/report.json").read_text())
    report["corpus_manifest_sha256"] = "0" * 64
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result = json.loads(evaluate_report(report_path, tmp_path / "evaluation.json", Path("data/AMZN/corpus-manifest.json")).read_text())
    binding = next(c for c in result["checks"] if c["name"] == "report corpus binding")
    assert binding["passed"] is False


def test_evaluation_requires_human_verification_disclosure(tmp_path: Path):
    report = json.loads(Path("data/AMZN/report.json").read_text())
    report["risk_status"]["human_verification_status"] = "Verified"
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result = json.loads(evaluate_report(report_path, tmp_path / "evaluation.json").read_text())
    check = next(c for c in result["checks"] if c["name"] == "human verification disclosure")
    assert check["passed"] is False


def test_evaluation_rejects_verified_evidence_under_unverified_report_status(tmp_path: Path):
    report = json.loads(Path("data/AMZN/report.json").read_text())
    report["debt_instruments"][0]["evidence"][0]["human_verified"] = True
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result = json.loads(evaluate_report(report_path, tmp_path / "evaluation.json").read_text())
    check = next(c for c in result["checks"] if c["name"] == "verification flag consistency")
    assert check["passed"] is False


def test_evaluation_rejects_unsupported_narrative_risk_status(tmp_path: Path):
    report = json.loads(Path("data/AMZN/report.json").read_text())
    report["risk_status"]["covenant_breaches"] = ["Unsubstantiated breach"]
    report["risk_status"]["evidence"] = []
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result = json.loads(evaluate_report(report_path, tmp_path / "evaluation.json").read_text())
    check = next(c for c in result["checks"] if c["name"] == "risk status evidence coverage")
    assert check["passed"] is False


def test_evaluation_rejects_malformed_report_schema(tmp_path: Path):
    report = json.loads(Path("data/AMZN/report.json").read_text())
    del report["issuer"]
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result = json.loads(evaluate_report(report_path, tmp_path / "evaluation.json").read_text())
    check = next(c for c in result["checks"] if c["name"] == "report schema")
    assert check["passed"] is False


def test_evaluation_rejects_incomplete_evidence_object(tmp_path: Path):
    report = json.loads(Path("data/AMZN/report.json").read_text())
    report["debt_instruments"][0]["evidence"][0]["excerpt"] = ""
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result = json.loads(evaluate_report(report_path, tmp_path / "evaluation.json").read_text())
    check = next(c for c in result["checks"] if c["name"] == "evidence completeness")
    assert check["passed"] is False


def test_evaluation_rejects_unsupported_uncertainty_narrative(tmp_path: Path):
    report = json.loads(Path("data/AMZN/report.json").read_text())
    report["risk_status"]["evidence"] = []
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result = json.loads(evaluate_report(report_path, tmp_path / "evaluation.json").read_text())
    check = next(c for c in result["checks"] if c["name"] == "uncertainty evidence coverage")
    assert check["passed"] is False


def test_evaluation_rejects_report_missing_first_question_answer(tmp_path: Path):
    report = json.loads(Path("data/AMZN/report.json").read_text())
    report["follow_up_questions"] = []
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result = json.loads(evaluate_report(report_path, tmp_path / "evaluation.json").read_text())
    check = next(c for c in result["checks"] if c["name"] == "first-report question coverage")
    assert check["passed"] is False


def test_evaluation_rejects_renderer_noise_in_evidence_excerpt(tmp_path: Path):
    report = json.loads(Path("data/AMZN/report.json").read_text())
    report["debt_instruments"][0]["evidence"][0]["excerpt"] += " file:///tmp/rendered.html"
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result = json.loads(evaluate_report(report_path, tmp_path / "evaluation.json").read_text())
    check = next(c for c in result["checks"] if c["name"] == "evidence excerpt cleanliness")
    assert check["passed"] is False


def test_evaluation_rejects_duplicate_evidence_ids(tmp_path: Path):
    report = json.loads(Path("data/AMZN/report.json").read_text())
    report["debt_instruments"][1]["evidence"][0]["evidence_id"] = report["debt_instruments"][0]["evidence"][0]["evidence_id"]
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result = json.loads(evaluate_report(report_path, tmp_path / "evaluation.json").read_text())
    check = next(c for c in result["checks"] if c["name"] == "evidence ID coverage")
    assert check["passed"] is False


def test_evaluation_allows_repeated_reference_to_same_evidence_item(tmp_path: Path):
    report = json.loads(Path("data/AMZN/report.json").read_text())
    evidence = report["debt_instruments"][0]["evidence"][0]
    report["risk_status"]["evidence"].append(evidence)
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result = json.loads(evaluate_report(report_path, tmp_path / "evaluation.json").read_text())
    check = next(c for c in result["checks"] if c["name"] == "evidence ID coverage")
    assert check["passed"] is True


def test_evaluation_rejects_non_sec_evidence_url(tmp_path: Path):
    report = json.loads(Path("data/AMZN/report.json").read_text())
    report["debt_instruments"][0]["evidence"][0]["sec_url"] = "https://example.com/source"
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result = json.loads(evaluate_report(report_path, tmp_path / "evaluation.json").read_text())
    check = next(c for c in result["checks"] if c["name"] == "evidence completeness")
    assert check["passed"] is False


def test_evaluation_rejects_excerpt_not_present_in_bound_source(tmp_path: Path):
    report = json.loads(Path("data/AMZN/report.json").read_text())
    report["debt_instruments"][0]["evidence"][0]["excerpt"] = "This sentence is not present in the bound SEC filing."
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result = json.loads(evaluate_report(report_path, tmp_path / "evaluation.json", Path("data/AMZN/corpus-manifest.json")).read_text())
    check = next(c for c in result["checks"] if c["name"] == "evidence source-content binding")
    assert check["passed"] is False


def test_quarter_fixture_classifies_new_ddtl_without_fabricating_covenant_ratio():
    q1 = json.loads(Path("tests/fixtures/amzn_q1_snapshot.json").read_text())
    q2 = json.loads(Path("tests/fixtures/amzn_q2_snapshot.json").read_text())
    from ccrm.compare import DebtSnapshot
    changes = classify_amzn_changes(DebtSnapshot(**q1), DebtSnapshot(**q2))
    assert changes == ["new_ddtl_facility", "ddtl_outstanding_balance_reported"]
    assert extract_amzn_snapshot("In June 2026, we entered into a $ 17.5 billion unsecured delayed draw term loan.", "June 30, 2026").ddtl_present is True


def test_quarter_fixture_detects_new_amendment_only_in_current_period():
    previous = extract_amzn_snapshot("We have an aggregate $20.0 billion in unsecured revolving credit facilities.", "March 31, 2026")
    current = extract_amzn_snapshot("First Amendments dated June 8, 2026 were entered into.", "June 30, 2026")
    assert previous.amendment_present is False
    assert current.amendment_present is True
    assert "amendment_reported" in classify_amzn_changes(previous, current)


def test_quarter_fixture_extracts_short_term_balance_change():
    q1 = json.loads(Path("tests/fixtures/amzn_q1_snapshot.json").read_text())
    q2 = json.loads(Path("tests/fixtures/amzn_q2_snapshot.json").read_text())
    from ccrm.compare import DebtSnapshot
    previous = DebtSnapshot(**q1, short_term_outstanding="$152 million")
    current = DebtSnapshot(**q2, short_term_outstanding="$325 million")
    assert "short_term_outstanding_changed" in classify_amzn_changes(previous, current)


def test_real_quarter_filings_extract_short_term_balances():
    from ccrm.report import _normalized_text
    q1_path = next(Path("data/AMZN/corpus/0001018724-26-000014").glob("*.htm"))
    q2_path = next(Path("data/AMZN/corpus/0001018724-26-000026").glob("*.htm"))
    q1 = extract_amzn_snapshot(_normalized_text(q1_path), "March 31, 2026")
    q2 = extract_amzn_snapshot(_normalized_text(q2_path), "June 30, 2026")
    assert q1.short_term_outstanding == "$152 million"
    assert q2.short_term_outstanding == "$325 million"


def test_snapshot_covenant_absence_matching_is_case_insensitive():
    from ccrm.compare import extract_amzn_snapshot
    snapshot = extract_amzn_snapshot("We are NOT SUBJECT TO ANY FINANCIAL COVENANTS UNDER THE NOTES.", "Q2")
    assert snapshot.notes_have_no_financial_covenants is True


def test_generic_fixture_classifies_repayment_maturity_and_document_events():
    from ccrm.compare import DebtSnapshot
    previous = DebtSnapshot("Q1", False, None, "$100", True, "$20.0 billion", "2028", None, "none", False, False)
    current = DebtSnapshot("Q2", False, None, "$80", True, "$20.0 billion", "2027", "$20", "maintenance", True, True)
    changes = classify_amzn_changes(previous, current)
    assert changes == ["ddtl_outstanding_balance_changed", "maturity_changed", "repayment_reported", "covenant_status_changed", "amendment_reported", "waiver_reported"]


def test_llama_plan_is_bounded_and_makes_no_external_calls(tmp_path: Path):
    plan_path = build_llama_plan(Path("data/AMZN/corpus"), tmp_path / "llama-plan.json")
    plan = json.loads(plan_path.read_text())
    assert plan["external_calls_made"] == 0
    assert plan["parse_jobs_planned"] == 8
    assert plan["extract_jobs_planned"] == 3
    assert plan["index_or_batch_planned"] is False
    assert plan["validation"]["passed"] is True
    assert validate_llama_plan(plan_path)["passed"] is True
    assert len(bounded_source_documents(Path("data/AMZN/corpus"))) == 8
    assert all("0001018724-26-000004" not in document["path"] for document in json.loads(plan_path.read_text())["documents"])
    parsed_corpus = tmp_path / "parsed-corpus"
    for folder in ("ddtl-agreement", "revolving-amendment-364", "revolving-amendment-five-year"):
        parsed_dir = parsed_corpus / folder / "parsed"
        parsed_dir.mkdir(parents=True)
        (parsed_dir / "content.md").write_text("parsed", encoding="utf-8")
    assert len(bounded_agreement_parsed_documents(parsed_corpus)) == 3
    malformed = tmp_path / "malformed-plan.json"
    malformed.write_text(json.dumps({"documents": [{"parse": True, "extract": False}], "index_or_batch_planned": False}), encoding="utf-8")
    assert validate_llama_plan(malformed)["passed"] is False


def test_llama_plan_rejects_absolute_path_outside_declared_corpus(tmp_path: Path):
    plan_path = build_llama_plan(Path("data/AMZN/corpus"), tmp_path / "llama-plan.json")
    plan = json.loads(plan_path.read_text())
    outside = tmp_path / "outside.htm"
    outside.write_text("not corpus", encoding="utf-8")
    plan["documents"][0]["absolute_path"] = str(outside)
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    result = validate_llama_plan(plan_path)
    assert result["passed"] is False
    binding = next(c for c in result["checks"] if c["name"] == "source path binding")
    assert binding["passed"] is False


def test_llama_plan_rejects_relative_path_traversal(tmp_path: Path):
    plan_path = build_llama_plan(Path("data/AMZN/corpus"), tmp_path / "llama-plan.json")
    plan = json.loads(plan_path.read_text())
    outside = tmp_path / "outside.htm"
    outside.write_text("not corpus", encoding="utf-8")
    plan["documents"][0]["path"] = "../outside.htm"
    plan["documents"][0]["absolute_path"] = str(outside)
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    result = validate_llama_plan(plan_path)
    assert result["passed"] is False
    assert next(c for c in result["checks"] if c["name"] == "source path binding")["passed"] is False


def test_llama_plan_rejects_changed_source_content(tmp_path: Path):
    plan_path = build_llama_plan(Path("data/AMZN/corpus"), tmp_path / "llama-plan.json")
    plan = json.loads(plan_path.read_text())
    source = Path(plan["documents"][0]["absolute_path"])
    original = source.read_bytes()
    try:
        source.write_bytes(original + b" ")
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        result = validate_llama_plan(plan_path)
        assert result["passed"] is False
        assert next(c for c in result["checks"] if c["name"] == "source integrity")["passed"] is False
    finally:
        source.write_bytes(original)


def test_report_fails_closed_when_required_evidence_is_missing():
    import pytest
    with pytest.raises(ValueError, match="refusing to fabricate"):
        _required_excerpt(None, "test fact")


def test_report_evidence_builder_rejects_non_sec_url():
    import pytest
    with pytest.raises(ValueError, match="HTTPS SEC URL"):
        _ev("document", "https://example.com/source", "locator", "excerpt")


def test_report_fails_closed_when_required_agreement_section_is_missing():
    import pytest
    with pytest.raises(ValueError, match="Required agreement sections missing"):
        _required_agreement_sections({"6.01": "text"}, {"6.01", "8.01"})


def test_report_fails_closed_when_selected_filing_metadata_is_mismatched():
    import pytest
    manifest = {"documents": [{"filing": {"accession_number": "abc", "form": "8-K", "report_date": "2026-06-30"}}]}
    with pytest.raises(ValueError, match="period-inaccurate report"):
        _required_filing_metadata(manifest, "abc", "10-Q", "2026-06-30")


def test_llama_adapters_are_explicitly_cacheable():
    import inspect
    from ccrm.llama import extract_report, parse_document
    assert "force" in inspect.signature(parse_document).parameters
    assert "force" in inspect.signature(extract_report).parameters


def test_llama_client_requires_explicit_cost_authorization(monkeypatch):
    from ccrm import llama
    monkeypatch.setenv("LLAMA_CLOUD_API_KEY", "test-key")
    monkeypatch.delenv("LLAMA_CLOUD_COST_AUTHORIZED", raising=False)
    with __import__("pytest").raises(PermissionError, match="cost-gated"):
        llama._client()


def test_parse_result_normalization_accepts_text_and_rejects_empty():
    from types import SimpleNamespace
    import pytest
    from ccrm.llama import _parse_result_text

    text, metadata = _parse_result_text(SimpleNamespace(text="parsed fallback text"))
    assert text == "parsed fallback text"
    assert metadata[0]["characters"] == len(text)
    with pytest.raises(RuntimeError, match="no usable text"):
        _parse_result_text(SimpleNamespace(markdown=SimpleNamespace(pages=[])))


def test_empty_parse_cache_is_not_treated_as_usable(tmp_path: Path):
    from ccrm.llama import _usable_cached_parse
    cached = tmp_path / "content.md"
    cached.write_text("   ", encoding="utf-8")
    assert _usable_cached_parse(cached) is False
    cached.write_text("substantive parsed text", encoding="utf-8")
    assert _usable_cached_parse(cached) is True


def test_parse_cache_requires_matching_source_hash(tmp_path: Path):
    import hashlib
    source = tmp_path / "source.htm"
    source.write_text("original source", encoding="utf-8")
    parsed = tmp_path / "parsed" / "content.md"
    parsed.parent.mkdir()
    parsed.write_text("parsed source", encoding="utf-8")
    (parsed.parent / "metadata.json").write_text(json.dumps({"source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}), encoding="utf-8")
    from ccrm.llama import _usable_cached_parse
    assert _usable_cached_parse(parsed, source) is True
    source.write_text("changed source", encoding="utf-8")
    assert _usable_cached_parse(parsed, source) is False


def test_extract_rejects_empty_parsed_input_before_cloud_client(tmp_path: Path):
    from ccrm.llama import extract_report
    import pytest
    inputs = []
    for folder in ("ddtl-agreement", "revolving-amendment-364", "revolving-amendment-five-year"):
        parsed = tmp_path / folder / "parsed" / "content.md"
        parsed.parent.mkdir(parents=True)
        parsed.write_text("parsed", encoding="utf-8")
        inputs.append(parsed)
    inputs[0].write_text("", encoding="utf-8")
    with pytest.raises(RuntimeError, match="missing, empty, or stale"):
        extract_report(inputs, tmp_path / "extract.json")


def test_extract_rejects_stale_parsed_agreement_before_cloud_client(tmp_path: Path):
    from ccrm.llama import extract_report
    import pytest
    inputs = []
    for folder in ("ddtl-agreement", "revolving-amendment-364", "revolving-amendment-five-year"):
        agreement = tmp_path / folder / "agreement.htm"
        agreement.parent.mkdir(parents=True)
        agreement.write_text("current agreement", encoding="utf-8")
        parsed = agreement.parent / "parsed" / "content.md"
        parsed.parent.mkdir()
        parsed.write_text("stale parsed", encoding="utf-8")
        (parsed.parent / "metadata.json").write_text(json.dumps({"source_sha256": "0" * 64}), encoding="utf-8")
        inputs.append(parsed)
    with pytest.raises(RuntimeError, match="missing, empty, or stale"):
        extract_report(inputs, tmp_path / "extract.json")


def test_extract_cache_cannot_bypass_stale_input_validation(tmp_path: Path):
    import pytest
    from ccrm.llama import extract_report
    inputs = []
    for folder in ("ddtl-agreement", "revolving-amendment-364", "revolving-amendment-five-year"):
        agreement = tmp_path / folder / "agreement.htm"
        agreement.parent.mkdir(parents=True)
        agreement.write_text("current agreement", encoding="utf-8")
        parsed = agreement.parent / "parsed" / "content.md"
        parsed.parent.mkdir()
        parsed.write_text("stale parsed", encoding="utf-8")
        (parsed.parent / "metadata.json").write_text(json.dumps({"source_sha256": "0" * 64}), encoding="utf-8")
        inputs.append(parsed)
    output = tmp_path / "extract.json"
    output.write_text("cached output", encoding="utf-8")
    with pytest.raises(RuntimeError, match="missing, empty, or stale"):
        extract_report(inputs, output)


def test_extract_cache_requires_valid_three_document_envelope(tmp_path: Path):
    from ccrm.llama import _usable_cached_extract
    output = tmp_path / "extract.json"
    output.write_text("cached output", encoding="utf-8")
    assert _usable_cached_extract(output) is False
    output.write_text(json.dumps([{"document": "one", "result": {}}, {"document": "two", "result": {}}, {"document": "three", "result": {}}]), encoding="utf-8")
    assert _usable_cached_extract(output) is True
    output.write_text(json.dumps([{"document": "one", "result": {}}]), encoding="utf-8")
    assert _usable_cached_extract(output) is False


def test_extract_cache_binds_result_to_parsed_input_hash(tmp_path: Path):
    import hashlib
    from ccrm.llama import _usable_cached_extract
    parsed_documents = []
    entries = []
    for index in range(3):
        parsed = tmp_path / f"agreement-{index}.md"
        parsed.write_text(f"parsed {index}", encoding="utf-8")
        parsed_documents.append(parsed)
        entries.append({"document": str(parsed), "input_sha256": hashlib.sha256(parsed.read_bytes()).hexdigest(), "result": {}})
    output = tmp_path / "extract.json"
    output.write_text(json.dumps(entries), encoding="utf-8")
    assert _usable_cached_extract(output, parsed_documents) is True
    parsed_documents[0].write_text("changed parsed input", encoding="utf-8")
    assert _usable_cached_extract(output, parsed_documents) is False


def test_direct_extract_rejects_out_of_scope_document(tmp_path: Path):
    from ccrm.llama import extract_report
    import pytest
    inputs = []
    for folder in ("ddtl-agreement", "revolving-amendment-364", "other-document"):
        parsed = tmp_path / folder / "parsed" / "content.md"
        parsed.parent.mkdir(parents=True)
        parsed.write_text("parsed", encoding="utf-8")
        inputs.append(parsed)
    with pytest.raises(ValueError, match="approved agreement documents"):
        extract_report(inputs, tmp_path / "extract.json")


def test_cli_rejects_non_amzn_issuer_before_data_access(tmp_path: Path):
    import os
    import subprocess
    import sys
    environment = os.environ.copy()
    environment["PYTHONPATH"] = "src"
    result = subprocess.run(
        [sys.executable, "-m", "ccrm.cli", "evaluate", "--issuer", "OTHER", "--output", str(tmp_path)],
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode != 0
    assert "supports AMZN only" in result.stderr or "supports AMZN only" in result.stdout


def test_cloud_comparison_flags_missing_signals_and_unsupported_headroom(tmp_path: Path):
    cloud = tmp_path / "cloud.json"
    cloud.write_text(json.dumps({"commitment": "$17.5 billion", "outstanding": "$0", "covenant": "no financial covenant", "amendment": "First Amendment", "estimated_headroom": "12.0x"}))
    result = compare_cloud_output(cloud, Path("data/AMZN/report.json"), tmp_path / "comparison.json")
    comparison = json.loads(result.read_text())
    assert comparison["passed"] is False
    assert comparison["unsupported_headroom"] is True


def test_cloud_comparison_flags_structured_contradictory_amounts(tmp_path: Path):
    cloud = tmp_path / "cloud.json"
    cloud.write_text(json.dumps({
        "debt_instruments": [{"name": "DDTL Facility", "commitment_amount": "$12.0 billion", "outstanding_amount": "$2.0 billion"}],
        "covenants": [{"maintenance_or_incurrence": "No financial covenant"}],
        "changes": ["$17.5 billion", "$0", "First Amendment"],
    }))
    result = compare_cloud_output(cloud, Path("data/AMZN/report.json"), tmp_path / "comparison.json")
    comparison = json.loads(result.read_text())
    assert comparison["passed"] is False
    assert {item["field"] for item in comparison["contradictions"]} == {"ddtl_commitment", "ddtl_outstanding"}
    assert "debt_instruments[0]" in comparison["structured_evidence_gaps"]


def test_cloud_comparison_accepts_evidence_bearing_matching_output(tmp_path: Path):
    cloud = tmp_path / "cloud.json"
    cloud.write_text(json.dumps({
        "debt_instruments": [{"name": "DDTL Facility", "commitment_amount": "$17.5 billion", "outstanding_amount": "$0", "evidence": [{"document_id": "ddtl", "sec_url": "https://www.sec.gov/example", "locator": "Item 1.01", "excerpt": "$17.5 billion"}]}],
        "covenants": [{"maintenance_or_incurrence": "No financial covenant", "evidence": [{"document_id": "ddtl", "sec_url": "https://www.sec.gov/example", "locator": "Item 1.01", "excerpt": "No financial covenant"}]}],
        "changes": ["First Amendment", "Events of Default", "Remedies Upon Event of Default"],
        "estimated_headroom": None,
    }))
    result = compare_cloud_output(cloud, Path("data/AMZN/report.json"), tmp_path / "comparison.json")
    comparison = json.loads(result.read_text())
    assert comparison["passed"] is True
    assert comparison["contradictions"] == []
    assert comparison["structured_evidence_gaps"] == []


def test_cloud_comparison_accepts_structured_risk_status_keys(tmp_path: Path):
    cloud = tmp_path / "cloud.json"
    evidence = {"document_id": "ddtl", "sec_url": "https://www.sec.gov/example", "locator": "Section 8.01", "excerpt": "Events of default"}
    cloud.write_text(json.dumps({
        "debt_instruments": [{"commitment_amount": "$17.5 billion", "outstanding_amount": "$0", "evidence": [evidence]}],
        "covenants": [{"maintenance_or_incurrence": "No financial covenant", "evidence": [evidence]}],
        "risk_status": {"events_of_default": ["Events are defined"], "remedies_upon_event_of_default": ["Remedies are defined"], "evidence": [evidence]},
        "changes": ["First Amendment"],
        "estimated_headroom": None,
    }))
    result = compare_cloud_output(cloud, Path("data/AMZN/report.json"), tmp_path / "comparison.json")
    comparison = json.loads(result.read_text())
    assert comparison["passed"] is True


def test_cloud_comparison_rejects_evidence_outside_bounded_corpus(tmp_path: Path):
    cloud = tmp_path / "cloud.json"
    cloud.write_text(json.dumps({
        "debt_instruments": [{"commitment_amount": "$17.5 billion", "outstanding_amount": "$0", "evidence": [{"document_id": "unknown-document", "sec_url": "https://www.sec.gov/example", "locator": "Item 1.01", "excerpt": "$17.5 billion"}]}],
        "covenants": [{"maintenance_or_incurrence": "No financial covenant", "evidence": [{"document_id": "unknown-document", "sec_url": "https://www.sec.gov/example", "locator": "Item 1.01", "excerpt": "No financial covenant"}]}],
        "changes": ["First Amendment", "Events of Default", "Remedies Upon Event of Default"],
    }))
    result = compare_cloud_output(cloud, Path("data/AMZN/report.json"), tmp_path / "comparison.json", Path("data/AMZN/corpus-manifest.json"))
    comparison = json.loads(result.read_text())
    assert comparison["passed"] is False
    assert comparison["evidence_provenance_gaps"]


def test_cloud_comparison_failure_is_persisted_for_cli_exit_handling(tmp_path: Path):
    cloud = tmp_path / "cloud.json"
    cloud.write_text(json.dumps({"debt_instruments": [], "covenants": []}))
    result = compare_cloud_output(cloud, Path("data/AMZN/report.json"), tmp_path / "comparison.json")
    comparison = json.loads(result.read_text())
    assert comparison["passed"] is False


def test_compare_cloud_cli_exits_nonzero_on_failed_comparison(tmp_path: Path, monkeypatch):
    from ccrm.cli import main

    issuer_dir = tmp_path / "AMZN"
    issuer_dir.mkdir()
    (issuer_dir / "report.json").write_text(Path("data/AMZN/report.json").read_text(), encoding="utf-8")
    (issuer_dir / "corpus-manifest.json").write_text(Path("data/AMZN/corpus-manifest.json").read_text(), encoding="utf-8")
    cloud = tmp_path / "cloud.json"
    cloud.write_text(json.dumps({"debt_instruments": [], "covenants": []}), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["ccrm", "compare-cloud", "--issuer", "AMZN", "--output", str(tmp_path), "--cloud-output", str(cloud)])
    with __import__("pytest").raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    comparison = json.loads((issuer_dir / "cloud-comparison.json").read_text())
    assert comparison["passed"] is False
    assert comparison["structured_report_present"] is True


def test_cloud_comparison_normalizes_stringified_structured_result(tmp_path: Path):
    cloud = tmp_path / "cloud.json"
    cloud.write_text(json.dumps({"result": json.dumps({
        "debt_instruments": [{"commitment_amount": "$17.5 billion", "outstanding_amount": "$0"}],
        "covenants": [{"maintenance_or_incurrence": "No financial covenant"}],
        "changes": ["First Amendment"],
    })}))
    result = compare_cloud_output(cloud, Path("data/AMZN/report.json"), tmp_path / "comparison.json")
    comparison = json.loads(result.read_text())
    assert comparison["passed"] is False
    assert comparison["structured_evidence_gaps"]


def test_cloud_comparison_rejects_unsupported_risk_narrative(tmp_path: Path):
    cloud = tmp_path / "cloud.json"
    cloud.write_text(json.dumps({
        "debt_instruments": [{"commitment_amount": "$17.5 billion", "outstanding_amount": "$0", "evidence": [{"document_id": "ddtl", "sec_url": "https://www.sec.gov/example", "locator": "Item 1.01", "excerpt": "$17.5 billion"}]}],
        "covenants": [{"maintenance_or_incurrence": "No financial covenant", "evidence": [{"document_id": "ddtl", "sec_url": "https://www.sec.gov/example", "locator": "Item 1.01", "excerpt": "No financial covenant"}]}],
        "risk_status": {"covenant_breaches": ["Breach without evidence"]},
        "changes": ["First Amendment", "Events of Default", "Remedies Upon Event of Default"],
    }))
    result = compare_cloud_output(cloud, Path("data/AMZN/report.json"), tmp_path / "comparison.json")
    comparison = json.loads(result.read_text())
    assert comparison["passed"] is False
    assert "risk_status" in comparison["structured_evidence_gaps"]


def test_cloud_comparison_rejects_unsupported_structured_change_and_definition(tmp_path: Path):
    cloud = tmp_path / "cloud.json"
    cloud.write_text(json.dumps({
        "debt_instruments": [{"commitment_amount": "$17.5 billion", "outstanding_amount": "$0", "evidence": [{"document_id": "ddtl", "sec_url": "https://www.sec.gov/example", "locator": "Item 1.01", "excerpt": "$17.5 billion"}]}],
        "covenants": [{"maintenance_or_incurrence": "No financial covenant", "evidence": [{"document_id": "ddtl", "sec_url": "https://www.sec.gov/example", "locator": "Item 1.01", "excerpt": "No financial covenant"}]}],
        "changes_since_prior_period": [{"change_type": "amendment", "description": "Amendment", "evidence": []}],
        "financial_definitions": {"total_debt": "$1", "evidence": []},
        "changes": ["First Amendment", "Events of Default", "Remedies Upon Event of Default"],
    }))
    result = compare_cloud_output(cloud, Path("data/AMZN/report.json"), tmp_path / "comparison.json")
    comparison = json.loads(result.read_text())
    assert comparison["passed"] is False
    assert "changes_since_prior_period[0]" in comparison["structured_evidence_gaps"]
    assert "financial_definitions" in comparison["structured_evidence_gaps"]


def test_human_review_checklist_covers_sources_and_signoff(tmp_path: Path):
    checklist = build_review_checklist(Path("data/AMZN/report.json"), tmp_path / "review.md")
    text = checklist.read_text()
    assert "DDTL Facility" in text
    assert "Section 8.01" in text
    assert "five-Business-Day cure period" in text
    assert "First Amendment" in text
    assert "governing agreement: June 8, 2026 DDTL Credit Agreement" in text
    assert "Section 6.01** (agreement_defined)" in text
    assert "other short-term credit facilities increased from $152 million" in text
    assert "Evidence `E-" in text and "(reported / Note 7, Debt)" in text
    assert "Human verified" in text
    assert "Cloud comparison: ☐ Not run  ☐ Compared  ☐ Disagreements resolved" in text
    assert "deterministic SEC report remains authoritative" in text
    assert "Calculation: `$325 million - $152 million = $173 million increase`." in text


def test_review_state_is_hash_bound_and_fail_closed_until_all_actions_complete(tmp_path: Path):
    report = Path("data/AMZN/report.json")
    checklist = build_review_checklist(report, tmp_path / "review.md")
    state_path = initialize_review_state(report, checklist, tmp_path / "review-state.json", Path("data/AMZN/cloud-comparison.json"))
    state = json.loads(state_path.read_text())
    assert state["status"] == "machine_assembled"
    assert state["required_actions"]["provider_disagreements_resolved"] is False
    evidence_ids = list(state["evidence_items"])
    transition_review_state(state_path, "partially_reviewed", "Reviewer", "2026-09-05", ["report_facts_reviewed"], report, checklist, Path("data/AMZN/cloud-comparison.json"))
    import pytest
    with pytest.raises(ValueError, match="incomplete review actions"):
        transition_review_state(state_path, "human_verified", "Reviewer", "2026-09-05", ["agreement_sections_reviewed", "calculation_safety_reviewed"], report, checklist, Path("data/AMZN/cloud-comparison.json"))
    transition_review_state(state_path, "human_verified", "Reviewer", "2026-09-05", ["scope_and_period_reviewed", "agreement_sections_reviewed", "calculation_safety_reviewed", "provider_disagreements_resolved"], report, checklist, Path("data/AMZN/cloud-comparison.json"), completed_evidence_ids=evidence_ids)
    assert json.loads(state_path.read_text())["status"] == "human_verified"


def test_review_state_rejects_changed_provider_evidence(tmp_path: Path):
    report = Path("data/AMZN/report.json")
    checklist = build_review_checklist(report, tmp_path / "review.md")
    comparison = tmp_path / "comparison.json"
    comparison.write_text(Path("data/AMZN/cloud-comparison.json").read_text(), encoding="utf-8")
    state = initialize_review_state(report, checklist, tmp_path / "state.json", comparison)
    comparison.write_text(comparison.read_text() + "\nchanged", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="changed provider comparison"):
        transition_review_state(state, "partially_reviewed", "Reviewer", "2026-09-05", ["report_facts_reviewed"], report, checklist, comparison)


def test_review_state_binds_xbrl_corroboration(tmp_path: Path):
    report = Path("data/AMZN/report.json")
    checklist = build_review_checklist(report, tmp_path / "review.md")
    xbrl = Path("data/AMZN/xbrl-corroboration.json")
    state = initialize_review_state(report, checklist, tmp_path / "state.json", None, None, xbrl)
    xbrl_copy = tmp_path / "xbrl.json"
    xbrl_copy.write_text(xbrl.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="changed XBRL corroboration"):
        transition_review_state(state, "partially_reviewed", "Reviewer", "2026-09-05", ["report_facts_reviewed"], report, checklist, None, None, xbrl_copy)


def test_review_summary_separates_provider_gaps_and_out_of_scope_signals(tmp_path: Path):
    report = Path("data/AMZN/report.json")
    checklist = build_review_checklist(report, tmp_path / "review.md")
    state = initialize_review_state(report, checklist, tmp_path / "state.json", Path("data/AMZN/cloud-comparison.json"))
    summary = build_review_summary(
        report,
        Path("data/AMZN/cloud-comparison.json"),
        Path("data/AMZN/reducto-parse-audit.json"),
        state,
        tmp_path / "summary.md",
    )
    text = summary.read_text()
    assert "What is supported by parsed text" in text
    assert "Remaining structured-provider gaps" in text
    assert "ddtl_outstanding" in text
    assert "provider disagreements resolved" in text
    assert "Parse scope:" in text
    assert "filing-only annual context excluded" in text
    assert "SEC exhibit" in text


def test_cloud_comparison_handles_provider_value_wrappers(tmp_path: Path):
    cloud = tmp_path / "reducto.json"
    cloud.write_text(json.dumps([{
        "result": {
            "debt_instruments": [{"commitment": {"value": "$17.5 billion"}, "evidence": [{
                "document_id": {"value": "agreement.htm"},
                "locator": {"value": "Section 1.01"},
                "excerpt": {"value": "commitment"},
            }]}],
            "covenants": [],
        }
    }]), encoding="utf-8")
    result = json.loads(compare_cloud_output(cloud, Path("data/AMZN/report.json"), tmp_path / "comparison.json").read_text())
    assert result["structured_report_present"] is True
    assert result["evidence_provenance_gaps"] == []


def test_reducto_parse_audit_passes_presence_checks_for_cached_corpus(tmp_path: Path):
    result_path = audit_reducto_parse(
        Path("data/AMZN/corpus"),
        Path("data/AMZN/corpus-manifest.json"),
        tmp_path / "parse-audit.json",
    )
    result = json.loads(result_path.read_text())
    assert result["status"] == "parse_presence_only"
    assert result["human_verified"] is False
    assert result["passed"] is True
    assert len(result["documents"]) == 8
    hook = next(check for check in result["checks"] if check.get("check") == "Section 8.01")
    assert len(hook["evidence"]["excerpt"]) > len("8.01 events of default")
    assert "file:///" not in hook["evidence"]["excerpt"]
    assert "/data/" not in hook["evidence"]["excerpt"]
    assert result["evidence_excerpts_clean"] is True
    scope = next(check for check in result["checks"] if check.get("check") == "provider scope binding")
    assert scope["passed"] is True
    assert scope["provider_excluded_document_ids"] == ["0001018724-26-000004", "senior-notes-indenture", "senior-notes-supplemental-indenture"]
    assert len(result["corpus_manifest_sha256"]) == 64


def test_reducto_comparison_marks_filing_only_signals_out_of_scope(tmp_path: Path):
    cloud = tmp_path / "reducto.json"
    cloud.write_text(json.dumps([{"provider": "reducto", "document": "data/AMZN/corpus/ddtl-agreement/agreement.htm", "result": {"debt_instruments": [{"principal_amount": "US$17,500,000,000"}], "covenants": []}}]), encoding="utf-8")
    result = json.loads(compare_cloud_output(cloud, Path("data/AMZN/report.json"), tmp_path / "comparison.json").read_text())
    checks = {item["signal"]: item for item in result["checks"]}
    assert result["provider"] == "Reducto"
    assert checks["ddtl_outstanding"]["applicable"] is False
    assert checks["ddtl_commitment"]["found_in_cloud_output"] is True


def test_comparison_distinguishes_structured_gap_from_parse_text_support(tmp_path: Path):
    result = json.loads(compare_cloud_output(
        Path("data/AMZN/reducto-extract.json"),
        Path("data/AMZN/report.json"),
        tmp_path / "comparison.json",
        Path("data/AMZN/corpus-manifest.json"),
        Path("data/AMZN/reducto-parse-audit.json"),
    ).read_text())
    checks = {item["signal"]: item for item in result["checks"]}
    assert checks["events_of_default"]["found_in_cloud_output"] is False
    assert checks["events_of_default"]["parsed_text_support"] is True
    assert checks["remedies"]["parsed_text_support"] is True


def test_corpus_integrity_matches_all_recorded_artifacts():
    result = check_corpus_integrity(Path("data/AMZN/corpus-manifest.json"))
    assert result["passed"] is True
    assert len(result["checks"]) == 11


def test_corpus_integrity_resolves_relative_sources_from_manifest_root(tmp_path: Path, monkeypatch):
    manifest = Path("data/AMZN/corpus-manifest.json").resolve()
    decoy = tmp_path / "data/AMZN/corpus"
    decoy.mkdir(parents=True)
    (decoy / "0001018724-26-000014").mkdir()
    (decoy / "0001018724-26-000014" / "0001018724-26-000014-amzn-20260331.htm").write_text("decoy", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_corpus_integrity(manifest)
    assert result["passed"] is True


def test_corpus_integrity_fails_closed_on_changed_artifact(tmp_path: Path):
    source = tmp_path / "artifact.htm"
    source.write_text("original", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "documents": [{
            "document_id": "fixture",
            "source_file": str(source),
            "source_sha256": hashlib.sha256(b"original").hexdigest(),
        }]
    }), encoding="utf-8")
    source.write_text("changed", encoding="utf-8")

    result = check_corpus_integrity(manifest)

    assert result["passed"] is False
    assert result["checks"][0]["passed"] is False
