import hashlib
import json
from pathlib import Path


def check_corpus_integrity(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks = []
    for document in manifest.get("documents", []):
        source = document.get("source_file")
        digest = document.get("source_sha256")
        if not source or not digest:
            checks.append({"document": document.get("document_id", "filing"), "passed": False, "detail": "Missing local source or SHA-256 digest"})
            continue
        path = Path(source)
        if not path.is_absolute():
            # Ingested paths are relative to the project/output root (the
            # directory three levels above data/ISSUER/manifest.json).
            rooted = manifest_path.resolve().parent.parent.parent / path
            if rooted.exists():
                path = rooted
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        checks.append({"document": document.get("document_id") or document.get("filing", {}).get("accession_number"), "passed": actual == digest, "detail": "SHA-256 matches recorded local artifact" if actual == digest else "SHA-256 mismatch or missing artifact"})
    return {"passed": bool(checks) and all(c["passed"] for c in checks), "checks": checks}
