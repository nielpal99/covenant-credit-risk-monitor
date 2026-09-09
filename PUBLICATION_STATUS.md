# GitHub publication status

## Current decision

The project is not ready to push as a public repository yet. No external repository has been created and no code has been pushed.

## Safe boundary prepared

- Generated corpus, provider caches, rendered PDFs, local work files, and outputs are ignored.
- Public documentation no longer contains the local Filing Radar path.
- Credential-handling and issue-reporting rules are documented in `SECURITY.md`.

## Remaining publication work

1. Add a small sanitized fixture set so a clean checkout can run meaningful tests without the 123 MB local SEC/provider corpus.
2. Separate corpus-dependent integration tests from fixture-based package tests and make the public test command deterministic.
3. Choose and add an explicit open-source license before publication.
4. Create the external repository and push only after the sanitized test and secret preflight passes.

The current Amazon report remains a local evidence artifact and is not treated as public repository content.
