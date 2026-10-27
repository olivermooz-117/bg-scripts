
import json
import os
import boto3

REGION = os.environ.get("AWS_REGION", "us-east-2")
ALARM_NAME = "bg-green-5xx"
ALB_NAME = "bg-alb"
BLUE_TG_NAME = "bg-blue-tg"
GREEN_TG_NAME = "bg-green-tg"

elbv2 = boto3.client("elbv2", region_name=REGION)


def lambda_handler(event, context):
    print("Received event:", json.dumps(event, default=str))

    # Accept direct CloudWatch events and SNS notifications.
    alarms = []

    if event.get("AlarmName"):
        alarms.append(event)
    else:
        for record in event.get("Records", []):
            if record.get("EventSource") != "aws:sns":
                continue

            message = record.get("Sns", {}).get("Message", "")

            try:
                alarms.append(json.loads(message))
            except (TypeError, json.JSONDecodeError):
                print("Ignoring non-JSON SNS message.")

    # Only act on the configured Green failure alarm.
    matched = any(
        alarm.get("AlarmName") == ALARM_NAME
        and alarm.get("NewStateValue") == "ALARM"
        for alarm in alarms
    )

    if not matched:
        print("No matching Green failure alarm; no traffic changes made.")
        return {
            "statusCode": 200,
            "body": "Ignored: no matching alarm in ALARM state"
        }

    # Find the load balancer.
    lbs = elbv2.describe_load_balancers(
        Names=[ALB_NAME]
    )["LoadBalancers"]

    if not lbs:
        raise RuntimeError("ALB not found")

    alb_arn = lbs[0]["LoadBalancerArn"]

    # Find and verify a target group.
    def target_group_arn(name):
        groups = elbv2.describe_target_groups(
            Names=[name]
        )["TargetGroups"]

        if not groups:
            raise RuntimeError(f"Target group not found: {name}")

        if alb_arn not in groups[0].get("LoadBalancerArns", []):
            raise RuntimeError(
                f"Target group {name} is not associated with {ALB_NAME}"
            )

        return groups[0]["TargetGroupArn"]

    blue_arn = target_group_arn(BLUE_TG_NAME)
    green_arn = target_group_arn(GREEN_TG_NAME)

    # Roll back only if Blue has registered, healthy targets.
    targets = elbv2.describe_target_health(
        TargetGroupArn=blue_arn
    )["TargetHealthDescriptions"]

    if not targets or any(
        target["TargetHealth"]["State"] != "healthy"
        for target in targets
    ):
        raise RuntimeError(
            "Rollback blocked: Blue has no registered targets "
            "or at least one target is unhealthy."
        )

    # Find the HTTP listener.
    listeners = elbv2.describe_listeners(
        LoadBalancerArn=alb_arn
    )["Listeners"]

    http_listeners = [
        listener for listener in listeners
        if listener["Port"] == 80
    ]

    if not http_listeners:
        raise RuntimeError("HTTP listener on port 80 not found")

    # Send 100% of traffic to Blue.
    elbv2.modify_listener(
        ListenerArn=http_listeners[0]["ListenerArn"],
        DefaultActions=[{
            "Type": "forward",
            "ForwardConfig": {
                "TargetGroups": [
                    {"TargetGroupArn": blue_arn, "Weight": 100},
                    {"TargetGroupArn": green_arn, "Weight": 0}
                ]
            }
        }]
    )

    print("AUTOMATIC ROLLBACK SUCCESS: Blue=100%, Green=0%")

    return {
        "statusCode": 200,
        "body": "Rollback completed: traffic restored to Blue"
    }
