output "api_url" {
  description = "Public URL of the API."
  value       = "https://${azurerm_container_app.app["api"].ingress[0].fqdn}"
}

output "acr_login_server" {
  description = "Push images here: <server>/telco-ai-api:<tag>."
  value       = azurerm_container_registry.acr.login_server
}

output "key_vault_name" {
  description = "Key Vault holding DATABASE_URL, JWT_SECRET and the LLM key."
  value       = azurerm_key_vault.kv.name
}

output "resource_group" {
  value = azurerm_resource_group.rg.name
}
