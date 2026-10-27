# Blue-Green Deployment Strategy on AWS

## 1. Project Overview

This project demonstrates a Blue-Green deployment strategy for a web application hosted on Amazon EC2 instances behind an AWS Application Load Balancer (ALB).

The goal is to improve deployment safety by maintaining separate Blue and Green environments, validating target health, shifting traffic between environments, monitoring application errors, and providing a rollback procedure when a deployment fails.

The project uses Amazon EC2, an Application Load Balancer, weighted target groups, AWS CLI, Bash automation scripts, Amazon CloudWatch alarms, Amazon SNS notifications, and a Lambda function tested for rollback logic.

The project demonstrates:
- Weighted traffic shifting between Blue and Green environments.
- Application traffic testing using response headers.
- Simulated HTTP 500 errors.
- Manual rollback to the Blue environment.
- Application recovery and post-rollback validation.
- CloudWatch monitoring and SNS alarm notifications.
- Successful manual testing of Lambda rollback logic.

**Important limitation:** The Lambda rollback logic was successfully tested using a manual test event. End-to-end automatic rollback initiated by an actual CloudWatch alarm transition has not yet been verified.

## 2. Architecture

The project consists of the following components:

- **Blue environment:** The original application environment and intended rollback destination.
- **Green environment:** The alternate environment used to validate deployments and receive traffic.
- **Application Load Balancer:** Distributes incoming HTTP requests between Blue and Green.
- **Blue target group:** `bg-blue-tg`
- **Green target group:** `bg-green-tg`
- **ALB:** `bg-alb`
- **Amazon CloudWatch:** Monitors target health, HTTP 5xx errors, and response latency.
- **Amazon SNS:** Sends alarm notifications through the `bg-deploy-alerts` topic.
- **AWS Lambda:** `bg-auto-rollback`, tested manually to validate rollback logic.

The ALB listener uses weighted forwarding to control the distribution of traffic between the two target groups.

The deployment scripts allow traffic weights to be changed without rebuilding the application. Health checks are performed before traffic is shifted to an environment with a non-zero weight, unless the health-check bypass is explicitly enabled.

### Architecture flow

```text
Users
  |
  v
Application Load Balancer (bg-alb)
  |
  +---------------------+
  |                     |
  v                     v
Blue Target Group     Green Target Group
(bg-blue-tg)          (bg-green-tg)
  |                     |
  v                     v
Blue EC2 instances    Green EC2 instances

CloudWatch Alarms
  |
  v
Amazon SNS Notifications

Lambda (bg-auto-rollback)
  |
  v
Rollback logic tested manually
  |
  v
Blue 100% / Green 0%
```

The diagram represents the project components and the tested rollback logic. It does not imply that automatic CloudWatch-to-Lambda rollback has been verified end to end.

## 3. Repository Contents

| File | Description |
|---|---|
| `README.md` | Project documentation, test results, and operational procedures. |
| `switch-traffic.sh` | Updates ALB listener weights between Blue and Green and checks target health by default. |
| `traffic-test.sh` | Sends requests through the ALB and counts responses using the `X-Environment` header. |
| `rollback.sh` | Returns traffic to Blue by configuring Blue to 100% and Green to 0%. |
| `switch.log` | Records successful traffic-switching operations and timestamps. |

The Lambda function is deployed in AWS as `bg-auto-rollback`. Its successful manual test is documented in this README; the Lambda source code and deployment configuration are not listed as files in this repository.

## 4. Prerequisites

Before running the scripts, ensure that:

- AWS CLI is installed and configured.
- The AWS identity has permission to describe load balancers, listeners, and target groups and to modify the ALB listener.
- Blue and Green EC2 instances and target groups have been created.
- The ALB listener is configured on HTTP port 80.
- Both target groups are registered with the ALB.
- The scripts are executable.
- The application returns an `X-Environment` response header identifying the environment serving the request.

The project resources are deployed in the `us-east-2` (Ohio) AWS region.

Navigate to the scripts directory:

```bash
cd ~/bg-scripts
```

If necessary, make the scripts executable:

