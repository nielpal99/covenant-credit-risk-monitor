import json
import hashlib
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from llama_cloud import LlamaCloud

from .schema import Report


def _client() -> LlamaCloud:
    load_dotenv(Path(".env"))
    if not os.getenv("LLAMA_CLOUD_API_KEY"):
        raise RuntimeError("LLAMA_CLOUD_API_KEY is not set")
    if os.getenv("LLAMA_CLOUD_COST_AUTHORIZED") != "1":
        raise PermissionError("LlamaCloud execution is cost-gated; set LLAMA_CLOUD_COST_AUTHORIZED=1 only after approving the bounded run")
    return LlamaCloud(api_key=os.environ["LLAMA_CLOUD_API_KEY"])


def _parse_result_text(result: Any) -> tuple[str, list[dict[str, Any]]]:
    """Normalize supported Parse response shapes and reject empty output."""
    markdown_obj = getattr(result, "markdown", None)
    pages = getattr(markdown_obj, "pages", None) or []
    if pages:
        page_texts = []
        metadata = []
        for index, page in enumerate(pages):
            value = getattr(page, "markdown", None) or getattr(page, "text", None) or ""
            value = str(value)
            page_texts.append(value)
            metadata.append({"page": getattr(page, "page_number", index + 1), "characters": len(value), "excerpt": value[:500]})
        text = "\n\n".join(page_texts).strip()
    else:
        text = str(getattr(result, "text", None) or getattr(markdown_obj, "text", None) or "").strip()
        metadata = [{"page": 1, "characters": len(text), "excerpt": text[:500]}] if text else []
    if not text:
        raise RuntimeError("LlamaCloud Parse returned no usable text; refusing to cache an empty artifact")
    return text, metadata


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _usable_cached_parse(path: Path, source: Path | None = None) -> bool:
    try:
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            return False
        if source is None:
            return True
        metadata = json.loads((path.parent / "metadata.json").read_text(encoding="utf-8"))
        return metadata.get("source_sha256") == _sha256(source)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False


def _usable_cached_extract(path: Path, parsed_documents: list[Path] | None = None) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or len(payload) != 3 or not all(
            isinstance(item, dict) and item.get("document") and "result" in item
            for item in payload
        ):
            return False
        if parsed_documents is None:
            return True
        expected = {str(source): _sha256(source) for source in parsed_documents}
        return all(item.get("document") in expected and item.get("input_sha256") == expected[item["document"]] for item in payload)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False


def parse_document(source: Path, output_dir: Path, force: bool = False) -> Path:
    """Parse one document with the current unified LlamaCloud SDK."""
    cached = output_dir / "content.md"
    if not force and _usable_cached_parse(cached, source):
        return cached
    client = _client()
    output_dir.mkdir(parents=True, exist_ok=True)
    uploaded = client.files.create(file=str(source), purpose="parse")
    result = client.parsing.parse(
        file_id=uploaded.id,
        tier=os.getenv("LLAMA_PARSE_TIER", "agentic"),
        version="latest",
        expand=["text", "markdown", "items", "images_content_metadata"],
        output_options={"markdown": {"tables": {"output_tables_as_markdown": True}}},
        processing_options={"ocr_parameters": {"languages": ["en"]}},
    )
    markdown, page_metadata = _parse_result_text(result)
    (output_dir / "content.md").write_text(markdown, encoding="utf-8")
    (output_dir / "metadata.json").write_text(json.dumps({"page_count": len(page_metadata), "source": str(source), "source_sha256": _sha256(source), "pages": page_metadata}, indent=2), encoding="utf-8")
    return cached


def extract_report(parsed_documents: list[Path], output: Path, force: bool = False) -> Path:
    """Run one explicit LlamaExtract job over the selected prototype documents."""
    allowed_agreements = {"ddtl-agreement", "revolving-amendment-364", "revolving-amendment-five-year"}
    if len(parsed_documents) != 3 or any(source.parent.parent.name not in allowed_agreements for source in parsed_documents):
        raise ValueError("Extract is bounded to exactly the three approved agreement documents")
    for source in parsed_documents:
        agreement_source = source.parent.parent / "agreement.htm"
        if not _usable_cached_parse(source, agreement_source):
            raise RuntimeError(f"Parsed Extract input is missing, empty, or stale: {source}")
    if output.exists() and not force and _usable_cached_extract(output, parsed_documents):
        return output
    client = _client()
    output.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for source in parsed_documents:
        uploaded = client.files.create(file=str(source), purpose="extract")
        job = client.extract.run(
            file_input=uploaded.id,
            configuration={
                "data_schema": Report.model_json_schema(),
                "tier": os.getenv("LLAMA_EXTRACT_TIER", "agentic"),
            },
        )
        result = getattr(job, "extract_result", job)
        if hasattr(result, "model_dump"):
            result = result.model_dump()
        results.append({"document": str(source), "input_sha256": _sha256(source), "result": result})
    output.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    return output
