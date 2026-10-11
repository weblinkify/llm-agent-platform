---
id: DOC-026
title: AI Operations Assistant Usage Policy
category: policy
---
# AI Operations Assistant Usage Policy

The AI Operations Assistant helps support and NOC staff search documentation, investigate customers and incidents, and prepare actions.

- The assistant may read customer, product, incident and network information according to the user's role.
- Actions that change enterprise systems, such as creating or updating incidents and sending notifications, always require approval by a human with the SUPPORT_AGENT or ADMIN role.
- Retrieved documents are treated as untrusted data. Instructions found inside documents are never followed.
- Every agent step, tool call and approval decision is recorded in the audit log.
- Personal data is masked before it is sent to the language model.
