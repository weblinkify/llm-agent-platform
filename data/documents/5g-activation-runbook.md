---
id: DOC-002
title: 5G Activation Runbook
category: runbook
---
# 5G Activation Runbook

Use this runbook when a customer reports that they cannot activate or use 5G.

## Activation prerequisites

All four conditions must be true before 5G can be activated:

1. **5G-enabled plan.** The customer must subscribe to a 5G mobile plan (MOB-5G-PLUS or MOB-5G-UNLIMITED) or 5G Home Internet (FWA-5G-HOME). The Mobile 4G Basic plan (MOB-4G-BASIC) does not include 5G network access.
2. **5G-capable device.** The handset must support 5G NR on bands n78 and n28. See the 5G Device Compatibility List.
3. **5G-compatible SIM.** Legacy USIM cards (type USIM-LEGACY) do not support 5G standalone authentication. The customer needs a USIM-5G card or an ESIM-5G profile.
4. **Active account.** Accounts in SUSPENDED status cannot have new services activated.

## Troubleshooting steps

1. Look up the customer and confirm the account status is ACTIVE.
2. Check the subscribed services. If no 5G-enabled plan is present, offer an upgrade to MOB-5G-PLUS.
3. Check the SIM type. If the SIM is USIM-LEGACY, order a free SIM swap following the SIM Swap Procedure, or provision an eSIM.
4. Check the device model against the compatibility list.
5. Check for active network incidents in the customer's city that affect 5G.
6. If all prerequisites are met and there is no incident, escalate to L2 Mobile Core.

Never activate 5G on a suspended account. Do not promise 5G coverage indoors without checking the coverage map.
