"""Bounded Reducto Parse/Extract adapter.

The adapter deliberately uses the HTTP API rather than a provider SDK so the
prototype has one small, inspectable integration surface. Credentials are read
from the environment and are never written to cache files.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from .schema import Report

BASE_URL = "https://platform.reducto.ai"
AGREEMENT_FOLDERS = {
    "ddtl-agreement",
    "revolving-amendment-364",
    "revolving-amendment-five-year",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _api_key() -> str:
    load_dotenv(Path(".env"))
    key = os.getenv("REDUCTO_API_KEY")
    if not key:
        raise RuntimeError("REDUCTO_API_KEY is not set")
    if os.getenv("REDUCTO_COST_AUTHORIZED") != "1":
        raise PermissionError(
            "Reducto execution is cost-gated; set REDUCTO_COST_AUTHORIZED=1 only after approving the bounded run"
        )
    return key


def _headers(key: str, content_type: bool = False) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {key}"}
    if content_type:
        headers["Content-Type"] = "application/json"
    return headers


def _request(response: requests.Response) -> Any:
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"Reducto returned non-JSON response (HTTP {response.status_code})") from exc
    if not response.ok:
        detail = payload.get("detail") if isinstance(payload, dict) else None
        raise RuntimeError(f"Reducto request failed (HTTP {response.status_code}): {detail or 'unknown error'}")
    return payload


def _upload(path: Path, key: str) -> str:
    path = _uploadable_source(path)
    with path.open("rb") as handle:
        response = requests.post(
            f"{BASE_URL}/upload",
            headers=_headers(key),
            files={"file": (path.name, handle, "application/octet-stream")},
            timeout=300,
        )
    payload = _request(response)
    file_id = payload.get("file_id") if isinstance(payload, dict) else None
    if not file_id:
        raise RuntimeError("Reducto upload returned no file_id")
    return str(file_id)


def _chrome_binary() -> str:
    candidates = [
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("Reducto needs a local HTML renderer; Google Chrome or Chromium was not found")


def _uploadable_source(source: Path) -> Path:
    """Render SEC HTML to a cached PDF because Reducto rejects HTML uploads."""
    if source.suffix.lower() not in {".htm", ".html", ".xhtml"}:
        return source
    rendered = source.parent / "reducto-input.pdf"
    metadata_path = source.parent / "reducto-input.json"
    source_hash = _sha256(source)
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("source_sha256") == source_hash and rendered.stat().st_size > 0:
            return rendered
    except (OSError, UnicodeError, json.JSONDecodeError):
        pass
    rendered_tmp = rendered.with_suffix(".tmp.pdf")
    command = [
        _chrome_binary(),
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=1000",
        f"--print-to-pdf={rendered_tmp}",
        source.resolve().as_uri(),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Could not render SEC HTML for Reducto: {exc}") from exc
    if completed.returncode != 0 or not rendered_tmp.is_file() or rendered_tmp.stat().st_size == 0:
        rendered_tmp.unlink(missing_ok=True)
        raise RuntimeError("Could not render SEC HTML for Reducto as a non-empty PDF")
    rendered_tmp.replace(rendered)
    metadata_path.write_text(
        json.dumps({"provider": "reducto", "source": str(source), "source_sha256": source_hash, "rendered": str(rendered), "rendered_sha256": _sha256(rendered), "renderer": "Chrome headless"}, indent=2),
        encoding="utf-8",
    )
    return rendered


def _parse_payload(file_id: str) -> dict[str, Any]:
    return {
        "input": file_id,
        "retrieval": {"chunking": {"chunk_mode": "disabled"}},
        "formatting": {"table_output_format": "dynamic"},
        "settings": {"persist_results": True},
    }


def _extract_payload(file_id: str, source: Path) -> dict[str, Any]:
    # Keep this schema deliberately flat. Reducto accepts JSON Schema, but the
    # full Pydantic report schema contains $defs/ref graphs that are not needed
    # for agreement review and can cause opaque provider errors.
    evidence = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string"},
                "locator": {"type": "string"},
                "excerpt": {"type": "string"},
            },
            "required": ["locator", "excerpt"],
        },
    }
    schema = {
        "type": "object",
        "properties": {
            "debt_instruments": {"type": "array", "items": {"type": "object"}},
            "covenants": {"type": "array", "items": {"type": "object"}},
            "financial_definitions": {"type": "object"},
            "risk_status": {"type": "object"},
            "changes_since_prior_period": {"type": "array", "items": {"type": "object"}},
            "evidence": evidence,
        },
        "required": ["debt_instruments", "covenants", "evidence"],
    }
    return {
        "input": file_id,
        "instructions": {
            "schema": schema,
            "system_prompt": (
                f"Extract only debt, covenant, definitions, risk-status, and change facts from {source.name}. "
                "supported by this agreement. Do not invent financial covenants, balances, "
                "periods, SEC URLs, or evidence excerpts. Use null or empty collections when "
                "the agreement does not support a value."
            ),
        },
        "settings": {
            "citations": {"enabled": True, "numerical_confidence": True, "parent_block": "full"},
            "persist_results": True,
        },
    }


def _download_url(url: str) -> Any:
    """Download Reducto's presigned URL result without adding bearer auth."""
    response = requests.get(url, timeout=300)
    if not response.ok:
        raise RuntimeError(f"Reducto URL result download failed (HTTP {response.status_code})")
    try:
        return response.json()
    except ValueError:
        return response.text


