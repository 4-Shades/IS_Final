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
  description = "Public subnet IDs for the ECS tasks, which get public IPs for outbound access."
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnet IDs for the public Host Application Load Balancer."
}

variable "ecs_security_group_id" {
  type        = string
  description = "Security group attached to the ECS tasks. It must allow egress to Ollama and required APIs."
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

variable "llm_provider" {
  type        = string
  description = "LLM backend for the Stay and Activities agents: openai (cloud default) or ollama."
  default     = "openai"

  validation {
    condition     = contains(["openai", "ollama"], var.llm_provider)
    error_message = "llm_provider must be openai or ollama."
  }
}

variable "openai_model" {
  type    = string
  default = "gpt-4o-mini"
}

variable "openai_api_key_parameter_arn" {
  type        = string
  description = "ARN of the SSM SecureString parameter holding the OpenAI API key (foundation output openai_api_key_parameter_arn)."
  default     = ""
}

variable "ollama_base_url" {
  type        = string
  description = "Ollama URL reachable from the ECS tasks. Only used when llm_provider = ollama."
  default     = ""
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

variable "use_fargate_spot" {
  type        = bool
  description = "Run tasks on Fargate Spot (about 70% cheaper; AWS may interrupt tasks with a 2-minute warning)."
  default     = true
}

variable "schedule_enabled" {
  type        = bool
  description = "Scale every service to zero outside the active window. Tasks and their public IPs only exist while running."
  default     = true
}

variable "schedule_timezone" {
  type        = string
  description = "IANA time zone for the start and stop schedules."
  default     = "Asia/Manila"
}

variable "schedule_start_cron" {
  type        = string
  description = "When services scale up to desired_count (Application Auto Scaling cron format)."
  default     = "cron(0 8 * * ? *)"
}

variable "schedule_stop_cron" {
  type        = string
  description = "When services scale down to zero (Application Auto Scaling cron format)."
  default     = "cron(0 22 * * ? *)"
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
