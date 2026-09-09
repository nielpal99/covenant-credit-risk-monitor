# Commercialization strategy and gap assessment

## Product thesis

The product should sell a recurring credit-review workflow, not a generic AI summary. The customer pays for a defensible answer to:

> What changed, what obligations govern the exposure, what capacity is supportable, and what requires human attention?

The strongest differentiator is the trust chain: source document → evidence excerpt → structured obligation → safe calculation boundary → reviewer decision.

## Best initial customer

The best initial buyer is a credit, treasury, or portfolio-monitoring team that reviews multiple issuers every quarter but does not have a large covenant-operations function.

Good early use cases:

- quarterly debt and covenant review for a focused portfolio;
- lender or treasury committee preparation;
- amendment and waiver review;
- evidence-backed exception triage before a senior analyst signs off.

Poor initial use cases:

- retail investing;
- automated trading or default prediction;
- broad market surveillance;
- bulk document processing without analyst review.

## What is valuable today

The Amazon prototype already demonstrates four credible customer benefits:

1. It consolidates filings and agreements into one debt view.
2. It catches period changes such as the $173M increase in other short-term borrowings.
3. It refuses to manufacture covenant headroom when definitions or inputs are incomplete.
4. It narrows 24 evidence items into four explicit review exceptions.

That is enough for a paid design-partner pilot, but not yet enough for a broad production purchase. Amazon is a relatively transparent issuer, and one period comparison does not yet prove recurring value.

## Critical product gaps

### 1. Recurring-period proof

Amazon now has two genuine periods in immutable artifacts, including a March 31, 2026 historical snapshot and the June 30, 2026 full workflow run. The cross-period comparison surfaces meaningful changes, but the older snapshot is intentionally bounded and does not yet have full report parity or a completed human release review.

### 2. General issuer configuration

The report builder still contains Amazon-specific assumptions. Issuer configuration needs to control CIK, filing selection, period mapping, instrument families, agreement relationships, and report vocabulary without weakening the common trust gates.

### 3. Agreement intelligence depth

The product maps review hooks, but does not yet reliably normalize full covenant definitions, baskets, thresholds, cure rights, reporting obligations, amendment effects, or remedy mechanics into a reusable obligation model.

### 4. Customer workflow surface

The current output is a strong artifact bundle, not yet an analyst workbench. A commercial product needs a focused queue showing new changes, unresolved exceptions, evidence, reviewer ownership, and final disposition.

### 5. Measured economic value

Workflow compression is demonstrated, but analyst time saved, false-positive rate, review accuracy, and cost per issuer are not measured. These must be captured in a design-partner pilot rather than inferred.

### 6. Source coverage boundary

SEC filings are a strong base for public issuers, but lender teams may also need private credit agreements, lender notices, waivers, compliance certificates, and amendment packages that are not public SEC exhibits.

### 7. Release and operational controls

The product has durable readiness and review state, but still needs a clearer license/public-fixture policy, reproducible refresh command, retention policy, user/role model, and exportable audit package before production deployment.

## Commercial wedge

Package the first product as a quarterly review packet:

- executive decision brief;
- debt and covenant inventory;
- period-over-period change ledger;
- source-linked agreement map;
- agent-generated exception queue;
- human approval record;
- immutable evidence bundle.

Start with a paid, narrow pilot priced around the number of issuers and reporting periods reviewed—not around unrestricted document volume. Expand pricing only after the pilot measures analyst effort and review outcomes.

## Pilot acceptance criteria

A design-partner pilot should not be declared successful until it demonstrates:

- two genuine reporting periods for Amazon, with comparable full-period coverage and human review;
- one second issuer with a materially different debt or covenant structure;
- all populated material facts linked to usable SEC or agreement evidence;
- no unsupported headroom calculations;
- an explicit human approval trail;
- measured review time and exception-resolution time;
- a documented comparison against the customer’s existing review process.

## Expansion rule

Do not add many issuers yet. Add one deliberately different issuer after the Amazon recurring workflow is proven. The purpose is to test generality, not to inflate the demo corpus.

## Non-negotiable trust boundaries

The product remains intentionally non-autonomous in the financial decision sense. It may autonomously assemble, compare, validate, and prioritize evidence. It must not autonomously make trading decisions, predict default, declare covenant compliance, or mark a customer report approved without an accountable reviewer.
