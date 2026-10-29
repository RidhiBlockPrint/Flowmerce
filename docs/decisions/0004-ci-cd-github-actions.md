# ADR 0004: CI with GitHub Actions; deployment deferred

- Status: approved (owner approved Stage A on 2026-10-29)
- Date: 2026-10-29

## Decision
1. Use **GitHub Actions** for continuous integration. The repository is already on GitHub, and the planning documents list it for CI/CD.
2. **Stage A** (this decision) is CI only: lint, type check and tests on Python 3.12 and 3.14; the frontend type check and build on Node 24; a Python smoke test that boots the app on a throwaway folder; and weekly Dependabot update pull requests.
3. **Deployment, release artifacts and a container image are not part of this decision.** They wait on the hosting choice and the database decision (roadmap B1).
4. Workflow files are YAML configuration. Their steps are one-line commands; any logic lives in Python (`scripts/ci_smoke.py`), consistent with ADR 0001.
5. Third-party Actions are pinned to full commit hashes, verified against GitHub's API when added.

## Rationale
The checks the owner needs already exist and pass locally. Running them automatically on every change catches regressions before they are merged, and a throwaway-folder smoke test proves the app boots without touching real data or secrets.

## Alternatives considered
- No CI, relying on local checks (status quo).
- Another CI service (GitLab CI, CircleCI, Jenkins): more setup and a second account for no benefit while the code is on GitHub.
- Pinning Actions to version tags only: simpler, but a moved tag could change what runs.
- Building deployment now: not possible without a hosting target, and unsafe with the current SQLite file storage.

## Advantages
- Every push and pull request is checked the same way, on a clean machine.
- No secrets are needed, so there is little to leak.
- Python 3.12 (the declared minimum) is tested for the first time.
- Dependency and Action updates arrive as small, reviewable pull requests.

## Disadvantages
- It cannot be run end to end locally; it is proven only by running on GitHub.
- The first run may fail (most likely on Python 3.12, which has never been tested). That would be a real finding, not a pipeline fault.
- It adds a maintenance task: reviewing Dependabot pull requests.
- Private-repository Actions minutes are limited (small for this workload).
- The workflow YAML could not be machine-validated locally (no YAML parser installed); GitHub validates it on the first run.

## Consequences and dependencies
- The owner must change GitHub settings by hand (workflow permissions, branch protection, Dependabot alerts); steps are in `docs/operations/ci-cd.md`.
- Pushing workflow files needs a GitHub credential with the `workflow` permission; this has not been verified.
- A deployment stage needs: a hosting decision, the database decision (B1), a secrets plan, and GitHub Environments with manual approval. Open questions are tracked in the roadmap.
- Roadmap item F1 moves to Implemented (not yet run on GitHub).
