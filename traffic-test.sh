#!/bin/bash
# Usage: ./traffic-test.sh [REQUESTS]  - shows which environment answered
N=${1:-20}
DNS=$(aws elbv2 describe-load-balancers --names bg-alb --region us-east-2 --query 'LoadBalancers[0].DNSName' --output text)
echo "ALB: http://$DNS  ($N requests)"
for i in $(seq 1 $N); do
  curl -s -D - -o /dev/null "http://$DNS/" | tr -d '\r' | grep -i '^x-environment'
done | sort | uniq -c
