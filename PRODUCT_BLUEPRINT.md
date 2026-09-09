# Covenant & Credit Risk Monitor — final-product blueprint

## Product goal

For a credit analyst, lender, or treasury team, produce one evidence-linked answer to: **what obligations govern this issuer, what room remains under them, and what changed since the prior reporting period?** Every conclusion must retain its source, calculation boundary, and review status.

## Final product shape

The product should be organized as four layers with a hard trust boundary between them:

1. **Source and corpus layer** — SEC filings, exhibits, XBRL facts, document manifests, source hashes, filing periods, and agreement relationships.
2. **Intelligence layer** — debt instruments, governing agreements, covenant terms, financial definitions, events of default, amendments, changes, and safe calculations.
3. **Evidence and review layer** — stable evidence IDs, excerpts, provenance, provider comparisons, reviewer checklist, review state, and unresolved questions.
4. **Release layer** — evaluation, readiness status, report bundle, and a clear distinction between internal-review and customer-ready output.

The deterministic SEC report is authoritative. Document-processing providers may accelerate extraction or surface review candidates, but they cannot silently overwrite sourced facts or make an incomplete calculation appear verified.

## Current prototype versus final target

| Area | Current state | Final target | Next bounded work |
|---|---|---|---|
| Issuer workflow | AMZN-specific, one quarter comparison | Configured issuer run with the same gates | Generalize only after AMZN human review and two immutable reporting runs |
| Corpus | 11 SEC-bound sources, including context agreements | Reproducible versioned corpus per reporting period | Run identity and immutable snapshot now implemented |
| Intelligence | Deterministic debt/covenant report; no unsupported headroom | Structured instrument/agreement graph and safe calculations | Improve agreement mapping and calculation inputs |
| Provider use | Cached Reducto Parse/Extract comparison | Optional, bounded, replaceable provider adapter | Resolve targeted structured extraction gaps if justified |
| Review | Checklist and hash-bound state | Evidence-level review with auditable sign-off | Complete AMZN review and preserve decision history |
| Release | Separate artifacts and status file | One readiness gate controlling distribution | Implemented by `readiness.json` |

## What “customer-ready” means

A report is customer-ready only when:

- the corpus is complete for the selected scope and all local sources pass integrity/provenance checks;
- every material report fact has stable evidence and a usable locator;
- any calculation is supported by the exact definition, period, inputs, exclusions, and agreement version;
- unknowns are explicitly labeled instead of inferred;
- the selected issuer, instrument family, and comparison period have been human reviewed;
- the durable readiness artifact says `customer_ready`.

## Deliberate non-goals

No news, market prices, brokerage integrations, autonomous alerts, trading recommendations, default prediction, or bulk processing until the single-issuer workflow is proven.

## Phased roadmap

### Phase 1 — trusted single-issuer report

Finish AMZN human review, preserve the evidence decision history, and close or explicitly document the remaining agreement-mapping gaps.

### Phase 2 — repeatable reporting-period refresh

Run identifier, immutable corpus snapshot, hash verification, non-mutating snapshot creation, and verified prior-run comparison are implemented. The remaining work is a source-refresh policy and a real second-period snapshot to validate meaningful deltas.

### Phase 3 — controlled issuer configuration

Replace AMZN-specific constants with an issuer configuration while retaining the same source, calculation, review, and readiness gates. Validate a second issuer only after `expansion_ready` is true: Phase 1 is signed off and two real AMZN reporting-period runs have been compared.

### Phase 4 — analyst workflow surface

Add a focused interface for reviewing evidence, resolving disagreements, and exporting the signed report bundle. Keep the underlying SEC/evidence model authoritative.

## Decisions still requiring product judgment

- Whether provider-assisted structured extraction is worth its cost after human review.
- Which second issuer best tests maintenance-covenant calculations.
- Whether the first interface should be a local analyst workbench or a shared service.
