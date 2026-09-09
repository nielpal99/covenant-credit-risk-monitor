# Covenant & Credit Risk Monitor — product status

## Current state

- **Product:** Covenant & Credit Risk Monitor
- **Prototype issuer:** AMZN
- **Latest comparison period:** June 30, 2026 versus March 31, 2026
- **Scope:** quarterly SEC filings plus Amazon's latest 10-K, the DDTL agreement, two revolving-credit amendments, and Senior Notes indenture context; no news, market prices, brokerage data, alerts, or default prediction
- **Readiness:** Internal-review prototype; not human verified and not production ready
- **Deterministic report authority:** The SEC-based report remains authoritative over incomplete provider extraction

## Verified outcomes

- DDTL commitment: $17.5 billion
- DDTL outstanding balance: $0 at June 30, 2026
- DDTL commitment expiry: September 30, 2026
- Financial covenant headroom: **not calculable**; no unsupported ratio is emitted
- Other short-term credit facilities: $152 million prior quarter to $325 million latest quarter, a sourced $173 million increase
- Eleven-document report corpus has manifest-bound SHA-256 integrity, including the latest 10-K and two Senior Notes indentures as provider-excluded context
- Every report evidence item has a stable ID and SEC provenance
- Senior Notes principal is now captured from the latest 10-Q as $132.1 billion, separately from fair value
- Inline-XBRL corroboration and report-alignment checks passed for six selected June 30, 2026 debt facts; it remains machine-only
- Report evaluation: 26/26 checks passed
- Automated test suite: 105 tests passed
- Reducto Parse presence audit: passed, presence only
- Reducto Parse audit is bound to the manifest hash and explicitly excludes the filing-only 10-K from its eight-document provider scope
- Evaluation persists a ten-question coverage matrix with statuses, caveats, and stable evidence IDs
- Review summary surfaces the verified Reducto Parse scope and the intentional annual-context exclusion
- Clean rebuild from the available Filing Radar/SEC inputs reproduces the eleven-document corpus, report, passing evaluation, and integrity checks
- Release readiness artifact reports `internal_review`; automated quality passes, human review is the blocking gate, and provider comparison gaps are explicitly optional/documented
- Expansion gate reports `expansion_ready: false`; expansion should wait for AMZN human verification and a second real immutable reporting-period run
- Agent review now checks source binding, evidence completeness, corpus availability, key DDTL facts, change provenance, and calculation safety; its hash is bound into `review-state.json` and it produces a focused exception list while preserving human approval as the release gate
- Customer decision brief now translates the evidence bundle into a source-linked liquidity conclusion, decision-relevant changes, uncertainty boundaries, and four prioritized approval exceptions
- Human approval packet now turns those four exceptions into proposed dispositions and explicit confirmation steps without weakening the customer-ready gate
- Duplicate same-period rebuilds are now recognized as identical by period, verified corpus content, and report content; they cannot falsely count as historical change or unlock issuer expansion
- Workflow metrics record 24 evidence items narrowed to 4 explicit agent exceptions; analyst time savings remain deliberately unmeasured
- Period registry confirms four duplicate builds of one reporting period and no genuine second period
- Agreement map preserves 10 source-linked agreement review hooks, all explicitly marked `human_review_required`
- GitHub publication preflight initialized a local repository and confirms generated corpus/provider artifacts are ignored; public release remains blocked on sanitized fixtures, test separation, and license selection
- Public prototype repository: https://github.com/nielpal99/covenant-credit-risk-monitor; fresh checkout passes the corpus-independent suite with generated-corpus integration tests correctly skipped
- Immutable run snapshot created at `data/AMZN/runs/run-7571ecacc62fcf80/`; its recorded artifact hashes verify successfully and repeated snapshot creation is idempotent
- Snapshot-to-snapshot comparison now verifies both immutable inputs and persists corpus, debt-instrument, covenant, and declared-report deltas without mutating either run; current smoke comparison is identical because only one reporting-period snapshot exists

## Active blockers

1. **Human approval is incomplete.** The agent review is complete, but twenty-four evidence items and five approval actions remain unchecked in `data/AMZN/review-state.json`.
2. **Reducto structured extraction is incomplete.** The comparison remains unresolved for revolving amendments, Events of Default, and remedies. Cached Parse text supports those hooks, but structured Extract did not return them.
3. **Prototype scope is single-issuer.** Generalization to another issuer is intentionally deferred until this report is reviewed.

## Inputs needed

- A reviewer must check the linked SEC evidence and record completed evidence IDs and review actions using `ccrm review-state`.
- Additional Reducto usage requires explicit cost authorization before rerunning Extract.
- The previously exposed Reducto credential should be revoked and replaced; no replacement credential belongs in this repository or any report.

## Next recommended iteration

Complete human review of the DDTL agreement sections, debt facts, calculation safety, and provider disagreements, then create and compare a second real reporting-period snapshot. Do not expand to another issuer until `expansion_ready` becomes true. A targeted Reducto Extract retry remains optional and should be justified by a specific unresolved customer workflow; the cached Reducto run remains eight-document Parse / three-agreement Extract coverage.

## Evidence artifacts

- `data/AMZN/report.md` — human-readable report
- `data/AMZN/evaluation.json` — persisted evaluation
- `data/AMZN/human-review-checklist.md` — source-linked review handoff
- `data/AMZN/review-state.json` — hash-bound durable review state
- `data/AMZN/review-summary.md` — concise provider-gap summary
- `data/AMZN/xbrl-corroboration.json` — bounded SEC inline-XBRL corroboration
- `data/AMZN/readiness.json` — persisted release/readiness gate
- `data/AMZN/runs/` — immutable reporting-period snapshots and run manifests
