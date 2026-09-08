## 1. Settle Before Writing

These change what gets written. Each is a documentation read, not a cloud operation.

- [x] 1.1 Read [CSI driver configuration options: Sync mounted content with a Kubernetes secret](https://learn.microsoft.com/en-us/azure/aks/csi-secrets-store-configuration-options) — confirmed: the synced Kubernetes Secret is materialised only once a pod mounts the CSI volume, and is deleted again when the last consuming pod is removed. Recorded in `design.md` D5 with citation, replacing the "not verified" paragraph; the backend Deployment's `csi` volume mount carries the one-line comment `CLAUDE.md` allows for this mechanical constraint.
- [x] 1.2 Read [Key Vault soft-delete overview](https://learn.microsoft.com/en-us/azure/key-vault/general/soft-delete-overview) — confirmed: a soft-deleted vault's name can't be reused until its retention period expires, configurable 7–90 days at creation, 90 by default. Recorded in `design.md` D10 with citation, replacing the "not verified" sentence; noted there that this design sets no retention period explicitly, so the vault gets the 90-day default unless a task below states otherwise.
- [x] 1.3 Decided: the metrics workspace is defined in the cluster resource group, alongside items 1–8, and is destroyed with the cluster on every teardown (`design.md` D10). This is interim — D10 records the trigger that moves it to the platform resource group later — and needs no further action here beyond building Section 5 against it.
- [x] 1.4 Confirmed. Built `frontend/` with `NEXT_PUBLIC_API_URL=http://build-time-marker.example:8111` (a value chosen not to collide with anything else) — it was inlined into `.next/static/chunks/app/page-*.js` and `.next/server/app/page.js`. Started that same build with `next start` under a *different* runtime value, `NEXT_PUBLIC_API_URL=http://runtime-marker.example:9222` (mirroring what `docker-compose.yaml`'s `environment:` entry does — set a value only the running container's process sees, after the build already happened). The served JS chunk still contained only `build-time-marker.example`; `runtime-marker.example` appeared nowhere in the served page or chunk. The compose entry is inert, as D1 reasoned; the claim is not wrong, so D1's build-argument decision (Section 2.3) stands unchanged. `frontend/.next/` is gitignored — no tracked file changed (`git status --short` clean).

## 2. Application Changes

- [x] 2.1 In `backend/api/main.py`, `_cors_allowed_origins()` reads `CORS_ALLOWED_ORIGINS` (comma-separated), defaulting to `["http://localhost:3000"]` when unset, and `allow_origins=_cors_allowed_origins()` replaces the literal list. No other behaviour changes.
- [x] 2.2 Added `TestCORS.test_configured_origin_is_used_when_env_var_set` to `backend/tests/test_api_main.py`. It calls the real `_cors_allowed_origins()` against a fresh throwaway `FastAPI`/`TestClient` rather than `api.main`'s already-built module-level `app` — reloading `api.main` to pick up a changed env var would re-run its OTel provider setup for no reason this test needs. The two existing CORS cases are unmodified and still pass.
- [x] 2.3 `frontend/Dockerfile` gained `ARG NEXT_PUBLIC_API_URL=http://localhost:8000` and `ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL` before `RUN npm run build`, matching today's inlined-fallback value exactly, so a `docker build` with no `--build-arg` produces today's image.
- [x] 2.4 Run and recorded:
      ```
      $ cd backend && pytest tests/ -v
      ======================== 78 passed, 1 warning in 4.53s ========================
      $ ruff check backend/
      All checks passed!
      $ ruff format --check backend/
      26 files already formatted
      $ cd frontend && npm test
      Test Files  6 passed (6)
           Tests  21 passed (21)
      $ npm run lint
      ✔ No ESLint warnings or errors
      ```
      All five pass. (The pytest run's trailing `--- Logging error ---`/`I/O operation on closed file` traceback is the console `BatchSpanProcessor`'s background export thread writing after interpreter shutdown, printed after "78 passed" — pre-existing and unrelated to this change, not a test failure.)
- [x] 2.5 Ran `docker-compose up --build -d`. All four services reached `healthy`/`Up` with no config other than this repository's own files — no `CORS_ALLOWED_ORIGINS` or overriding `NEXT_PUBLIC_API_URL` set anywhere:
      ```
      $ docker-compose ps
      backend      Up (healthy)   127.0.0.1:8000->8000/tcp
      frontend     Up             127.0.0.1:3000->3000/tcp
      grafana      Up (healthy)   127.0.0.1:3001->3000/tcp
      prometheus   Up (healthy)   127.0.0.1:9090->9090/tcp

      $ docker-compose exec -T backend env | grep -i cors
      (CORS_ALLOWED_ORIGINS not set — default path is active)
      $ curl -i -X OPTIONS localhost:8000/chat -H "Origin: http://localhost:3000" ...
      HTTP/1.1 200 OK / access-control-allow-origin: http://localhost:3000
      $ curl -i -X OPTIONS localhost:8000/chat -H "Origin: http://evil.example.com" ...
      HTTP/1.1 400 Bad Request

      $ docker-compose exec -T frontend env | grep -i NEXT_PUBLIC
      NEXT_PUBLIC_API_URL=http://localhost:8000
      $ docker-compose exec -T frontend sh -c "grep -rl localhost:8000 .next/static/chunks"
      .next/static/chunks/app/page-c3c9f7e66ffa18da.js

      $ curl -s -X POST localhost:8000/chat -d '{"message":"What is the weather in Tokyo?"}'
      {"intent":"weather","response":"The current weather in Tokyo..."}   (real end-to-end response)
      ```
      CORS accepts `localhost:3000` and rejects an unconfigured origin, exactly as before 2.1; the frontend build argument added in 2.3 defaulted to `http://localhost:8000` and the bundle carries it, exactly as before 2.3. No behavior differs from today. `docker-compose down -v` was not run — the stack is still up, left for the user's own call on when to stop it.

## 3. Workload Definition — the Chart

Lands at `Infrastructure/helm/travel-agent/` (D13). `Infrastructure/k8s/`'s two files become templates here and that directory is removed.

- [x] 3.1 `Infrastructure/helm/travel-agent/Chart.yaml` and `values.yaml` created. `values.yaml` declares image repository/tag, `backend.corsAllowedOrigins`, `frontend.apiUrl`, `replicaCount`, and `resources` for both containers, plus the ServiceAccount/Key Vault/Gateway coordinates later tasks need — all empty-string or same-as-today defaults, so a bare `helm template` with no overrides renders without a real Azure identifier anywhere.
- [x] 3.2 `templates/backend-deployment.yaml` and `backend-service.yaml` port the two `Infrastructure/k8s/` files: `image` and `CORS_ALLOWED_ORIGINS` now read from values, `backend-service.yaml` is otherwise byte-for-byte the same Service, still `ClusterIP`.
- [x] 3.3 `templates/frontend-deployment.yaml` and `frontend-service.yaml` added (D1). No runtime env var — `NEXT_PUBLIC_API_URL` is a build-time value (D1, task 1.4), so there is nothing for this Deployment to configure at runtime. Service is `ClusterIP`.
- [x] 3.4 Both Deployments carry `resources.requests`/`resources.limits` from `values.yaml` (`resources.backend`, `resources.frontend`) — done inline while writing 3.2/3.3 rather than as a separate pass, since the field lives in the same container spec.
- [x] 3.5 `templates/backend-serviceaccount.yaml` added, annotated `azure.workload.identity/client-id` from `values.yaml`. The backend Deployment's pod template gained `serviceAccountName` and the `azure.workload.identity/use: "true"` label (D5).
- [x] 3.6 `templates/secretproviderclass.yaml` added: `secretObjects` syncs the vault's `google-api-key` into the `travel-agent-secrets` Kubernetes Secret the existing `secretKeyRef` already reads; `parameters` use the Workload ID access mode (`usePodIdentity: "false"`, `clientID` from values, no `useVMManagedIdentity`). The backend Deployment gained the CSI `volumeMounts`/`volumes` block task 1.1 established is required, with that task's one-line comment carried onto the mount (D5).
- [x] 3.7 `templates/gateway.yaml` and `httproute.yaml` added (D2): one `Gateway` with two named listeners (frontend/backend), each with its own `HTTPRoute` by hostname. `gatewayClassName` and `spec.infrastructure.annotations` are the only fields sourced from `values.yaml`'s `gateway.*` — everything else (`apiVersion`, `kind`, `listeners`, `parentRefs`, `hostnames`, `backendRefs`) is upstream Gateway API.
- [x] 3.8 Satisfied by 3.7's default: `values.yaml`'s `gateway.internalAnnotations` sets `service.beta.kubernetes.io/azure-load-balancer-internal: "true"` as the *default*, not an opt-in, so a plain render has no public address without anyone remembering to ask for one.
- [x] 3.9 `templates/chroma-pvc.yaml` (a `ReadWriteOnce` PVC) and `templates/rag-ingest-job.yaml` (a `pre-install,pre-upgrade` Helm hook running `python rag/ingest.py` against that PVC, reusing the backend image, ServiceAccount and CSI mount) added, per 3.10's decision (D11).
- [x] 3.10 Decided and recorded in `design.md` D11: a single-replica `ReadWriteOnce` PVC, not a standalone Chroma server. One backend replica removes the reason a server was proposed for ("multi-replica pods can't share a named volume"), and a server would touch `backend/rag/retriever.py` — this step's Impact line names only two application-code changes (CORS, frontend build arg), and this isn't a third. Ingestion runs as a Helm hook rather than an operator command, sequenced before the Deployment mounts the same volume — Helm blocks on hook completion, so the two never mount concurrently. Open Questions' "Chroma server mode versus single-replica PVC" bullet removed.
- [x] 3.11 `Infrastructure/k8s/` deleted (`rm -r`). `docs/step5.md` and `docs/plan.md`'s path references to it are untouched, per `proposal.md`'s Non-Goals.
- [x] 3.12 Rendered and dry-run validated:
      ```
      $ helm lint Infrastructure/helm/travel-agent -f Infrastructure/helm/travel-agent/values-example.yaml
      [INFO] Chart.yaml: icon is recommended
      1 chart(s) linted, 0 chart(s) failed
      ```
      `kubectl apply --dry-run=client` needs a reachable API server even for client-side validation of CRDs (Gateway/HTTPRoute/SecretProviderClass aren't in kubectl's built-in scheme) — no real cluster exists yet and none may be created outside the gate in Section 7, so a throwaway local `kind` cluster was used purely for schema recognition, with the two upstream CRD sets installed (Gateway API `v1.2.0`, Secrets Store CSI Driver's `SecretProviderClass`), then deleted immediately after. This is the same shape task 6.5 asks CI to do on PRs where no cloud credential exists — no Azure resource, no `az`, no `terraform` was touched.
      ```
      $ kind create cluster --name chart-lint
      $ kubectl apply -f https://.../gateway-api/releases/download/v1.2.0/standard-install.yaml
      $ kubectl apply -f https://.../secrets-store-csi-driver/.../secrets-store.csi.x-k8s.io_secretproviderclasses.yaml
      $ helm template travel-agent Infrastructure/helm/travel-agent -f Infrastructure/helm/travel-agent/values-example.yaml | kubectl apply --dry-run=client -f -
      serviceaccount/travel-agent-backend created (dry run)
      persistentvolumeclaim/travel-agent-chroma-db created (dry run)
      service/travel-agent-backend created (dry run)
      service/travel-agent-frontend created (dry run)
      deployment.apps/travel-agent-backend created (dry run)
      deployment.apps/travel-agent-frontend created (dry run)
      gateway.gateway.networking.k8s.io/travel-agent-gateway created (dry run)
      httproute.gateway.networking.k8s.io/travel-agent-frontend created (dry run)
      httproute.gateway.networking.k8s.io/travel-agent-backend created (dry run)
      secretproviderclass.secrets-store.csi.x-k8s.io/travel-agent-secrets-spc created (dry run)
      job.batch/travel-agent-rag-ingest created (dry run)
      $ kind delete cluster --name chart-lint
      ```
      All 11 rendered objects validate, both with the example overrides and with bare `values.yaml` defaults (re-run, same 11 lines).
- [x] 3.13 Read the rendered `Gateway`/`HTTPRoute` against a port to EKS: exactly two things change — `spec.gatewayClassName` (currently `approuting-istio`) and the contents of `spec.infrastructure.annotations` (Azure's `service.beta.kubernetes.io/azure-load-balancer-internal` swapped for AWS's load-balancer-controller equivalent). Both are already `values.yaml` fields (`gateway.className`, `gateway.internalAnnotations`), so the port needs a new values file, not a template edit. `apiVersion`, `kind`, `listeners`, `parentRefs`, `sectionName`, `hostnames`, `backendRefs` are unchanged — no provider detail leaked into the routing rules.

## 4. Infrastructure Definitions — Platform State

Lands at `Infrastructure/terraform/platform/` (D10). Applied once; survives teardown. Nothing in this section is applied here — Section 7 gates that.

- [x] 4.1 `Infrastructure/terraform/platform/main.tf`: `azurerm_resource_group.platform`, named by `var.resource_group_name` (default `travel-agent-platform`) in `var.region` (default `germanywestcentral`, D12).
- [x] 4.2 `registry.tf`: `azurerm_container_registry.this`, SKU `Basic`, `admin_enabled = false` — no stored registry credential, consistent with D4's reason for choosing ACR over GHCR in the first place. Named with a `random_string` suffix for ACR's global-uniqueness requirement.
- [x] 4.3 `keyvault.tf`: `azurerm_key_vault.this` only, RBAC-authorized, `soft_delete_retention_days = 90` made explicit (D10's finding). **No `azurerm_key_vault_secret` resource exists in this state** — that resource type always stores its `value` in Terraform state regardless of how it's populated, so managing the secret object here, even with a placeholder, would put something in state D5 says must never be there, and would fight the out-of-band `az keyvault secret set` write on every `terraform plan`. Read "the secret object only" in this task's own text as settled by D5's explicit sentence rather than as a separate instruction to create a secret-shaped resource; the object is created entirely out-of-band, name and value both. Also added: an optional `operator_object_id` variable granting whoever runs `az keyvault secret set` the `Key Vault Secrets Officer` role, since an RBAC-enabled vault denies that write to everyone by default.
- [x] 4.5 (before 4.4 in the file but done together — see below) `identities.tf`: `azurerm_user_assigned_identity.backend` + `azurerm_role_assignment.backend_keyvault_secrets_user` (`Key Vault Secrets User`, unconditional — authorizes the identity regardless of federation status). The federated identity credential itself, `azurerm_federated_identity_credential.backend_serviceaccount`, is conditional on `var.aks_oidc_issuer_url` (`count = 0` when empty) because its `issuer` argument is the AKS cluster's OIDC issuer URL — an output of `Infrastructure/terraform/cluster/`, which doesn't exist on this state's first apply. This state is applied twice: once before the cluster exists (credential skipped), once after (credential created) — documented in the new `Infrastructure/terraform/platform/README.md` rather than asserted here without a mechanism.
- [x] 4.4 `identities.tf`: `azurerm_user_assigned_identity.ci` + `azurerm_federated_identity_credential.ci`, subject `repo:Taliko5/travel-agent-platform:ref:refs/heads/main` (`var.github_repository`/`var.ci_deploy_branch`), audience `api://AzureADTokenExchange`, issuer `https://token.actions.githubusercontent.com` — matches D4's push-job gate exactly. Also `azurerm_role_assignment.ci_acr_push` (`AcrPush`, scoped to the registry). **Not done here, and noted rather than silently skipped:** the AKS-scoped role CI needs for `az aks get-credentials` (task 6.4) references a cluster this state doesn't have — that role assignment belongs in `Infrastructure/terraform/cluster/` (Section 5), against this state's `ci_identity_principal_id` output. Neither `design.md` nor `tasks.md` currently names that role assignment as a Section 5 task; flagging it now so it isn't rediscovered when Section 6's CI job turns out not to authenticate.
- [x] 4.6 Confirmed by inspection, not by running `terraform` (out of scope for this pass): `grep -rn "azurerm_key_vault_secret" .` matches only the comments in `keyvault.tf` explaining its absence — no such resource exists. Every `outputs.tf` value resolves to `.id`, `.name`, `.location`, `.login_server`, `.tenant_id`, `.client_id`, or `.principal_id`; none is a secret-shaped attribute, and with no `azurerm_key_vault_secret` resource there is no `.value` anywhere in this state to expose. No state file exists yet — nothing has been applied.

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
- [ ] 11.7 In that section, document how to rotate `GOOGLE_API_KEY`: setting a new value with `az keyvault secret set` updates the vault, the CSI mount and the synced Kubernetes Secret, but not a running container's environment — Kubernetes populates env vars from a Secret once, at container start, and does not hot-reload them. The rotation is not complete until the backend pod is restarted (`kubectl rollout restart deployment/<backend>`), and that restart step is the one an operator is most likely to forget precisely because everything else about rotation *is* automatic (`design.md` D5).
- [ ] 11.8 In that section, document the teardown command, and immediately beside it — not in a separate paragraph an operator could miss — state explicitly that teardown has no relationship to `docker-compose down -v`, which destroys `prometheus_data` and cannot be regenerated.
- [ ] 11.9 In that section, document what teardown destroys, what survives it, and the standing cost of what survives, pointing at `design.md`'s inventory for the figure rather than restating it (`CLAUDE.md`: never restate figures).
- [ ] 11.10 Confirm no step written anywhere in this change, including the new `README.md` section, instructs a client to disable certificate verification, and that the README's access instructions name the authenticated tunnel rather than a plaintext address someone could reuse from elsewhere.
- [ ] 11.11 Re-read this change's spec scenarios against what the run actually observed. Any scenario the run contradicted is a spec defect or an implementation defect; report which, and stop rather than reconciling the spec to the observation.
