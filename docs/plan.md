# Plan

## Roadmap

| Step | Description | Status |
|---|---|---|
| 1–2 | LangGraph agent (intent classify + response) | Done |
| 3a | RAG: ChromaDB ingest + retriever | Done |
| 3b | RAG: Wire retriever into agent graph | Done |
| 4 | MCP servers — weather, flights, hotels | Done |
| 5 | Docker + docker-compose + k8s manifests | Done |
| 6 | Frontend — Next.js 14 / TypeScript | Done |
| 7 | GitHub Actions CI/CD | Done |
| 8 | Observability (Grafana, Prometheus, OpenTelemetry) | Done |
| 9 | Azure deployment (AKS) | Done |
| 10 | CI branch separation + browser-triggered cluster launch | Planned |
| 11 | Private networking — VNet, private endpoints, Private DNS, TLS | Planned |
| 12 | IaC quality gates + remote Terraform state | Planned |
| 13 | Container image and Helm chart hardening | Planned |
| 14 | Managed data service — PostgreSQL or Blob Storage | Planned |
| 15 | Port to AWS (EKS) | Planned |

---

## Steps 1–2: LangGraph Agent

- `agent/state.py` — `AgentState` TypedDict
- `agent/nodes.py` — `classify_intent`, `generate_response` using `gemini-3.5-flash`
- `agent/graph.py` — `build_graph()`, linear: START → classify → generate → END
- `api/main.py` — FastAPI with `GET /health` and `POST /chat`

Decisions: Gemini over OpenAI (free tier); `thinking_level="low"` for speed; intent allowlist + `.strip().lower()` + `next()` double validation.

---

## Step 3a: RAG — ChromaDB Ingest + Retriever

- `rag/data/` — 4 destination files (Abu Dhabi, Fukuoka, Lima, Riga)
- `rag/ingest.py` — embeds with `gemini-embedding-001`, saves to ChromaDB
- `rag/retriever.py` — `retrieve_context(query, k=2)` with lazy `get_vectorstore()`

---

## Step 3b: Wire RAG into Agent

- `context: Optional[str]` added to `AgentState`
- `retrieve_context_node` added to `nodes.py`
- Graph updated: classify → retrieve → generate

---

## Step 4: MCP Servers

See `docs/step4.md`.

Built: `weather_server.py` (live), `flight_server.py` (mock), `hotel_server.py` (mock), conditional routing in graph, `call_*_tool` nodes, lazy init for `get_model()` and `get_vectorstore()`.

Tests: 47 tests, all mocked, pass without `GOOGLE_API_KEY`.

---

## Step 5: Docker + docker-compose

See `docs/step5.md`.

Built: `backend/Dockerfile`, `.dockerignore`, `docker-compose.yaml`, `backend/.env.example`, `Infrastructure/k8s/backend-deployment.yaml`, `Infrastructure/k8s/backend-service.yaml`.

---

## Step 6: Frontend

See `docs/step6.md` and `openspec/changes/add-chat-frontend/`.

Built: Next.js 14 (App Router, TypeScript) chat UI, Chakra UI pastel "unicorn" theme. `frontend/src/app/components/` split into `ChatInterface.tsx` (state + `POST /chat` fetch), `MessageList.tsx`, `MessageBubble.tsx`, `ChatInput.tsx` (star send button), `SparkleHeader.tsx` — one component per concern so each can be swapped independently later. Containerized (`frontend/Dockerfile`) and added to `docker-compose.yaml`.

Also required adding `CORSMiddleware` to `backend/api/main.py` (`allow_origins=["http://localhost:3000"]`) — discovered during smoke testing that the backend had none, which silently blocked every browser `fetch` despite `curl` working fine.

Verified: `npm run dev` + local backend, and full `docker-compose up --build` — both confirmed intent + response round-trip end-to-end.

