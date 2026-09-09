"""No-upload audit of Reducto Parse caches against the bounded SEC corpus."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


REQUIRED_AGREEMENT_HOOKS = {
    "Section 6.01": "6.01 financial statements",
    "Section 6.02": "6.02 certificates",
    "Section 6.03": "6.03 notices",
    "Section 7.01": "7.01 liens",
    "Section 7.02": "7.02 fundamental changes",
    "Section 8.01": "8.01 events of default",
    "Section 8.02": "8.02 remedies upon event of default",
    "Default cure": "five business days",
    "Amendment text": "first amendment",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_urls(manifest: dict[str, Any]) -> dict[str, str]:
    return {
        d.get("document_id") or d.get("filing", {}).get("accession_number"): d.get("sec_url") or d.get("filing", {}).get("source_url")
        for d in manifest.get("documents", [])
    }


def _context_excerpt(text: str, phrase: str, radius: int = 360) -> str:
    lowered = text.lower()
    needle = phrase.lower()
    candidates: list[tuple[int, int]] = []
    cursor = 0
    while True:
        index = lowered.find(needle, cursor)
        if index < 0:
            break
        context = lowered[max(0, index - radius): min(len(text), index + len(phrase) + radius)]
        score = 0
        score += 5 if "file:///" not in context else -10
        score += 2 if "## " in context else 0
        score += 2 if any(word in context for word in ("shall", "deliver", "borrower", "administrative agent")) else 0
        score += 7 if f"{needle}." in context else 0
        score += 4 if any(word in context for word in ("if any event of default occurs", "take any or all", "within 120 days")) else 0
        if needle == "five business days":
            score += 4 if "principal" in context and "interest" in context else 0
        candidates.append((score, index))
        cursor = index + 1
    start = max(candidates, default=(0, -1))[1]
    if start < 0:
        return phrase
    left = max(0, start - radius)
    right = min(len(text), start + len(phrase) + radius)
    excerpt = " ".join(text[left:right].split())
    # Reducto's rendered-text cache can prefix a substantive passage with a
    # local renderer path, page counter, and timestamp. Those are not source
    # evidence and must not leak into reviewer-facing excerpts.
    excerpt = re.sub(r"(?:file:///|/Users/|/data/)[^\s]+", "", excerpt)
    excerpt = re.sub(r"\b\d+/\d+\s+\d+/\d+/\d+,\s+\d+:\d+\s+[AP]M\b", "", excerpt)
    return " ".join(excerpt.split()).strip()


def audit_reducto_parse(corpus: Path, manifest_path: Path, output: Path) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    urls = _manifest_urls(manifest)
    manifest_ids = {
        d.get("document_id") or d.get("filing", {}).get("accession_number")
        for d in manifest.get("documents", [])
    }
    expected_provider_ids = {
        d.get("document_id") or d.get("filing", {}).get("accession_number")
        for d in manifest.get("documents", [])
        if not d.get("filing_only") and not d.get("provider_excluded")
    }
    documents: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for parsed in sorted(corpus.glob("*/reducto-parsed/content.md")):
        source_artifact = parsed.parent.parent / "agreement.htm"
        if not source_artifact.is_file():
            candidates = list(parsed.parent.parent.glob("*.htm"))
            source_artifact = candidates[0] if candidates else source_artifact
        document_id = parsed.parent.parent.name
        text = parsed.read_text(encoding="utf-8")
        metadata_path = parsed.parent / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
        expected_hash = _sha256(source_artifact) if source_artifact.is_file() else None
        integrity = bool(text.strip()) and metadata.get("provider") == "reducto" and metadata.get("source_sha256") == expected_hash
        checks.append({"document_id": document_id, "check": "non-empty source-bound Parse cache", "passed": integrity})
        documents.append({
            "document_id": document_id,
            "source": str(source_artifact),
            "sec_url": urls.get(document_id),
            "source_sha256": expected_hash,
            "parsed_sha256": _sha256(parsed),
            "characters": len(text),
        })
        if document_id in {"ddtl-agreement", "revolving-amendment-364", "revolving-amendment-five-year"}:
            normalized = " ".join(text.lower().split())
            for name, phrase in REQUIRED_AGREEMENT_HOOKS.items():
                if name == "Amendment text" and document_id == "ddtl-agreement":
                    continue
                checks.append({
                    "document_id": document_id,
                    "check": name,
                    "passed": phrase in normalized,
                    "evidence": {
                        "document_id": document_id,
                        "sec_url": urls.get(document_id),
                        "locator": f"Reducto Parse text — {name}",
                        "excerpt": _context_excerpt(text, phrase),
                        "kind": "provider_parse_presence",
                        "human_verified": False,
                    },
                })
    evidence_excerpts_clean = all(
        not any(marker in check.get("evidence", {}).get("excerpt", "") for marker in ("file:///", "/Users/", "/data/", "localhost:"))
        for check in checks
        if check.get("evidence")
    )
    parsed_ids = {document["document_id"] for document in documents}
    provider_scope_ok = (
        len(documents) == 8
        and parsed_ids == expected_provider_ids
        and parsed_ids.issubset(manifest_ids)
        and all(document.get("sec_url") for document in documents)
    )
    checks.append({
        "check": "provider scope binding",
        "passed": provider_scope_ok,
        "expected_document_count": len(expected_provider_ids),
        "actual_document_count": len(documents),
        "provider_excluded_document_ids": sorted(manifest_ids - expected_provider_ids),
    })
    result = {
        "provider": "Reducto",
        "status": "parse_presence_only",
        "human_verified": False,
        "corpus_manifest": str(manifest_path),
        "corpus_manifest_sha256": _sha256(manifest_path),
        "provider_scope": "eight non-filing-only corpus documents; filing-only annual context excluded",
        "documents": documents,
        "checks": checks,
        "passed": bool(documents) and all(check["passed"] for check in checks) and evidence_excerpts_clean,
        "evidence_excerpts_clean": evidence_excerpts_clean,
        "note": "Presence checks show that Reducto Parse retained text containing the hook; they do not replace human verification of the cited SEC exhibit.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return output
