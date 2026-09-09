# Covenant & Credit Risk Monitor

[GitHub repository](https://github.com/nielpal99/covenant-credit-risk-monitor)

Licensed under the [MIT License](LICENSE).

An SEC-first prototype that turns debt filings and credit agreements into an evidence-linked answer to:

> What obligations govern this issuer, what room remains under them, and what changed since the prior reporting period?

## Why it matters

Credit and treasury teams spend time reconciling filings, exhibits, amendments, covenant language, and quarter-over-quarter changes. This project organizes that work into a reviewable report with:

- source-linked debt and agreement facts;
- explicit covenant and headroom boundaries;
- safe calculations that refuse unsupported ratios;
- immutable reporting-period snapshots and comparisons;
- agent-assisted review with human approval preserved as the release gate.

## Current prototype

The first issuer is Amazon.com, Inc. (AMZN), comparing June 30, 2026 with March 31, 2026.

The prototype identifies a $17.5B delayed-draw term loan facility, confirms it was undrawn at quarter-end, tracks revolving and commercial-paper capacity, captures the $173M increase in other short-term borrowings, and maps agreement sections for covenants, defaults, remedies, reporting, and amendments.

The report deliberately does not invent covenant headroom. The current release remains `internal_review`, not customer-ready, because human approval is still required; a bounded historical March 31, 2026 snapshot now provides the second genuine period for repeatability testing.

## Trust boundary

The deterministic report is grounded in SEC filings and exhibits. Evidence carries document identity, SEC URL, locator, excerpt, and source hashes. Provider extraction is optional and review-only; it cannot overwrite the SEC-backed report.

Human review is separate from agent review:

`machine_assembled → agent_reviewed → human approval → customer_ready`

No news, market prices, brokerage integrations, trading recommendations, default prediction, autonomous alerts, or bulk processing are included.

## Run the public checkout

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -m "not integration"
```

The public suite is corpus-independent. The larger integration suite requires the private/generated Amazon corpus and is intentionally excluded from GitHub.

## Run locally with the Amazon corpus

```bash
ccrm ingest-amzn --filing-radar /path/to/filing-radar-export
ccrm report --issuer AMZN
ccrm evaluate --issuer AMZN
ccrm agent-review --issuer AMZN
ccrm decision-brief --issuer AMZN
ccrm approval-packet --issuer AMZN
ccrm readiness --issuer AMZN
ccrm historical-snapshot --issuer AMZN
ccrm period-registry --issuer AMZN
ccrm review-queue --issuer AMZN
ccrm compare-runs --prior-run data/AMZN/runs/run-historical-20260331/run-manifest.json --current-run data/AMZN/runs/RUN_ID/run-manifest.json --output data/AMZN/q1-to-q2-comparison.json
```

Generated SEC documents, provider caches, rendered files, and reports live under `data/` and are ignored by Git.

## Repository map

- [`PRODUCT_BLUEPRINT.md`](PRODUCT_BLUEPRINT.md) — product goal and final-product shape
- [`STATUS.md`](STATUS.md) — durable readiness and known gaps
- [`ROADMAP.md`](ROADMAP.md) — prioritized product history and remaining work
- [`SECURITY.md`](SECURITY.md) — credential and publication rules
- [`PUBLICATION_STATUS.md`](PUBLICATION_STATUS.md) — GitHub release boundary
- [`COMMERCIALIZATION.md`](COMMERCIALIZATION.md) — customer, gap, pilot, and commercialization strategy
- [`src/ccrm/report.py`](src/ccrm/report.py) — deterministic report builder
- [`src/ccrm/evaluate.py`](src/ccrm/evaluate.py) — evidence and calculation gates
- [`src/ccrm/review.py`](src/ccrm/review.py) — review state and sign-off controls
- [`src/ccrm/run.py`](src/ccrm/run.py) — immutable snapshots and comparisons
- [`src/ccrm/review_queue.py`](src/ccrm/review_queue.py) — structured analyst exception queue

Detailed provider, Reducto, XBRL, review, and snapshot commands are in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

The `issuer-coverage` command can inventory a second issuer’s genuine SEC source set without pretending that source coverage is a completed credit report.
The `issuer-config` command can turn that inventory into a reviewable period-selection draft; it does not enable credit conclusions.

## Project status

This is a focused prototype, not a production credit system. Amazon now has two distinct real periods, but expansion to other issuers remains gated until its human approval and broader trust gates are proven.
