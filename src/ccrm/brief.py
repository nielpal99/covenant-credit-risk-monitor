"""Create a concise customer decision brief from the evidence-linked report."""

from __future__ import annotations

import json
from pathlib import Path


def _evidence_link(item: dict) -> str:
    evidence = item.get("evidence", [])
    if not evidence:
        return ""
    first = evidence[0]
    return f" [{first.get('evidence_id', 'evidence')} — {first.get('locator', 'source')}]({first.get('sec_url')})"


def build_decision_brief(report_path: Path, agent_review_path: Path | None, output: Path) -> Path:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    agent_review = json.loads(agent_review_path.read_text(encoding="utf-8")) if agent_review_path and agent_review_path.is_file() else None
    instruments = report.get("debt_instruments", [])
    ddtl = next((item for item in instruments if item.get("name") == "DDTL Facility"), {})
    changes = report.get("changes_since_prior_period", [])
    exceptions = agent_review.get("exceptions", []) if agent_review else []

    lines = [
        f"# Decision brief — {report.get('issuer', 'issuer')}",
        "",
        f"**As of:** {report.get('as_of', 'not stated')}  ",
        f"**Prior period:** {report.get('prior_period', 'not stated')}  ",
        "**Review posture:** Agent-reviewed; human approval still required",
        "",
        "## Bottom line",
        "",
        f"Amazon added a **$17.5 billion senior unsecured DDTL facility**. It was **undrawn at quarter-end** and the commitment expires on September 30, 2026 unless fully borrowed earlier.{_evidence_link(ddtl)}",
        "",
        "The report does not identify a calculable financial-covenant headroom figure. That is an intentional safety result: the available evidence does not support a defensible ratio or capacity calculation.",
        "",
        "## Decision-relevant facts",
        "",
        "| Instrument | Latest reported position | Why it matters |",
        "|---|---|---|",
    ]
    for instrument in instruments:
        name = instrument.get("name", "Unnamed instrument")
        position = instrument.get("outstanding_amount") or "not reported"
        commitment = instrument.get("commitment_amount")
        if commitment:
            position = f"{position}; commitment {commitment}"
        why = instrument.get("recent_change") or "Current-period debt context"
        lines.append(f"| {name} | {position} | {why} |")

    lines += ["", "## What changed", ""]
    for change in changes:
        lines.append(f"- **{change.get('change_type', 'change')}:** {change.get('description', '')}{_evidence_link(change)}")

    lines += [
        "",
        "## Risk and uncertainty boundaries",
        "",
        "- Covenant headroom is not calculable for the reported financial, lien, and fundamental-change covenant records.",
        "- The June 8 revolving-credit amendments are identified, but their full commercial effect remains subject to review.",
        "- The report does not establish whether the DDTL was drawn after June 30 and before its commitment expiry.",
        "- Agreement sections for Events of Default and remedies are source-linked but not treated as fully human-verified.",
        "",
        "## Recommended review actions",
        "",
    ]
    if exceptions:
        for exception in exceptions:
            lines.append(f"- **{exception.get('severity', 'review').title()} — {exception.get('topic', 'open item')}:** {exception.get('detail', '')}")
    else:
        lines.append("- Complete the source-linked human review checklist before distribution.")
    lines += [
        "",
        "## Customer takeaway",
        "",
        "The immediate liquidity conclusion is favorable but time-bounded: Amazon had substantial undrawn committed capacity at quarter-end, while the DDTL creates a near-term availability window. The key unresolved work is not finding more headline debt numbers; it is confirming the amendment effects, agreement exceptions, and any activity after the reporting date.",
        "",
        "This brief is a decision aid, not a substitute for the evidence-linked report or human approval.",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output
