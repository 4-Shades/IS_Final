# AWS foundation

This module creates the AWS resources required before deploying the Host, Stay, and Activities ECS services:

- VPC with public subnets across two Availability Zones
- Internet gateway routing (no NAT gateway)
- ALB and ECS security groups
- ECS task execution and task IAM roles; the execution role can read the `/travel/openai-api-key` and `/travel/host-api-key` SSM parameters
- ECR repositories for `host`, `stay`, and `activities`
- A GitHub Actions OIDC provider and role (`github_actions_role_arn` output) that lets pushes to `main` push images to those repositories, and nothing else
- A private, encrypted S3 bucket for ALB access logs (`alb_logs_bucket` output), expiring logs after `alb_log_retention_days` (30)

## Deploy

```bash
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

Use the outputs as inputs to `../ecs-agents`. The foundation module must be applied first because the ECS module reads the ECR repositories and IAM/network IDs it creates.

## Cost note

There is no NAT gateway. ECS tasks run in the public subnets with public IPs and reach ECR, CloudWatch Logs, and Railway through the internet gateway. Each public IPv4 address is billed hourly, which is far cheaper than a NAT gateway.

## Security note

The ALB security group allows HTTP port 80. The Host API is protected by an API key and AWS WAF (see the root README's [Public API security](../../../README.md#public-api-security)), but traffic is unencrypted until an ACM certificate and HTTPS listener are added, which needs a domain. The ECS security group does not allow public inbound traffic, so tasks are unreachable from the internet despite having public IPs.

Only one GitHub OIDC provider can exist per AWS account. If the account already has one, set `create_github_oidc_provider = false` and the module looks it up instead.