```bash
chmod +x switch-traffic.sh traffic-test.sh rollback.sh
```

## 5. Traffic Switching

The `switch-traffic.sh` script accepts two arguments: the Blue traffic weight and the Green traffic weight.

### Examples

Send approximately 90% of traffic to Blue and 10% to Green:

```bash
./switch-traffic.sh 90 10
```

Split traffic between the environments:

```bash
./switch-traffic.sh 50 50
```

Send all traffic to Green:

```bash
./switch-traffic.sh 0 100
```

Return all traffic to Blue:

```bash
./switch-traffic.sh 100 0
```

The script retrieves the ALB, target-group, and listener ARNs using the AWS CLI.

Before changing the listener, the script checks the health of each target group assigned a non-zero traffic weight. If a target is not healthy, the script aborts the change unless the health-check bypass is explicitly enabled.

After a successful listener update, the configured traffic weights and UTC timestamp are appended to `switch.log`.

The configured weights represent the intended distribution. Actual request counts can differ because weighted routing is probabilistic.

## 6. Validation and Traffic Test Results

Traffic was tested by sending HTTP requests through the ALB and counting responses based on the `X-Environment` response header.

### Recorded test results

| Configuration | Requests | Blue responses | Green responses | Observation |
|---|---:|---:|---:|---|
| 90/10 | 200 | 184 | 16 | Both environments received traffic. |
| 50/50 | 40 | 26 | 14 | Both environments received traffic. |
| 100% Green | 20 | 0 | 20 | All sampled requests reached Green. |
| Rollback to 100% Blue | 20 | 20 | 0 | All sampled requests reached Blue. |

### Verification of the 90/10 configuration

The ALB listener was inspected using the AWS CLI and confirmed to have:

- Blue target group weight: `90`
- Green target group weight: `10`

Both target groups reported a healthy target, and target-group stickiness was disabled.

The 200-request test returned 184 Blue responses and 16 Green responses. This is an observed split of 92% Blue and 8% Green, demonstrating that both environments received traffic under the 90/10 configuration.

An earlier 90/10 test returned 40 Blue responses and no Green responses across 40 requests. That result was not treated as proof of a successful 90/10 distribution. The later 200-request test confirmed that requests reached both target groups.

An earlier 50/50 test recorded 29 Blue responses and 11 Green responses across 40 requests. This was a separate run from the 26/14 result shown in the table.

### Repeat the traffic test

Run:

```bash
./traffic-test.sh 200
```

The script queries the ALB endpoint and counts responses according to the environment header returned by the application.

These results demonstrate that the listener configuration can be changed and that requests can reach both environments under different weighted configurations.

## 7. Failure Simulation

A deliberate application failure was introduced on the Blue EC2 instance to test error handling and recovery.

A temporary Apache configuration rule was created to return HTTP 500 responses:

```bash
printf 'RewriteEngine On\nRewriteRule ^ - [R=500,L]\n' \
  | sudo tee /etc/httpd/conf.d/fault.conf

sudo systemctl reload httpd
```

The local application response was checked:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost/
```

The result was:

```text
500
```

Requests through the ALB also showed HTTP 500 errors during the failure test.

This simulated a faulty application response and provided a practical test of error monitoring and the recovery procedure.

**Note:** The failure simulation deliberately modified the Blue web server. The temporary rule had to be removed separately to restore the application.

## 8. Manual Rollback and Application Recovery

The `rollback.sh` script was used to return traffic to Blue.

Run the script from the deployment scripts directory:

```bash
cd ~/bg-scripts
./rollback.sh
```

The script invokes the traffic-switching script with Blue set to 100% and Green set to 0%. It sets `SKIP_HEALTH_CHECK=1` to bypass the target health gate so that the listener configuration can be switched even if Blue is unhealthy.

This bypass should be used carefully: redirecting traffic to an unhealthy Blue environment can result in application errors.

Changing the listener does not repair an application failure, so the application must be recovered separately.

### Restore the Blue application

Connect to the Blue EC2 instance and remove the temporary fault configuration:

```bash
sudo rm -f /etc/httpd/conf.d/fault.conf
sudo systemctl reload httpd
```

Verify the local response:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost/
```

