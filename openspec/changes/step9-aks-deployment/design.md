## Context

`docs/plan.md`'s `## Step 9` fixes the target, the assembly model, the ephemeral-cluster deliverable and the reason a public endpoint is not part of it, and `## Step 10` fixes what is deferred. This document does not re-argue any of that; it decides the layer `docs/plan.md` calls "the cloud-specific one — network, identity, registry, ingress controller, log sink."

What exists in the repository today, read rather than recalled:

```
$ ls Infrastructure/k8s/
backend-deployment.yaml  backend-service.yaml
$ grep -n "^  [a-z]*:" docker-compose.yaml
2:  backend:
19:  frontend:
30:  prometheus:
44:  grafana:
```

Four services in compose, two manifests covering one of them. `backend/api/main.py` line 84 hardcodes `allow_origins=["http://localhost:3000"]`. `backend/.dockerignore` excludes `rag/chroma_db/`, so the vector store is not in the image and has to be produced at runtime. `frontend/Dockerfile` runs `npm run build` at image-build time. `.github/workflows/ci.yml` has jobs `changes`, `test`, `build-backend`, `frontend`, `build-frontend`, `gitleaks` — and no job called `build`, which is what `docs/step7.md`'s ECR draft declares a dependency on.

The two Step 9 commitments in `docs/step5.md`, quoted from the file:

```
| Step 9 | Server mode, standalone StatefulSet | Multi-replica pods can't share a named volume |

**k8s Service: `ClusterIP`** — within-cluster access for dev/CI. One-line change to `LoadBalancer` or ALB Ingress in Step 9.
```

Both are answered in D11.

**Provenance of every Azure figure below.** Prices were read from the anonymous Azure Retail Prices API on 2026-08-25, filtered to `armRegionName eq 'germanywestcentral'`, in USD. Every figure was read fresh for this region; none is converted or scaled from a figure read for another one. Example call and its actual output:

```
$ curl -s -G "https://prices.azure.com/api/retail/prices" \
    --data-urlencode "\$filter=serviceName eq 'Azure Kubernetes Service' and armRegionName eq 'germanywestcentral'"
0.1 1 Hour | Standard Uptime SLA | Azure Kubernetes Service | USD
0.6 1 Hour | Standard Long Term Support | Azure Kubernetes Service | USD
```

The rendered pricing pages on `azure.microsoft.com` serve their numbers via client-side script and returned literal `$-` placeholders when fetched, which is why the API was used instead. Every non-price Azure statement in this document is followed by the Microsoft Learn URL it was read from. Claims reasoned to rather than read are labelled **[reasoned]** and are not treated as settled.

## Azure resources this change would create, and what each costs

Nothing here is applied. This is the list `docs/plan.md` requires to be approved before any billable resource exists.

**Region.** Every figure below is `germanywestcentral` (D12).

**Availability in this region, checked rather than assumed.** The retail price list returns `Azure Kubernetes Service` meters for `germanywestcentral`, so AKS is offered there. The Free tier follows from the tiers page's own region table — *"Public regions and Azure Government regions where AKS is supported | Free, Standard, Premium"* ([free-standard-pricing-tiers](https://learn.microsoft.com/en-us/azure/aks/free-standard-pricing-tiers)) — a documented inference from that table, not a per-region confirmation. Neither [app-routing](https://learn.microsoft.com/en-us/azure/aks/app-routing), [app-routing-gateway-api](https://learn.microsoft.com/en-us/azure/aks/app-routing-gateway-api) nor [managed-gateway-api](https://learn.microsoft.com/en-us/azure/aks/managed-gateway-api) states any region restriction or supported-region list; their prerequisites are CLI-version and cluster-configuration only. **Not verified:** which Kubernetes minor versions this specific region currently offers. The version table in [supported-kubernetes-versions](https://learn.microsoft.com/en-us/azure/aks/supported-kubernetes-versions) is global and carries the caveat *"it might take up to 10 business days for a new release or a new version to be available in all regions"*; there is no per-region table in the docs, `az aks get-versions --location germanywestcentral` is out of scope for this pass, and the AKS release-status site is a client-side application with no machine-readable per-region feed found. Nothing observed contradicts D2 or D3 — but the version range in D2 is a global statement, and confirming it here is one CLI call at apply time.

### Created when the cluster is raised, destroyed when it is torn down

| # | Resource | Why it exists | Retail price (germanywestcentral, USD) |
|---|---|---|---|
| 1 | Resource group (cluster) | Container for 2–7; makes teardown one operation | $0 |
| 2 | AKS managed cluster, **Free** tier | The cluster. D3 | $0 cluster management |
| 3 | System node pool: 2 × `Standard_D4as_v5` | Runs everything: app pods, ingress control plane and proxies, CSI driver, metrics add-on. Sized in D14 | $0.208/hour each → **$0.416/hour** |
| 4 | 2 × node OS disk, Premium SSD | One per node | P6: $11.227/month each; P10: $21.68/month each |
| 5 | Node resource group (`MC_…`) | Created by AKS, not by us; holds 3, 4, 6, 7 and the CSI add-on's identity | $0 for the group itself |
| 6 | Standard Load Balancer (AKS-managed) | Cluster egress, and the ingress Gateway's frontend | $0.025/hour for the first 5 rules; $0.01/hour per rule beyond; $0.005/GB processed |
| 7 | 1 × Standard static public IPv4 | Cluster outbound. **Not** an inbound endpoint — D2 | $0.005/hour |
| 8 | Azure Monitor workspace | Managed Prometheus ingestion target. D7, D8 | No standing meter appears in the retail price list; ingestion $0.16 per 10M samples, query $0.001 per 10M samples |

**Cost floor while the cluster is up:** 3 + 4 + 6 + 7 = $0.416 + $0.031 + $0.025 + $0.005 ≈ **$0.48/hour** ≈ $3.81 for an eight-hour session, before metrics ingestion (D8, small) and egress. **[reasoned]** — arithmetic over the read prices, with the OS-disk monthly figure divided by 730.

Egress: the retail list shows `Standard Data Transfer Out` at $0.0/GB up to a 100 GB tier minimum, then $0.08–$0.087/GB. An ephemeral demo cluster does not approach 100 GB.

### Created once, and deliberately kept after teardown

| # | Resource | Why it survives | Retail price (germanywestcentral, USD) |
|---|---|---|---|
| 9 | Resource group (platform) | Holds 10–13, which teardown must not touch | $0 |
| 10 | Azure Container Registry, **Basic** | CI pushes here on every merge to `main`. Destroying it breaks CI. D4 | **$0.1666/day** (≈ $5.00/30 days); 10 GB included; $0.10/GB/month over |
| 11 | Azure Key Vault (standard), holding one secret | Source of `GOOGLE_API_KEY`. D5 | No standing meter; **$0.03 per 10,000 operations** |
| 12 | User-assigned managed identity + federated identity credential (GitHub Actions → ACR/AKS) | Lets CI authenticate with no stored secret. D4 | $0 |
| 13 | User-assigned managed identity + federated identity credential (backend ServiceAccount → Key Vault) | Lets the pod read the vault with no stored secret. D5 | $0 |

**Standing cost between sessions: item 10 alone, ≈ $5/month.** Everything else on this list is free at rest.

### Created by Azure without being asked for

