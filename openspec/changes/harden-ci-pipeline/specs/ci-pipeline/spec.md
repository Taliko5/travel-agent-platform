## ADDED Requirements

### Requirement: Backend verification job
The system SHALL run a `test` job on every push to `main` and every pull request targeting `main` that changes backend-relevant paths, which installs backend dependencies, runs `ruff check backend/`, and runs `pytest backend/tests/ -v`.

#### Scenario: Backend change on a PR
- **WHEN** a pull request modifies a file under `backend/`
- **THEN** the `test` job runs lint and tests and the PR shows a `test` status check

#### Scenario: Docs-only change
- **WHEN** a pull request modifies only files under `docs/`
- **THEN** the `test` job still reports a status (skipping its real work via path filtering) so it remains satisfiable as a required check

### Requirement: Backend Docker build job
The system SHALL run a `build-backend` job, gated on `test` passing, that builds `backend/Dockerfile` with `push: false` using GitHub Actions layer caching.

#### Scenario: Backend test job fails
- **WHEN** the `test` job fails on a pull request
- **THEN** `build-backend` does not run

#### Scenario: Backend test job passes
- **WHEN** the `test` job passes
- **THEN** `build-backend` builds the backend Docker image without pushing it anywhere

### Requirement: Frontend verification job
The system SHALL run a `frontend` job on every push to `main` and every pull request targeting `main` that changes frontend-relevant paths, which installs frontend dependencies via `npm ci`, runs `npm run lint`, runs `npm test`, and runs `npm run build`.

#### Scenario: Frontend change on a PR
- **WHEN** a pull request modifies a file under `frontend/`
- **THEN** the `frontend` job installs dependencies, lints, tests, and builds, and the PR shows a `frontend` status check

#### Scenario: Lint runs non-interactively
- **WHEN** the `frontend` job runs `npm run lint` in a CI runner with no TTY
- **THEN** linting completes and exits with a pass/fail status without prompting for ESLint installation

#### Scenario: Test step passes today with no tests authored
- **WHEN** the `frontend` job runs `npm test` and no test runner or test files exist yet
- **THEN** the placeholder `test` script exits successfully, so the job is not blocked by the absence of a real frontend test suite

#### Scenario: Real tests land later
- **WHEN** a future change (tracked separately as "Step 6c: Frontend unit tests") replaces the placeholder `test` script with a real test runner invocation and adds test files
- **THEN** the `frontend` job requires no workflow YAML change — `npm test` now exercises the real suite

### Requirement: Frontend Docker build job
The system SHALL run a `build-frontend` job, gated on `frontend` passing, that builds `frontend/Dockerfile` with `push: false` using GitHub Actions layer caching.

#### Scenario: Frontend job fails
- **WHEN** the `frontend` job fails on a pull request
- **THEN** `build-frontend` does not run

#### Scenario: Frontend job passes
- **WHEN** the `frontend` job passes
- **THEN** `build-frontend` builds the frontend Docker image without pushing it anywhere

### Requirement: Path-scoped job execution
The system SHALL skip a job's substantive work (but still report a status check) when no file relevant to that job's stack changed, using job-level path filtering rather than workflow-level triggers.

#### Scenario: Backend-only change
- **WHEN** a pull request only modifies files under `backend/`
- **THEN** `frontend` and `build-frontend` report success without running lint/build/docker steps, and `test`/`build-backend` run normally

#### Scenario: Frontend-only change
- **WHEN** a pull request only modifies files under `frontend/`
- **THEN** `test` and `build-backend` report success without running lint/test/docker steps, and `frontend`/`build-frontend` run normally

### Requirement: Concurrency control
The system SHALL cancel in-progress workflow runs for the same branch or pull request when a new run is triggered for that same ref.

#### Scenario: Rapid successive pushes to a PR branch
- **WHEN** a second push occurs to a PR branch while its first run is still in progress
- **THEN** the first run is cancelled and only the second run continues to completion

### Requirement: Least-privilege token permissions
The system SHALL request only `contents: read` permission for the workflow's `GITHUB_TOKEN`, rather than relying on the default broad permission set.

#### Scenario: Workflow execution
- **WHEN** any job in the workflow runs
- **THEN** its `GITHUB_TOKEN` has read-only access to repository contents and no write or administrative scopes

### Requirement: Required status checks on main
The `test`, `frontend`, `build-backend`, and `build-frontend` checks SHALL be configured as required status checks on the `main` branch, such that a pull request cannot be merged while any of them is failing or has not run.

#### Scenario: A required check is failing
- **WHEN** a pull request has a failing `test`, `frontend`, `build-backend`, or `build-frontend` check
- **THEN** GitHub blocks merging the pull request into `main` until the check passes

#### Scenario: Branch protection is not yet configured
- **WHEN** branch protection has not been configured on `main`
- **THEN** this requirement is not met and CI results are advisory only — this is documented as a manual, out-of-band prerequisite tracked outside version control

### Requirement: Automated dependency updates
The system SHALL define a `renovate.json` at the repo root covering `backend/requirements.txt` (pip) and `frontend/package-lock.json` (npm), such that outdated dependencies produce automated update pull requests once the Renovate GitHub App is installed on the repository.

#### Scenario: Renovate App not installed
- **WHEN** `renovate.json` exists but the Mend Renovate GitHub App has not been installed on the repository
- **THEN** no update pull requests or Dependency Dashboard issue are produced — installation is a required, manual, out-of-band prerequisite

#### Scenario: Renovate App installed
- **WHEN** the Renovate GitHub App is installed and `renovate.json` is present on the default branch
- **THEN** a Dependency Dashboard issue is created and outdated pip/npm dependencies produce update pull requests

### Requirement: Container image vulnerability scanning
The system SHALL scan the `build-backend` and `build-frontend` Docker images with Trivy after each is built, uploading results as SARIF to the repository's Security tab, without failing the build on findings.

#### Scenario: Image scan completes
- **WHEN** `build-backend` or `build-frontend` finishes building its image
- **THEN** a Trivy scan runs against that image and uploads SARIF results to the Security tab, and the job does not fail regardless of findings

#### Scenario: Future tightening
- **WHEN** existing base-image CVEs have been triaged (a follow-up outside this change's scope)
- **THEN** the scan step MAY be reconfigured to fail the job on `CRITICAL` (and later `HIGH`) severity findings

### Requirement: Secret scanning
The system SHALL scan pull request and push diffs for committed secrets using gitleaks, independent of and in addition to container image vulnerability scanning.

#### Scenario: Secret introduced in a diff
- **WHEN** a pull request's diff contains a pattern matching a known secret format (e.g. an API key)
- **THEN** the gitleaks job reports a finding on that pull request

#### Scenario: No secrets in diff
- **WHEN** a pull request's diff contains no matching secret patterns
- **THEN** the gitleaks job passes
