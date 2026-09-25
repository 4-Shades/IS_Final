# AWS ECS specialist agents

This module deploys the Host, Stay, and Activities FastAPI services to ECS Fargate using `Dockerfile.agent`. The Host is exposed through an internet-facing HTTP Application Load Balancer; Stay and Activities remain private through AWS Cloud Map. Create the AWS foundation module first; this module reads its existing ECR repositories, VPC, subnets, security groups, and IAM role outputs.

## Prerequisites

- Terraform >= 1.6
- AWS credentials configured for the target account
- An existing VPC with public subnets (tasks get public IPs; there is no NAT gateway)
- An ECS task execution role with ECR pull and CloudWatch Logs permissions
- An ECS task role for the application
- Security groups for the host and ECS tasks
- Network egress from the task subnets to the Railway Ollama endpoint
- Public subnets for the Host Application Load Balancer
- An ALB security group allowing inbound TCP 80

The host must be able to resolve and reach the private Cloud Map namespace. If the host runs in Lambda, attach it to the same VPC and configure its security group and DNS support accordingly.

## Deploy

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
terraform init
terraform apply -var-file=terraform.tfvars
```

Build and push the agent image to each repository shown by Terraform:

```bash
docker build -f ../../../Dockerfile.agent -t travel-stay-agent:latest ../../../
docker tag travel-stay-agent:latest <stay-ecr-repository-url>:<image-tag>
docker push <stay-ecr-repository-url>:<image-tag>

docker tag travel-stay-agent:latest <activities-ecr-repository-url>:<image-tag>
docker push <activities-ecr-repository-url>:<image-tag>

docker tag travel-stay-agent:latest <host-ecr-repository-url>:<image-tag>
docker push <host-ecr-repository-url>:<image-tag>
```

Set `image_tag` to the pushed tag before applying. The same image is used for both services; `APP_MODULE` selects the service at runtime.

## Host configuration

Use the Terraform outputs in the host service:

```env
STAY_SERVICE_URL=http://stay.travel.internal:8002
ACTIVITIES_SERVICE_URL=http://activities.travel.internal:8003
FLIGHT_SERVICE_URL=https://<railway-flight-domain>
OLLAMA_BASE_URL=https://<railway-ollama-domain>
```

The public Host API URL is returned as `host_public_url`. The initial Terraform listener is HTTP for validation only; add an ACM certificate and HTTPS listener before production use. Do not expose the Cloud Map names publicly.

## Network requirements

- ECS task security group: allow outbound TCP 443 to the Railway Ollama endpoint and required APIs.
- ECS task security group: allow inbound TCP 8002-8003 from the host security group only.
- Host Lambda security group: allow outbound TCP 8002-8003 to the ECS task security group.
- ECS Host task security group: allow outbound TCP 8002-8003 to the ECS task security group.
- Tasks run in public subnets with `assign_public_ip = true` to pull images, send logs, and reach Railway. The ECS security group allows no inbound traffic from the internet.

Security group rules are owned by `../foundation`; this module only attaches the groups.

## Cost controls

- `schedule_enabled` scales every service between `desired_count` (at `schedule_start_cron`) and zero (at `schedule_stop_cron`) in `schedule_timezone`. With no running tasks there are no task public IPv4 addresses or Fargate charges. The ALB and its public IPs keep billing; run `terraform destroy` here if the stack will sit idle for days.
- `use_fargate_spot` runs tasks on Fargate Spot. AWS can reclaim a Spot task with two minutes' notice; ECS starts a replacement automatically.
- To start the services outside the window, run `aws ecs update-service --cluster travel-agents --service <name> --desired-count 1 --region us-east-1`. The next scheduled stop scales them back down.

## Destroy

```bash
terraform destroy -var-file=terraform.tfvars
```

ECR repositories are created and protected by `../foundation`; the ECS module only reads them.
