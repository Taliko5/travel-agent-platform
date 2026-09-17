# Azure Monitor workspace — ingestion target for managed Prometheus. Placement
# in the cluster (not platform) resource group is D10's decision (task 5.6).
resource "azurerm_monitor_workspace" "this" {
  name                = "${var.cluster_name}-metrics"
  resource_group_name = azurerm_resource_group.cluster.name
  location            = azurerm_resource_group.cluster.location
  tags                = var.tags
}

# DCE + DCR + association below: declared explicitly because cluster.tf's
# monitor_metrics block only enables the add-on, it doesn't wire a workspace
# to it — design.md D8's mechanism note (task 5.6).
resource "azurerm_monitor_data_collection_endpoint" "prometheus" {
  name                = "${var.cluster_name}-dce"
  resource_group_name = azurerm_resource_group.cluster.name
  location            = azurerm_resource_group.cluster.location
  kind                = "Linux"
  tags                = var.tags
}

resource "azurerm_monitor_data_collection_rule" "prometheus" {
  name                        = "${var.cluster_name}-dcr"
  resource_group_name         = azurerm_resource_group.cluster.name
  location                    = azurerm_resource_group.cluster.location
  kind                        = "Linux"
  data_collection_endpoint_id = azurerm_monitor_data_collection_endpoint.prometheus.id
  tags                        = var.tags

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
  # name required here — provider quirk, see design.md D8.
  name                    = "${var.cluster_name}-dcra"
  target_resource_id      = azurerm_kubernetes_cluster.this.id
  data_collection_rule_id = azurerm_monitor_data_collection_rule.prometheus.id
}
