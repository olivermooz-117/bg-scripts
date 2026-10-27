# Blue-Green Deployment Strategy on AWS

## 1. Project Overview

This project implements a Blue-Green deployment strategy for a web application hosted on Amazon EC2 instances behind an AWS Application Load Balancer (ALB).

The objective is to support zero-downtime deployments by maintaining separate Blue and Green environments, validating the new environment, shifting traffic between environments, and providing a rollback procedure if the new version fails.

## 2. Architecture

The deployment consists of:

- **Blue environment:** The current production environment.
- **Green environment:** The new application environment.
- **Application Load Balancer:** Distributes requests between Blue and Green target groups.
- **Target groups:** Represent the Blue and Green application instances.
- **CloudWatch:** Supports monitoring of application and infrastructure metrics.

Traffic distribution is controlled through the ALB listener configuration.

## 3. Repository Contents

| File | Purpose |
|---|---|
| `switch-traffic.sh` | Changes the traffic distribution between Blue and Green. |
| `traffic-test.sh` | Sends requests through the ALB and counts responses from each environment. |
| `rollback.sh` | Returns traffic to the Blue environment. |
| `switch.log` | Records traffic-switching operations. |

## 4. Traffic Switching

The traffic-switching script accepts the Blue and Green traffic weights as arguments.

Examples:

```bash
./switch-traffic.sh 90 10
./switch-traffic.sh 50 50
./switch-traffic.sh 0 100
```

These commands represent:

- 90% Blue and 10% Green.
- 50% Blue and 50% Green.
- 0% Blue and 100% Green.

The script reports target health and records the configured traffic distribution.

## 5. Validation and Testing

The following traffic tests were performed through the Application Load Balancer:

| Test | Observed result |
|---|---|
| 90/10 traffic distribution | 34 Blue responses and 6 Green responses across 40 requests. |
| 50/50 traffic distribution | 29 Blue responses and 11 Green responses across 40 requests. |
| 100% Green | 20 Green responses across 20 requests. |
| Rollback to Blue | 40 HTTP 200 responses after rollback. |
| Post-rollback validation | 20 Blue responses across 20 requests. |

The intermediate traffic results show that requests reached both environments. Individual request counts may differ from the configured weights because of sampling variability.

## 6. Failure Simulation and Rollback

A failure scenario was tested by configuring an EC2 web server to return HTTP 500 responses.

Requests through the ALB subsequently returned HTTP 500 during the failure test.

The rollback script was then executed:

```bash
./rollback.sh
```

The script reported that all traffic was being returned to Blue.

Subsequent tests confirmed HTTP 200 responses and showed that requests were reaching Blue.

The measured execution time for the rollback script was approximately 7.6 seconds in one test.

This demonstrates the tested rollback procedure. Automatic CloudWatch alarm-triggered rollback should only be claimed if the alarm integration has also been implemented and verified.

## 7. Traffic Testing

To test traffic distribution, run:

```bash
./traffic-test.sh 40
```

To test a smaller number of requests:

```bash
./traffic-test.sh 20
```

The script reports how many responses identify Blue and Green.

## 8. Monitoring and Health Checks

The ALB target groups provide health information about the registered instances.

CloudWatch monitoring should cover relevant metrics, including:

- Application Load Balancer HTTP 5xx responses.
- Target response errors.
- Target health.
- Request counts.
- EC2 CPU utilization.

Alarm thresholds should be selected according to the application's expected behavior.

If automatic rollback is required, the alarm-to-rollback integration must be configured, secured, and tested separately.

## 9. Rollback Procedure

If the Green environment fails validation or produces unacceptable errors:

1. Check the ALB target health and application logs.
2. Execute the rollback script:

   ```bash
   ./rollback.sh
   ```

3. Allow the ALB configuration to take effect.
4. Send requests through the ALB.
5. Verify that Blue receives traffic and returns successful responses.
6. Investigate the Green environment before attempting another deployment.

## 10. Results

The recorded tests demonstrated:

- Traffic switching between Blue and Green.
- Gradual traffic distribution.
- Requests reaching Green after a full traffic switch.
- Simulated HTTP 500 failures.
- Recovery to Blue through the rollback script.
- Successful HTTP 200 responses after rollback.

These results provide evidence of traffic management, validation, and rollback behavior.

## 11. Limitations and Future Improvements

Potential improvements include:

- Integrating CloudWatch alarms with an automated rollback mechanism.
- Automating smoke tests before production traffic is shifted.
- Capturing additional latency and error-rate measurements.
- Keeping deployment logs and test evidence as versioned artifacts.
- Adding a documented deployment and recovery runbook.

## 12. Conclusion

This project demonstrates a practical Blue-Green traffic-management approach using AWS infrastructure and shell scripts. Testing covered weighted traffic switching, failure simulation, and restoration of traffic to the Blue environment.