**UI polish** (`openspec/changes/improve-chat-ui/`): assistant responses now render as real markdown (`react-markdown` + `remark-gfm`, headings/bold/lists) instead of literal `#`/`**` characters via `MessageBubble.tsx`. New `ThinkingIndicator.tsx` shows a three-dot bounce + "...thinking" bubble in the message list while a request is in flight. `ChatInterface.tsx`'s outer panel now has a visible border/shadow card treatment, and the page background (`globals.css`) carries the unicorn pastel gradient that was previously accent-only. Also bumped frontend Node runtime 20 → 24 (latest LTS): `frontend/.nvmrc`, `package.json` `engines`, and `Dockerfile` base image all updated; `tsc`/`build`/`dev` verified clean under Node 24.18.0.

**Step 6c: Testing, Linting & Formatting** (`openspec/changes/step6c-test-lint-format/`): closed the gap left by Step 7's CI draft, which found the frontend had zero automated tests and no formatter, and the backend had no coverage for its actual request-handling path.

Frontend: Vitest + React Testing Library + jsdom (chosen over Jest for faster startup and less config against this Next.js/ESM setup). `frontend/src/test-utils.tsx` exports `renderWithProviders`, wrapping RTL's `render` with the real `Providers`/`ChakraProvider` component — every component test uses it instead of bare `render`, since the app always mounts inside the custom "unicorn" theme. 6 new test files, 21 tests, covering `ChatInput`, `MessageBubble` (including markdown rendering), `MessageList`, `ThinkingIndicator`, and `ChatInterface` (mocked `fetch`, asserts request shape + response rendering + loading-indicator lifecycle); `SparkleHeader` gets a smoke test only, being stateless/decorative. Added Prettier + `eslint-config-prettier` (`.prettierrc`, `format`/`format:check` scripts) and `@vitest/coverage-v8` (report-only, no thresholds). `frontend/package.json` also gained `eslint` + `eslint-config-next` here, since `harden-ci-pipeline` (the change that was going to add them) hadn't landed yet.

Backend: 3 new test files closing coverage gaps in `agent/graph.py` (`route_by_intent` branching), `api/main.py` (`/health`, `/`, `/chat` via `TestClient` with `api.main.graph` mocked — no LLM call, no API key needed — plus CORS header assertions), and `rag/retriever.py` (`retrieve_context` with `get_vectorstore` mocked). 63 tests total, all passing. Also discovered `pytest`, `pytest-asyncio`, and `ruff` were installed locally but never frozen into `backend/requirements.txt` — meaning CI's `pip install -r requirements.txt` step wouldn't have actually provided them; added all three plus `pytest-cov`. `ruff format --check backend/` and `pytest --cov=backend --cov-report=term` (report-only coverage) are now wired into the CI `test` job.

Frontend CI wiring (format-check, real `npm test`, coverage as actual workflow steps) is verified working locally but not yet wired into `.github/workflows/ci.yml` — that requires the `frontend` job `harden-ci-pipeline` introduces, which hadn't been applied yet at the time this landed.

---

## Step 7: GitHub Actions CI/CD

See `docs/step7.md` and `openspec/changes/harden-ci-pipeline/`.

Goal: backend (`test`/`build-backend`) and frontend (`frontend`/`build-frontend`) verification + Docker build jobs on push to `main` and PRs, gated by branch protection so the checks are a real merge requirement. No secrets required — all tests mocked. Step 9 adds a `push` job for ACR.

