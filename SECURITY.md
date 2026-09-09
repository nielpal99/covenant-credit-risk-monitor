# Security policy

## Scope

The monitor processes SEC filings and optional third-party document-provider outputs. API credentials, provider job metadata, rendered source documents, and generated issuer artifacts must remain outside version control.

## Credential handling

- Store `REDUCTO_API_KEY` and `LLAMA_CLOUD_API_KEY` only in the local environment or an approved secret manager.
- Never commit `.env` files, API keys, bearer tokens, provider result URLs, or credentials embedded in logs.
- Paid provider execution is explicitly cost-gated by the application; do not remove that guard.

## Reporting issues

Do not include confidential filings, credentials, provider payloads, or customer data in a public issue. Reproduce with the smallest sanitized fixture possible.
