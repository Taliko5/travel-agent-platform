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

- Add a `deployment` capability: Terraform-defined Azure infrastructure, Kubernetes manifests that reference a real registry and a real secret source, and a documented raise/verify/destroy cycle.
- **Nothing is applied by this change.** No Azure resource is created, no `terraform` command is run, no `az` command is run. `design.md` opens with the complete list of resources a future apply would create and what each costs, because `docs/plan.md` requires that list to be approved before any billable resource exists.
- Replace the imperative `kubectl create secret` step from `docs/step5.md` with Azure Key Vault reached through the Secrets Store CSI driver and Microsoft Entra Workload ID. The application keeps reading `GOOGLE_API_KEY` from its environment; nothing in `backend/` changes for this (`design.md` D5).
- Redirect the image-push job drafted in `docs/step7.md`'s "Step 9 extension (ECR push)" to Azure Container Registry, authenticated by an OIDC federated identity credential rather than a stored access key. The drafted snippet is stale in a second way as well — it declares `needs: build`, and `.github/workflows/ci.yml` has no `build` job, only `build-backend` and `build-frontend` (`design.md` D4).
- Make the CORS origin in `backend/api/main.py` configurable. It is currently `allow_origins=["http://localhost:3000"]`, a literal. This is the one application-code change the step requires (`design.md` D6).
- Add container CPU and memory monitoring via Azure Monitor managed Prometheus, and connect the **existing local Grafana** to the resulting Azure Monitor workspace as a second datasource rather than deploying a new Grafana (`design.md` D7, D8). The local Prometheus and its history are not touched, moved, or migrated by anything in this change.

## Capabilities

### Added Capabilities
- `deployment`: how this stack is built into images, published, placed on a managed Kubernetes cluster, given its secret, reached, observed, and destroyed. New capability — nothing in `openspec/specs/` covers any of it today (`openspec/specs/` holds `chat-frontend` only).

## Impact

- **Affected code**: `backend/api/main.py` (CORS origins read from the environment — D6) and `frontend/Dockerfile` (the API base URL must become a build argument; `NEXT_PUBLIC_*` values are inlined by Next.js at build time, so the runtime `environment:` entry in `docker-compose.yaml` does not reach the browser bundle — D1). No other application file changes.
- **Affected infrastructure**: `Infrastructure/k8s/*.yaml` rewritten and extended; new Terraform under `Infrastructure/`; a new `push` job in `.github/workflows/ci.yml`.
- **Affected tests**: `backend/tests/test_api_main.py` covers CORS and will need a case for the configured-origin path. No test requires a cluster, an Azure subscription, or a credential — the pipeline's "passes on a fresh fork with zero configuration" property from `docs/step7.md` is preserved, because the new `push` job is gated on `main` and skipped everywhere else.
- **Cost.** Nothing in this change spends anything. A future apply does, and the whole inventory is in `design.md`'s "Azure resources this change would create" — figures live there once and are not repeated here.
- **Destructive-operation boundary.** Cluster teardown (D10) destroys Azure resources only. It has no relationship to `docker-compose down -v`, and the two must never be run as if they were the same step: the first destroys a cluster that is designed to be destroyed, the second destroys `prometheus_data`, which is not.

## Non-Goals

- **Amending the `observability` capability.** Step 8 justified its structured JSON logging by CloudWatch's line-oriented ingestion, and that requirement now names a sink this step does not use. The logging work itself is unaffected — the format is right, the named sink is wrong. Redirecting it is a separate change and is deliberately not attempted here.
- **Closing `docs/plan.md`'s Grafana-credential item in `openspec/`.** `design.md` D9 decides what the credential should be and why, but the requirement that would bind it belongs to `observability`, not to `deployment`, so no spec text for it is written by this change. D9 also records a factual contradiction between `docs/plan.md` and `docker-compose.yaml` that is reported rather than fixed.
- **Porting to EKS.** That is Step 10, and `docs/plan.md` explains why it comes after rather than alongside.
- **A permanently reachable URL, TLS certificates, or a DNS zone.** The cluster is ephemeral by decision; nothing that only makes sense for a long-lived endpoint is designed here.
- **Authentication, rate limiting, or a request deadline on `/chat`.** `chat-request-deadline` is a separate proposal. This change keeps `/chat` off the public internet (D2) instead of hardening it.
- **Autoscaling behaviour, multi-region, availability zones, or private cluster networking.** Out of scope for a cluster that exists for hours.
- **`tasks.md` and `specs/deployment/spec.md`.** Deliberately not written in this pass.