The response returned HTTP 200 after the temporary fault rule was removed and Apache was reloaded.

Exit the SSH session and test the ALB again:

```bash
cd ~/bg-scripts
./traffic-test.sh 20
```

The post-rollback test returned 20 Blue responses out of 20 requests.

An earlier recovery test also recorded 40 HTTP 200 responses after rollback. One recorded rollback execution took approximately 7.6 seconds.

These tests demonstrate that the manual rollback procedure restored traffic routing to Blue and that the application returned successful responses after the fault was removed.

## 9. CloudWatch Monitoring and SNS Notifications

CloudWatch alarms were configured in the `us-east-2` region to monitor application and target-group health.

| Alarm | Purpose | Configured threshold |
|---|---|---|
| `bg-green-unhealthy-hosts` | Detects unhealthy Green targets. | At least 1 unhealthy target for 2 datapoints within 2 minutes. |
| `bg-green-5xx` | Detects target HTTP 5xx errors. | At least 5 target 5xx responses in 1 datapoint within 1 minute. |
| `bg-alb-high-latency` | Detects elevated target response latency. | Response time greater than 1 second for 3 datapoints within 3 minutes. |
| `bg-blue-unhealthy-hosts` | Detects unhealthy Blue targets. | At least 1 unhealthy target for 2 datapoints within 2 minutes. |

During testing, the Green unhealthy-host and Green 5xx alarms were observed in the `ALARM` state. The high-latency and Blue unhealthy-host alarms were observed in the `OK` state at the time checked. Alarm states can change as metrics change.

### SNS notification verification

The `bg-green-5xx` alarm was configured to send a notification to the SNS topic:

```text
bg-deploy-alerts
```

The alarm history recorded successful execution of the SNS notification action on 27 October 2026 at 13:14:54 UTC.

This verifies that the CloudWatch alarm notification action executed. An SNS notification is separate from a rollback action and does not, by itself, demonstrate that traffic was automatically redirected.

## 10. Lambda Rollback Logic Test

A Lambda function named `bg-auto-rollback` was configured as part of the rollback automation work.

The Lambda rollback logic was tested successfully using a manual test event simulating an alarm transition.

The test event contained the following information:

```json
{
  "AlarmName": "bg-green-5xx",
  "NewStateValue": "ALARM",
  "OldStateValue": "OK",
  "NewStateReason": "Controlled test of automatic rollback",
  "Region": "US East (Ohio)"
}
```

The successful test produced the following log message:

```text
AUTOMATIC ROLLBACK SUCCESS: Blue=100%, Green=0%
```

The test demonstrates that the Lambda rollback logic executed successfully for the manually supplied event and reported the intended final traffic configuration.

### What this test proves

- The Lambda function executed for the manual test event.
- The rollback logic reported successful completion.
- The intended final routing was Blue at 100% and Green at 0%.

### What this test does not yet prove

- That a real CloudWatch alarm transition automatically invoked the Lambda function.
- That an actual alarm-triggered invocation completed the rollback end to end.
- That rollback will always succeed if the Blue target group or application is unhealthy.

**Current status:** Lambda rollback logic tested successfully. Automatic CloudWatch-triggered rollback has not yet been verified end to end.

To complete that verification, a real alarm transition must be correlated with the Lambda invocation in CloudWatch Logs and evidence of the resulting ALB listener configuration.

## 11. Manual Rollback Runbook

If Green fails validation or begins producing unacceptable errors, use the following procedure.

1. Inspect target health in the EC2 console or using the AWS CLI.
2. Review the relevant CloudWatch alarms and application logs.
3. Run the rollback script:

   ```bash
   cd ~/bg-scripts
   ./rollback.sh
   ```

4. Verify the listener weights are Blue `100` and Green `0`.
5. Repair the faulty application or server separately if necessary.
6. Test the ALB endpoint:

   ```bash
   ./traffic-test.sh 20
   ```

