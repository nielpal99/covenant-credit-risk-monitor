import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DebtSnapshot:
    period_end: str
    ddtl_present: bool
    ddtl_commitment: str | None
    ddtl_outstanding: str | None
    notes_have_no_financial_covenants: bool
    revolving_commitment: str | None
    maturity_date: str | None = None
    repayment_amount: str | None = None
    covenant_status: str | None = None
    amendment_present: bool = False
    waiver_present: bool = False
    short_term_outstanding: str | None = None


def extract_amzn_snapshot(text: str, period_end: str) -> DebtSnapshot:
    normalized = re.sub(r"\s+", " ", text).strip()
    ddtl_match = re.search(r"entered into a \$ ?([\d.]+) billion unsecured delayed draw term loan", normalized, re.I)
    no_draw = bool(re.search(r"no borrowings outstanding under the Term Loan as of " + re.escape(period_end), normalized, re.I))
    revolving = re.search(r"aggregate \$ ?([\d.]+) billion in unsecured revolving credit facilities", normalized, re.I)
    short_term = re.search(r"There were \$ ?[\d.]+ million and \$ ?([\d.]+) million of borrowings outstanding under these facilities as of December 31, 2025 and " + re.escape(period_end), normalized, re.I)
    return DebtSnapshot(
        period_end=period_end,
        ddtl_present=bool(ddtl_match),
        ddtl_commitment=f"${ddtl_match.group(1)} billion" if ddtl_match else None,
        ddtl_outstanding="$0" if no_draw else None,
        notes_have_no_financial_covenants="not subject to any financial covenants under the notes" in normalized.lower(),
        revolving_commitment=f"${revolving.group(1)} billion" if revolving else None,
        short_term_outstanding=f"${short_term.group(1)} million" if short_term else None,
        amendment_present=bool(re.search(r"First Amendment(?:s)?[^.]{0,160}?dated(?: as of)? June 8, 2026", normalized, re.I)),
    )


def classify_amzn_changes(previous: DebtSnapshot, current: DebtSnapshot) -> list[str]:
    changes: list[str] = []
    if current.ddtl_present and not previous.ddtl_present:
        changes.append("new_ddtl_facility")
    if current.ddtl_outstanding and previous.ddtl_outstanding is None:
        changes.append("ddtl_outstanding_balance_reported")
    elif current.ddtl_outstanding != previous.ddtl_outstanding and previous.ddtl_outstanding is not None:
        changes.append("ddtl_outstanding_balance_changed")
    if current.notes_have_no_financial_covenants != previous.notes_have_no_financial_covenants:
        changes.append("notes_covenant_status_changed")
    if current.revolving_commitment != previous.revolving_commitment:
        changes.append("revolving_commitment_changed")
    if current.short_term_outstanding and previous.short_term_outstanding is None:
        changes.append("short_term_outstanding_reported")
    elif current.short_term_outstanding != previous.short_term_outstanding and previous.short_term_outstanding is not None:
        changes.append("short_term_outstanding_changed")
    if current.maturity_date != previous.maturity_date and current.maturity_date is not None:
        changes.append("maturity_changed")
    if current.repayment_amount is not None:
        changes.append("repayment_reported")
    if current.covenant_status != previous.covenant_status and current.covenant_status is not None:
        changes.append("covenant_status_changed")
    if current.amendment_present and not previous.amendment_present:
        changes.append("amendment_reported")
    if current.waiver_present and not previous.waiver_present:
        changes.append("waiver_reported")
    return changes
