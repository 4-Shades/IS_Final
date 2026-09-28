variable "aws_region" {
  type        = string
  description = "AWS region for the foundation resources."
  default     = "us-east-1"
}

variable "name_prefix" {
  type        = string
  description = "Prefix applied to AWS resource names."
  default     = "travel"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR range for the travel planner VPC."
  default     = "10.40.0.0/16"
}

variable "availability_zones" {
  type        = list(string)
  description = "At least two Availability Zones in the selected region."
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "Provide at least two Availability Zones."
  }
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "CIDR ranges for the public subnets used by the ALB and ECS tasks."
  default     = ["10.40.0.0/20", "10.40.16.0/20"]
}

variable "openai_api_key_parameter_name" {
  type        = string
  description = "SSM SecureString parameter holding the OpenAI API key. Create it with the AWS CLI so the key never enters Terraform state."
  default     = "/travel/openai-api-key"
}

variable "github_repository" {
  type        = string
  description = "GitHub repository (owner/name) allowed to push agent images to ECR from Actions on main."
  default     = "4-Shades/IS_Final"
}

variable "create_github_oidc_provider" {
  type        = bool
  description = "Create the account's GitHub Actions OIDC provider. Set false if the account already has one; only one is allowed per account."
  default     = true
}

variable "host_api_key_parameter_name" {
  type        = string
  description = "SSM SecureString parameter holding the key clients must send in X-API-Key to the public Host API."
  default     = "/travel/host-api-key"
}

variable "otel_headers_parameter_name" {
  type        = string
  description = "SSM SecureString parameter holding OTEL_EXPORTER_OTLP_HEADERS for Grafana Cloud (Authorization=Basic ...)."
  default     = "/travel/otel-otlp-headers"
}

variable "alb_log_retention_days" {
  type        = number
  description = "Days to keep ALB access logs in S3."
  default     = 30
}

variable "log_retention_days" {
  type    = number
  default = 14
}
