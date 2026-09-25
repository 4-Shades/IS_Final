# AWS ECS specialist agents

This module deploys the Stay and Activities FastAPI services to ECS Fargate using `Dockerfile.agent`.

## Prerequisites

- Terraform >= 1.6
- AWS credentials configured for the target account
- An existing VPC with private subnets
- An ECS task execution role with ECR pull and CloudWatch Logs permissions
- An ECS task role for the application
- Security groups for the host and ECS tasks
- Network egress from the task subnets to the Railway Ollama endpoint

The host must be able to resolve and reach the private Cloud Map namespace. If the host runs in Lambda, attach it to the same VPC and configure its security group and DNS support accordingly.

## Deploy

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
terraform init
terraform apply -var-file=terraform.tfvars
```

Build and push one image for each repository shown by Terraform:

```bash
docker build -f ../../../Dockerfile.agent -t travel-stay-agent:latest ../../../
docker tag travel-stay-agent:latest <stay-ecr-repository-url>:<image-tag>
docker push <stay-ecr-repository-url>:<image-tag>

docker tag travel-stay-agent:latest <activities-ecr-repository-url>:<image-tag>
docker push <activities-ecr-repository-url>:<image-tag>
```

Set `image_tag` to the pushed tag before applying. The same image is used for both services; `APP_MODULE` selects the service at runtime.

## Host configuration

Use the Terraform outputs in the host service:

```env
STAY_SERVICE_URL=http://stay.travel.internal:8002
ACTIVITIES_SERVICE_URL=http://activities.travel.internal:8003
```

Keep `OLLAMA_BASE_URL` set to the Railway Ollama endpoint. Do not expose the Cloud Map names publicly.

## Network requirements

- ECS task security group: allow outbound TCP 443 to the Railway Ollama endpoint and required APIs.
- ECS task security group: allow inbound TCP 8002-8003 from the host security group only.
- Host Lambda security group: allow outbound TCP 8002-8003 to the ECS task security group.
- Private subnets need NAT or suitable VPC endpoints to pull images and send logs.

## Destroy

```bash
terraform destroy -var-file=terraform.tfvars
```

ECR repositories are protected from accidental deletion with `force_delete = false`.
