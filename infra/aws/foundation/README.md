# AWS foundation

This module creates the AWS resources required before deploying the Host, Stay, and Activities ECS services:

- VPC with public and private subnets across two Availability Zones
- Internet gateway and NAT gateway routing
- ALB and ECS security groups
- ECS task execution and task IAM roles
- ECR repositories for `host`, `stay`, and `activities`

## Deploy

```bash
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

Use the outputs as inputs to `../ecs-agents`. The foundation module must be applied first because the ECS module reads the ECR repositories and IAM/network IDs it creates.

## Cost note

A NAT gateway incurs hourly and data-processing charges. `single_nat_gateway = true` is cheaper for development but less resilient. Use `false` for one NAT gateway per Availability Zone in production.

## Security note

The ALB security group allows HTTP port 80 for initial validation. Add an ACM certificate and HTTPS listener before exposing the Host API to real users. The ECS security group does not allow public inbound traffic.
