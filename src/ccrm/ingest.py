import json
import hashlib
import os
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


ISSUER = "AMZN"
DDTL_ACCESSION = "0001104659-26-072140"


def _sec_session() -> requests.Session:
    user_agent = os.getenv("SEC_USER_AGENT", "Covenant Credit Risk Monitor research contact@example.com")
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
    return session


def _copy_manifest(filing_radar: Path, destination: Path, accession: str) -> dict:
    source_manifest = filing_radar / "data" / ISSUER / accession / "manifest.json"
    if not source_manifest.exists():
        if accession != "0001018724-26-000004":
            raise FileNotFoundError(source_manifest)
        payload = {
            "filing": {
                "ticker": ISSUER, "cik": "0001018724", "accession_number": accession,
                "form": "10-K", "filing_date": "2026-02-06", "report_date": "2025-12-31",
                "primary_document": "amzn-20251231.htm",
                "source_url": "https://www.sec.gov/Archives/edgar/data/1018724/000101872426000004/amzn-20251231.htm",
            },
            "source_file": "amzn-20251231.htm",
            "parser": None,
            "filing_only": True,
            "role": "latest annual context",
        }
    else:
        payload = json.loads(source_manifest.read_text(encoding="utf-8"))
    destination.mkdir(parents=True, exist_ok=True)
    source = Path(payload["source_file"])
    if source_manifest.exists() and not source.is_absolute():
        source = filing_radar / source
    target = destination / source.name
    if source.exists():
        target.write_bytes(source.read_bytes())
    else:
        response = _sec_session().get(payload["filing"]["source_url"], timeout=60)
        response.raise_for_status()
        target.write_bytes(response.content)
    payload["source_file"] = str(target)
    payload["source_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    (destination / "manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def ingest_amzn(filing_radar: Path, output: Path) -> Path:
    """Create the quarterly prototype corpus plus latest annual filing context."""
    corpus = output / ISSUER / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    accessions = [
        "0001018724-26-000014",  # Q1 10-Q
        "0001018724-26-000026",  # Q2 10-Q
        "0001018724-26-000004",  # latest annual 10-K, filing-only context
        DDTL_ACCESSION,           # agreement 8-K
        "0001018724-26-000012",  # Q1 earnings 8-K
        "0001018724-26-000024",  # Q2 earnings 8-K
    ]
    records = [_copy_manifest(filing_radar, corpus / accession, accession) for accession in accessions]
    records_by_accession = {record["filing"]["accession_number"]: record for record in records}

    agreement_dir = corpus / "ddtl-agreement"
    agreement_dir.mkdir(exist_ok=True)
    eight_k = Path(records_by_accession[DDTL_ACCESSION]["source_file"])
    soup = BeautifulSoup(eight_k.read_bytes(), "html.parser")
    exhibit_href = next(a["href"] for a in soup.find_all("a", href=True) if "tm2613616d4_ex10-1.htm" in a["href"])
    sec_url = urljoin(records_by_accession[DDTL_ACCESSION]["filing"]["source_url"], exhibit_href)
    response = _sec_session().get(sec_url, timeout=60)
    response.raise_for_status()
    (agreement_dir / "agreement.htm").write_bytes(response.content)
    agreement_meta = {"document_id": "ddtl-agreement", "sec_url": sec_url, "source_file": str(agreement_dir / "agreement.htm"), "source_sha256": hashlib.sha256((agreement_dir / "agreement.htm").read_bytes()).hexdigest(), "source_8k": records_by_accession[DDTL_ACCESSION]["filing"]}
    (agreement_dir / "manifest.json").write_text(json.dumps(agreement_meta, indent=2), encoding="utf-8")
    q2_source = corpus / "0001018724-26-000026" / Path(records_by_accession["0001018724-26-000026"]["source_file"]).name
    q2_soup = BeautifulSoup(q2_source.read_bytes(), "html.parser")
    amendment_docs = []
    for document_id, href_name, label in [
        ("revolving-amendment-364", "amzn-20260630xex102.htm", "Exhibit 10.2"),
        ("revolving-amendment-five-year", "amzn-20260630xex103.htm", "Exhibit 10.3"),
    ]:
        href = next(a["href"] for a in q2_soup.find_all("a", href=True) if href_name in a["href"])
        amendment_url = urljoin(records_by_accession["0001018724-26-000026"]["filing"]["source_url"], href)
        amendment_dir = corpus / document_id
        amendment_dir.mkdir(exist_ok=True)
        amendment_response = _sec_session().get(amendment_url, timeout=60)
        amendment_response.raise_for_status()
        (amendment_dir / "agreement.htm").write_bytes(amendment_response.content)
        amendment_docs.append({"document_id": document_id, "label": label, "sec_url": amendment_url, "source_file": str(amendment_dir / "agreement.htm"), "source_sha256": hashlib.sha256((amendment_dir / "agreement.htm").read_bytes()).hexdigest(), "source_10q": records[1]["filing"]})
    annual_source = corpus / "0001018724-26-000004" / Path(records_by_accession["0001018724-26-000004"]["source_file"]).name
    annual_soup = BeautifulSoup(annual_source.read_bytes(), "html.parser")
    indenture_docs = []
    for document_id, href_name, label in [
        ("senior-notes-indenture", "d445039dex401.htm", "2012 senior-notes indenture"),
        ("senior-notes-supplemental-indenture", "d325485dex41.htm", "2022 supplemental senior-notes indenture"),
    ]:
        href = next(a["href"] for a in annual_soup.find_all("a", href=True) if href_name in a["href"])
        indenture_url = urljoin(records_by_accession["0001018724-26-000004"]["filing"]["source_url"], href)
        indenture_dir = corpus / document_id
        indenture_dir.mkdir(exist_ok=True)
        response = _sec_session().get(indenture_url, timeout=60)
        response.raise_for_status()
        (indenture_dir / "agreement.htm").write_bytes(response.content)
        indenture_docs.append({"document_id": document_id, "label": label, "sec_url": indenture_url, "source_file": str(indenture_dir / "agreement.htm"), "source_sha256": hashlib.sha256((indenture_dir / "agreement.htm").read_bytes()).hexdigest(), "source_10k": records_by_accession["0001018724-26-000004"]["filing"], "provider_excluded": True, "role": label})
    (output / ISSUER / "corpus-manifest.json").write_text(json.dumps({"issuer": ISSUER, "documents": records + [agreement_meta] + amendment_docs + indenture_docs}, indent=2), encoding="utf-8")
    return output / ISSUER / "corpus-manifest.json"
