## 1. Settle Before Writing

These change what gets written. Each is a documentation read, not a cloud operation.

- [ ] 1.1 Read the AKS "sync a secret as a Kubernetes secret" how-to and establish whether the synced Kubernetes Secret is materialised only when a pod mounts the CSI volume. `design.md` D5 flags this as unverified. If it holds, the backend Deployment carries a `csi` volume mount it never reads, and that needs the one-line comment `CLAUDE.md` allows for a mechanical constraint. Record the answer in D5, replacing the "not verified in this pass" paragraph.
- [ ] 1.2 Read the Azure Key Vault soft-delete overview and establish whether a deleted vault's name is reserved for a retention period. `design.md` D10 flags this as unverified, and it decides whether any teardown step may touch the vault at all. Record the answer in D10.
- [x] 1.3 Decided: the metrics workspace is defined in the cluster resource group, alongside items 1–8, and is destroyed with the cluster on every teardown (`design.md` D10). This is interim — D10 records the trigger that moves it to the platform resource group later — and needs no further action here beyond building Section 5 against it.
- [ ] 1.4 Confirm `design.md`'s D1 claim that `docker-compose.yaml`'s `NEXT_PUBLIC_API_URL` entry never reaches the browser bundle, by grepping a built `frontend/.next/` for the compose value. It is currently marked **[reasoned]**. If the claim is wrong, D1's build-argument decision needs revisiting before Section 2.3.

## 2. Application Changes

- [ ] 2.1 In `backend/api/main.py`, read the CORS origin list from an environment variable, defaulting to `["http://localhost:3000"]` when unset (D6). No other behaviour changes.
- [ ] 2.2 Add a case to `backend/tests/test_api_main.py` covering the configured-origin path alongside the existing default-origin coverage, and confirm the existing cases still pass unmodified.
- [ ] 2.3 Add a build argument to `frontend/Dockerfile` supplying `NEXT_PUBLIC_API_URL` at image-build time, defaulting to today's value so a local `docker build` with no argument produces today's image (D1).
- [ ] 2.4 Run `cd backend && pytest tests/ -v`, `ruff check backend/`, `ruff format --check backend/`, `cd frontend && npm test` and `npm run lint`. Record the actual output. These must pass before anything below is written.
- [ ] 2.5 Run `docker-compose up --build` and confirm the local stack behaves exactly as it does today with no new environment set. Do not run `docker-compose down -v`.

## 3. Workload Definition — the Chart

Lands at `Infrastructure/helm/travel-agent/` (D13). `Infrastructure/k8s/`'s two files become templates here and that directory is removed.

- [ ] 3.1 Create `Chart.yaml` and `values.yaml`. `values.yaml` declares, at minimum: image repository and tag, the backend's accepted CORS origins, the frontend's API base URL, replica counts, and resource requests and limits for both containers.
- [ ] 3.2 Port `Infrastructure/k8s/backend-deployment.yaml` and `backend-service.yaml` to templates, substituting the hardcoded `image: travel-agent-backend:latest` and the CORS origin with values. Service stays `ClusterIP`.
- [ ] 3.3 Add frontend Deployment and Service templates (D1). Service stays `ClusterIP`.
- [ ] 3.4 Add resource requests and limits to both containers (D14). Requests are what make a capacity shortfall surface as a scheduling decision rather than as contention; Section 9 measures whether the values chosen here are right.
- [ ] 3.5 Add the ServiceAccount template carrying the workload-identity annotation, and the pod-template label the platform requires for identity injection (D5).
- [ ] 3.6 Add the `SecretProviderClass` template binding the vault and the secret name, and whatever volume mount task 1.1 established is required for the Kubernetes Secret to materialise (D5).
- [ ] 3.7 Add the `Gateway` and `HTTPRoute` templates (D2). Keep the provider binding — gateway class name and load-balancer annotations — in `values.yaml`, so the routing rules themselves carry to another provider unchanged.
- [ ] 3.8 Annotate the `Gateway` onto an internal load balancer (D2). The entry point must have no public address.
- [ ] 3.9 Add the vector-store templates: whichever of Chroma-in-server-mode or a single-replica volume Section 3.10 decides, plus the ingestion step that populates it, expressed as part of the chart rather than as an operator command (D11).
- [ ] 3.10 Decide server mode versus single-replica volume, and record the decision and its reason in `design.md` D11, closing that Open Question. `design.md` deliberately left this to implementation; the spec requires only that no replica holds the corpus locally and that no manual post-deploy command is needed.
- [ ] 3.11 Delete `Infrastructure/k8s/`. Do not repoint the path references in `docs/step5.md` or `docs/plan.md` — `proposal.md`'s Non-Goals records why those are records, not stale text.
- [ ] 3.12 Run `helm template` over the chart with a representative values file and pipe it to `kubectl apply --dry-run=client`. Record the output. This is the lint step the loose YAML never had.
- [ ] 3.13 Read the rendered routing resources against a port to another managed Kubernetes provider, and record exactly which fields would have to change. The set must be limited to the gateway class name and the provider annotations; anything else in it means a provider detail leaked into a routing rule, and is fixed here rather than left for Step 10 to discover.

