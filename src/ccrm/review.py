import json
import hashlib
from pathlib import Path


REVIEW_STATUSES = ("machine_assembled", "partially_reviewed", "human_verified")
REVIEW_ACTIONS = (
    "scope_and_period_reviewed",
    "report_facts_reviewed",
    "agreement_sections_reviewed",
    "calculation_safety_reviewed",
    "provider_disagreements_resolved",
)


def _report_evidence_ids(report: dict) -> list[str]:
    ids: list[str] = []
    collections = list(report.get("debt_instruments", [])) + list(report.get("covenants", []))
    collections += [report.get("financial_definitions", {}), report.get("risk_status", {})]
    collections += list(report.get("changes_since_prior_period", []))
    for item in collections:
        for evidence in item.get("evidence", []) if isinstance(item, dict) else []:
            if evidence.get("evidence_id") and evidence["evidence_id"] not in ids:
                ids.append(evidence["evidence_id"])
    return ids


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def initialize_review_state(
    report_path: Path,
    checklist_path: Path,
    output: Path,
    cloud_comparison_path: Path | None = None,
    parse_audit_path: Path | None = None,
    xbrl_corroboration_path: Path | None = None,
) -> Path:
    """Create a hash-bound state machine without claiming human verification."""
    report = json.loads(report_path.read_text(encoding="utf-8"))
    comparison = None
    if cloud_comparison_path and cloud_comparison_path.is_file():
        comparison = json.loads(cloud_comparison_path.read_text(encoding="utf-8"))
    actions = {action: False for action in REVIEW_ACTIONS}
    if comparison is None or comparison.get("passed") is True:
        actions["provider_disagreements_resolved"] = True
    state = {
        "issuer": report["issuer"],
        "status": "machine_assembled",
        "report": str(report_path),
        "report_sha256": _sha256(report_path),
        "corpus_manifest_sha256": report.get("corpus_manifest_sha256"),
        "checklist": str(checklist_path),
        "checklist_sha256": _sha256(checklist_path),
        "parse_audit": str(parse_audit_path) if parse_audit_path else None,
        "parse_audit_sha256": _sha256(parse_audit_path) if parse_audit_path and parse_audit_path.is_file() else None,
        "cloud_comparison": str(cloud_comparison_path) if cloud_comparison_path else None,
        "cloud_comparison_sha256": _sha256(cloud_comparison_path) if cloud_comparison_path and cloud_comparison_path.is_file() else None,
        "xbrl_corroboration": str(xbrl_corroboration_path) if xbrl_corroboration_path else None,
        "xbrl_corroboration_sha256": _sha256(xbrl_corroboration_path) if xbrl_corroboration_path and xbrl_corroboration_path.is_file() else None,
        "required_actions": actions,
        "evidence_items": {evidence_id: False for evidence_id in _report_evidence_ids(report)},
        "reviewer": None,
        "date": None,
        "history": [{"status": "machine_assembled", "reviewer": None, "date": None}],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return output


def transition_review_state(
    state_path: Path,
    target_status: str,
    reviewer: str,
    review_date: str,
    completed_actions: list[str],
    report_path: Path,
    checklist_path: Path,
    cloud_comparison_path: Path | None = None,
    parse_audit_path: Path | None = None,
    xbrl_corroboration_path: Path | None = None,
    completed_evidence_ids: list[str] | None = None,
) -> Path:
    if target_status not in REVIEW_STATUSES or target_status == "machine_assembled":
        raise ValueError("Review transitions must target partially_reviewed or human_verified")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") == "human_verified":
        raise ValueError("Human-verified state is terminal and cannot be changed")
    if state.get("report_sha256") != _sha256(report_path) or state.get("checklist_sha256") != _sha256(checklist_path):
        raise ValueError("Review state is stale; initialize a new state for the changed report or checklist")
    if cloud_comparison_path and state.get("cloud_comparison_sha256") != _sha256(cloud_comparison_path):
        raise ValueError("Review state is stale; initialize a new state for the changed provider comparison")
    if parse_audit_path and state.get("parse_audit_sha256") != _sha256(parse_audit_path):
        raise ValueError("Review state is stale; initialize a new state for the changed Parse audit")
    if xbrl_corroboration_path and state.get("xbrl_corroboration_sha256") != _sha256(xbrl_corroboration_path):
        raise ValueError("Review state is stale; initialize a new state for the changed XBRL corroboration")
    completed_evidence_ids = completed_evidence_ids or []
    unknown = set(completed_actions) - set(REVIEW_ACTIONS)
    if unknown:
        raise ValueError(f"Unknown review actions: {sorted(unknown)}")
    evidence_items = dict(state.get("evidence_items", {}))
    unknown_evidence = set(completed_evidence_ids) - set(evidence_items)
    if unknown_evidence:
        raise ValueError(f"Unknown evidence IDs: {sorted(unknown_evidence)}")
    actions = dict(state.get("required_actions", {}))
    for action in completed_actions:
        actions[action] = True
    for evidence_id in completed_evidence_ids:
        evidence_items[evidence_id] = True
    if target_status == "human_verified" and not all(actions.get(action) is True for action in REVIEW_ACTIONS):
        missing = [action for action in REVIEW_ACTIONS if actions.get(action) is not True]
        raise ValueError(f"Cannot mark human_verified; incomplete review actions: {', '.join(missing)}")
    if target_status == "human_verified" and not all(evidence_items.values()):
        missing = [evidence_id for evidence_id, complete in evidence_items.items() if not complete]
        raise ValueError(f"Cannot mark human_verified; incomplete evidence items: {', '.join(missing)}")
    if target_status == "partially_reviewed" and not (any(actions.values()) or any(evidence_items.values())):
        raise ValueError("Partially reviewed state requires at least one completed review action or evidence item")
    state["status"] = target_status
    state["required_actions"] = actions
    state["evidence_items"] = evidence_items
    state["reviewer"] = reviewer.strip()
    state["date"] = review_date.strip()
    state.setdefault("history", []).append({"status": target_status, "reviewer": reviewer.strip(), "date": review_date.strip(), "completed_actions": completed_actions, "completed_evidence_ids": completed_evidence_ids})
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state_path


def record_agent_review(state_path: Path, agent_review_path: Path) -> Path:
    """Bind a successful agent review to the durable review state."""
    state = json.loads(state_path.read_text(encoding="utf-8"))
    agent_review = json.loads(agent_review_path.read_text(encoding="utf-8"))
    if agent_review.get("status") != "agent_reviewed":
        raise ValueError("Cannot record an unsuccessful agent review")
    if state.get("status") == "human_verified":
        raise ValueError("Human-verified state is terminal and cannot be changed")
    if state.get("report_sha256") != agent_review.get("report_sha256") or state.get("corpus_manifest_sha256") != agent_review.get("corpus_manifest_sha256"):
        raise ValueError("Agent review is bound to a different report or corpus manifest")
    state["agent_review"] = str(agent_review_path)
    state["agent_review_sha256"] = _sha256(agent_review_path)
    state["agent_review_status"] = "agent_reviewed"
    if state.get("status") == "machine_assembled":
        state["status"] = "agent_reviewed"
    state.setdefault("history", []).append({"status": "agent_reviewed", "reviewer": "agent", "date": None, "agent_review_sha256": _sha256(agent_review_path)})
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state_path


def build_review_summary(
    report_path: Path,
    comparison_path: Path,
    parse_audit_path: Path,
    state_path: Path,
    output: Path,
) -> Path:
    """Create a concise, evidence-linked handoff for the remaining reviewer work."""
    report = json.loads(report_path.read_text(encoding="utf-8"))
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    audit = json.loads(parse_audit_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    report_evidence = [e for item in report.get("risk_status", {}).get("evidence", []) for e in [item]]
    evidence_items = state.get("evidence_items", {})
    reviewed_evidence = sum(complete is True for complete in evidence_items.values())
    required_actions = state.get("required_actions", {})
    completed_actions = sum(complete is True for complete in required_actions.values())
    lines = [
        f"# Review summary — {report['issuer']}",
        "",
        f"**Report status:** `{state.get('status', 'unknown')}`  ",
        f"**Evidence review progress:** `{reviewed_evidence}/{len(evidence_items)}` items complete  ",
        f"**Action progress:** `{completed_actions}/{len(required_actions)}` actions complete  ",
        f"**Provider comparison:** `{'passed' if comparison.get('passed') else 'unresolved'}`  ",
        f"**Parse presence audit:** `{'passed' if audit.get('passed') else 'failed'}` (presence only; not human verification)",
        f"**Parse scope:** `{audit.get('provider_scope', 'not recorded')}`  ",
        "",
        "The deterministic SEC report remains authoritative. This summary identifies the smallest remaining review set and does not change report facts.",
        "",
        "## What is supported by parsed text",
        "",
    ]
    for check in audit.get("checks", []):
        evidence = check.get("evidence")
        if evidence and check.get("passed"):
            lines.append(f"- **{check['document_id']} — {check['check']}:** {evidence['excerpt'][:420]} [SEC exhibit]({evidence['sec_url']})")
    lines += ["", "## Remaining structured-provider gaps", ""]
    signal_locators = {
        "revolving_amendment": {"Exhibits 10.2 and 10.3", "First Amendment"},
        "events_of_default": {"Section 8.01"},
        "remedies": {"Section 8.02"},
    }
    for check in comparison.get("checks", []):
        if check.get("applicable", True) and not check.get("found_in_cloud_output"):
            matching = [e for e in report_evidence if e.get("locator") in signal_locators.get(check.get("signal"), set())]
            links = " ".join(f"[report evidence — {e['locator']}]({e['sec_url']})" for e in matching if e.get("sec_url"))
            lines.append(f"- **{check['signal']}:** structured Extract did not return the expected hook. Human-review source links: {links}")
    lines += ["", "## Explicitly out of scope for agreement Extract", ""]
    for check in comparison.get("checks", []):
        if check.get("applicable") is False:
            lines.append(f"- **{check['signal']}:** {check.get('reason', 'Not applicable to the selected provider input scope.')}")
    lines += ["", "## Required reviewer actions", ""]
    for action, complete in required_actions.items():
        lines.append(f"- [{'x' if complete else ' '}] {action.replace('_', ' ')}")
    lines += ["", "## Boundary", "", "Do not mark the report human-verified until the agreement sections, report facts, calculation safety, and provider disagreements have all been reviewed and recorded in `review-state.json`."]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def build_review_checklist(report_path: Path, output: Path, cloud_comparison_path: Path | None = None, parse_audit_path: Path | None = None) -> Path:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    lines = [
        f"# Human review checklist — {report['issuer']}",
        "",
        "This checklist is a review handoff, not an approval. Check each item against the linked source before treating the report as verified.",
        "",
        "## Scope and period",
        "",
        f"- [ ] Confirm reporting period: {report['as_of']} versus prior period {report['prior_period']}",
        f"- Corpus manifest SHA-256: `{report.get('corpus_manifest_sha256') or 'not recorded'}`",
        "- [ ] Confirm the selected agreement version and all amendments are complete",
        "",
        "## Debt instruments",
        "",
    ]
    for instrument in report.get("debt_instruments", []):
        evidence = instrument.get("evidence", [])
        links = " ".join(f"[{e.get('evidence_id', 'unassigned')} — {e['kind']} / {e['locator']}]({e['sec_url']})" for e in evidence)
        version = instrument.get("agreement_version") or "not specified"
        lines.append(f"- [ ] Verify **{instrument['name']}**: commitment {instrument.get('commitment_amount') or 'not reported'}, outstanding {instrument.get('outstanding_amount') or 'not reported'}; governing agreement: {version} {links}")
        for evidence_item in evidence:
            lines.append(f"  - [ ] Evidence `{evidence_item.get('evidence_id', 'unassigned')}` ({evidence_item['kind']} / {evidence_item['locator']}): {evidence_item['excerpt'][:240]}")
    lines += ["", "## Quarter-over-quarter changes", ""]
    for change in report.get("changes_since_prior_period", []):
        links = " ".join(f"[{e.get('evidence_id', 'unassigned')} — source / {e['locator']}]({e['sec_url']})" for e in change.get("evidence", []))
        calculation = f" Calculation: `{change['calculation']}`." if change.get("calculation") else ""
        lines.append(f"- [ ] Verify **{change['change_type']}** — {change['description']}{calculation} {links}")
        for evidence_item in change.get("evidence", []):
            lines.append(f"  - [ ] Evidence `{evidence_item.get('evidence_id', 'unassigned')}` ({evidence_item['kind']} / {evidence_item['locator']}): {evidence_item['excerpt'][:240]}")
    lines += ["", "## Covenants and calculation safety", ""]
    for covenant in report.get("covenants", []):
        links = " ".join(f"[{e.get('evidence_id', 'unassigned')} — {e['kind']} / {e['locator']}]({e['sec_url']})" for e in covenant.get("evidence", []))
        lines.append(f"- [ ] Verify **{covenant['name']}** status is **{covenant['status']}**, agreement version is **{covenant.get('agreement_version') or 'not specified'}**, and that no unsupported headroom is presented {links}")
    lines += [
        "- [ ] Confirm the report does not imply a traditional maintenance covenant where none is disclosed",
        "- [ ] Confirm definitions, testing dates, required inputs, add-backs, exclusions, and agreement version before any future headroom calculation",
        "",
        "## Default and remedy observations",
        "",
    ]
    lines.extend(f"- [ ] Review event-of-default observation: {item}" for item in report.get("risk_status", {}).get("events_of_default", []))
    lines += [
        "",
        "## Amendments and agreement monitoring hooks",
        "",
    ]
    for evidence in report.get("risk_status", {}).get("evidence", []):
        if evidence["locator"].startswith("Section ") or evidence["locator"] in {"First Amendment", "Exhibits 10.2 and 10.3"}:
            lines.append(f"- [ ] Review `{evidence.get('evidence_id', 'unassigned')}` **{evidence['locator']}** ({evidence['kind']}) and confirm the excerpt is complete: {evidence['excerpt'][:240]} [source]({evidence['sec_url']})")
    lines += ["", "## Open questions", ""]
    lines.extend(f"- [ ] {question}" for question in report.get("follow_up_questions", []))
    comparison = None
    if cloud_comparison_path and cloud_comparison_path.is_file():
        try:
            comparison = json.loads(cloud_comparison_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            comparison = None
    if comparison is None:
        cloud_status = "No provider comparison is recorded. The deterministic SEC report remains authoritative until a provider output is reviewed."
        cloud_marks = "Cloud comparison: ☐ Not run  ☐ Compared  ☐ Disagreements resolved"
    else:
        cloud_status = (
            f"A provider comparison was run from `{comparison.get('cloud_output', cloud_comparison_path)}`. "
            "The deterministic SEC report remains authoritative until every disagreement and provenance gap is reviewed."
        )
        cloud_marks = f"Cloud comparison: ☐ Not run  ☑ Compared ({'passed' if comparison.get('passed') else 'unresolved disagreements/provenance gaps'})  ☐ Disagreements resolved"
    lines += ["", "## Reducto Parse coverage", ""]
    if parse_audit_path and parse_audit_path.is_file():
        try:
            parse_audit = json.loads(parse_audit_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            parse_audit = None
        if parse_audit:
            lines.append(f"- Provider Parse presence audit: **{'passed' if parse_audit.get('passed') else 'failed'}** ({parse_audit.get('status', 'unclassified')}); this is not human verification.")
            for check in parse_audit.get("checks", []):
                if check.get("evidence"):
                    evidence = check["evidence"]
                    lines.append(f"- [ ] Review **{check['document_id']} / {check['check']}**: {evidence['excerpt'][:500]} [SEC source]({evidence['sec_url']})")
    else:
        lines.append("- No Reducto Parse presence audit is recorded.")
    lines += ["", "## Cloud comparison status", "", cloud_status, "", cloud_marks, "", "## Sign-off", "", "Durable review state: see `review-state.json`; this checklist remains a review handoff, not an approval.", "", "Reviewer: ____________________", "", "Date: ____________________", "", "Verification status: ☐ Not reviewed  ☐ Partially reviewed  ☐ Human verified"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output
