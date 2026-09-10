# AKS managed cluster (design.md D3: Free tier). Task 5.2.
resource "azurerm_kubernetes_cluster" "this" {
  name                = var.cluster_name
  resource_group_name = azurerm_resource_group.cluster.name
  location            = azurerm_resource_group.cluster.location
  dns_prefix          = var.cluster_name
  kubernetes_version  = var.kubernetes_version
  sku_tier            = "Free"
  tags                = var.tags

  default_node_pool {
    name       = "system"
    node_count = var.node_count
    vm_size    = var.node_vm_size
  }

  identity {
    type = "SystemAssigned"
  }

  # design.md D5: required for Microsoft Entra Workload ID, which the
  # backend ServiceAccount's federated credential depends on.
  oidc_issuer_enabled       = true
  workload_identity_enabled = true

  # design.md D4's extension: Azure RBAC for Kubernetes Authorization gates
  # what the CI identity's role assignments (task 5.9) actually grant inside
  # the API server, not just who can fetch a kubeconfig.
  role_based_access_control_enabled = true

  azure_active_directory_role_based_access_control {
    azure_rbac_enabled = true
  }

  # design.md D5: syncs GOOGLE_API_KEY from the platform state's Key Vault.
  # secret_rotation_enabled keeps the mounted file and the synced Kubernetes
  # Secret current on a poll interval — D5 is explicit that this still stops
  # short of a running container's environment, which only a pod restart
  # refreshes.
  key_vault_secrets_provider {
    secret_rotation_enabled  = true
    secret_rotation_interval = "2m"
  }

  # design.md D8: Azure Monitor managed Prometheus, minimal ingestion
  # profile left at its default (nothing here turns it off). Requires an
  # existing Azure Monitor workspace when annotations_allowed/labels_allowed
  # are both set — monitoring.tf defines that workspace (task 5.6).
  monitor_metrics {
    annotations_allowed = ""
    labels_allowed      = ""
  }

  # design.md D2: base enablement of the App Routing add-on. NGINX is
  # explicitly turned off (D2 rejects it by name) rather than left at the
  # provider's own default ("AnnotationControlled", which would deploy it) —
  # the azapi_update_resource below layers the Istio/Gateway API
  # implementation on top of this, azurerm's part is enablement only.
  web_app_routing {
    dns_zone_ids              = []
    default_nginx_controller  = "None"
  }
}

# design.md D2's mechanism update: the azurerm provider has no attribute for
# the app-routing add-on's Gateway API/Istio mode, so this patches the two
# ARM properties directly rather than declaring a second full resource for
# the cluster. Both properties and the stable (non-preview) API version that
# carries them are read from Microsoft's own schema, not assumed — see
# design.md D2 for the citations (the managedClusters 2026-04-01 template
# reference and the Java SDK's ManagedClusterWebAppRoutingGatewayApiImplementations
# class, which agree independently).
resource "azapi_update_resource" "app_routing_gateway_api" {
  type        = "Microsoft.ContainerService/managedClusters@2026-04-01"
  resource_id = azurerm_kubernetes_cluster.this.id

  body = {
    properties = {
      ingressProfile = {
        # --enable-gateway-api: installs the managed Gateway API CRDs.
        gatewayAPI = {
          installation = "Standard"
        }
        # --enable-app-routing-istio: the sidecar-less Istio control plane
        # that implements Gateway API for the App Routing add-on (D2).
        webAppRouting = {
          gatewayAPIImplementations = {
            appRoutingIstio = {
              mode = "Enabled"
            }
          }
        }
      }
    }
  }
}