7. Confirm that requests reach Blue and that the application returns successful HTTP responses.
8. Investigate and validate Green before attempting another deployment.

The rollback script changes the traffic configuration; it does not repair a failed application or guarantee that Blue is healthy. Always verify application health after rollback.

## 12. Evidence and Screenshots

The following screenshots are recommended to document the implementation and test results.

| Screenshot | Evidence |
|---|---|
| ALB listener configuration | Shows the weighted forwarding rules for Blue and Green. |
| Blue target-group health | Shows registered Blue targets and their health. |
| Green target-group health | Shows registered Green targets and their health. |
| Weighted traffic test output | Shows requests reaching Blue and Green under a configured split. |
| Manual rollback output | Shows the rollback script execution. |
| Final listener routing | Shows Blue at 100% and Green at 0%. |
| Failure simulation | Shows the HTTP 500 response during testing. |
| Post-recovery test | Shows successful responses after the fault configuration was removed. |
| CloudWatch alarm history | Shows alarm state transitions and action history. |
| SNS notification evidence | Shows the configured topic and notification action. |
| Lambda manual test | Shows the successful test invocation and rollback result. |
| Lambda execution logs | Shows the `AUTOMATIC ROLLBACK SUCCESS` message. |

If automatic rollback is required by the assessment, also capture evidence of a real CloudWatch alarm transition, the corresponding Lambda invocation, and the resulting listener configuration. Do not present a manually supplied Lambda test event as proof of an automatic alarm-triggered rollback.

## 13. Results and Lessons Learned

The project demonstrated the following:

- Separate Blue and Green target groups behind an Application Load Balancer.
- ALB weighted forwarding with 90/10, 50/50, and 0/100 configurations.
- Verification of listener weights and target health using the AWS CLI.
- Traffic reaching both environments during the latest 90/10 and 50/50 tests.
- Full sampled traffic delivery to Green under the 0/100 configuration.
- Deliberate simulation of HTTP 500 errors.
- Manual rollback to Blue and successful application recovery.
- CloudWatch alarm monitoring and successful execution of an SNS notification action.
- Successful manual testing of the Lambda rollback logic, which reported Blue at 100% and Green at 0%.

The tests highlighted the importance of verifying actual listener configuration, inspecting target health, checking application response headers, and recording real test results rather than assuming that configured traffic weights will produce an exact split in every sample.

They also reinforced that traffic rollback and application recovery are distinct steps: redirecting requests to Blue does not repair a faulty server.

Finally, testing the Lambda rollback logic and verifying automatic CloudWatch-triggered execution are separate milestones. The first was successfully tested; the second remains unverified.

## 14. Limitations and Future Improvements

Potential improvements include:

- Verifying the complete CloudWatch-to-Lambda automatic rollback workflow with a real alarm transition.
- Recording correlated alarm history, Lambda invocation logs, and final ALB listener state.
- Adding stricter input validation to reject invalid traffic weights before changing the listener.
- Automating application smoke tests before shifting traffic to Green.
- Repeating weighted-routing tests with larger request samples.
- Recording additional latency, error-rate, and recovery-time measurements.
- Retaining screenshots and terminal output as evidence of tested configurations and results.
- Confirming that the Blue environment remains healthy before relying on it as the rollback destination.
- Adding the Lambda source code and deployment configuration to the repository if appropriate for the project requirements.

## 15. Conclusion

This project demonstrates a practical Blue-Green deployment approach using Amazon EC2, an Application Load Balancer, weighted target groups, Bash scripts, CloudWatch alarms, and SNS notifications.

Testing covered weighted traffic switching, application failure simulation, manual rollback, and post-recovery validation. The latest 90/10 test confirmed that requests reached both Blue and Green, while the failure-recovery test demonstrated that traffic could be returned to Blue and the application restored.

CloudWatch alarm notification actions were verified, and the Lambda rollback logic was successfully tested using a manual test event.

**Final status:** Manual Blue/Green traffic switching and rollback demonstrated; Lambda rollback logic tested successfully; end-to-end automatic CloudWatch-triggered rollback remains to be verified.
