## Why

`docs/plan.md`'s `## Step 9: Azure Deployment (AKS)` settles the target (AKS), the assembly model (by hand, not AKS Automatic), the deliverable (the repository, with the cluster raised on demand and destroyed afterwards) and the reason a public endpoint is not part of it. Those decisions are not restated here — read that section. This change is what turns them into a `deployment` capability with stated requirements.

What the repository currently holds for this step is two Kubernetes manifests covering one of the four services `docker-compose.yaml` runs, and both of them encode assumptions that a managed cluster invalidates:

```
$ ls Infrastructure/k8s/
backend-deployment.yaml  backend-service.yaml
$ grep -n "image:\|secretKeyRef\|type:" Infrastructure/k8s/*.yaml
Infrastructure/k8s/backend-deployment.yaml:19:          image: travel-agent-backend:latest
Infrastructure/k8s/backend-deployment.yaml:25:                secretKeyRef:
Infrastructure/k8s/backend-service.yaml:12:  type: ClusterIP
```

An unqualified image tag no registry can resolve, a Secret that has to be created by hand outside version control, and a Service type that reaches nothing from outside the cluster. Each is fine for `kubectl apply --dry-run` and none of them survives contact with AKS. `design.md` decides each one.

Two commitments about Step 9 are already on record in `docs/step5.md` and this change has to answer both rather than quietly drop them:

```
$ grep -n "Step 9" docs/step5.md
5:Containerize the FastAPI backend so it runs identically in dev, CI, and production. Add Kubernetes manifests as the foundation for Step 9.
20:| Step 9 | Server mode, standalone StatefulSet | Multi-replica pods can't share a named volume |
26:**k8s Service: `ClusterIP`** — within-cluster access for dev/CI. One-line change to `LoadBalancer` or ALB Ingress in Step 9.
```

The first is honoured in substance and revised in mechanism; the second names an AWS load balancer and cannot be honoured as written. `design.md` D11 handles both.

## What Changes

- Add a `deployment` capability: Terraform-defined Azure infrastructure, a Helm chart for the workload, and a documented raise/verify/destroy cycle.
- **Nothing is applied by this change.** No Azure resource is created, no `terraform` command is run, no `az` command is run. `design.md` opens with the complete list of resources a future apply would create and what each costs, because `docs/plan.md` requires that list to be approved before any billable resource exists.
- Package the workload as a Helm chart at `Infrastructure/helm/travel-agent/`, carrying the image repository and tag, the CORS origin and the frontend's API URL as `values.yaml` entries. `Infrastructure/k8s/`'s two loose manifests become chart templates and that directory ceases to exist (`design.md` D13).
- Add a frontend Deployment and Service. The repository has manifests for the backend only (D1).
- Add a `Gateway` and an `HTTPRoute` served by the application routing add-on's Gateway API implementation, which the cluster enables. The Services stay `ClusterIP`, the Gateway's load balancer is internal, and the operator reaches it with `kubectl port-forward` (D2).
- Give the ChromaDB vector store storage that outlives a pod, so it stops being per-pod local state. The mechanism — Chroma in server mode, or a single-replica ReadWriteOnce PVC — is left to `tasks.md` (D11).
- Add a ServiceAccount carrying the workload-identity annotation and a `SecretProviderClass` to the workload objects, and enable the OIDC issuer, workload identity and the Key Vault add-on on the cluster (D5).
- Replace the imperative `kubectl create secret` step from `docs/step5.md` with Azure Key Vault reached through the Secrets Store CSI driver and Microsoft Entra Workload ID. The application keeps reading `GOOGLE_API_KEY` from its environment; nothing in `backend/` changes for this (D5).
- Give the workload objects resource requests, and size the cluster's node pool at 2 × `Standard_D4as_v5` — AKS's documented system-pool minimum SKU and minimum node count (D14).
- Create the cluster on the **Free** tier. The AKS cost-analysis add-on requires Standard or Premium, so it is neither available nor used (D3).
- Add container CPU and memory monitoring via Azure Monitor managed Prometheus with the minimal ingestion profile left on, and connect the **existing local Grafana** to the resulting Azure Monitor workspace as a second datasource (D7, D8). The local Prometheus and its history are not touched, moved, or migrated by anything in this change.
- Put no Prometheus and no Grafana on the cluster, and do not enable Container insights (D1, D7, D8).
- Split the Terraform into two states: `Infrastructure/terraform/platform/`, which survives teardown and holds the only standing cost (the registry), and `Infrastructure/terraform/cluster/`, which is destroyed at the end of every session (D10).
- Redirect the image-push job drafted in `docs/step7.md`'s "Step 9 extension (ECR push)" to Azure Container Registry, authenticated by an OIDC federated identity credential rather than a stored access key, and extend it to deploy with `helm upgrade --install`. The drafted snippet is stale in a second way as well — it declares `needs: build`, and `.github/workflows/ci.yml` has no `build` job, only `build-backend` and `build-frontend` (D4, D13).
- Add `helm template | kubectl apply --dry-run=client` as the workload's lint step, which the loose YAML has no equivalent of (D13).
- Make the CORS origin in `backend/api/main.py` configurable. It is currently `allow_origins=["http://localhost:3000"]`, a literal. This is the one application-code change the step requires (D6).

