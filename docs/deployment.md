# Deployment

## Local

```bash
docker compose up --build          # UI :3000, API :8000/docs, Jaeger :16686
```

No `.env` or API keys are needed. To use a real model, create `.env` with, for example, `LLM_PROVIDER=openai` and `OPENAI_API_KEY=...`.

## Azure (Terraform)

`infrastructure/terraform` provisions:

* Resource group and Log Analytics
* Azure Container Registry, pulled with a user-assigned managed identity
* Key Vault (RBAC mode) holding `DATABASE_URL`, `JWT_SECRET` and the LLM key, referenced by the Container Apps as secrets
* PostgreSQL Flexible Server 16 with the `VECTOR` extension allow-listed
* A Container Apps environment with an internal `mcp` app and an external `api` app (HTTP autoscaling 1–5)

```bash
cd infrastructure/terraform
terraform init && terraform apply -var llm_provider=azure_openai \
  -var azure_openai_endpoint=https://<name>.openai.azure.com \
  -var azure_openai_chat_deployment=gpt-4o-mini
az keyvault secret set --vault-name $(terraform output -raw key_vault_name) \
  --name azure-openai-api-key --value <key>
```

Then build and push the image to the ACR and run the manual **Deploy to Azure** workflow. CI validates the Terraform on every push (`fmt`, `validate`). It has not been applied as part of this repository.

## Vercel (public demo)

The demo runs the API as a Vercel Python function (`api/index.py`, `vercel.json`) in mock mode with in-memory stores. The Next.js app (`apps/frontend`) is deployed as a second project whose `API_URL` points at the API deployment.
