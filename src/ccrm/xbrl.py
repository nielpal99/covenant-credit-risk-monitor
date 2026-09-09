"""Bounded inline-XBRL corroboration for the AMZN debt snapshot."""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


EXPECTED_FACTS = (
    ("us-gaap:LongTermDebt", "132.1", "usd", "Senior Notes principal"),
    ("us-gaap:LongTermDebtFairValue", "123.8", "usd", "Senior Notes fair value"),
    ("us-gaap:LineOfCreditFacilityMaximumBorrowingCapacity", "20.0", "usd", "Revolving facilities capacity"),
    ("amzn:CommercialPaperMaximumBorrowingCapacity", "30.0", "usd", "Commercial paper capacity"),
    ("us-gaap:ShortTermBorrowings", "325", "usd", "Other short-term borrowings"),
    ("us-gaap:DebtInstrumentFaceAmount", "17.5", "usd", "DDTL facility commitment"),
)


def _numeric_value(raw: str, scale: str | None) -> str:
    value = raw.replace(",", "").replace("—", "0").strip()
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        return value
    if scale is None:
        return value
    scaled = Decimal(value) * (Decimal(10) ** int(scale))
    return str(int(scaled)) if scaled == scaled.to_integral_value() else str(scaled)


def _display_value(raw: str, scale: str | None, unit: str | None) -> str:
    currency = {"usd": "$", "eur": "€", "gbp": "£", "chf": "CHF "}.get(unit or "", "")
    magnitude = {"9": "billion", "6": "million", "3": "thousand"}.get(str(scale), "units")
    return f"{currency}{raw.replace(',', '').strip()} {magnitude}"


def _contexts(soup: BeautifulSoup) -> dict[str, dict[str, Any]]:
    contexts: dict[str, dict[str, Any]] = {}
    for context in soup.find_all(["xbrli:context", "context"]):
        context_id = context.get("id")
        if not context_id:
            continue
        instant = context.find(["xbrli:instant", "instant"])
        start = context.find(["xbrli:startdate", "startdate"])
        end = context.find(["xbrli:enddate", "enddate"])
        members = [m.get_text(" ", strip=True) for m in context.find_all(["xbrldi:explicitmember", "explicitmember"])]
        contexts[context_id] = {
            "instant": instant.get_text(strip=True) if instant else None,
            "start": start.get_text(strip=True) if start else None,
            "end": end.get_text(strip=True) if end else None,
            "dimensions": members,
        }
    return contexts


def _facts(soup: BeautifulSoup, contexts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for tag in soup.find_all(["ix:nonfraction", "nonfraction", "ix:nonnumeric", "nonnumeric"]):
        name = tag.get("name")
        context_ref = tag.get("contextref")
        if not name or not context_ref:
            continue
        raw = tag.get_text(" ", strip=True)
        fact = {
            "name": name,
            "context_ref": context_ref,
            "unit": tag.get("unitref"),
            "raw_value": raw,
            "scale": tag.get("scale"),
            "numeric_value": _numeric_value(raw, tag.get("scale")),
            "display_value": _display_value(raw, tag.get("scale"), tag.get("unitref")),
            "context": contexts.get(context_ref, {}),
        }
        facts.append(fact)
    return facts


def build_xbrl_corroboration(source: Path, sec_url: str, output: Path, report_path: Path | None = None) -> Path:
    soup = BeautifulSoup(source.read_bytes(), "html.parser")
    contexts = _contexts(soup)
    facts = _facts(soup, contexts)
    selected: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for name, raw_value, unit, label in EXPECTED_FACTS:
        candidates = [
            fact for fact in facts
            if fact["name"] == name and fact["raw_value"].replace(",", "") == raw_value and fact.get("unit") == unit
        ]
        # Prefer an instantaneous June 30, 2026 fact when multiple tagged
        # values share the same concept and displayed value.
        candidates.sort(key=lambda fact: fact.get("context", {}).get("instant") == "2026-06-30", reverse=True)
        match = candidates[0] if candidates else None
        checks.append({"label": label, "fact": name, "expected_raw_value": raw_value, "found": match is not None})
        if match:
            selected.append({
                "label": label,
                "fact": name,
                "document_id": "0001018724-26-000026",
                "sec_url": sec_url,
                "locator": f"Inline XBRL fact {name} / context {match['context_ref']}",
                "context_ref": match["context_ref"],
                "context": match["context"],
                "unit": match["unit"],
                "raw_value": match["raw_value"],
                "scale": match["scale"],
                "numeric_value": match["numeric_value"],
                "display_value": match["display_value"],
                "period": match["context"].get("instant") or f"{match['context'].get('start')} to {match['context'].get('end')}",
                "kind": "xbrl_corroboration",
                "human_verified": False,
            })
    report_alignment = []
    if report_path and report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        instruments = {item.get("name"): item for item in report.get("debt_instruments", [])}
        expected_report_values = {
            "Senior Notes principal": (instruments.get("Senior Notes", {}).get("outstanding_amount") or "", "132.1 billion"),
            "Senior Notes fair value": (instruments.get("Senior Notes", {}).get("outstanding_amount") or "", "123.8 billion"),
            "Revolving facilities capacity": (instruments.get("Unsecured revolving credit facilities", {}).get("commitment_amount") or "", "20.0 billion"),
            "Commercial paper capacity": (instruments.get("Commercial Paper Programs", {}).get("commitment_amount") or "", "30.0 billion"),
            "Other short-term borrowings": (instruments.get("Other short-term credit facilities", {}).get("outstanding_amount") or "", "325 million"),
            "DDTL facility commitment": (instruments.get("DDTL Facility", {}).get("commitment_amount") or "", "17.5 billion"),
        }
        for label, (report_value, expected_text) in expected_report_values.items():
            report_alignment.append({"label": label, "expected_text": expected_text, "report_value": report_value, "aligned": expected_text.lower() in report_value.lower()})
    report_alignment_passed = not report_alignment or all(item["aligned"] for item in report_alignment)
    result = {
        "provider": "SEC Inline XBRL",
        "source": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "sec_url": sec_url,
        "status": "machine_corroboration_only",
        "human_verified": False,
        "checks": checks,
        "facts": selected,
        "report": str(report_path) if report_path else None,
        "report_alignment": report_alignment,
        "report_alignment_passed": report_alignment_passed,
        "passed": bool(selected) and all(check["found"] for check in checks) and report_alignment_passed,
        "note": "XBRL facts corroborate selected standard debt values; they do not establish covenant definitions, agreement remedies, or human verification.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return output
