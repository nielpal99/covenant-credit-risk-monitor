from typing import Literal

from pydantic import BaseModel, Field


EvidenceKind = Literal["reported", "agreement_defined", "calculated", "estimate", "interpretation", "missing"]


class Evidence(BaseModel):
    evidence_id: str = ""
    kind: EvidenceKind
    document_id: str
    sec_url: str
    locator: str = Field(description="Page, section, exhibit, or text locator")
    excerpt: str
    human_verified: bool = False


class DebtInstrument(BaseModel):
    name: str
    instrument_type: str
    agreement_version: str | None = None
    principal_amount: str | None = None
    outstanding_amount: str | None = None
    commitment_amount: str | None = None
    maturity_date: str | None = None
    interest_rate_or_spread: str | None = None
    rate_type: str | None = None
    secured_status: str | None = None
    priority: str | None = None
    guarantors: list[str] = []
    collateral: str | None = None
    recent_change: str | None = None
    evidence: list[Evidence] = []


class Covenant(BaseModel):
    name: str
    covenant_type: str
    applicable_instrument: str
    agreement_version: str | None = None
    threshold: str | None = None
    testing_date_or_frequency: str | None = None
    actual_reported_value: str | None = None
    calculated_value: str | None = None
    estimated_headroom: str | None = None
    status: Literal["not_calculable", "partially_calculable", "estimated", "verified"]
    maintenance_or_incurrence: str
    agreement_section: str | None = None
    exceptions: list[str] = []
    add_backs: list[str] = []
    baskets: list[str] = []
    cure_rights: str | None = None
    grace_periods: str | None = None
    calculation_limitations: list[str] = []
    evidence: list[Evidence] = []


class FinancialDefinitions(BaseModel):
    ebitda: str | None = None
    consolidated_ebitda_adjustments: list[str] = []
    total_debt: str | None = None
    net_debt: str | None = None
    interest_expense: str | None = None
    cash_and_equivalents: str | None = None
    permitted_exclusions: list[str] = []
    pro_forma_adjustments: list[str] = []
    fiscal_period_requirements: str | None = None
    evidence: list[Evidence] = []


class RiskStatus(BaseModel):
    events_of_default: list[str] = []
    waivers: list[str] = []
    amendments: list[str] = []
    reporting_violations: list[str] = []
    liquidity_concerns: list[str] = []
    covenant_breaches: list[str] = []
    uncertainty_or_missing_information: list[str] = []
    human_verification_status: str
    evidence: list[Evidence] = []


class Change(BaseModel):
    change_type: Literal["facility_added", "balance_reported", "balance_changed", "amendment"]
    description: str
    calculation: str | None = None
    evidence: list[Evidence] = []


class Report(BaseModel):
    issuer: str
    as_of: str
    prior_period: str
    corpus_manifest_sha256: str | None = None
    scope: str
    debt_instruments: list[DebtInstrument]
    covenants: list[Covenant]
    financial_definitions: FinancialDefinitions
    risk_status: RiskStatus
    changes_since_prior_period: list[Change]
    follow_up_questions: list[str]