## 4. Infrastructure Definitions — Platform State

Lands at `Infrastructure/terraform/platform/` (D10). Applied once; survives teardown. Nothing in this section is applied here — Section 7 gates that.

- [ ] 4.1 Define the platform resource group.
- [ ] 4.2 Define the container registry (D4).
- [ ] 4.3 Define the Key Vault, and the secret *object* only. The secret's value is set out-of-band and must never enter Terraform state or the repository (D5).
- [ ] 4.4 Define the user-assigned identity and federated credential for CI, scoped to this repository and the branch that deploys (D4).
- [ ] 4.5 Define the user-assigned identity and federated credential for the backend's ServiceAccount, and the role assignment granting it read access to the vault secret (D5).
- [ ] 4.6 Confirm no `output` and no resource attribute in this state exposes a secret value, and that the state file this configuration would produce contains no key material.

## 5. Infrastructure Definitions — Cluster State

Lands at `Infrastructure/terraform/cluster/` (D10). Destroyed and recreated every session. Reads the platform state's outputs; never writes to it.

- [ ] 5.1 Define the cluster resource group.
- [ ] 5.2 Define the managed cluster on the Free tier (D3), with the OIDC issuer and workload identity enabled (D5).
- [ ] 5.3 Define the system node pool: two nodes at the SKU D14 decided. The SKU and node count are variables, so Section 9's measurement can change them without a rewrite.
- [ ] 5.4 Enable the Key Vault secrets provider add-on (D5), the application routing add-on's Gateway API implementation (D2), and managed Prometheus metrics collection with the minimal ingestion profile (D8).
- [ ] 5.5 Define the registry attachment granting the cluster pull access (D4).
- [ ] 5.6 Define the metrics workspace in the cluster resource group (D10, task 1.3).
- [ ] 5.7 Confirm every region-bearing resource in Sections 4 and 5 reads a single region variable, so no resource can be created in a second region by omission.
- [ ] 5.8 Confirm this configuration's state contains no reference that would let `terraform destroy` here reach anything in the platform state.

## 6. Pipeline

- [ ] 6.1 Add a `push` job to `.github/workflows/ci.yml`, gated on `github.ref == 'refs/heads/main' && github.event_name == 'push'`, needing `build-backend` and `build-frontend`. Do not copy `docs/step7.md`'s draft unchanged — it declares `needs: build`, which does not exist in this workflow (D4).
- [ ] 6.2 Authenticate the job by OIDC federation with `permissions: id-token: write`, passing client, tenant and subscription identifiers. No long-lived credential is stored in the repository's secrets (D4).
- [ ] 6.3 Build and push both images tagged with the commit SHA. Pass the cluster's backend URL as the frontend image's build argument (D1).
- [ ] 6.4 Add the deploy step: obtain cluster credentials, then `helm upgrade --install` with the image tag and the registry login server supplied as values (D13).
- [ ] 6.5 Add the chart render-and-validate check from task 3.12 as a step that runs on pull requests, where no cloud credential exists.
- [ ] 6.6 Confirm on a pull request that the publish and deploy steps do not run and the pipeline still reports success — the "passes on a fresh fork with zero configuration" property from `docs/step7.md`.

## 7. Pre-Apply Gate

Nothing below Section 6 has created a billable resource. Everything below this section does. The spec requires approval of the inventory and authorization of the specific raise to be two separate permissions, and this section is where the second one is obtained.

