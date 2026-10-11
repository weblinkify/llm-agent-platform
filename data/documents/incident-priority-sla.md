---
id: DOC-001
title: Incident Priority and SLA Policy
category: sla
---
# Incident Priority and SLA Policy

This policy defines incident priorities and the response and restoration targets that the Network Operations Centre (NOC) must meet.

## Priority definitions

- **Priority 1 (P1)** — Critical. Complete loss of a core service (mobile data, voice, fiber) for more than 1,000 customers, any loss of emergency calling, or a security incident with active customer impact.
- **Priority 2 (P2)** — High. Significant degradation affecting more than 100 customers, or complete outage for a single business customer with an SLA contract.
- **Priority 3 (P3)** — Medium. Limited degradation, workaround available, or fewer than 100 customers affected.
- **Priority 4 (P4)** — Low. Cosmetic issues, questions and single-customer issues with no service loss.

## Response and restoration targets

| Priority | Acknowledge | First update | Restore service |
|---|---|---|---|
| P1 | 15 minutes | 30 minutes | 4 hours |
| P2 | 30 minutes | 1 hour | 8 hours |
| P3 | 4 hours | 1 business day | 3 business days |
| P4 | 1 business day | 3 business days | 10 business days |

A Priority 1 network incident must be acknowledged within 15 minutes and service must be restored within 4 hours. The duty manager must be paged immediately for every P1, and status updates are published to customers every 30 minutes until resolution.

## Measurement

SLA clocks start when the incident is created in the incident management system, not when the fault started. Clocks pause only while waiting for customer access to premises.
