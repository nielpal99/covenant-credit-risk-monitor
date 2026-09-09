# GitHub publication status

## Current decision

The prototype is published at https://github.com/nielpal99/covenant-credit-risk-monitor. The repository contains source, tests, and documentation only; generated Amazon/provider artifacts remain local.

## Safe boundary prepared

- Generated corpus, provider caches, rendered PDFs, local work files, and outputs are ignored.
- Public documentation no longer contains the local Filing Radar path.
- Credential-handling and issue-reporting rules are documented in `SECURITY.md`.
- GitHub Actions runs the corpus-independent public test suite on pushes and pull requests.

## Remaining publication work

1. Add a small sanitized fixture set so a clean checkout can run meaningful tests without the 123 MB local SEC/provider corpus.
2. Corpus-dependent integration tests are separated from the public package tests; the remaining work is to add a small sanitized fixture set for meaningful clean-checkout coverage.
3. Choose and add an explicit open-source license and repository CI policy before treating the repository as a finished public project.

The current Amazon report remains a local evidence artifact and is not treated as public repository content.
