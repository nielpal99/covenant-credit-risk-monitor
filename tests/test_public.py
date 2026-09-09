from ccrm.compare import classify_amzn_changes, extract_amzn_snapshot
from ccrm.schema import Covenant


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
