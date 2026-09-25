output "vpc_id" {
  description = "VPC ID for the ECS deployment."
  value       = aws_vpc.travel.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs for the Host ALB and the ECS tasks."
  value       = [for subnet in aws_subnet.public : subnet.id]
}

output "ecs_security_group_id" {
  value = aws_security_group.ecs.id
}

output "alb_security_group_id" {
  value = aws_security_group.alb.id
}

output "ecs_task_execution_role_arn" {
  value = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_role_arn" {
  value = aws_iam_role.ecs_task.arn
}

output "openai_api_key_parameter_arn" {
  value = local.openai_api_key_parameter_arn
}

output "ecr_repository_urls" {
  description = "ECR repository URLs consumed by the ECS module."
  value       = { for name, repository in aws_ecr_repository.agent : name => repository.repository_url }
}

output "ecr_repository_names" {
  value = { for name, repository in aws_ecr_repository.agent : name => repository.name }
}
