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
  description = "CIDR ranges for the public ALB subnets."
  default     = ["10.40.0.0/20", "10.40.16.0/20"]
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "CIDR ranges for the private ECS task subnets."
  default     = ["10.40.32.0/20", "10.40.48.0/20"]
}

variable "single_nat_gateway" {
  type        = bool
  description = "Use one NAT gateway to reduce cost, or one per AZ for higher availability."
  default     = true
}

variable "log_retention_days" {
  type    = number
  default = 14
}
