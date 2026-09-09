"""Build a human approval packet from agent-reviewed exceptions."""

from __future__ import annotations

import json
from pathlib import Path


_DISPOSITIONS = {
    "agreement amendments": (
        "Approve as a bounded disclosure: the June 8 amendments are confirmed by the 10-Q and exhibits, but no unverified commercial effect should be inferred.",
        "Confirm the amendment sections do not change the report's stated commitments, balances, or covenant-calculation boundary.",
    ),
    "covenant capacity": (
        "Approve the safety boundary: headroom remains not calculable and no unsupported ratio is presented.",
        "Confirm the report does not imply that not calculable means zero headroom or a breach.",
    ),
    "events of default and remedies": (
        "Approve as source-linked but bounded: the report identifies Sections 8.01 and 8.02 without claiming a complete legal abstraction.",
        "Confirm the five-Business-Day cure observation and the limited description of remedies are accurate enough for this report's scope.",
    ),
    "post-period activity": (
        "Defer as an open monitoring item: the quarter-end corpus cannot establish activity after June 30.",
        "Confirm this remains an explicit follow-up for the next refreshed filing period rather than a current-period conclusion.",
    ),
}


def build_approval_packet(issuer_dir: Path, output: Path) -> Path:
    report = json.loads((issuer_dir / "report.json").read_text(encoding="utf-8"))
    agent = json.loads((issuer_dir / "agent-review.json").read_text(encoding="utf-8"))
    lines = [
        f"# Human approval packet — {report.get('issuer', 'issuer')}",
        "",
        "This packet is the final review handoff after agent review. It proposes dispositions; checking an item is a human decision and must be recorded in `review-state.json`.",
        "",
        f"**Agent review status:** `{agent.get('status')}`  ",
        f"**Agent checks:** `{sum(check.get('passed') is True for check in agent.get('checks', []))}/{len(agent.get('checks', []))}` passed  ",
        f"**Human approval required:** `{agent.get('human_approval_required')}`",
        "",
        "## Proposed dispositions",
        "",
    ]
    for index, exception in enumerate(agent.get("exceptions", []), start=1):
        topic = exception.get("topic", "open item")
        disposition, question = _DISPOSITIONS.get(topic, ("Review the exception against the linked evidence.", "Record the decision and any caveat."))
        lines += [
            f"### {index}. {topic.title()} ({exception.get('severity', 'review')})",
            "",
            f"**Agent finding:** {exception.get('detail', '')}",
            "",
            f"**Recommended disposition:** {disposition}",
            "",
            f"**Human confirmation:** [ ] {question}",
            "",
        ]
    lines += [
        "## Release decision",
        "",
        "Before release, the reviewer must also confirm the report scope and period, material report facts, agreement sections, calculation safety, and provider disagreement treatment. The existing evidence-level checklist remains authoritative for those confirmations.",
        "",
        "- [ ] I reviewed the four exceptions above against the linked SEC evidence.",
        "- [ ] I reviewed the evidence-level checklist and recorded completed evidence IDs.",
        "- [ ] I recorded the five required review actions in the durable review state.",
        "- [ ] I approve distribution of this report for its stated scope and period.",
        "",
        "Reviewer: ____________________",
        "",
        "Date: ____________________",
        "",
        "This packet does not itself change readiness or mark the report customer-ready.",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output