def _parse_content(payload: dict[str, Any], key: str) -> tuple[str, list[dict[str, Any]]]:
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Reducto Parse returned no structured result")
    if result.get("type") == "url":
        url = result.get("url") or result.get("result_url")
        if not url:
            raise RuntimeError("Reducto Parse returned a URL result without a URL")
        downloaded = _download_url(str(url))
        if isinstance(downloaded, str):
            try:
                downloaded = json.loads(downloaded)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Reducto URL result was neither JSON nor parse content") from exc
        result = downloaded.get("result", downloaded) if isinstance(downloaded, dict) else {}
    chunks = result.get("chunks", []) if isinstance(result, dict) else []
    if not isinstance(chunks, list):
        raise RuntimeError("Reducto Parse returned invalid chunks")
    contents: list[str] = []
    pages: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            continue
        content = str(chunk.get("content") or "").strip()
        if content:
            contents.append(content)
        blocks = chunk.get("blocks") or []
        page_numbers = [
            block.get("bbox", {}).get("page")
            for block in blocks
            if isinstance(block, dict) and isinstance(block.get("bbox"), dict) and block["bbox"].get("page")
        ]
        pages.append({"chunk": index, "pages": sorted(set(page_numbers)), "characters": len(content), "excerpt": content[:500]})
    text = "\n\n".join(contents).strip()
    if not text:
        raise RuntimeError("Reducto Parse returned no usable text; refusing to cache an empty artifact")
    return text, pages


def _usable_cached_parse(path: Path, source: Path | None = None) -> bool:
    try:
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            return False
        if source is None:
            return True
        metadata = json.loads((path.parent / "metadata.json").read_text(encoding="utf-8"))
        return metadata.get("source_sha256") == _sha256(source) and metadata.get("provider") == "reducto"
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False


def parse_document(source: Path, output_dir: Path, force: bool = False) -> Path:
    cached = output_dir / "content.md"
    if not force and _usable_cached_parse(cached, source):
        return cached
    key = _api_key()
    output_dir.mkdir(parents=True, exist_ok=True)
    file_id = _upload(source, key)
    response = _request(
        requests.post(
            f"{BASE_URL}/parse",
            headers=_headers(key, content_type=True),
            json=_parse_payload(file_id),
            timeout=900,
        )
    )
    text, pages = _parse_content(response, key)
    cached.write_text(text, encoding="utf-8")
    (output_dir / "metadata.json").write_text(
        json.dumps(
            {
                "provider": "reducto",
                "source": str(source),
                "source_sha256": _sha256(source),
                "job_id": response.get("job_id"),
                "studio_link": response.get("studio_link"),
                "usage": response.get("usage"),
                "page_count": len(pages),
                "pages": pages,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return cached


def extract_report(agreement_sources: list[Path], output: Path, force: bool = False) -> Path:
    if len(agreement_sources) != 3 or any(source.parent.name not in AGREEMENT_FOLDERS for source in agreement_sources):
        raise ValueError("Reducto Extract is bounded to exactly the three approved agreement documents")
    if output.exists() and not force:
        try:
            cached = json.loads(output.read_text(encoding="utf-8"))
            expected = {str(source): _sha256(source) for source in agreement_sources}
            if isinstance(cached, list) and len(cached) == 3 and all(
                isinstance(item, dict) and item.get("document") in expected and item.get("input_sha256") == expected[item["document"]] and "result" in item
                for item in cached
            ):
                return output
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
    key = _api_key()
    output.parent.mkdir(parents=True, exist_ok=True)
    results = []
    partial = output.with_suffix(output.suffix + ".partial")
    results = []
    if not force and partial.exists():
        try:
            candidate = json.loads(partial.read_text(encoding="utf-8"))
            expected = {str(source): _sha256(source) for source in agreement_sources}
            if isinstance(candidate, list):
                results = [item for item in candidate if isinstance(item, dict) and item.get("document") in expected and item.get("input_sha256") == expected[item["document"]]]
        except (OSError, UnicodeError, json.JSONDecodeError):
            results = []
    completed_documents = {item["document"] for item in results}
    for source in agreement_sources:
        if str(source) in completed_documents:
            continue
        file_id = _upload(source, key)
        response = _request(
            requests.post(
                f"{BASE_URL}/extract",
                headers=_headers(key, content_type=True),
                json=_extract_payload(file_id, source),
                timeout=900,
            )
        )
        results.append(
            {
                "provider": "reducto",
                "document": str(source),
                "input_sha256": _sha256(source),
                "job_id": response.get("job_id"),
                "studio_link": response.get("studio_link"),
                "usage": response.get("usage"),
                "result": response.get("result"),
                "confidence": response.get("confidence"),
                "confidence_reason": response.get("confidence_reason"),
            }
        )
        partial.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    output.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    partial.unlink(missing_ok=True)
    return output
