variable "aws_region" {
  type        = string
  description = "AWS region for the ECS deployment."
  default     = "us-east-1"
}

variable "name_prefix" {
  type        = string
  description = "Prefix applied to AWS resource names."
  default     = "travel"
}

variable "vpc_id" {
  type        = string
  description = "VPC containing the ECS services and Cloud Map namespace."
}

variable "task_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for the ECS tasks."
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnet IDs for the public Host Application Load Balancer."
}

variable "ecs_security_group_id" {
  type        = string
  description = "Security group attached to the ECS tasks. It must allow egress to Ollama and required APIs."
}

variable "host_security_group_id" {
  type        = string
  description = "Security group used by the host Lambda or ECS service. It is allowed to call the agents."
}

variable "alb_security_group_id" {
  type        = string
  description = "Security group attached to the public Host Application Load Balancer."
}

variable "execution_role_arn" {
  type        = string
  description = "ECS task execution role ARN with ECR pull and CloudWatch Logs permissions."
}

variable "task_role_arn" {
  type        = string
  description = "ECS task role ARN for the application containers."
}

variable "image_tag" {
  type        = string
  description = "Tag of the agent image to deploy."
  default     = "latest"
}

variable "ollama_base_url" {
  type        = string
  description = "Private or authenticated Ollama URL reachable from the ECS task subnets."
}

variable "flight_service_url" {
  type        = string
  description = "HTTPS URL of the existing Railway Flight agent."
}

variable "ollama_model" {
  type    = string
  default = "llama3.2:3b"
}

variable "ollama_embedding_model" {
  type    = string
  default = "embeddinggemma"
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "container_cpu" {
  type    = number
  default = 512
}

variable "container_memory" {
  type    = number
  default = 1024
}

variable "log_retention_days" {
  type    = number
  default = 14
}