## Capabilities

### Added Capabilities
- `deployment`: how this stack is built into images, published, placed on a managed Kubernetes cluster, given its secret, reached, observed, and destroyed. New capability — nothing in `openspec/specs/` covers any of it today (`openspec/specs/` holds `chat-frontend` only).

## Impact

- **Affected code**: `backend/api/main.py` (CORS origins read from the environment — D6) and `frontend/Dockerfile` (the API base URL must become a build argument; `NEXT_PUBLIC_*` values are inlined by Next.js at build time, so the runtime `environment:` entry in `docker-compose.yaml` does not reach the browser bundle — D1). No other application file changes.
- **Affected infrastructure**: `Infrastructure/k8s/`'s two manifests become templates in a new Helm chart at `Infrastructure/helm/travel-agent/`, and that directory is removed; new Terraform in two separate states at `Infrastructure/terraform/platform/` and `Infrastructure/terraform/cluster/`; a new `push` job in `.github/workflows/ci.yml` that pushes to ACR and deploys with `helm upgrade --install`.
- **Affected tests**: `backend/tests/test_api_main.py` covers CORS and will need a case for the configured-origin path. No test requires a cluster, an Azure subscription, or a credential — the pipeline's "passes on a fresh fork with zero configuration" property from `docs/step7.md` is preserved, because the new `push` job is gated on `main` and skipped everywhere else.
- **Cost.** Nothing in this change spends anything. A future apply does, and the whole inventory is in `design.md`'s "Azure resources this change would create" — figures live there once and are not repeated here.
- **Destructive-operation boundary.** Cluster teardown (D10) destroys Azure resources only. It has no relationship to `docker-compose down -v`, and the two must never be run as if they were the same step: the first destroys a cluster that is designed to be destroyed, the second destroys `prometheus_data`, which is not.

## Non-Goals

- **Amending the `observability` capability.** Step 8 justified its structured JSON logging by CloudWatch's line-oriented ingestion, and that requirement now names a sink this step does not use. The logging work itself is unaffected — the format is right, the named sink is wrong. Redirecting it is a separate change and is deliberately not attempted here.
- **Closing `docs/plan.md`'s Grafana-credential item in `openspec/`.** `design.md` D9 decides what the credential should be and why, but the requirement that would bind it belongs to `observability`, not to `deployment`, so no spec text for it is written by this change. The two `docker-compose.yaml` edits D9 decided are already in the repository from commit `89f04e9`, outside this change; what is left of D9 is an operator action, not a repository edit.
- **Repointing the `Infrastructure/k8s/` paths in `docs/step5.md` (lines 39, 40, 59–61) and `docs/plan.md` (line 61).** Those lines record what Step 5 built and validated; per `openspec/config.yaml`'s split a record reports rather than binds, so they stay as written and the new layout is stated here and in `design.md` D13 instead. They are not stale text awaiting a fix.
- **Porting to EKS.** That is Step 10, and `docs/plan.md` explains why it comes after rather than alongside.
- **A permanently reachable URL or a DNS zone.** The cluster is ephemeral by decision; nothing that only makes sense for a long-lived endpoint is designed here. **TLS is no longer grouped with these** — an internal Gateway can terminate TLS without either of them, so it needed deciding on its own terms rather than inheriting their exclusion. `design.md` D15 decides it: no certificate, because the only client reaches the Gateway through an already-encrypted `kubectl port-forward` tunnel, and a self-signed certificate nobody validates is worse than plain HTTP. D15 also records the trigger that voids that decision.
- **Authentication, rate limiting, or a request deadline on `/chat`.** `chat-request-deadline` is a separate proposal. This change keeps `/chat` off the public internet (D2) instead of hardening it.
- **Autoscaling behaviour, multi-region, availability zones, or private cluster networking.** Out of scope for a cluster that exists for hours.
- **`tasks.md` and `specs/deployment/spec.md`.** Deliberately not written in this pass.
