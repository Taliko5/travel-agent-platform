# Azure Monitor workspace (design.md D7, D8, D10; task 5.6) — the ingestion
# target for managed Prometheus. Lives in the cluster resource group, not the
# platform one: design.md D10 records this as an interim placement, destroyed
# with the cluster on every teardown, with the trigger that would move it to
# the platform state (comparing metrics across sessions) written down there
# rather than pre-built for here.
resource "azurerm_monitor_workspace" "this" {
  name                = "${var.cluster_name}-metrics"
  resource_group_name = azurerm_resource_group.cluster.name
  location            = azurerm_resource_group.cluster.location
  tags                = var.tags
}

# The data collection endpoint + rule + association below are the mechanism
# `--enable-azure-monitor-metrics` provisions on your behalf when the CLI
# creates the workspace link; they're declared explicitly here because
# `azurerm_kubernetes_cluster.this`'s `monitor_metrics` block (cluster.tf)
# only turns on the add-on, it doesn't wire it to a specific workspace.
# Shape mirrors AKS's own auto-provisioned DCE/DCR pair for this scenario;
# not independently verified against Microsoft's ARM template in this pass —
# task 9.10's ingestion-metric read is what confirms data is actually
# flowing, per design.md's own "not verified, here is what would settle it"
# convention (see D8).
resource "azurerm_monitor_data_collection_endpoint" "prometheus" {
  name                = "${var.cluster_name}-dce"
  resource_group_name = azurerm_resource_group.cluster.name
  location            = azurerm_resource_group.cluster.location
  kind                = "Linux"
  tags                = var.tags
}

resource "azurerm_monitor_data_collection_rule" "prometheus" {
  name                         = "${var.cluster_name}-dcr"
  resource_group_name          = azurerm_resource_group.cluster.name
  location                     = azurerm_resource_group.cluster.location
  kind                         = "Linux"
  data_collection_endpoint_id  = azurerm_monitor_data_collection_endpoint.prometheus.id
  tags                         = var.tags

  destinations {
    monitor_account {
      monitor_account_id = azurerm_monitor_workspace.this.id
      name               = "prometheusMonitorAccount"
    }
  }

  data_flow {
    streams      = ["Microsoft-PrometheusMetrics"]
    destinations = ["prometheusMonitorAccount"]
  }

  data_sources {
    prometheus_forwarder {
      streams = ["Microsoft-PrometheusMetrics"]
      name    = "PrometheusDataSource"
    }
  }
}

resource "azurerm_monitor_data_collection_rule_association" "prometheus" {
  target_resource_id      = azurerm_kubernetes_cluster.this.id
  data_collection_rule_id = azurerm_monitor_data_collection_rule.prometheus.id
}
