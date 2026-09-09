# Development guide

This document contains operational detail kept out of the first-time-reader README.

## Local report workflow

```bash
ccrm ingest-amzn --filing-radar /path/to/filing-radar-export
ccrm report --issuer AMZN
ccrm evaluate --issuer AMZN
ccrm review-checklist --issuer AMZN
ccrm review-summary --issuer AMZN
ccrm agent-review --issuer AMZN
ccrm decision-brief --issuer AMZN
ccrm approval-packet --issuer AMZN
ccrm workflow-metrics --issuer AMZN
ccrm agreement-map --issuer AMZN
ccrm period-registry --issuer AMZN
ccrm readiness --issuer AMZN
```

The review state is hash-bound to the report, checklist, provider comparison, Parse audit, XBRL corroboration, and agent review. It can reach `human_verified` only through explicit reviewer actions and evidence IDs.

## Immutable runs

```bash
ccrm snapshot --issuer AMZN
ccrm verify-snapshot --run-manifest data/AMZN/runs/RUN_ID/run-manifest.json
ccrm historical-snapshot --issuer AMZN
ccrm compare-runs --prior-run data/AMZN/runs/run-historical-20260331/run-manifest.json --current-run data/AMZN/runs/RUN_ID/run-manifest.json --output data/AMZN/q1-to-q2-comparison.json
ccrm compare-runs \
  --prior-run data/AMZN/runs/PRIOR/run-manifest.json \
  --current-run data/AMZN/runs/CURRENT/run-manifest.json \
  --output data/AMZN/run-comparison.json
```

Snapshots copy the corpus and regenerate bound artifacts. Duplicate builds of the same period do not count as historical evidence.

## Optional provider paths

Paid provider calls require both credentials and explicit cost authorization.

```bash
export LLAMA_CLOUD_COST_AUTHORIZED=1
ccrm parse --issuer AMZN
ccrm extract --issuer AMZN
```

Reducto is the active alternative when LlamaParse credits are unavailable:

```bash
export REDUCTO_COST_AUTHORIZED=1
ccrm reducto-parse --issuer AMZN
ccrm reducto-extract --issuer AMZN
ccrm reducto-audit --issuer AMZN
ccrm compare-cloud --cloud-output data/AMZN/reducto-extract.json
```

The bounded provider scope is eight SEC artifacts for Parse and three agreement artifacts for Extract. Filing-only annual context is excluded. Provider output remains comparison evidence and cannot overwrite the deterministic SEC report.

## XBRL corroboration

```bash
ccrm xbrl-corroborate --issuer AMZN
```

This produces supplemental machine corroboration for selected standard debt facts. It does not establish covenant definitions, headroom, remedies, or human verification.

## Controlled issuer scoping

```bash
ccrm issuer-coverage --issuer AAPL --filing-radar /path/to/filing-radar-export
ccrm issuer-config --issuer AAPL --coverage data/AAPL/coverage.json
```

`issuer-config` selects genuine latest/prior 10-Q candidates and the latest 10-K for review. It remains a configuration draft: credit reporting is disabled until issuer-specific instruments, agreements, calculations, and trust gates are configured.

Use source inventory before adding an issuer-specific report:

```bash
ccrm issuer-coverage \
  --issuer AAPL \
  --filing-radar /path/to/filing-radar-export \
  --output data
```

This records genuine forms, reporting dates, SEC URLs, source availability, and source hashes. It does not infer debt, covenant, headroom, or customer readiness.

## Evaluation boundaries

The evaluation checks:

- SEC URL provenance and corpus membership;
- source hash integrity;
- evidence IDs and excerpt presence;
- report-period accuracy;
- ten-question coverage;
- calculation safety;
- explicit uncertainty and missing-information narratives;
- alignment of supplemental XBRL evidence.

No covenant ratio is calculated unless the definition, testing date, financial period, required inputs, exclusions, and agreement version are available.
