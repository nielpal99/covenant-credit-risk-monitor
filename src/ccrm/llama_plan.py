import json
import hashlib
from pathlib import Path


AGREEMENT_FOLDERS = {"ddtl-agreement", "revolving-amendment-364", "revolving-amendment-five-year"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounded_source_documents(corpus: Path) -> list[Path]:
    sources = sorted(corpus.glob("*/**/*.htm"))
    # Annual filings are retained in the report corpus as filing-only context;
    # the historical provider plan remains the eight-document cached run.
    filing_only = {
        str(d.get("source_file"))
        for d in json.loads((corpus.parent / "corpus-manifest.json").read_text(encoding="utf-8")).get("documents", [])
        if d.get("filing_only") or d.get("provider_excluded")
    }
    sources = [source for source in sources if str(source) not in filing_only]
    agreement_sources = [source for source in sources if source.relative_to(corpus).parts[0] in AGREEMENT_FOLDERS]
    if len(sources) != 8 or len(agreement_sources) != 3:
        raise ValueError(f"Expected exactly 8 bounded corpus documents and 3 agreement documents; found {len(sources)} and {len(agreement_sources)}")
    return sources


def bounded_agreement_parsed_documents(corpus: Path) -> list[Path]:
    parsed = sorted(
        source for source in corpus.glob("*/parsed/content.md")
        if source.parent.parent.name in AGREEMENT_FOLDERS
    )
    if len(parsed) != 3:
        raise ValueError(f"Expected exactly 3 parsed agreement documents for Extract; found {len(parsed)}")
    return parsed


def _validation_checks(documents: list[dict], index_or_batch_planned: bool, corpus_root: Path | None = None) -> list[dict]:
    def is_agreement_document(document: dict) -> bool:
        parts = Path(document.get("path", "")).parts
        return bool(parts) and parts[0] in AGREEMENT_FOLDERS

    def is_bound(document: dict) -> bool:
        if corpus_root is None:
            return False
        relative = Path(document.get("path", ""))
        absolute = Path(document.get("absolute_path", ""))
        if not relative or relative.is_absolute() or not absolute.is_absolute():
            return False
        try:
            resolved_root = corpus_root.resolve()
            resolved = (resolved_root / relative).resolve()
            resolved.relative_to(resolved_root)
        except ValueError:
            return False
        return absolute.resolve() == resolved

    source_paths_bound = all(is_bound(document) for document in documents)
    source_integrity_ok = corpus_root is not None and all(
        document.get("sha256") == _sha256(Path(document.get("absolute_path", "")))
        for document in documents
        if Path(document.get("absolute_path", "")).is_file()
    ) and all(Path(document.get("absolute_path", "")).is_file() for document in documents)
    return [
        {"name": "bounded document count", "passed": 0 < len(documents) <= 8},
        {"name": "all local sources exist", "passed": bool(documents) and all(Path(d.get("absolute_path", "")).is_file() for d in documents)},
        {"name": "source path binding", "passed": source_paths_bound},
        {"name": "source integrity", "passed": source_integrity_ok},
        {"name": "parse coverage", "passed": all(d.get("parse") is True for d in documents)},
        {"name": "extract scope", "passed": all(d.get("extract") is is_agreement_document(d) for d in documents)},
        {"name": "no index or batch", "passed": index_or_batch_planned is False},
    ]


def validate_llama_plan(plan_path: Path) -> dict:
    """Validate a persisted no-upload plan without making external calls."""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    documents = plan.get("documents", [])
    corpus_root_value = plan.get("corpus_root")
    corpus_root = Path(corpus_root_value).resolve() if corpus_root_value else None
    checks = _validation_checks(documents, plan.get("index_or_batch_planned"), corpus_root)
    return {"passed": all(check["passed"] for check in checks), "checks": checks}


def build_llama_plan(corpus: Path, output: Path) -> Path:
    """Create a no-upload plan for one bounded corpus."""
    sources = bounded_source_documents(corpus)
    documents = []
    for source in sources:
        relative = source.relative_to(corpus)
        is_agreement = relative.parts[0] in {"ddtl-agreement", "revolving-amendment-364", "revolving-amendment-five-year"}
        documents.append({
            "path": str(relative),
            "absolute_path": str(source.resolve()),
            "bytes": source.stat().st_size,
            "sha256": _sha256(source),
            "parse": True,
            "extract": is_agreement,
            "purpose": "agreement or amendment" if is_agreement else "SEC filing context",
        })
    result = {
        "issuer": "AMZN",
        "corpus_root": str(corpus.resolve()),
        "external_calls_made": 0,
        "cost_authorization_required": True,
        "parse_jobs_planned": sum(1 for d in documents if d["parse"]),
        "extract_jobs_planned": sum(1 for d in documents if d["extract"]),
        "index_or_batch_planned": False,
        "cost_estimate": "Not estimated: pricing depends on the configured LlamaCloud tier and account plan; confirm before upload.",
        "validation_gates": [
            "Compare extracted debt and covenant fields against deterministic SEC evidence.",
            "Require source locator and excerpt for every populated field.",
            "Reject any headroom value unless exact definition, period, inputs, exclusions, and agreement version are present.",
        ],
        "documents": documents,
    }
    result["validation"] = {"passed": True, "checks": _validation_checks(documents, result["index_or_batch_planned"], corpus.resolve())}
    result["validation"]["passed"] = all(check["passed"] for check in result["validation"]["checks"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return output
