# travel-agent

Kubernetes workload for the travel agent platform: backend, frontend,
ingress, and the delivery of the backend's secret.

This chart owns the Kubernetes-level workload only; the underlying Azure
infrastructure (cluster, registry, vault, identities) is provisioned by a
separate Terraform configuration, decided in this repository's Step 9
deployment change. Deploying this chart assumes that infrastructure already
exists — it is not created by `helm install`.

## What's in this chart

- Backend and frontend `Deployment`/`Service` pairs (`ClusterIP`)
- A `Gateway` and two `HTTPRoute`s (frontend, backend), routed by hostname
- A `ServiceAccount` federated to the backend's Azure identity, and a
  `SecretProviderClass` that syncs the backend's API key from the vault
- A `PersistentVolumeClaim` for the retrieval corpus, populated by a
  pre-install/pre-upgrade hook Job before the backend Deployment starts

## Values

See `values.yaml` for the full set of configurable inputs — image
repository/tag, CORS origins, replica counts, resource requests/limits,
Gateway class and load-balancer annotations, and the Key Vault/identity
coordinates the running infrastructure supplies. `values-example.yaml` shows
a representative override set shaped like what CI actually passes at deploy
time.
