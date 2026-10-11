---
id: DOC-010
title: Fixed Broadband Troubleshooting
category: runbook
---
# Fixed Broadband Troubleshooting

## Slow speed or packet loss

1. Check for active incidents in the customer's city that affect FIB-100 or FIB-1000.
2. Ask the customer to test with a wired connection to rule out Wi-Fi interference.
3. Run a line test from the access management portal. Optical power below -27 dBm indicates a fiber fault.
4. Restart the optical network terminal (ONT).
5. If the line test fails, book a technician visit through L2 Fixed Access.

## No connection

If the ONT LOS light is red, the fiber is broken. Check for incidents in the area before booking a technician, because known backbone faults are handled by the NOC.
