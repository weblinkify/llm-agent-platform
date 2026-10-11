data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {
  length  = 5
  special = false
  upper   = false
}

resource "random_password" "postgres" {
  length  = 32
  special = false
}

resource "random_password" "jwt" {
  length  = 48
  special = false
}

locals {
  prefix   = "${var.name}-${random_string.suffix.result}"
  compact  = "${var.name}${random_string.suffix.result}"
  db_name  = "telco_ai"
  database = "postgresql://telcoadmin:${random_password.postgres.result}@${azurerm_postgresql_flexible_server.db.fqdn}:5432/${local.db_name}?sslmode=require"
}

resource "azurerm_resource_group" "rg" {
  name     = "rg-${local.prefix}"
  location = var.location
  tags     = var.tags
}

resource "azurerm_log_analytics_workspace" "logs" {
  name                = "log-${local.prefix}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

# ---------------------------------------------------------------- Registry
resource "azurerm_container_registry" "acr" {
  name                = "acr${local.compact}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "Basic"
  admin_enabled       = false
  tags                = var.tags
}

resource "azurerm_user_assigned_identity" "apps" {
  name                = "id-${local.prefix}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = var.tags
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
}

# ---------------------------------------------------------------- Secrets
resource "azurerm_key_vault" "kv" {
  name                       = "kv-${local.compact}"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  purge_protection_enabled   = true
  soft_delete_retention_days = 7
  tags                       = var.tags
}

resource "azurerm_role_assignment" "kv_admin" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "kv_apps" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
}

resource "azurerm_key_vault_secret" "database_url" {
  name         = "database-url"
  value        = local.database
  key_vault_id = azurerm_key_vault.kv.id
  depends_on   = [azurerm_role_assignment.kv_admin]
}

resource "azurerm_key_vault_secret" "jwt" {
  name         = "jwt-secret"
  value        = random_password.jwt.result
  key_vault_id = azurerm_key_vault.kv.id
  depends_on   = [azurerm_role_assignment.kv_admin]
}

# Set the value out of band: az keyvault secret set --name azure-openai-api-key ...
resource "azurerm_key_vault_secret" "llm_key" {
  name         = "azure-openai-api-key"
  value        = "set-me"
  key_vault_id = azurerm_key_vault.kv.id
  depends_on   = [azurerm_role_assignment.kv_admin]

  lifecycle {
    ignore_changes = [value]
  }
}

# ---------------------------------------------------------------- Database
resource "azurerm_postgresql_flexible_server" "db" {
  name                          = "psql-${local.prefix}"
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  version                       = "16"
  sku_name                      = var.postgres_sku
  storage_mb                    = 32768
  administrator_login           = "telcoadmin"
  administrator_password        = random_password.postgres.result
  public_network_access_enabled = true
  zone                          = "1"
  tags                          = var.tags
}

resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.db.id
  value     = "VECTOR"
}

resource "azurerm_postgresql_flexible_server_database" "app" {
  name      = local.db_name
  server_id = azurerm_postgresql_flexible_server.db.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# Allows Azure services (Container Apps) to connect. Use VNet integration for production.
resource "azurerm_postgresql_flexible_server_firewall_rule" "azure" {
  name             = "allow-azure-services"
  server_id        = azurerm_postgresql_flexible_server.db.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# ---------------------------------------------------------------- Container Apps
resource "azurerm_container_app_environment" "env" {
  name                       = "cae-${local.prefix}"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.logs.id
  tags                       = var.tags
}

locals {
  common_env = {
    LLM_PROVIDER                 = var.llm_provider
    AZURE_OPENAI_ENDPOINT        = var.azure_openai_endpoint
    AZURE_OPENAI_CHAT_DEPLOYMENT = var.azure_openai_chat_deployment
    APP_ENV                      = "production"
  }
  secrets = {
    "database-url"         = azurerm_key_vault_secret.database_url.versionless_id
    "jwt-secret"           = azurerm_key_vault_secret.jwt.versionless_id
    "azure-openai-api-key" = azurerm_key_vault_secret.llm_key.versionless_id
  }
  secret_env = {
    DATABASE_URL         = "database-url"
    JWT_SECRET           = "jwt-secret"
    AZURE_OPENAI_API_KEY = "azure-openai-api-key"
  }
  apps = {
    mcp = {
      image   = "telco-ai-api"
      command = ["telco-mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8001"]
      port    = 8001
      public  = false
      env     = { OTEL_SERVICE_NAME = "telco-mcp-server" }
    }
    api = {
      image   = "telco-ai-api"
      command = null
      port    = 8000
      public  = true
      env     = { MCP_SERVER_URL = "http://ca-mcp-${local.prefix}/mcp", DEMO_MODE = "false" }
    }
  }
}

resource "azurerm_container_app" "app" {
  for_each                     = local.apps
  name                         = "ca-${each.key}-${local.prefix}"
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  registry {
    server   = azurerm_container_registry.acr.login_server
    identity = azurerm_user_assigned_identity.apps.id
  }

  dynamic "secret" {
    for_each = local.secrets
    content {
      name                = secret.key
      key_vault_secret_id = secret.value
      identity            = azurerm_user_assigned_identity.apps.id
    }
  }

  ingress {
    external_enabled = each.value.public
    target_port      = each.value.port
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 1
    max_replicas = 5

    container {
      name    = each.key
      image   = "${azurerm_container_registry.acr.login_server}/${each.value.image}:${var.image_tag}"
      command = each.value.command
      cpu     = 0.5
      memory  = "1Gi"

      dynamic "env" {
        for_each = merge(local.common_env, each.value.env)
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.secret_env
        content {
          name        = env.key
          secret_name = env.value
        }
      }

      liveness_probe {
        transport = "TCP"
        port      = each.value.port
      }
    }

    http_scale_rule {
      name                = "http"
      concurrent_requests = "50"
    }
  }

  depends_on = [azurerm_role_assignment.acr_pull, azurerm_role_assignment.kv_apps]
}
