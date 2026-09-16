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

  # Gates what task 5.9's role assignments grant — design.md D4.
  role_based_access_control_enabled = true

  azure_active_directory_role_based_access_control {
    azure_rbac_enabled = true
    # Required once azure_rbac_enabled is set (provider schema), though the
    # value itself just matches tenant_id's documented default.
    tenant_id = data.azurerm_client_config.current.tenant_id
  }

  # Syncs GOOGLE_API_KEY from the platform state's Key Vault — design.md D5.
  key_vault_secrets_provider {
    secret_rotation_enabled  = true
    secret_rotation_interval = "2m"
  }

  # Requires an existing workspace once both fields are set — design.md D8.
  # "" is rejected by the provider schema; "app" is a test candidate for
  # the minimal non-empty value, not yet confirmed as final.
  monitor_metrics {
    annotations_allowed = "app"
    labels_allowed      = "app"
  }

  # Base enablement; NGINX explicitly off — design.md D2.
  web_app_routing {
    dns_zone_ids             = []
    default_nginx_controller = "None"
  }
}

# Patches the two ARM properties azurerm has no attribute for — design.md D2.
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