- [ ] 7.1 Confirm the cost inventory in `design.md` is still accurate against the definitions actually written in Sections 4 and 5. If a resource was added, removed or resized while writing them, update the inventory and return to the owner for re-approval before continuing.
- [ ] 7.2 Present the raise to the owner: what will be created, the expected hourly cost while up, the expected standing cost after teardown, and the intended session length. Obtain an explicit go-ahead for **that specific raise**.
- [ ] 7.3 Record in `docs/step9-raise-evidence.md` the date, the commit, and the wording of the go-ahead, before running anything.
- [ ] 7.4 **Stop rule.** If 7.2 has not happened, no task in Sections 8, 9 or 10 may run. The owner having approved the cost inventory is not authorization to apply. Approval of one raise is not authorization for the next one.

## 8. Raise

Ordering is not optional: platform state before cluster state (D10). Every command and its output goes into the evidence file as it runs, not afterwards.

- [ ] 8.1 Apply the platform state. Record the output.
- [ ] 8.2 Set the secret value into the vault out-of-band. Confirm afterwards that the value appears in no Terraform state file and no repository file.
- [ ] 8.3 Query the Kubernetes versions the region actually offers, and record them. `design.md` D2 notes the supported-version table is global and carries a ten-business-day propagation caveat; this is the one call that settles it. Record which version the cluster is created at.
- [ ] 8.4 Before applying the cluster state as written, attempt to create the node pool at a 2-vCPU SKU and record the platform's response verbatim. `design.md` D14 rests on a documented minimum that Microsoft's own Terraform samples contradict. If the create is refused, the requirement is enforced and D14 stands. If it is accepted, destroy the result immediately, record that the documented requirement is not enforced in practice, and record the cost consequence D14 already quantified.
- [ ] 8.5 Apply the cluster state. Record the output and the elapsed time.
- [ ] 8.6 Record the node OS disk type and size the platform actually provisioned, closing that Open Question. `design.md`'s inventory prices two possibilities because the default was not verified.
- [ ] 8.7 Deploy the workload with `helm upgrade --install`, or let the pipeline's deploy step do it, and record which path was used.

## 9. Verify

Each task's output is a measurement, quoted into the evidence file. A task that cannot be measured is reported as unmeasured rather than asserted.

- [ ] 9.1 **Capacity.** Run `kubectl describe node` and `kubectl top pods -A`. Record allocatable capacity per node, the actual requests of the platform's own components, and the workload's. `design.md` D14 states explicitly that the add-on pods' requests are not known and are not guessed; this is the measurement that replaces the estimate. Record whether any pod is `Pending`.
- [ ] 9.2 **Secret delivery.** Confirm the backend pod obtained the secret and serves a real `/chat` request. Record whether the CSI volume mount established in task 1.1 was in fact required, by testing the configuration without it if the answer was "not required".
- [ ] 9.3 **Secret containment.** Search the repository at this commit, both Terraform state files, and the built image layers for the secret value. Record the searches and their results. Separately, list the repository's configured CI secrets and variables and record that none is a credential that would still authenticate if copied out.
- [ ] 9.4 **End-to-end through the browser client.** Reach the frontend, ask a travel question, and confirm the response is served by the backend on the same cluster. Record the request and the response.
- [ ] 9.5 **Routing.** Confirm requests reach both services through the `Gateway` and `HTTPRoute`, and that neither Service is individually reachable from outside the cluster.
- [ ] 9.6 **The entry point is internal.** Confirm the Gateway's load balancer has no public address, and that the only access path is the authenticated tunnel. Record the address it does have.
- [ ] 9.7 **Corpus availability.** Ask a retrieval-grounded question and record the answer. Delete the serving pod, wait for its replacement, ask the same question, and record that answer. They must match, with no operator action in between.
- [ ] 9.8 **Reproducibility.** Record every command run between task 8.1 and here that was not already written in the repository. The spec requires that set to be empty except for supplying the secret value; anything else in it is a defect to fix in Sections 3–6, not an observation to file.
- [ ] 9.9 **Parameterisation.** Deploy a second commit and record that nothing changed but the supplied values — no tracked file edited, no rendered manifest committed.
- [ ] 9.10 **Metrics.** Query container CPU, memory working set and CPU throttling per application container from the workspace. Record the queries and their results.
- [ ] 9.11 **Grafana datasource.** Add the workspace as a second datasource on the existing local Grafana and confirm it queries. Record that the existing Prometheus datasource and its history are untouched.
- [ ] 9.12 **Ingestion volume.** Read the workspace's own ingestion metric for the session and record it. `design.md` D8's cost figure is arithmetic over two assumed inputs; this measurement replaces it, and per `CLAUDE.md` it then lives in one place and is pointed at.
- [ ] 9.13 **Local history untouched.** Confirm `prometheus_data` was neither read from, written to, nor deleted by any step in Sections 8 or 9.
- [ ] 9.14 **Nothing history-bearing was placed on the cluster.** List the workloads actually running in every namespace and record that none is a metrics-storage or dashboard workload whose data would be expected to outlive the session. Destroying this cluster must destroy no observability history.
- [ ] 9.15 **Grant revocation.** Runs last in this section deliberately — it breaks a working deployment, and nothing after it but teardown needs the deployment to work, so a slow or failed restore blocks nothing. Remove the workload identity's read grant on the vault secret, restart the backend pod, and record what the replacement does: it must fail to obtain the secret rather than succeed from anything cached. Then restore the grant and record how long it took to take effect. `design.md` D4 records role-propagation latency as documented behaviour, so a slow restore is a measurement for the evidence file, not a failure. Task 9.3 establishes only the structural claim that no cacheable credential exists; this is the behavioural one.

