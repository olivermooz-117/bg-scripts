#!/bin/bash
# Send 100% of traffic back to Blue (skips the health gate so it always works)
echo "ROLLBACK: sending all traffic to Blue"
SKIP_HEALTH_CHECK=1 ~/bg-scripts/switch-traffic.sh 100 0
