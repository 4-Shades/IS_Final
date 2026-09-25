output "stay_service_url" {
  description = "Private URL for the Stay agent."
  value       = "http://stay.${aws_service_discovery_private_dns_namespace.agents.name}:8002"
}

output "activities_service_url" {
  description = "Private URL for the Activities agent."
  value       = "http://activities.${aws_service_discovery_private_dns_namespace.agents.name}:8003"
}

output "stay_ecr_repository_url" {
  value = aws_ecr_repository.agent["stay"].repository_url
}

output "activities_ecr_repository_url" {
  value = aws_ecr_repository.agent["activities"].repository_url
}

output "cloud_map_namespace" {
  value = aws_service_discovery_private_dns_namespace.agents.name
}
