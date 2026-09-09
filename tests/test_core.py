import json
from pathlib import Path

from ccrm.schema import Covenant


def test_no_financial_covenant_is_not_calculable():
    covenant = Covenant(
        name="Financial covenants",
        covenant_type="financial covenant absence",
        applicable_instrument="DDTL Facility",
        status="not_calculable",
        maintenance_or_incurrence="No financial covenant",
    )
    assert covenant.status == "not_calculable"
    assert covenant.estimated_headroom is None


def test_corpus_manifest_has_quarterly_and_annual_context():
    manifest = json.loads(Path("data/AMZN/corpus-manifest.json").read_text())
    assert manifest["issuer"] == "AMZN"
    assert len(manifest["documents"]) == 11  # quarterly/annual filings, DDTL exhibit, revolving amendments, and Senior Notes indenture context


def test_copied_filing_manifest_matches_local_artifact():
    manifest = json.loads(Path("data/AMZN/corpus/0001018724-26-000026/manifest.json").read_text())
    source = Path(manifest["source_file"])
    assert source.exists()
    import hashlib
    assert manifest["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
