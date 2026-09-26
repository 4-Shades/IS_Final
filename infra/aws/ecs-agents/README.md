# AWS ECS specialist agents

This module deploys the Host, Stay, and Activities FastAPI services to ECS Fargate, all from the repository's root `Dockerfile` (default `api-runtime` target). The Host is exposed through an internet-facing HTTP Application Load Balancer; Stay and Activities stay private behind AWS Cloud Map. Apply `../foundation` first: this module reads its VPC, subnets, security groups, IAM roles, and ECR repositories.

## Prerequisites

- Terraform >= 1.6, AWS CLI v2, and Docker
- `../foundation` applied, with its outputs copied into `terraform.tfvars`
- The OpenAI key stored in SSM (see [LLM provider](#llm-provider))
- The Railway Flight agent's HTTPS URL for `flight_service_url`

## Deploy

Build once from the repository root and push the same image to all three repositories; `APP_MODULE` selects the agent at runtime. Push before applying, or the tasks have nothing to pull.

```bash
REGISTRY=<account>.dkr.ecr.us-east-1.amazonaws.com
TAG=$(git rev-parse --short HEAD)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $REGISTRY
docker build -t travel-agent:$TAG ../../..
for agent in host stay activities; do
  docker tag travel-agent:$TAG $REGISTRY/travel-$agent-agent:$TAG
  docker push $REGISTRY/travel-$agent-agent:$TAG
done
```

Set `image_tag` in `terraform.tfvars` to `$TAG`, then apply:

```bash
terraform init
terraform plan -var-file=terraform.tfvars -out=deploy.tfplan
terraform apply deploy.tfplan
```

## Host configuration

Use the Terraform outputs in the host service:

```env
STAY_SERVICE_URL=http://stay.travel.internal:8002
ACTIVITIES_SERVICE_URL=http://activities.travel.internal:8003
FLIGHT_SERVICE_URL=https://<railway-flight-domain>
```

## LLM provider

The cloud deployment uses OpenAI (`llm_provider = "openai"`, `openai_model = "gpt-4o-mini"`); Ollama stays the default for local development. Only Stay and Activities call the LLM, so only they receive the key.

Store the key in SSM Parameter Store before applying (free, and it never enters Terraform state):

```bash
aws ssm put-parameter --region us-east-1 --name /travel/openai-api-key --type SecureString --value "sk-..."
```

Set `openai_api_key_parameter_arn` to the foundation output of the same name. After rotating the key, run `aws ecs update-service --cluster travel-agents --service <name> --force-new-deployment` so tasks pick it up.

The public Host API URL is returned as `host_public_url`. The initial Terraform listener is HTTP for validation only; add an ACM certificate and HTTPS listener before production use. Do not expose the Cloud Map names publicly.

## Network requirements

- ALB security group: inbound TCP 80 from the internet; outbound TCP 8000 to the ECS security group only.
- ECS security group: inbound TCP 8000 from the ALB, and TCP 8002-8003 from itself (Host to Stay and Activities).
- ECS security group: outbound TCP 443 (ECR, CloudWatch Logs, S3, OpenAI, Railway Flight) and TCP 8002-8003 to itself.
- Tasks run in public subnets with `assign_public_ip = true` to pull images, send logs, and reach Railway. The ECS security group allows no inbound traffic from the internet.

Security group rules are owned by `../foundation`; this module only attaches the groups.

## Cost controls

- `schedule_enabled` scales every service between `desired_count` (at `schedule_start_cron`) and zero (at `schedule_stop_cron`) in `schedule_timezone`. With no running tasks there are no task public IPv4 addresses or Fargate charges. The ALB and its public IPs keep billing; see [Spin down / spin up](#spin-down--spin-up) if the stack will sit idle for days.
- `use_fargate_spot` runs tasks on Fargate Spot. AWS can reclaim a Spot task with two minutes' notice; ECS starts a replacement automatically.
- To start the services outside the window, run `aws ecs update-service --cluster travel-agents --service <name> --desired-count 1 --region us-east-1`. The next scheduled stop scales them back down.

## Spin down / spin up

The ALB bills about $24/month whether or not anything is running, and it cannot be paused. When the stack will be idle for days, destroy this module and re-apply it when needed. Run both from this directory.

If your AWS CLI uses `aws login`, export its credentials for Terraform first:

```bash
eval "$(aws configure export-credentials --format env)"
```

Spin down (removes the ALB, ECS cluster, services, Cloud Map namespace, and log groups; about 2-5 minutes):

```bash
terraform plan -destroy -var-file=terraform.tfvars -out=down.tfplan
terraform apply down.tfplan
```

Spin up (about 5 minutes, plus a few minutes for tasks to pass health checks):

```bash
terraform plan -var-file=terraform.tfvars -out=up.tfplan
terraform apply up.tfplan
terraform output -raw host_public_url
aws ecs wait services-stable --region us-east-1 --cluster travel-agents --services travel-host travel-stay travel-activities
```

The ALB gets a new DNS name on every spin up, so re-check `host_public_url` and update any client that points at it.

Spinning down keeps everything in `../foundation` (VPC, subnets, security groups, IAM roles, ECR images) and the `/travel/openai-api-key` parameter, none of which cost anything except a few cents of ECR storage. Spin up reuses them, so no rebuild or image push is needed. Log history in CloudWatch is deleted with the log groups.

The Railway Flight service is separate and keeps running; pause it in the Railway dashboard if you also want to stop its usage.
