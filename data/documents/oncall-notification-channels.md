---
id: DOC-028
title: On-call and Notification Channels
category: reference
---
# On-call and Notification Channels

| Team | Channel | Used for |
|---|---|---|
| L2 Mobile Core | `l2-mobile-core` | 5G, 4G, VoLTE and roaming faults |
| L2 Fixed Access | `l2-fixed-access` | Fiber and broadband faults |
| L3 Network Engineering | `l3-network` | Multi-site faults, vendor escalations |
| Customer Support | `support-team` | Customer-affecting incidents, callbacks |
| Duty Manager | `duty-manager` | All P1 incidents |

Notifications about customer-affecting incidents go to `support-team`. Notifications must include the incident ID and must not contain customer personal data.