The Key Vault CSI add-on creates a managed identity in the node resource group and this cannot be prevented: *"The add-on creates a managed identity named `azurekeyvaultsecretsprovider-xxxxx` in the node resource group (`MC_`) and assigns it to the Virtual Machine Scale Set automatically. … It's not supported to prevent creation of the identity."* ([csi-secrets-store-driver](https://learn.microsoft.com/en-us/azure/aks/csi-secrets-store-driver)). It costs nothing and is destroyed with the node resource group.

### Deliberately not created

| Resource | Why not |
|---|---|
| Azure Managed Grafana | $0.0445/hour per node plus $6/month per user beyond the included set. D7 keeps the Grafana that already exists |
| Log Analytics workspace / Container insights | $2.99/GB ingested, $0.13/GB/month retained. D8 chooses metrics over logs |
| Application Gateway for Containers | A second billable ingress resource with its own lifecycle. D2 |
| AKS cost analysis add-on | Requires Standard or Premium tier, and its Kubernetes views are EA/MCA-only. D3 |
| Azure DNS zone, App Gateway WAF, Azure Firewall, private endpoints | No public endpoint exists to name, protect or privatise. `docs/plan.md` |

## Goals / Non-Goals

**Goals:**
- Produce a resource list precise enough to be approved or refused before anything is billable, with each price traceable to the call that produced it.
- Decide every cloud-specific mechanism the Kubernetes layer sits on, and say which decisions are portable to Step 10 and which are thrown away.
- Answer the three questions `docs/plan.md` leaves open — observability placement, container CPU/memory monitoring and its cost, Grafana's credential — rather than restating them.
- Answer both `docs/step5.md` Step 9 commitments explicitly, including the one that cannot be honoured as written.
- Mark unverified claims as unverified and name what would settle each, instead of filling gaps.

**Non-Goals:**
- Implementing anything. This document and `proposal.md` are the entire deliverable of this pass; `tasks.md` and the spec delta follow after review.
- Creating any Azure resource, running `terraform`, or running `az`.
- Amending the `observability` capability, including the CloudWatch-shaped logging requirement and the Grafana credential requirement.
- Deciding the region, the subscription, or who operates the raise/destroy cycle.

## Decisions

### D0 — The Kubernetes layer is written once; the Azure layer is written knowing it will be thrown away
`docs/plan.md` already states that Deployment, Service, Ingress/Gateway, HPA, probes and `kubectl` carry between clouds and the cloud-specific layer does not. The consequence for this design, which is the part worth writing down: every decision below is tagged as **portable** (survives Step 10 unchanged) or **disposable** (rewritten for EKS). A decision that looks cheap now but drags Azure specifics into the manifests is expensive later, and D2, D4 and D5 are each chosen partly on that basis.

### D1 — Deploy backend and frontend. Prometheus and Grafana stay off the cluster (portable)
`docker-compose.yaml` runs four services. Two go to the cluster.

**Backend** — the point of the exercise. **Frontend** — without it the cluster runs an API with no client, and `docs/plan.md`'s verification-record approach needs something to exercise end to end.

**Prometheus and Grafana are not deployed.** Not an omission: D7 replaces them with a managed ingestion target and reuses the Grafana that already exists. Deploying a second Prometheus into the cluster would create a second, empty history alongside the 90-day one the owner decided to keep, with no relationship between them.

Two consequences that are not optional:

**The frontend's API URL is baked at build time, not injected at run time.** `frontend/src/app/components/ChatInterface.tsx:16` reads `process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"`, and `frontend/Dockerfile` runs `npm run build` during the image build with no `ARG` or `ENV` for it. Next.js inlines `NEXT_PUBLIC_*` into the browser bundle at build time ([Next.js: Bundling Environment Variables for the Browser](https://nextjs.org/docs/app/guides/environment-variables#bundling-environment-variables-for-the-browser)), so the `NEXT_PUBLIC_API_URL` entry in `docker-compose.yaml` never reaches the bundle — compose works because the inlined fallback happens to be the right value on a developer's machine. In the cluster it is not. `frontend/Dockerfile` gains a build argument and CI passes the cluster's backend URL when building the image. **[reasoned]** for the specific claim that the compose entry is inert: it follows from the file contents plus the documented inlining, and was not confirmed by inspecting a built bundle. Settle it by grepping `.next/` after a build.

**The vector store is not in the image.** `backend/.dockerignore` line 8 excludes `rag/chroma_db/`, and `Infrastructure/k8s/backend-deployment.yaml` mounts nothing, so a pod starts with an empty ChromaDB directory and RAG returns nothing. Compose papers over this with a named volume plus a one-off `docker-compose exec backend python rag/ingest.py`. See D11.

**Mechanism note (task 6.3): one source for the backend URL, read at CI runtime, not duplicated as a second literal.** `values.yaml`'s `frontend.apiUrl` already carries the comment that the field exists so CI's image-build step and this chart's deploy step read the same value from one place instead of two — a `push` job that hardcoded `NEXT_PUBLIC_API_URL` as its own literal, while leaving `frontend.apiUrl` at its `http://localhost:8000` placeholder, would leave that comment aspirational rather than true. The `push` job instead reads `gateway.backendHost` (D2) — the chart's own record of the backend's hostname — out of `values.yaml` with `yq` (present on the GitHub-hosted runner image already — no install step needed) into a step output, and uses that one output twice: as the frontend image's `NEXT_PUBLIC_API_URL` build argument, and as `helm upgrade --install`'s `--set frontend.apiUrl=...`, overriding the placeholder so the deployed chart's value matches what was actually baked into the image. The `http://` prefix is written once in the workflow rather than stored in `values.yaml` alongside the bare hostname — D15 already decided the Gateway listener is plain HTTP with no TLS, so the scheme is a fixed design constant of this deployment, not a per-environment value `values.yaml` needs to carry.

### D2 — Ingress: the application routing add-on's Gateway API implementation, on an internal load balancer (portable at the manifest layer, disposable at the Azure layer)

The options that actually exist on AKS today, read from [Concepts - Ingress Networking in AKS](https://learn.microsoft.com/en-us/azure/aks/concepts-network-ingress) (page dated 2026-06-05) and [Application Routing Add-On with the Kubernetes Gateway API](https://learn.microsoft.com/en-us/azure/aks/app-routing-gateway-api) (page dated 2026-07-01):

| Option | API | Hosting | Status, quoted |
|---|---|---|---|
| Application routing add-on, managed NGINX | Ingress API | In-cluster | *"Microsoft will provide official support for critical security patches for application routing add-on NGINX Ingress resources through **November 2026**."* Upstream Ingress NGINX maintenance ended **March 2026** |
| Application routing add-on, Gateway API implementation | Gateway API | In-cluster (Istio control plane) | *"aims to serve as a successor to the managed NGINX add-on"*; *"Starting with AKS version 1.36, new AKS Automatic clusters use Kubernetes Gateway API via the application routing add-on by default"* |
| Application Gateway for Containers | Ingress **and** Gateway API | Azure hosted | *"the evolution of AGIC"*; *"FQDN (no static IP)"* |
| Istio service mesh add-on ingress gateway | Istio Ingress API | In-cluster | GA; *"The Istio add-on currently doesn't support Gateway API for Istio ingress traffic"* |
| No ingress controller: `ClusterIP` + `kubectl port-forward` | — | — | Always available |

The AKS versions this targets: 1.34, 1.35 and 1.36 are the GA minor versions as of today, with 1.36 GA'd June 2026 and 1.33 out of support since July 2026; a cluster created through the CLI *"defaults to the N-1 minor version and latest patch"* ([Supported Kubernetes versions in AKS](https://learn.microsoft.com/en-us/azure/aks/supported-kubernetes-versions), page dated 2026-08-05). All five options above are available across that range.

**Decision: the Gateway API implementation, enabled with `--enable-app-routing-istio` on an AKS Standard cluster, with the `Gateway` annotated onto an internal load balancer.**

Managed NGINX is rejected on a date, not a preference: it has roughly three months of Azure security-patch support left from today, and its upstream project stopped being maintained five months ago. Writing a repository artefact — which is the whole deliverable — against a controller with a published end date inside the quarter is choosing a dead path deliberately. Application Gateway for Containers is the right answer when you need mTLS to backends, weighted traffic splitting or Azure-hosted autoscaling; this stack needs none of those, and it adds a separately-billed resource with its own lifecycle to raise and destroy. Plain `port-forward` costs nothing but leaves the ingress layer unwritten, which makes the repository silent about the one thing Step 10 is supposed to prove moves between clouds.

**Internal, not external.** The add-on's Gateway creates a `LoadBalancer` Service by default, and the docs note: *"The example above creates an external ingress load balancer service that's accessible from outside the cluster. You can add annotations to create an internal load balancer."* Internal is what `docs/plan.md` requires — no permanently public endpoint, and `/chat` stays off the open internet while it has no authentication, no rate limit and no deadline. The operator reaches the Gateway with `kubectl port-forward`; the Gateway is still real, still exercised, still in the repository, and never internet-reachable.

**Costs this decision carries.** The implementation *"deploys an Istio control plane"*; `istiod` runs with an HPA whose *"Min replicas: Two"* and cannot be set lower (*"doesn't allow setting the minReplicas to less than the initial default of 2"*), and each `Gateway` gets its own Deployment with *"a Horizontal Pod Autoscaler (HPA) with two minimum replicas and a PodDisruptionBudget (PDB) with a minimum availability of one."* That is at least four extra pods before any application pod is scheduled, and it is why D1's node pool is two nodes rather than one. Prerequisites, quoted: *"You must use `azure-cli` version `2.86.0` or higher"* and *"Enable the [Managed Gateway API installation]. Use of self-managed Gateway API CRDs with the application routing add-on is unsupported."*

**Portability.** `Gateway` and `HTTPRoute` are upstream Kubernetes resources and cross to EKS unchanged. `gatewayClassName: approuting-istio` and the Azure load-balancer annotations do not. That split is the intended one.

**Mechanism update (task 5.4): `azapi_update_resource`, not a native `azurerm` attribute.** The decision above stood unchanged; what changed is how Section 5 turns it on. The `azurerm` provider pinned in `versions.tf` (`~> 4.0`) has no attribute for it — its `web_app_routing` block supports only `dns_zone_ids` and `default_nginx_controller` ([azurerm_kubernetes_cluster](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/kubernetes_cluster)). What actually turns the mode on was read from Microsoft's own schema rather than assumed, at the first **stable, non-preview** `Microsoft.ContainerService/managedClusters` API version that carries it, **`2026-04-01`**:

| Path | Type | Value that enables it |
|---|---|---|
| `properties.ingressProfile.gatewayAPI.installation` | `ManagedClusterIngressProfileGatewayConfiguration` | `"Standard"` (default `"Disabled"`) — installs the managed Gateway API CRDs; the `--enable-gateway-api` flag |
| `properties.ingressProfile.webAppRouting.gatewayAPIImplementations.appRoutingIstio.mode` | `ManagedClusterAppRoutingIstio` | `"Enabled"` (default `"Disabled"`) — the sidecar-less Istio control plane for App Routing; the `--enable-app-routing-istio` flag |

Read from the [`managedClusters` 2026-04-01 ARM template reference](https://learn.microsoft.com/en-us/azure/templates/microsoft.containerservice/2026-04-01/managedclusters), and the second path independently again, word-for-word the same property, from the Java SDK's [`ManagedClusterWebAppRoutingGatewayApiImplementations`](https://learn.microsoft.com/en-us/java/api/com.azure.resourcemanager.containerservice.models.managedclusterwebapproutinggatewayapiimplementations) class — *"Configuration for using a sidecar-less Istio control plane for managed ingress via the Gateway API with App Routing."* Two independently-generated Microsoft references agreeing is the closest this pass gets to confirmation without a live cluster. Both CLI flags are GA together as of AKS release `v20260428` per the [AKS Engineering Blog's GA announcement](https://blog.aks.azure.com/2026/06/10/app-routing-gateway-api-ga) — *"You no longer need preview feature flags or the `aks-preview` extension"* — which is why a **stable** API version carries the property at all; the [earlier post announcing the feature](https://blog.aks.azure.com/2026/03/18/app-routing-gateway-api) predates that GA and was still preview-gated. **Not verified against a live cluster**: what would settle it is task 9.5's routing check actually reaching the `Gateway` through this path rather than failing to find it.

**Three ways to apply that patch, weighed against each other:**

| Option | What it is | Rejected because |
|---|---|---|
| Full `azapi_resource` declaring the whole cluster | Replace `azurerm_kubernetes_cluster.this` with an `azapi_resource` carrying the entire ARM body | Every other cluster property — D3's tier, D5's OIDC/workload identity/Key Vault provider, D8's `monitor_metrics`, D14's node pool — would move onto the untyped preview-adjacent surface with it, for the sake of one property. Broader blast radius than the change needs, and it throws away `azurerm`'s typed schema for everything the provider already handles correctly |
| `null_resource` + `local-exec` running `az aks update --enable-gateway-api --enable-app-routing-istio` | Terraform's standing escape hatch for provider gaps | Weaker on the two things this design already tracks carefully: `terraform plan` cannot show the change before it happens, and a `local-exec` reports success on exit code 0 whether or not the property actually changed. It is the "someone has to remember a command was needed" shape D5 rejected for the vault secret, moved into a provisioner instead of into prose |
| `azapi_update_resource` against the existing `azurerm_kubernetes_cluster.this` (**chosen**) | A merge-patch resource: `resource_id` targets the cluster `azurerm` already declares; `body` carries only the `ingressProfile` subtree above | — |

Both rejected alternatives are real patterns, not straw men — the same tradeoff between them shows up in `hashicorp/terraform-provider-azurerm`'s own GitHub issues for this exact class of gap, where different teams have landed on each. `azapi_update_resource` is narrower than the first (it patches `properties.ingressProfile` only; every other property stays under `azurerm`'s management, untouched) and more state-trackable than the second (the patched values become Terraform state attributes; `terraform plan` shows drift against them the same way it does for any other resource, which a shell command does not give for free).

**Base enablement stays in `azurerm`, where it already works.** The App Routing add-on's base enablement (`ingressProfile.webAppRouting.enabled`) is `azurerm`'s `web_app_routing` block — no gap there, so `cluster.tf` declares it directly rather than folding it into the patch. `default_nginx_controller = "None"` is set explicitly on that block: enabling `web_app_routing` at all provisions the add-on, and leaving `default_nginx_controller` at the provider's own default (`AnnotationControlled`) would deploy the exact managed-NGINX controller this decision rejects by name, running alongside the Istio implementation the patch turns on. `azapi_update_resource` adds only the two properties `azurerm` cannot express.

**New provider dependency, named as one.** `azapi` is not used anywhere else in this repository; `versions.tf` pins it (`~> 2.0`) and says so in a comment, matching how that file already comments its other choices. Disposable in D0's sense: the property this patches, and the provider that patches it, have no EKS equivalent to carry forward to Step 10.

**What `terraform destroy` does to this patch.** `azapi_update_resource`'s own documentation states that deleting it performs no operation and the patched properties stay as they are. Destroying the whole cluster (D10, Section 10) removes the property along with the cluster it belonged to, which is the only teardown path any task in this change takes — recorded here so an `azapi_update_resource`-only destroy is never assumed to revert the mode the way destroying a plain `azurerm` resource would.

### D3 — AKS **Free** tier (disposable)

Quoted from [AKS Free, Standard, and Premium pricing tiers](https://learn.microsoft.com/en-us/azure/aks/free-standard-pricing-tiers) (page dated 2026-07-06):

| Tier | When to use | Cluster sizes | Feature comparison |
|---|---|---|---|
| Free | *"Development and test environments, learning, evaluation, and non-production workloads."* | *"Recommended for clusters with fewer than 10 nodes."* | *"Free cluster management. … Supports up to 1,000 nodes. No financially backed uptime SLA."* |
| Standard | *"Production workloads requiring uptime SLA coverage."* | up to 5,000 nodes | *"Uptime SLA enabled by default."* |
| Premium | *"Production workloads requiring uptime SLA plus 24-month Long Term Support (LTS)."* | up to 5,000 nodes | LTS; requires `--k8s-support-plan AKSLongTermSupport` |

SLA terms: *"With availability zones: 99.95% … Without availability zones: 99.9% … Free tier: best-effort uptime (no financially backed SLA)."* Retail prices read today: Standard `Standard Uptime SLA` $0.10/hour, Premium `Standard Long Term Support` $0.60/hour.

**Decision: Free.** A two-node cluster that exists for hours and is destroyed is the documented Free-tier scenario verbatim. Standard would add $0.10/hour — comparable to the entire node bill in D1's sizing — to buy an API-server SLA on a cluster whose availability target is "up while someone is looking at it." Premium's LTS is for staying on a Kubernetes version for two years; this cluster does not outlive an afternoon.

**What Free costs us, stated rather than glossed:** AKS cost analysis is unavailable. *"Your cluster must use the `Standard` or `Premium` tier, not the `Free` tier"* and *"Once you enable cost analysis, you can't downgrade your cluster to the `Free` tier without first disabling cost analysis"* ([AKS cost analysis](https://learn.microsoft.com/en-us/azure/aks/cost-analysis), page dated 2026-07-29). This costs less than it sounds: the same page limits its Kubernetes views to *"the Enterprise Agreement and Microsoft Customer Agreement Microsoft Azure offer types"*, so on a pay-as-you-go subscription the add-on would not produce the namespace-level views anyway, while still forcing the cluster onto a paid tier. The table above is what this design offers instead of that add-on.

**Tier is a one-line change** (`az aks update --tier standard`, or the Terraform equivalent) if the reasoning ever stops holding.

### D4 — Azure Container Registry Basic; GitHub Actions authenticates by OIDC federation, with no stored secret (disposable)

**Registry: ACR Basic.** $0.1666/day with 10 GB included. Chosen over GHCR for one mechanical reason: `az aks update --attach-acr` *"assigns the [AcrPull role] to the Microsoft Entra ID managed identity associated with the agent pool"*, and *"This article covers automatic authentication between AKS and ACR. If you need to pull an image from a private external registry, use an image pull secret"* ([Integrate ACR with AKS](https://learn.microsoft.com/en-us/azure/aks/cluster-container-registry-integration), page dated 2026-05-08). GHCR would put a long-lived registry credential back into the cluster as an `imagePullSecret` — the exact thing D5 exists to remove for the other secret.

Two caveats read on that page and carried forward: the integration *"isn't supported for ABAC-enabled ACR registries"* (those need `Container Registry Repository Reader` assigned manually instead), and there is a documented role-propagation latency when `AcrPull` is granted via an Entra group rather than directly.

**Authentication from CI: a user-assigned managed identity with a federated identity credential.** GitHub Actions gets an OIDC token from `https://token.actions.githubusercontent.com`; Entra trusts it for one repository and one ref. The workflow needs `permissions: id-token: write` — *"Require write permission to Fetch an OIDC token"* — and `azure/login@v2` with `client-id`, `tenant-id`, `subscription-id` ([Authenticate to Azure from GitHub Actions by OpenID Connect](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect)). Those three values are identifiers, not secrets; nothing that could be replayed is stored in GitHub.

This replaces `docs/step7.md`'s "Step 9 extension (ECR push)" block, which uses `aws-actions/configure-aws-credentials@v4` with `secrets.AWS_ACCESS_KEY_ID` / `secrets.AWS_SECRET_ACCESS_KEY` — a long-lived key pair. The redirect from AWS to Azure is forced by `docs/plan.md`; moving from a stored key pair to federation is a separate improvement and is taken deliberately. The drafted snippet is also stale in a way unrelated to the cloud: it declares `needs: build`, and `.github/workflows/ci.yml` contains `build-backend` and `build-frontend`, no `build`. Copying it forward unchanged would produce a workflow that fails to parse.

**Shape of the new job:** a `push` job gated on `github.ref == 'refs/heads/main' && github.event_name == 'push'`, needing `build-backend` and `build-frontend`, tagging images `${{ github.sha }}`. Because it is gated, `docs/step7.md`'s "passes on a fresh fork with zero configuration" property survives — a fork has no federated credential and never reaches the job.

**AKS-scoped access for the same identity (resolves the gap task 4.4 flagged).** Task 4.4 built the CI identity and its ACR push grant, and noted in the same breath that `az aks get-credentials` (task 6.4) and the `helm upgrade --install` that follows it (task 6.4, D13) need a role assignment scoped to the cluster — a resource the platform state doesn't have. Settled here, for Section 5 (task 5.9) to implement against this state's own `azurerm_kubernetes_cluster` resource.

**Decision: enable Azure RBAC for Kubernetes Authorization on the cluster** — `azure_active_directory_role_based_access_control.azure_rbac_enabled = true` on the `azurerm_kubernetes_cluster` resource task 5.2 defines — **and grant the CI identity two role assignments scoped to the cluster resource: "Azure Kubernetes Service Cluster User Role" and "Azure Kubernetes Service RBAC Writer."**

Quoted from [Use Azure RBAC for Kubernetes Authorization](https://learn.microsoft.com/en-us/azure/aks/manage-azure-rbac): Cluster User "allows access to the Kubernetes API server (required to use `kubectl`)" — this is the credential-retrieval role `az aks get-credentials` (task 6.4) needs, and it grants nothing about what the retrieved credential can then do inside the API server. RBAC Writer "allows read and write access to most objects in a namespace" — which is what `helm upgrade --install` needs to create and update the chart's Deployments, Services, ServiceAccount, `SecretProviderClass`, `Gateway` and `HTTPRoute` (Section 3), without the delete-anything, every-namespace reach of Cluster Admin.

**Rejected: "Azure Kubernetes Service Cluster Admin Role."** It grants unrestricted access to every namespace and every verb — more than a `helm upgrade --install` run from one narrowly-scoped GitHub Actions job needs. This is the same proportionality D4 already applies to the registry (`AcrPush`, not `Owner`) and D5 already applies to the backend identity (`Key Vault Secrets User`, not `Key Vault Administrator`); granting Cluster Admin here would work against that posture rather than extend it.

**Rejected: local accounts.** AKS's alternative to Azure RBAC for Kubernetes Authorization is a static kubeconfig credential from `az aks get-credentials --admin` against local Kubernetes accounts. That is exactly the shape of credential D4's OIDC federation exists to avoid — a bearer credential that authenticates on its own if it leaks, with no federation and no expiry tied to a GitHub Actions run. Azure RBAC for Kubernetes Authorization keeps every access decision behind Entra, so the CI identity's existing OIDC-federated token is what authenticates, exactly as it already does against ACR.

**Mechanism.** Both are `azurerm_role_assignment` resources living in `Infrastructure/terraform/cluster/`, not the platform state — the scope is `azurerm_kubernetes_cluster.this.id`, a resource that state doesn't have (D10's same reasoning task 4.4 already gave for deferring this). Both assignments target `principal_id = var.ci_identity_principal_id`, fed from the platform state's `ci_identity_principal_id` output (task 5.9) — the identity D4 already created, not a new one. RBAC Writer is assigned at the **cluster** scope rather than a single namespace, because nothing in this design restricts `helm upgrade --install` to one namespace.

**Portability:** disposable, like the rest of D4. EKS's equivalent of "who can authenticate and what can they then do" is an access entry or an `aws-auth` ConfigMap, not an Azure RBAC role assignment — this mechanism does not cross to Step 10 unchanged.

**CI runtime configuration: eight identifiers, as repository Variables (resolves gaps Section 6 found).** `tasks.md` never stated where the `push` job (task 6.1) reads the OIDC identifiers `azure/login` needs (task 6.2), the ACR login server (task 6.3), the AKS cluster's name and resource group (task 6.4), or — found in a later review pass of the same section — the backend identity's client ID and the vault's name that `helm upgrade --install` needs to actually wire up D5's secret-delivery mechanism (also task 6.4). Each is used in the workflow but none had a source. Settled here, in the same style as this section's other extensions.

**Decision: all eight as GitHub Actions repository Variables (`${{ vars.NAME }}`), not Secrets.**

| Variable | Source | Needs task 8.1 first? |
|---|---|---|
| `AZURE_CLIENT_ID` | Platform state's `ci_identity_client_id` output | Yes |
| `AZURE_TENANT_ID` | The Azure AD tenant ID | No |
| `AZURE_SUBSCRIPTION_ID` | The Azure subscription ID | No |
| `ACR_LOGIN_SERVER` | Platform state's `acr_login_server` output | Yes |
| `AKS_CLUSTER_NAME` | `Infrastructure/terraform/cluster/variables.tf`'s `cluster_name` default (`travel-agent`) | No |
| `AKS_RESOURCE_GROUP_NAME` | That same state's `resource_group_name` default (`travel-agent-cluster`) | No |
| `BACKEND_IDENTITY_CLIENT_ID` | Platform state's `backend_identity_client_id` output | Yes |
| `KEY_VAULT_NAME` | Platform state's `key_vault_name` output | Yes |

**Variables, not Secrets — same reasoning D4 already gave for `client-id`/`tenant-id`/`subscription-id` in the OIDC-login step:** *"Those three values are identifiers, not secrets; nothing that could be replayed is stored in GitHub."* All eight here are identifiers — client IDs, a tenant ID, a subscription ID, a DNS hostname, and three resource names — not bearer credentials. Marking any of them Secret would only mask them in logs for no security benefit, and would make the four name-shaped variables harder to cross-check by eye against the Terraform defaults and outputs they have to match.

**No ninth variable for `keyVault.tenantId`.** `azurerm_key_vault.this`'s `tenant_id` (`keyvault.tf`) is `data.azurerm_client_config.current.tenant_id` — the same Azure AD tenant `AZURE_TENANT_ID` already names. A vault created in a different tenant than the one CI authenticates against isn't a configuration this design has anywhere else, so introducing a second variable for what is structurally the same value would only create a second place for the tenant ID to go stale against the first. The deploy step reuses `${{ vars.AZURE_TENANT_ID }}` for `--set keyVault.tenantId=...` instead. `Infrastructure/terraform/platform/outputs.tf` already exposes a `key_vault_tenant_id` output for this same value, and it goes unused here on purpose — consuming it would thread the one fact `data.azurerm_client_config.current.tenant_id` names through two differently-named variables (`AZURE_TENANT_ID` and a hypothetical `KEY_VAULT_TENANT_ID`) instead of one, which is the exact duplication this paragraph exists to avoid.

**The split matters because two states, not one, are applied on the raise/destroy schedule (D10).** `AZURE_TENANT_ID` and `AZURE_SUBSCRIPTION_ID` name the Azure AD directory and subscription themselves — properties of the account the operator is already signed into, true before any `terraform apply` and unaffected by any teardown. `AKS_CLUSTER_NAME` and `AKS_RESOURCE_GROUP_NAME` are Terraform *input* variable defaults, not outputs — literals this design already chose (`variables.tf`), not values Azure assigns back after creation — so they're equally knowable before any apply. All four are set once, now, rather than deferred (Section 6's own new task covers this). `AZURE_CLIENT_ID`, `ACR_LOGIN_SERVER`, `BACKEND_IDENTITY_CLIENT_ID` and `KEY_VAULT_NAME` are different in kind: all four are Terraform *outputs* of the platform state — two identities' client IDs and two globally-unique names carrying a `random_string` suffix (tasks 4.2, 4.3) — none exists as a value until task 8.1 has actually applied that state. Setting them now would mean setting them to nothing; task 8.2 sets all four, positioned after the state that produces them and before the deploy step that consumes them.

**Not duplicated as workflow literals.** `AKS_CLUSTER_NAME` and `AKS_RESOURCE_GROUP_NAME` could have been written directly into `.github/workflows/ci.yml` as literal strings, since both are already fixed by `variables.tf`'s defaults rather than assigned at apply time. Reading them from a repository Variable instead means the workflow and the Terraform default can never independently drift — the alternative is the exact failure shape `CLAUDE.md`'s "never restate figures" rule already warns about, just for a resource name instead of a measurement.

### D5 — `GOOGLE_API_KEY` comes from Azure Key Vault via the Secrets Store CSI driver, with the pod federated by Workload ID. The plain `secretKeyRef` does not survive (disposable)

What exists today, from `Infrastructure/k8s/backend-deployment.yaml`:

```yaml
            - name: GOOGLE_API_KEY
              valueFrom:
                secretKeyRef:
                  name: travel-agent-secrets
                  key: google-api-key
```

and `docs/step5.md`'s instruction to create it by hand: `kubectl create secret generic travel-agent-secrets --from-literal=google-api-key=<key>`.

**This does not survive**, for a reason that is about the repository rather than about cryptography: the Secret's existence is an out-of-band manual step recorded in prose, so a cluster raised from Terraform is not actually reproducible from Terraform — someone has to remember a command. That is precisely the failure mode `docs/plan.md` rejects when it says the deliverable is the repository.

**Decision:** the vault is Terraform-managed; the secret *value* is set out-of-band with `az keyvault secret set` and never enters Terraform state or the repository. The AKS cluster runs `--enable-addons azure-keyvault-secrets-provider` together with `--enable-oidc-issuer --enable-workload-identity` (*"If you want to use Microsoft Entra Workload ID, the `az aks create` command must include the `--enable-oidc-issuer` and `--enable-workload-identity` parameters"*, [csi-secrets-store-driver](https://learn.microsoft.com/en-us/azure/aks/csi-secrets-store-driver)). The backend's ServiceAccount is annotated with `azure.workload.identity/client-id` and the pod labelled `azure.workload.identity/use: "true"` — *"This label is required in the pod template spec"* ([Workload ID on AKS](https://learn.microsoft.com/en-us/azure/aks/workload-identity-overview)) — and that identity holds `Key Vault Secrets User` on the vault, the role the docs name for the `secret` object type.

**The `secretKeyRef` block in the Deployment stays.** The CSI driver's *"Syncs with Kubernetes secrets"* feature produces the Kubernetes Secret, and the container keeps reading `GOOGLE_API_KEY` from its environment. Nothing in `backend/` changes: `load_dotenv()` and `os.environ` in `backend/api/main.py` and `backend/rag/retriever.py` are untouched, and no Azure SDK enters `requirements.txt`. What changes is where the Secret comes from — a vault with RBAC and an audit trail, instead of a shell command someone ran once.

**The Deployment needs both the volume mount and the `secretKeyRef`.** *"Your secrets sync after you start a pod to mount them. When you delete the pods that consume the secrets, your Kubernetes secret is also deleted."* ([CSI driver configuration options: Sync mounted content with a Kubernetes secret](https://learn.microsoft.com/en-us/azure/aks/csi-secrets-store-configuration-options)). So the sync is pod-mount-driven in both directions: the Deployment carries a `csi` volume it never reads from directly, only to trigger the sync that produces the Kubernetes Secret the `secretKeyRef` actually reads — and that Secret disappears with the last pod that mounts it, which matters on the next raise if anything other than this Deployment ever expected the Secret to persist. The volume mount gets the one-line comment `CLAUDE.md` allows for a mechanical constraint with no home in the docs: `# Unread by the container; mounting it is what makes the CSI driver sync GOOGLE_API_KEY into the Kubernetes Secret secretKeyRef below reads.`

**Rotation stops at the Secret object; it does not reach a running container.** The paragraph above describes the CSI driver keeping the mounted file and the synced Kubernetes Secret current. `GOOGLE_API_KEY` is read as an environment variable via `secretKeyRef`, not from the mounted file — and Kubernetes populates a container's environment from a Secret exactly once, at container start; it does not watch the Secret object for changes the way the mounted file is kept current. So rotating the value in the vault updates the vault, the mount and the Secret object, but an already-running container keeps the old value in its environment until that pod is restarted. Rotation is therefore not complete on `az keyvault secret set` alone — it needs a `kubectl rollout restart` of the backend Deployment to actually take effect, and nothing in this design makes that restart automatic.

**Portability:** the ServiceAccount/Secret shape crosses to EKS; the vault, the identity and the federation are rewritten against IRSA and Secrets Manager.

### D6 — The CORS origin becomes configuration, defaulting to today's value (portable)

`backend/api/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
```

**Decision:** read the list from an environment variable, defaulting to `http://localhost:3000` when unset. Local development, `docker-compose up` and `pytest` all behave exactly as they do now; the cluster supplies its own origin through the Deployment.

The tempting alternative is to leave it alone, on the grounds that with `kubectl port-forward` the browser is on `localhost:3000` anyway and the literal still matches. It is true, and it is why this is a small change rather than an urgent one — but it makes the deployment correct only under one access path, and it makes D2's Gateway pointless the moment anything is served through it. A hardcoded origin is also the kind of thing that is invisible until it fails at request time with an error that names CORS rather than naming the deployment.

`backend/tests/test_api_main.py` already covers CORS and gains a case for the configured path. This is the only application-code change in the step besides `frontend/Dockerfile`'s build argument (D1).

### D7 — Metrics go to an Azure Monitor workspace; the existing local Grafana reads them. No Grafana is deployed (disposable)

`docs/plan.md` lists three options: lift the Prometheus/Grafana pair into the cluster, defer to Azure Monitor, or leave observability local and out of the step. The constraint it attaches is the one that decides it — the local Prometheus holds history the owner decided to keep, and a new cluster does not inherit it.

**Decision: Azure Monitor managed Prometheus for the cluster (`--enable-azure-monitor-metrics`), no Azure Managed Grafana, and the local compose stack completely untouched.** The Grafana already running in compose gains a *second* datasource pointing at the Azure Monitor workspace's query endpoint.

That last part is what makes this work rather than being two disconnected systems, and it is documented: self-managed Grafana can query managed Prometheus using Azure Auth against an Entra app registration ([Connect Grafana to Azure Monitor managed service for Prometheus](https://learn.microsoft.com/en-us/azure/azure-monitor/metrics/prometheus-grafana)). One Grafana, two datasources, two systems, no merging.

Why not the other two options:

- **Lifting Prometheus and Grafana into the cluster** means a PersistentVolumeClaim, a managed disk, and a decision about whether `prometheus_data`'s 90 days follow it. Both answers are bad: migrating the history puts a laptop's data into a cluster that did not produce it, and not migrating it creates a second empty history whose relationship to the first is undefined. It also destroys the dashboards on every teardown unless they are re-provisioned, and `observability/grafana/provisioning/` already provisions them — for a Grafana that is not going anywhere.
- **Leaving observability out entirely** would leave `docs/plan.md`'s container CPU/memory question unanswered, which D8 answers.

**Nothing about the local stack changes.** `observability/prometheus.yml`, `observability/grafana/provisioning/`, `prometheus_data`, `grafana_data` and the 90-day retention decided by `prometheus-retention-policy` are all outside this change. Adding a datasource is a Grafana configuration action, not a change to the Prometheus that holds the history.

**Cost:** the Azure Monitor workspace has no standing meter in the retail price list — it bills on ingestion and query, quantified in D8. Azure Managed Grafana Standard would have been $0.0445/hour per node plus $6/month per user; not spending that is a direct consequence of this decision, not a rounding.

### D8 — Container CPU and memory: managed Prometheus' default `cadvisor` target, minimal ingestion profile left on. Container insights is not enabled (disposable)

`docs/plan.md` is right that no orchestrator supplies this for free. Three ways to get it:

| Mechanism | What it costs (germanywestcentral retail) | What it gives |
|---|---|---|
| Managed Prometheus (`--enable-azure-monitor-metrics`) | $0.16 per 10M samples ingested; $0.001 per 10M samples queried | `cadvisor` scraped by default |
| Container insights (`--enable-addons monitoring`, Log Analytics) | $2.99/GB `Analytics Logs Data Ingestion`; $0.13/GB/month retention | Logs, events, inventory, plus metrics |
| Self-managed Prometheus scraping kubelet/cAdvisor | $0 to Azure; node capacity + scrape config nobody has written | Whatever you configure |

**Decision: managed Prometheus, minimal ingestion profile left at its default.**

The default targets are *"`cadvisor`, `nodeexporter`, `kubelet`, `kube-state-metrics`, `networkobservabilityRetina`"*, and the `cadvisor` metric list collected by default includes `container_cpu_usage_seconds_total`, `container_memory_working_set_bytes`, `container_memory_rss`, `container_cpu_cfs_throttled_periods_total` and `container_spec_cpu_quota` ([Default Prometheus metrics configuration](https://learn.microsoft.com/en-us/azure/azure-monitor/containers/prometheus-metrics-scrape-default), page dated 2026-08-18). That is container CPU and memory, requests-versus-usage and throttling — the whole question — with no scrape configuration written by us. Linking the workspace to Grafana also provisions the standard `Kubernetes / Compute Resources / …` dashboards.

The **minimal ingestion profile** stays on because it is the cost control: *"This setting reduces the volume of metrics ingested by limiting them to only metrics used by default dashboards, default recording rules, and default alerts. … If this setting is disabled, then all available metrics for the default targets are collected which can significantly increase ingestion volume."*

**Container insights is not enabled.** It is the expensive one by an order of magnitude per unit, and this stack's application logs are already structured JSON on stdout — Step 8 built that. Paying $2.99/GB to re-ingest them into Log Analytics buys a query language the repository does not otherwise use.

**What enabling it costs, quantified.** The unit price is read: $0.16 per 10M ingested samples. Turning that into a monthly figure needs an active-series count and a scrape interval, and **I do not know either for this cluster.** The shape, **[reasoned]** and stated as arithmetic rather than as a measurement: at a 30-second scrape interval a single series produces 120 samples/hour, so 1,000 active series ≈ 120,000 samples/hour ≈ $0.0019/hour — under a cent for an eight-hour session, and roughly $1.40 if a cluster ran for a month. Both inputs are assumptions: the 30-second default interval was not read from a Microsoft page in this pass, and the series count is a guess. **What would settle it:** raise the cluster once and read the workspace's own ingestion metric for the session; that is a measurement, and per `CLAUDE.md` it then lives in exactly one place and is pointed at, not copied.

The honest summary is that ingestion is small relative to $0.48/hour of nodes and load balancer, but "small" here is an estimate and is labelled as one.

### D9 — Grafana's credential: decided here, specified elsewhere; and a contradiction in `docs/plan.md` reported rather than fixed

`docs/plan.md` carries this from Step 8: Grafana *"still runs on its unchanged default login (`admin`/`admin`, printed in `docs/step8.md`'s "Running Locally"). Harmless while `grafana` is bound to `localhost`, as it is today — it stops being harmless the moment a deployment exposes it past that."*

**The premise is not what the repository does.** From `docker-compose.yaml`:

```
$ grep -n -A3 "^  grafana:" docker-compose.yaml
44:  grafana:
45:    image: grafana/grafana:latest
46:    ports:
47:      - "3001:3000"
$ grep -rn "GF_" docker-compose.yaml
$ echo "exit=$?"
exit=1
```

`"3001:3000"` is Docker Compose's short port syntax with no host-IP part, which publishes on all host interfaces rather than on loopback ([Compose file reference: ports](https://docs.docker.com/reference/compose-file/services/#ports)). And there is no `GF_SECURITY_ADMIN_PASSWORD` anywhere in the file — the grep returns nothing. So Grafana is on `admin`/`admin` and reachable from the local network today, not only after some future deployment exposes it. I have **not** verified this against a running container: `docker compose ps` returned `Cannot connect to the Docker daemon`, so this rests on the file plus Docker's documented default. Per `CLAUDE.md`'s "stop rather than improvise", this is reported and `docs/plan.md` is not edited.

**The decision**, so the question is not left open: Grafana's admin password is supplied by `GF_SECURITY_ADMIN_PASSWORD` from the operator's environment with no default value in the repository, and the published port is bound explicitly to `127.0.0.1`.

**Both edits are already in the repository, and landed outside this change.** The observation above reads `docker-compose.yaml` as it stood before commit `89f04e9`, which carried them:

```
$ git log --oneline -- docker-compose.yaml
89f04e9 doc: create proposal md for task9
306e335 feat:step8
220f7fc feat: implementing frontend, dockerfile fro frontend,
14a799f create docker file for backend
91a4a61 initial commit
$ grep -n "127.0.0.1\|env_file" docker-compose.yaml
7:      - "127.0.0.1:8000:8000"
8:    env_file:
24:      - "127.0.0.1:3000:3000"
33:      - "127.0.0.1:9090:9090"
47:      - "127.0.0.1:3001:3000"
48:    env_file:
```

All four published ports are on loopback, and `grafana` reads `observability/grafana/.env` with `required: false`, whose committed template `observability/grafana/.env.example` carries `GF_SECURITY_ADMIN_PASSWORD=choose-a-real-password`. Two consequences. This change makes no `docker-compose.yaml` edit, so `proposal.md`'s "no other application file changes" holds as written. And what is left of D9 is an operator action — copy `.env.example` to `.env` and set a real value — not a repository edit; until someone does, Grafana starts on its own default, now on loopback only. The `docs/plan.md` contradiction reported above is also resolved by that same commit for the binding half: `grafana` *is* bound to `localhost`, as `docs/plan.md` says it is.

**Where the requirement lives: not here.** A requirement about how Grafana is credentialled belongs to the `observability` capability, which this change does not amend by instruction. So D9 decides, `proposal.md`'s Non-Goals records that no spec text is written for it, and closing `docs/plan.md`'s Step 8 carry-over item properly needs an `observability` delta that someone still has to write. What D9 *does* bind for `deployment` is negative and testable: this change never places Grafana anywhere the default credential would be exposed, because D7 does not deploy Grafana at all.

### D10 — Teardown is deleting the cluster resource group; the platform resource group survives (disposable)

**Two states, two paths.** The two resource groups are two Terraform configurations with separate state: `Infrastructure/terraform/platform/` holds items 9–13 and is applied once; `Infrastructure/terraform/cluster/` holds items 1–8 and is the one `terraform destroy` runs against. One state holding both would make the routine operation capable of taking the registry with it.

**Mechanism:** `terraform destroy` against the cluster configuration, or `az group delete` on the cluster resource group. Deleting the cluster's resource group also removes the node resource group — *"These commands delete the ACR and AKS cluster and the clusters node resource group that begins with `MC_`"* ([Integrate ACR with AKS](https://learn.microsoft.com/en-us/azure/aks/cluster-container-registry-integration)). The platform resource group (items 9–13) is a **separate** resource group precisely so that one `terraform destroy` cannot take the registry and the vault with it.

**What is lost, and is meant to be:**
- Every cluster metric in the Azure Monitor workspace. The workspace lives in the cluster resource group — item 8 in the inventory, created fresh on every raise — and is destroyed with it, taking the whole observability record of that session. Deliberate for this iteration: a session's metrics describe a cluster that no longer exists. See below for the trigger that would move it.
- The cluster's ChromaDB. Pods start with an empty vector store (D1), so the next raise re-runs ingestion — and `rag/ingest.py` calls the Gemini embeddings API, so re-ingesting spends quota. Not the thirteen-minute `scripts/generate_load.py`, but not free either.
- The Gateway's internal address, the node pool, the load balancer, the public IP.
- Nothing else. There is no cluster-side state anyone is expected to keep; that is the design, not an accident.

**What survives, and costs money:** ACR and its images (≈ $5/month). Destroying the registry would break CI's push job on the next merge to `main`, so it is kept on purpose rather than by omission.

**What survives at zero cost:** the Key Vault and its secret, the two managed identities and their federated credentials. *"You can't reuse the name of a key vault that was soft-deleted, until the retention period expires"* ([Key Vault soft-delete overview](https://learn.microsoft.com/en-us/azure/key-vault/general/soft-delete-overview)), and that period is configurable from 7 to 90 days at vault creation, defaulting to 90. This design's Terraform does not set the retention period explicitly anywhere, so unless a task in `tasks.md` states one, the vault gets the 90-day default — the longest the name stays unusable if the vault is ever deleted and a same-named one recreated. This matters only in that scenario; the platform resource group is not part of routine teardown, so it does not arise in the ordinary raise/destroy cycle.

**Where the workspace lives.** Decision: for this iteration, the Azure Monitor workspace stays in the cluster resource group — created fresh by `--enable-azure-monitor-metrics` on every raise, destroyed with the cluster on every teardown. This is interim, not settled: the alternative (moving it to the platform resource group, where it would survive and sessions would accumulate) was a real Open Question this design left unanswered rather than assumed, and the answer above is chosen because it costs nothing standing and requires no cross-state wiring to build, not because the question is closed for good.

**What this does not license.** The moment there is an actual need to compare metrics across sessions — more than one raise, with a reason to look at a trend rather than a single session's snapshot — this decision is void and the workspace moves to the platform resource group (`Infrastructure/terraform/platform/`, alongside items 9–13). That move is a change of ownership, not a relocation, and it carries one mechanical consequence worth recording now so it is not rediscovered from scratch later: the cluster state's `--enable-azure-monitor-metrics` currently *creates* the workspace as part of raising the cluster; once the workspace lives in the platform state, the cluster state instead has to *attach* to the existing workspace by resource ID — a cross-state reference read from the platform state's output, not a new workspace created on every raise. Not implemented here, the same way D2 and D15 record the trigger that would void them without pre-building for it.

**What teardown has nothing to do with:** `docker-compose down -v`. Cluster teardown destroys resources designed to be destroyed; `docker-compose down -v` destroys `prometheus_data`, which per `CLAUDE.md` needs an explicit instruction every time. Any teardown documentation this change produces must say so on the same page, because the two are one careless sentence apart.

### D11 — The two `docs/step5.md` Step 9 commitments: one honoured in substance, one revisited

**"Step 9 | Server mode, standalone StatefulSet | Multi-replica pods can't share a named volume."** The reasoning holds and is confirmed by the current manifest: `Infrastructure/k8s/backend-deployment.yaml` mounts nothing at all, so every replica would start with an empty `rag/chroma_db` (excluded from the image by `backend/.dockerignore`) and RAG would silently return nothing. The commitment is honoured in substance — the vector store must stop being per-pod local state.

**Decided (task 3.10): a single-replica ReadWriteOnce PVC, not a standalone Chroma server.** The chart runs one backend replica (`values.yaml` `replicaCount.backend: 1`), which removes the reason a server would be needed — "multi-replica pods can't share a named volume" doesn't apply when there is one pod to begin with, and D14's capacity accounting already has no headroom budgeted for a second stateful workload alongside the Istio control plane, the CSI DaemonSets and managed Prometheus. Server mode would also touch `backend/rag/retriever.py` — `Chroma(persist_directory=CHROMA_DIR, ...)` becomes an `HttpClient` pointed at a service — which is an application-code change this step doesn't otherwise make (`proposal.md`'s Impact line: CORS and the frontend build argument are the only two). A PVC mounted at `rag/chroma_db` needs none of that: `CHROMA_DIR` stays a local path, `get_vectorstore()` is unchanged, and the four lines `docs/step5.md` already named as the only mode-dependent code stay untouched because this isn't a mode Chroma has to know about — it's just a volume.

**Ingestion is a Helm hook Job, not an operator command.** `helm.sh/hook: pre-install,pre-upgrade` runs `python rag/ingest.py` against the same PVC before the backend Deployment is created or updated — Helm hooks block until the hook resource completes, so the Job releases the ReadWriteOnce volume before the Deployment's pod tries to mount it; the two never mount concurrently. The Job reuses the backend image, the backend's ServiceAccount and workload-identity label, and its own CSI volume mount — it needs `GOOGLE_API_KEY` for the Gemini embeddings API exactly as the backend does, and on a first install nothing else has synced the Secret yet. This closes the spec's Requirement 8: no replica ever holds the corpus as per-pod local state, and no manual step runs between a deploy and the app answering correctly.

**What survives a pod restart without re-ingesting:** the PVC. Deleting or rescheduling the backend pod (task 9.7) doesn't touch the hook, which only runs on `helm install`/`helm upgrade`. What does not survive is the PVC itself across a cluster teardown (D10) — the next raise's `helm install` re-runs the ingest hook, which is the quota cost D10 already names.

**"k8s Service: `ClusterIP` … One-line change to `LoadBalancer` or ALB Ingress in Step 9."** This one is revisited, not honoured, and on two counts. ALB is an AWS load balancer and has no meaning on AKS. And the change is not one line: D2 replaces `type: ClusterIP` in `Infrastructure/k8s/backend-service.yaml` not with `type: LoadBalancer` but with a `Gateway` plus an `HTTPRoute` in front of Services that stay `ClusterIP` — which is more work than the note anticipated and is the reason `docs/plan.md` says the manifests change on every line anyway. The half of the note that survives: `ClusterIP` was the right Step 5 default, and the Services themselves keep it.

### D12 — Region: `germanywestcentral` (disposable)
Owner's decision, not derived here. What it settles technically is the price basis for every figure in the inventory above — each one read for this region rather than converted from another — and the region every resource in that inventory is created in. Nothing else in this design turns on it: AKS and its Free tier, the application routing add-on and its Managed Gateway API prerequisite, ACR, Key Vault and the Azure Monitor workspace are all available there, so D2's ingress choice and D3's tier choice stand unchanged. Disposable in D0's sense — the EKS port picks its own region and reads its own prices.

### D13 — The workload is packaged as a Helm chart; Terraform stays raw (portable)
`grep -rni helm` over this repository returns nothing, and `Infrastructure/k8s/` holds two loose YAML files. So this is a decision to introduce Helm, not to keep it.

**Decision: one chart covering the Kubernetes workload; Terraform keeps owning everything Azure.**

The reason is the one thing raw manifests cannot do here without duplication: `Infrastructure/k8s/backend-deployment.yaml` hardcodes `image: travel-agent-backend:latest`, and D4 tags images `${{ github.sha }}` in an ACR whose login server is a Terraform output. Every deploy therefore has to substitute at least an image repository and a tag, and D6 adds a CORS origin and D1 adds the frontend's API URL. Raw YAML leaves three ways to do that — commit a rendered file per deploy, run `sed` in CI, or hand-maintain `kustomize` overlays — and the first two are what `kubectl apply` pipelines usually rot into. A chart makes the substitution set explicit in `values.yaml` and typed at the point of use.

**What the chart covers:** the backend and frontend Deployments and Services, the ServiceAccount carrying D5's workload-identity annotation, the `SecretProviderClass`, the `Gateway` and `HTTPRoute` from D2, and the resource requests D14 depends on. **What stays Terraform:** every Azure resource in the inventory above — cluster, node pool, ACR, Key Vault, identities, federated credentials, role assignments, Azure Monitor workspace — plus the add-on enablement flags, which are cluster properties rather than workload. The boundary is the one D0 already draws: the chart is the portable layer and crosses to EKS with its values changed; Terraform is the disposable layer and is rewritten.

**Where both live:**

```
Infrastructure/
├── helm/travel-agent/          chart: Chart.yaml, values.yaml, templates/
└── terraform/
    ├── platform/               survives teardown (D10)
    └── cluster/                destroyed each session (D10)
```

`Infrastructure/` is already this repository's boundary around deployable infrastructure, so the split above reads directly off those two subdirectories. `Infrastructure/k8s/`'s two manifests become templates in the chart and that directory ceases to exist — chart templates are not applyable with `kubectl apply -f`, so leaving them behind would leave a path that no longer means what it says.

That makes `docs/step5.md` lines 39, 40 and 59–61 and `docs/plan.md` line 61 name files that will not be at those paths. **They are not edited.** Per `openspec/config.yaml`'s split — *"A record of what was … reports on the system rather than binding it"* — those lines record what Step 5 built and validated at the time, and a record retro-fitted to a later layout stops being a record. The current layout is stated here and in `proposal.md`; there is nothing in `docs/` to fix.

**How CI uses it:** the `push` job from D4 already authenticates to Azure by OIDC; deploying is `az aks get-credentials` then `helm upgrade --install` with `--set image.tag=${{ github.sha }}` and the registry login server. `helm template | kubectl apply --dry-run=client` is also the lint step the current loose YAML has no equivalent of.

**This changes no Azure resource and no cost.** Helm is a client-side templating and release tool; nothing in the inventory above is added, removed or re-priced by adopting it. Helm 2's in-cluster Tiller — the thing that once would have made this false — has not existed since Helm 3.

**Rejected alternatives.** Kustomize is in `kubectl` already and needs no new dependency, but expressing "substitute a tag from CI" as an overlay per environment is more files than one `values.yaml` for the same result. Leaving the YAML raw and templating in CI puts the deployment contract in a workflow file, where it is invisible to anyone reading `Infrastructure/`.

### D14 — Node pool: 2 × `Standard_D4as_v5`, not `Standard_D2as_v5`; burstable is ruled out by AKS, not by arithmetic (disposable)
The cost table previously named `Standard_D2as_v5` with no sizing behind it, and the node line is the largest single item in the hourly figure. Checked against [use-system-pools](https://learn.microsoft.com/en-us/azure/aks/use-system-pools), that SKU does not qualify:

> - System node pools require a VM SKU of at least 4 vCPUs and 4 GB of memory.
> - B series VMs aren't supported for system node pools.
> - System pools must contain at least two nodes but the recommendation is three nodes.

`Standard_D2as_v5` is 2 vCPU. It is below the documented minimum, so the original entry was wrong regardless of what the workload needs. **Decision: `Standard_D4as_v5` — 4 vCPU, 16 GiB — two nodes**, which is the documented minimum SKU and the documented minimum node count. Three nodes is the recommendation, declined because it is a recommendation for production fault tolerance and this cluster is raised for hours and destroyed.

**What that provides, per node.** CPU: 4 cores reserve 140 millicores of kube-reserved, leaving 3,860m allocatable. Memory at the default 30 max-pods: `20 MB × 30 + 50 MB = 650 MB`, which is the lesser of that and 25% of total, plus a 100 Mi eviction threshold — roughly 15.25 GiB allocatable ([node-resource-reservations](https://learn.microsoft.com/en-us/azure/aks/node-resource-reservations), AKS 1.29-and-later rules). Across two nodes: ~7.7 vCPU and ~30 GiB schedulable.

**What has to fit.** D2's ingress is the driver: the Gateway API implementation runs an `istiod` control plane whose HPA cannot go below 2 replicas, plus a proxy Deployment per `Gateway` with its own HPA minimum of 2 — at least four pods before anything of ours is scheduled. Added to that: the Secrets Store CSI driver and its Azure provider (DaemonSets, so one set per node), the managed-Prometheus `ama-metrics` pods from D8, AKS's own `coredns`/`metrics-server`/`konnectivity`, and D1's two application pods. **The precise CPU and memory requests of the AKS-managed add-on pods are not stated on any page read for this design, and are not guessed here** — the sizing argument rests on the documented SKU floor, not on a per-pod tally. What would settle it is `kubectl top pods -A` and `kubectl describe node` on one raised cluster; until then the headroom above is an upper bound on capacity, not a demonstration that the workload fits.

**Burstable, priced rather than dismissed.** `Standard_B4ms` is 4 vCPU / 16 GiB at **$0.192/hour** in this region against `Standard_D4as_v5`'s **$0.208/hour** — so B-series is both sufficient on paper and about 8% cheaper, and a cluster that idles between short sessions is close to the archetypal burstable workload. It is ruled out by one sentence of AKS policy quoted above, not by capacity and not by price. Putting a B-series *user* pool alongside a conforming system pool is strictly more expensive than this decision, since the system pool's two 4-vCPU nodes still have to exist.

**A contradiction inside Microsoft's own documentation, recorded rather than resolved.** The Terraform samples on [cluster-container-registry-integration](https://learn.microsoft.com/en-us/azure/aks/cluster-container-registry-integration) and [csi-secrets-store-driver](https://learn.microsoft.com/en-us/azure/aks/csi-secrets-store-driver) both build `default_node_pool` on `Standard_DS2_v2`, a 2-vCPU size, which the system-pool requirement above forbids. This design follows the explicit requirement rather than the samples, because a stated requirement is the thing an apply will be judged against. If a 2-vCPU system pool turns out to be accepted in practice, the node line halves and the hourly floor returns to roughly its previous value — worth checking on the first raise, and not assumed here.

**Cost consequence, stated plainly:** this decision roughly doubles the node line and raises the hourly floor from about $0.27 to about $0.48. That is a correction, not an increase — the earlier figure priced a SKU that does not satisfy AKS's own requirement.

### D15 — No TLS certificate on the Gateway; the listener is plain HTTP on an internal address (portable)
`proposal.md` currently lists TLS certificates as out of scope in the same breath as a public URL and a DNS zone. That grouping does not hold up: an internal `Gateway` can terminate TLS perfectly well without either, using a self-signed or internally-issued certificate, so "there is no public hostname" is not by itself a reason to skip it. Reopened here and decided on its own terms.

**Decision: no certificate. The Gateway's listener is HTTP on the internal load balancer's address.**

The reason is what a certificate would actually be worth on this path. D2 puts the Gateway on an internal load balancer with no public IP and no DNS name, and the only client is an operator reaching it through `kubectl port-forward` — a tunnel that is already authenticated and encrypted by the Kubernetes API server. TLS terminating at the Gateway would encrypt the hop from the port-forward endpoint to the proxy, inside the cluster's own network, and leave the proxy-to-backend hop plaintext regardless. A self-signed certificate would also have no trust chain any client validates, so every consumer would be told to skip verification — which is worse than plain HTTP, because it trains the exact habit that makes real TLS failures invisible.

What it *would* cost is not zero: the add-on's TLS path binds a certificate from Key Vault through a `SecretProviderClass` and a `Gateway` listener reference, which is a second Key Vault object, a second CSI binding, and a rotation question, all in service of a hop that is already tunnelled.

**What this does not license.** The moment the Gateway stops being internal — an external load balancer, a DNS name, anything reachable without `port-forward` — this decision is void, and TLS becomes a precondition rather than a follow-up. That is the same boundary D2 draws for the same reason, and it is why this is recorded as a decision with a trigger rather than left in a Non-Goals list where the reasoning would not survive.

## Risks / Trade-offs

- **[Risk]** D2 chooses an implementation that deploys an Istio control plane, adding at least four pods before any application pod is scheduled, on a two-node cluster. If the node pool turns out to be too small, the symptom is `Pending` pods rather than a clear error. → **Mitigation**: node count is a Terraform variable, and the first raise is a verification step whose whole purpose is to find this. There is no mitigation inside the design; the sizing is an estimate until a cluster has run.
- **[Risk]** The application routing Gateway API implementation is the *successor* path and the managed NGINX path has a published end date, but the successor is younger. The limitations read today include no `TLSRoute` SNI passthrough, no egress management, and no Istio service mesh add-on alongside it. → **Mitigation**: none needed for this workload — it uses none of those — but adopting a service mesh later means disabling this first, and the docs describe that as a two-step operation requiring CRD deletion.
- **[Risk]** D8's cost figure is arithmetic over two assumed inputs, not a measurement, and is labelled as such. If active series or scrape frequency are much higher than assumed, ingestion could stop being negligible. → **Mitigation**: minimal ingestion profile stays on, which is the documented control; and one measured session replaces the estimate.
- **[Risk]** D5's Kubernetes-Secret sync may require a volume mount that the design has not confirmed. If it does and `tasks.md` omits it, the pod starts and fails at first Gemini call rather than at deploy time — a late, confusing failure. → **Mitigation**: named as unverified with the page to read, so it is closed before implementation rather than discovered at runtime.
- **[Risk]** D9 reports that `docs/plan.md` states something the repository contradicts, and deliberately does not fix it. The contradiction stays live until someone acts on it. → **Mitigation**: none inside this change, by design; fixing a doc nobody asked to have fixed is the failure mode `CLAUDE.md` names.
- **[Trade-off]** Keeping ACR alive between sessions costs ≈ $5/month for a repository that may sit idle. Destroying it would zero that and break CI's push job on the next merge. The $5 buys a working pipeline; it is a real recurring cost and is on the approval table rather than buried.
- **[Trade-off]** D7 leaves the cluster's metrics and the laptop's metrics in two different systems joined only by one Grafana. That is less tidy than one Prometheus, and it is the price of not endangering 90 days of history that cannot be regenerated.

## Migration Plan

Additive at the repository level apart from one move: `Infrastructure/k8s/*.yaml` become templates under `Infrastructure/helm/travel-agent/` (D13) and stop existing at their old paths. Nothing else is deleted — `docker-compose.yaml` keeps working unchanged for local development, and `docs/step5.md`'s local workflow is unaffected. The two application-code edits (D1's build argument, D6's CORS variable) both keep their current behaviour as the default, so a developer who pulls this branch and runs `docker-compose up` sees no difference.

Rollback before any apply is deleting the change directory. Rollback after an apply is D10's teardown, which is the normal end of every session rather than an exceptional path — the design has no "leave it running" state to roll back from.

Sequencing constraint worth stating now: the platform resource group (ACR, Key Vault, identities) is created once and outlives clusters, so it is applied first and separately — `Infrastructure/terraform/platform/` before `Infrastructure/terraform/cluster/`, per D10.

## Open Questions

- **Which subscription, and whether it has a free-tier credit.** Affects nothing in the design and everything in whether the cost table matters.
- **Whether `--enable-control-plane-metrics` is worth adding.** It is a separate flag on top of managed Prometheus, collecting API-server and etcd metrics. Extra ingestion for something nobody has asked to see on a cluster that lives for hours; not proposed, flagged so it is a decision rather than an omission.
- **Node OS disk size and type.** The cost table prices both P6 and P10 because the default was not verified in this pass, and an ephemeral OS disk may remove the line entirely for VM sizes with local temp storage. Settled by reading the AKS node OS-disk defaults and confirming the chosen VM size has a temp disk.
