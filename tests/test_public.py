from ccrm.compare import classify_amzn_changes, extract_amzn_snapshot
from ccrm.schema import Covenant
from ccrm.coverage import build_issuer_coverage


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