## 10. Teardown

- [ ] 10.1 Destroy the cluster state. Record the output.
- [ ] 10.2 Confirm no per-hour billable resource from the session remains: no cluster, no node pool, no load balancer, no public IP, and no orphaned node resource group.
- [ ] 10.3 Confirm the registry, the vault and both identities survive, and that the vault secret is still readable by the next raise.
- [ ] 10.4 Confirm the pipeline still publishes on the next merge to the default branch — teardown must not have broken CI.
- [ ] 10.5 Confirm the local stack is untouched: `prometheus_data` and `grafana_data` intact, local Grafana still serving its existing dashboards. Do not run `docker-compose down -v` at any point in this section or any other.
- [ ] 10.6 Record the standing cost now in effect, and confirm it matches what `design.md`'s inventory said would survive.

## 11. Record

Two different things get written here, to two different homes, and neither is `tasks.md` itself once this change archives. The observations go to `docs/`, following the precedent `docs/step8-9d-evidence.md` sets — that stays true. The raise/teardown *procedure* does not stay in this file: `openspec/config.yaml` governs `docs/` against `openspec/`, and both live under a change directory that moves to `openspec/changes/archive/` on archiving, same as `design.md`'s pointers and `docs/step8.md`'s scope note did. `README.md` is this repository's only permanent operator-facing document and is not governed by that split, so it is where a runbook that has to survive archiving belongs.

- [ ] 11.1 Complete `docs/step9-raise-evidence.md` from the material recorded during Sections 8, 9 and 10. Commands and their output, not summaries. State the commit and the cluster version the run was made against.
- [ ] 11.2 In that file, state which previously-unverified claims this run settled and what each measured: the pool's actual fit, the region's available versions, the CSI sync's volume requirement, the node OS disk default, and whether a 2-vCPU system pool is refused in practice.
- [ ] 11.3 In that file, name every question the run did not settle, and what would settle each. A gap that is not named reads afterwards as a question that was answered.
- [ ] 11.4 Update the affected `design.md` decisions to point at the measurement rather than restating it — D8's estimated ingestion figure and D14's capacity argument in particular. Each measurement lives in exactly one place.
- [ ] 11.5 Add `docs/step9-raise-evidence.md` to `CLAUDE.md`'s Docs section, following the existing one-line entries.
- [ ] 11.6 Add a "Deploying to Azure (Step 9)" section to `README.md` documenting the raise procedure as an operator runbook — apply the platform state, set the secret value, apply the cluster state, deploy the chart — in imperative steps matching the style of the README's existing "Running Locally" section, referencing this file's Sections 4, 5, 7 and 8 rather than restating their content.
- [ ] 11.7 In that section, document the teardown command, and immediately beside it — not in a separate paragraph an operator could miss — state explicitly that teardown has no relationship to `docker-compose down -v`, which destroys `prometheus_data` and cannot be regenerated.
- [ ] 11.8 In that section, document what teardown destroys, what survives it, and the standing cost of what survives, pointing at `design.md`'s inventory for the figure rather than restating it (`CLAUDE.md`: never restate figures).
- [ ] 11.9 Confirm no step written anywhere in this change, including the new `README.md` section, instructs a client to disable certificate verification, and that the README's access instructions name the authenticated tunnel rather than a plaintext address someone could reuse from elsewhere.
- [ ] 11.10 Re-read this change's spec scenarios against what the run actually observed. Any scenario the run contradicted is a spec defect or an implementation defect; report which, and stop rather than reconciling the spec to the observation.
