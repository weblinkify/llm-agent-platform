variable "name" {
  description = "Short name used as a prefix for all resources."
  type        = string
  default     = "telcoai"
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "westeurope"
}

variable "image_tag" {
  description = "Container image tag to deploy (e.g. a git SHA)."
  type        = string
  default     = "latest"
}

variable "llm_provider" {
  description = "mock, openai, azure_openai or anthropic."
  type        = string
  default     = "azure_openai"
}

variable "azure_openai_endpoint" {
  description = "Azure OpenAI endpoint (when llm_provider = azure_openai)."
  type        = string
  default     = ""
}

variable "azure_openai_chat_deployment" {
  description = "Azure OpenAI chat deployment name."
  type        = string
  default     = ""
}

variable "postgres_sku" {
  description = "PostgreSQL Flexible Server SKU."
  type        = string
  default     = "B_Standard_B1ms"
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default = {
    project = "telco-ai-operations-assistant"
    managed = "terraform"
  }
}
