#!/bin/bash
# Usage: ./switch-traffic.sh BLUE_WEIGHT GREEN_WEIGHT   e.g. ./switch-traffic.sh 90 10
set -uo pipefail
REGION=us-east-2
BLUE_W=${1:?usage: $0 BLUE_WEIGHT GREEN_WEIGHT}
GREEN_W=${2:?usage: $0 BLUE_WEIGHT GREEN_WEIGHT}

ALB_ARN=$(aws elbv2 describe-load-balancers --names bg-alb --region $REGION --query 'LoadBalancers[0].LoadBalancerArn' --output text)
BLUE=$(aws elbv2 describe-target-groups --names bg-blue-tg --region $REGION --query 'TargetGroups[0].TargetGroupArn' --output text)
GREEN=$(aws elbv2 describe-target-groups --names bg-green-tg --region $REGION --query 'TargetGroups[0].TargetGroupArn' --output text)
LISTENER=$(aws elbv2 describe-listeners --load-balancer-arn "$ALB_ARN" --region $REGION --query 'Listeners[?Port==`80`].ListenerArn | [0]' --output text)

check_healthy() {
  local bad
  bad=$(aws elbv2 describe-target-health --target-group-arn "$2" --region $REGION --query 'length(TargetHealthDescriptions[?TargetHealth.State!=`healthy`])' --output text)
  if [ "$bad" != "0" ]; then echo "ABORT: $1 has $bad non-healthy target(s). No change made."; exit 1; fi
  echo "$1 targets healthy"
}

if [ "${SKIP_HEALTH_CHECK:-0}" != "1" ]; then
  if [ "$BLUE_W" -gt 0 ]; then check_healthy blue "$BLUE"; fi
  if [ "$GREEN_W" -gt 0 ]; then check_healthy green "$GREEN"; fi
fi

cat > /tmp/actions.json <<EOT
[{"Type":"forward","ForwardConfig":{"TargetGroups":[
 {"TargetGroupArn":"$BLUE","Weight":$BLUE_W},
 {"TargetGroupArn":"$GREEN","Weight":$GREEN_W}]}}]
EOT

aws elbv2 modify-listener --listener-arn "$LISTENER" --region $REGION --default-actions file:///tmp/actions.json > /dev/null \
  && echo "$(date -u +%FT%TZ) traffic set: blue=$BLUE_W green=$GREEN_W" | tee -a ~/bg-scripts/switch.log
