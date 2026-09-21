# Running an AI Travel Agent on Azure AKS as a Disposable Cluster

An AI travel-planning agent built on LangGraph, RAG (ChromaDB), and a set of MCP tool servers, taken from local Docker Compose development through GitHub Actions CI/CD to a production-grade Azure Kubernetes Service (AKS) deployment. Built under a free-tier cost constraint while still exercising a production-realistic setup, with every non-trivial decision recorded as it was made.

**Stack:** Python/FastAPI/LangGraph, ChromaDB, Next.js, Terraform, AKS (Istio Gateway API, Workload Identity, Managed Prometheus), GitHub Actions (OIDC, no stored secrets)

[Full repository](https://github.com/Taliko5/travel-agent-platform) — the complete decision log lives in `design.md`, and verification evidence lives in `step9-raise-evidence.md`.

## Why a Disposable Cluster

To stay within a free-tier subscription's cost limits while still validating a production-realistic setup, Terraform state is split into two layers. The **platform layer** (ACR, Key Vault, Managed Identity) is applied once and persists. The **cluster layer** (the AKS cluster itself) is raised and torn down for each work session.

## Deploying Without Long-Lived Credentials

CI holds no long-lived Azure secrets at all. It authenticates via OIDC federation, requesting a short-lived token on each run to push to ACR and deploy to AKS.

![GitHub Actions CI/CD pipeline, all jobs green](evidence/88-ci-pipeline-green.png)

## Least Privilege vs. Operational Reality

CI's Azure role started at least privilege (RBAC Writer). Once actually deploying, it became clear that CRD resources like `Gateway` and `HTTPRoute` weren't covered by any built-in role below Cluster Admin. CI was temporarily elevated to Cluster Admin, and that trade-off was recorded in the design docs as a deliberate deviation to revisit later — not accepted as a final answer.

![Terraform switching the CI role from Writer to Cluster Admin, live](evidence/d4-rbac-cluster-admin-applied.png)

## No External Exposure

The Load Balancer carries no public IP — the app is reachable only through an internal LB. Today, a manual `kubectl port-forward` tunnel is the only access path, which is a deliberate design choice for this stage. It's also an operational constraint that requires a person to keep the tunnel open, and it's the thing the next step (launching and reaching the cluster from a browser) is meant to revisit.

![Public IP attached only to the internal Load Balancer, no external exposure](evidence/96-no-public-ip.png)

## Verifying Statelessness

The backend pod was deliberately deleted mid-session. After a new pod came up, the same question got the same answer back.

![Backend pod deleted, new pod comes up](evidence/97a-pod-delete.png)
![Same question after the delete returns the same answer](evidence/97b-chat-after-delete.png)

## Fault Injection: Revoking Key Vault Access

To verify that Workload-Identity-based secret retrieval was actually enforced (not just configured), the Key Vault role was deliberately revoked, confirming the pod failed, then restored.

![After revoking Key Vault access, secret retrieval fails with 403 Forbidden](evidence/915b-keyvault-failure.png)
![After restoring access, the pod comes back up healthy](evidence/915d-keyvault-recovered.png)

## Clean Teardown

At the end of a work session, the cluster layer is fully destroyed while the platform layer (ACR, Key Vault, Identity) survives intact.

![terraform destroy complete; resource group confirmed gone](evidence/10a-destroy-complete.png)

## Links

- [Repository](https://github.com/Taliko5/travel-agent-platform)
- Full decision log: `design.md`
- Verification evidence: `step9-raise-evidence.md`