Built: `dorny/paths-filter` job-level path filtering (backend-only and frontend-only changes skip the other stack's real work while still reporting a required status), workflow-level `concurrency` (cancel superseded runs) and `permissions: contents: read`, the frontend job (`npm ci` → lint → test → build, using the ESLint config and Vitest suite `step6c-test-lint-format` already landed), `build-frontend` (Docker build parity with backend), Trivy image scanning (non-blocking, SARIF to the Security tab) on both build jobs, and a `gitleaks` job for secret scanning. `renovate.json` added at repo root for automated pip/npm dependency updates.

Branch protection on `main` (requiring `test`, `frontend`, `build-backend`, `build-frontend`) and installing the Mend Renovate GitHub App are manual, out-of-band repo-admin steps — not committable as code, tracked as follow-ups in `docs/step7.md`.

Merged via PR #1. All six jobs (`changes`, `gitleaks`, `test`, `frontend`, `build-backend`, `build-frontend`) reported green. Caught two real issues along the way: `aquasecurity/trivy-action` needed a `v`-prefixed tag, and even `v0.28.0` failed because its internal `setup-trivy` pin had been deleted upstream — fixed by bumping to `v0.36.0`. Since the PR only touched CI/docs config (no `backend/`/`frontend/` files), `frontend`/`build-backend`/`build-frontend`'s *real* steps (lint/test/build/Trivy) were correctly path-filtered out rather than actually exercised — confirms path filtering works as designed, but full validation of those jobs (and Trivy's SARIF upload) awaits the next PR that touches those paths. `gitleaks` isn't path-filtered and ran for real, no findings.

Follow-up: Python version was hardcoded in both `ci.yml` and `backend/Dockerfile` with no shared source of truth (unlike Node's `.nvmrc`). Added `backend/.python-version` and switched `actions/setup-python` to `python-version-file`, mirroring the Node pattern (branch `single-source-python-version`).

---

## Step 8: Observability

Stack: OpenTelemetry → FastAPI and LangGraph instrumentation; Prometheus → metrics scraping; Grafana → dashboards; CloudWatch → AWS log aggregation.

Key metrics: `/chat` latency (p50/p95/p99), intent distribution, LLM call duration, RAG retrieval rate.

**2026-09-21 addendum.** Step 9 redirected this project from AWS to Azure. CloudWatch was never actually wired up as a log sink — structured JSON logging still ships to stdout locally, unchanged. Moving the log destination to an Azure equivalent is unscoped future work, not part of Step 9.

---

## Step 9: Azure Deployment (AKS)

Deploy the containerized stack to Azure Kubernetes Service, with the infrastructure defined in Terraform.

**Why AKS, and not ECS or EKS.** The earlier version of this section offered ECS ("simpler") or EKS ("matches the k8s manifests from Step 5"). The second reason did not survive inspection: `Infrastructure/k8s/` holds two files covering the backend alone, out of the four services `docker-compose.yaml` runs, and every line of them changes on the way to a managed cluster anyway — image reference, secret source, service type. What genuinely carries between clouds is Kubernetes itself: Deployment, Service, Ingress, HPA, probes, `kubectl`. That layer is identical on AKS, EKS and GKE. The layer that does not carry is the cloud-specific one — network, identity, registry, ingress controller, log sink. AKS is a given for this step rather than a conclusion argued here; what is worth recording is that the choice decides only that second layer, and that Step 15 exists to prove the first layer really does move.

**The deliverable is the repository, not a running URL.** This step produces Terraform, manifests and documentation; the cluster is raised on demand and torn down afterwards rather than left running. Writing the Terraform does not finish the step — raising a cluster from it, verifying it, and destroying it does, with the result recorded. Several of the assumptions this step rests on cannot be settled any other way, and the change's design names which ones. A public URL would show the chat UI, which is the one thing this step does not build — the network, the cluster and the deployment pipeline that it does build are legible in the Terraform and in a verification record of the kind `docs/step8-9d-evidence.md` already sets a precedent for. Keeping the cluster ephemeral also keeps `POST /chat` off the open internet, which matters while it has no authentication, no rate limit and no request deadline (`chat-request-deadline` is still a proposal).

**The cluster is assembled by hand, not with AKS Automatic.** Automatic provisions nodes and ingress on the cluster's behalf; assembling ingress and workload identity directly costs more work, but keeps the network, identity and ingress decisions explicit and under version control instead of delegated to a managed default that cannot be inspected or altered later.

Open questions this step has to settle, before any billable resource is created:

- Where observability lives. Prometheus holds local history that a new cluster does not inherit. The choice is between lifting the Prometheus/Grafana pair into the cluster, deferring to Azure Monitor, or leaving it local and out of this step entirely.
- Container CPU and memory monitoring, which no orchestrator supplies for free, and what enabling it costs.
- Grafana's credentials. It still runs on its unchanged default login (`admin`/`admin`, printed in `docs/step8.md`'s "Running Locally"). Harmless only while `docker-compose.yaml` binds its published port to `127.0.0.1`, which that file now states explicitly rather than leaving to Docker's default — an earlier version of this line asserted a loopback binding the file did not actually have, and the claim went unchecked. It stops being harmless the moment anything exposes it past that. Decide the real credential before `grafana` is reachable from anywhere but a developer's own machine.

**2026-09-21 addendum.** The first two questions are settled: `design.md` D7 settles where observability lives, and D8 settles container CPU/memory monitoring and its cost — D8's own cost estimate was itself later replaced by a real measurement, `docs/step9-raise-evidence.md` task 9.12. The third question, Grafana's credentials, was **not** resolved — `design.md` D9 names it explicitly as a contradiction left deliberately unfixed.

Prerequisites: Steps 5 and 7 complete (Docker images, CI). Two pieces of earlier work were written against AWS and need redirecting rather than reusing: the image push job drafted in `docs/step7.md`'s "Step 9 extension" targets ECR, and Step 8's structured JSON logging was justified by CloudWatch's line-oriented ingestion. The logging work itself still stands — the sink changes, the format does not — but the requirement naming CloudWatch lives in `openspec/`, and moving it needs a change of its own rather than an edit here.

---

## Step 10: CI Branch Separation & Browser-Triggered Cluster Launch

Two proposals, neither designed or scheduled yet — noted here for later.

**Separate `main` from a `release` branch.** `main` would stay integration-only (tests, build, push images to the registry); merging into `release` is what would trigger the actual `helm upgrade --install` deploy. The current single `push` job conflates "did the code merge cleanly" with "deploy this to whatever cluster happens to be raised right now" — surfaced concretely in `openspec/changes/step9-aks-deployment/tasks.md` task 10.4, where the deploy step failed simply because no cluster was raised at the time, which a merge to `main` alone can't distinguish from an actual regression.

**Trigger a cluster raise/teardown from a browser.** A GitHub Actions `workflow_dispatch` button, or similar, rather than requiring the operator to run Terraform/`az` commands by hand in Cloud Shell every time.

---

## Step 11: Private Networking — VNet, Private Endpoints, Private DNS, TLS

Not designed or scheduled yet — noted here for later.

**Why.** Step 9 keeps the workload off the public internet at the ingress layer only: the Gateway sits on an internal load balancer (`design.md` D2) and carries plain HTTP (D15). Everything underneath is left to Azure's defaults — the cluster has no explicit `network_profile` and no VNet this repository owns, and the registry and Key Vault are reached over their public endpoints. The network layer is the one part of the Azure design that is currently implicit rather than decided.

Scope:

- A Terraform-managed VNet with dedicated subnets (nodes, private endpoints, and a delegated subnet reserved for Step 14), with the AKS cluster placed in it on Azure CNI Overlay.
- Private endpoints for Key Vault and the container registry, with Private DNS Zones (`privatelink.vaultcore.azure.net`, `privatelink.azurecr.io`) linked to the VNet, and public network access disabled on both.
- TLS on the Gateway listeners — cert-manager, or a certificate held in Key Vault — revisiting D15.
- A cost check first: ACR private endpoints require the **Premium** SKU, which the current Basic registry (D4) does not support. This decision belongs in the design, not in the apply.
- Verification in the same style as `docs/step9-raise-evidence.md`: DNS inside the cluster resolves the vault and registry to private IPs, and the public endpoints refuse connections.

Placement matters for the two-layer split (D10): a VNet the persistent platform layer depends on (private endpoints) cannot live in the cluster resource group that is destroyed on every teardown.

---

## Step 12: IaC Quality Gates + Remote Terraform State

Not designed or scheduled yet — noted here for later.

**Why.** The CI pipeline verifies application code, container images and the Helm chart, but not the Terraform. Both states are local (`design.md` D10), which suits one operator but gives no locking and no shared source of truth.

Scope:

- A `terraform` CI job, path-filtered on `Infrastructure/terraform/**` like the existing jobs: `terraform fmt -check`, `terraform validate`, `tflint`, and a static security scan (`checkov` or `trivy config`).
- `terraform plan` on pull requests, with the plan posted to the PR, authenticated through the existing OIDC federation (D4) rather than a stored secret.
- Remote state in an Azure Storage account (`azurerm` backend, blob lease locking), created once, outside both states it serves.
- Commit `Infrastructure/terraform/cluster/.terraform.lock.hcl` — currently only the platform state's lock file is tracked.

---

## Step 13: Container Image and Helm Chart Hardening

Not designed or scheduled yet — noted here for later.

**Why.** The images and the chart are correct but minimal: both images run as root and are single-stage, Trivy findings never fail the build (`exit-code: '0'`), and the chart hardcodes resource names.

Scope:

- Images: non-root user, multi-stage builds, and Next.js `output: "standalone"` for a smaller frontend runtime image.
- Trivy: fail the build on `CRITICAL` findings once the current baseline is triaged.
- Chart: pod and container `securityContext` (`runAsNonRoot`, `readOnlyRootFilesystem` where possible, dropped capabilities), a default-deny `NetworkPolicy` with explicit allows, `_helpers.tpl` for release-scoped names and labels, and `helm lint` in the `chart-lint` job.
- Deploy: `helm upgrade --install --atomic --wait` so a failed rollout reverts on its own.
- Supply chain: pin third-party actions to commit SHAs, pin `kubelogin` to a version instead of `latest`, and install CRDs in `chart-lint` from a release tag instead of a `main`-branch URL.
- RBAC: revisit CI's temporary "Azure Kubernetes Service RBAC Cluster Admin" role (`Infrastructure/terraform/cluster/role-assignments.tf`, `design.md` D4) — replace it with a namespace-scoped custom role or Kubernetes RBAC covering only the chart's objects and CRDs, verified with `kubectl auth can-i`.

---

## Step 14: Managed Data Service — PostgreSQL or Blob Storage

Not designed or scheduled yet — noted here for later. One of the two, not both; the choice is part of the design.

**Why.** Everything the workload stores today lives on a single `ReadWriteOnce` PVC (ChromaDB), which is also why the backend Deployment uses the `Recreate` strategy. There is no managed data service in the architecture, and no data path that exercises the private networking from Step 11.

Options:

- **Azure Database for PostgreSQL Flexible Server** with private access (VNet integration on the delegated subnet from Step 11) — for example, to persist conversation history, which the API currently does not keep. Authenticating with Microsoft Entra ID through the backend's existing Workload Identity (D5) would keep the "no stored credentials" property instead of adding a database password.
- **Azure Blob Storage** behind a private endpoint — as the source of truth for the RAG documents in `backend/rag/data/`, which would be ingested from storage by the `rag-ingest` init container instead of being baked into the image.

Either way, Step 11 comes first: the point is the private data path, not the service itself.

---

## Step 15: Port to AWS (EKS)

Take the Step 9 workload to EKS. The Kubernetes manifests should cross unchanged; the Terraform, the identity model, the registry and the log sink will not.

Deferred on purpose. The value of this step is the port itself — a repository that demonstrates portability instead of asserting it — and with Step 9 complete, the port is unblocked and ready to be picked up whenever prioritized: still deferred by choice, not by a missing prerequisite.
