from ccrm.compare import classify_amzn_changes, extract_amzn_snapshot
from ccrm.schema import Covenant
from ccrm.coverage import build_issuer_coverage
from ccrm.issuer_config import build_issuer_config
from ccrm.review_queue import build_review_queue


def test_public_schema_preserves_safe_not_calculable_boundary():
    covenant = Covenant(
        name="Financial covenants",
        covenant_type="financial covenant absence",
        applicable_instrument="DDTL Facility",
        status="not_calculable",
        maintenance_or_incurrence="No financial covenant",
    )
    assert covenant.estimated_headroom is None


def test_public_period_parser_detects_zero_draw_and_balance_change():
    text = "We entered into a $ 17.5 billion unsecured delayed draw term loan. No borrowings outstanding under the Term Loan as of June 30, 2026. There were $ 455 million and $ 325 million of borrowings outstanding under these facilities as of December 31, 2025 and June 30, 2026."
    snapshot = extract_amzn_snapshot(text, "June 30, 2026")
    assert snapshot.ddtl_present is True
    assert snapshot.ddtl_outstanding == "$0"
    assert snapshot.short_term_outstanding == "$325 million"


def test_public_change_classifier_is_deterministic():
    prior = extract_amzn_snapshot("No borrowings outstanding under the Term Loan as of March 31, 2026.", "March 31, 2026")
    current = extract_amzn_snapshot("No borrowings outstanding under the Term Loan as of June 30, 2026.", "June 30, 2026")
    assert classify_amzn_changes(prior, current) == []


def test_public_issuer_coverage_is_source_only(tmp_path):
    radar = tmp_path / "radar" / "data" / "AAPL" / "one"
    radar.mkdir(parents=True)
    source = radar / "aapl.htm"
    source.write_text("SEC filing", encoding="utf-8")
    (radar / "manifest.json").write_text(__import__("json").dumps({"filing": {"accession_number": "1", "form": "10-Q", "report_date": "2026-06-27", "source_url": "https://www.sec.gov/example"}, "source_file": "data/AAPL/one/aapl.htm"}), encoding="utf-8")
    result = __import__("json").loads(build_issuer_coverage(tmp_path / "radar", "AAPL", tmp_path / "coverage.json").read_text())
    assert result["status"] == "source_scoped"
    assert result["customer_ready"] is False
    assert result["report_dates"] == ["2026-06-27"]


def test_public_issuer_config_draft_preserves_source_only_boundary(tmp_path):
    coverage = tmp_path / "coverage.json"
    coverage.write_text(__import__("json").dumps({
        "issuer": "AAPL",
        "status": "source_scoped",
        "documents": [
            {"form": "10-Q", "report_date": "2026-03-28", "accession": "prior"},
            {"form": "10-Q", "report_date": "2026-06-27", "accession": "latest"},
            {"form": "10-K", "report_date": "2025-09-27", "accession": "annual"},
        ],
    }), encoding="utf-8")
    result = __import__("json").loads(build_issuer_config(coverage, tmp_path / "config.json").read_text())
    assert result["status"] == "configuration_draft"
    assert result["credit_report_enabled"] is False
    assert result["selected_latest_10q"]["accession"] == "latest"
    assert result["selected_prior_10q"]["accession"] == "prior"


def test_public_review_queue_keeps_human_approval_as_release_gate(tmp_path):
    issuer_dir = tmp_path / "AMZN"
    issuer_dir.mkdir()
    (issuer_dir / "agent-review.json").write_text(__import__("json").dumps({
        "status": "agent_reviewed",
        "exceptions": [{"topic": "covenant capacity", "severity": "material", "detail": "Headroom is not calculable.", "evidence_ids": ["E-1"]}],
    }), encoding="utf-8")
    (issuer_dir / "report.json").write_text(__import__("json").dumps({"as_of": "June 30, 2026"}), encoding="utf-8")
    (issuer_dir / "review-state.json").write_text(__import__("json").dumps({"status": "agent_reviewed"}), encoding="utf-8")
    result = __import__("json").loads(build_review_queue(issuer_dir, issuer_dir / "review-queue.json").read_text())
    assert result["human_approval_required"] is True
    assert result["items"][0]["status"] == "open"
    assert result["items"][0]["owner"] is None
