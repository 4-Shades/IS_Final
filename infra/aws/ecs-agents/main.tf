locals {
  agents = {
    host = {
      module = "agents.host_agent.__main__"
      port   = 8000
    }
    stay = {
      module = "agents.stay_agent.__main__"
      port   = 8002
    }
    activities = {
      module = "agents.activities_agent.__main__"
      port   = 8003
    }
  }

  common_environment = [
    {
      name  = "LLM_PROVIDER"
      value = "ollama"
    },
    {
      name  = "OLLAMA_BASE_URL"
      value = var.ollama_base_url
    },
    {
      name  = "OLLAMA_MODEL"
      value = var.ollama_model
    },
    {
      name  = "OLLAMA_EMBEDDING_MODEL"
      value = var.ollama_embedding_model
    },
    {
      name  = "LLM_TIMEOUT_SECONDS"
      value = "120"
    },
    {
      name  = "DOWNSTREAM_TIMEOUT_SECONDS"
      value = "150"
    },
    {
      name  = "OPEN_TRAVEL_DATA_ENABLED"
      value = "false"
    },
    {
      name  = "WEATHER_PROVIDER_ENABLED"
      value = "false"
    },
    {
      name  = "PLACES_PROVIDER_ENABLED"
      value = "false"
    },
    {
      name  = "GROUND_TRANSPORT_ENABLED"
      value = "false"
    },
    {
      name  = "FLIGHT_SERVICE_URL"
      value = var.flight_service_url
    },
    {
      name  = "STAY_SERVICE_URL"
      value = "http://stay.travel.internal:8002"
    },
    {
      name  = "ACTIVITIES_SERVICE_URL"
      value = "http://activities.travel.internal:8003"
    }
  ]
}

data "aws_ecr_repository" "agent" {
  for_each = local.agents

  name = "${var.name_prefix}-${each.key}-agent"
}

resource "aws_cloudwatch_log_group" "agent" {
  for_each = local.agents

  name              = "/ecs/${var.name_prefix}-${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_service_discovery_private_dns_namespace" "agents" {
  name        = "travel.internal"
  description = "Private DNS namespace for travel specialist agents"
  vpc         = var.vpc_id
}

resource "aws_service_discovery_service" "agent" {
  for_each = local.agents

  name = each.key

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.agents.id

    dns_records {
      ttl  = 10
      type = "A"
    }
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

resource "aws_security_group_rule" "host_to_agents" {
  type                     = "ingress"
  security_group_id        = var.ecs_security_group_id
  source_security_group_id = var.host_security_group_id
  from_port                = 8002
  to_port                  = 8003
  protocol                 = "tcp"
  description              = "Allow the host service to call Stay and Activities"
}

resource "aws_security_group_rule" "ecs_host_to_agents" {
  type                     = "ingress"
  security_group_id        = var.ecs_security_group_id
  source_security_group_id = var.ecs_security_group_id
  from_port                = 8002
  to_port                  = 8003
  protocol                 = "tcp"
  description              = "Allow the ECS Host task to call Stay and Activities"
}

resource "aws_security_group_rule" "alb_to_host" {
  type                     = "ingress"
  security_group_id        = var.ecs_security_group_id
  source_security_group_id = var.alb_security_group_id
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  description              = "Allow the public ALB to call the Host service"
}

resource "aws_security_group_rule" "public_http_to_alb" {
  type              = "ingress"
  security_group_id = var.alb_security_group_id
  cidr_blocks       = ["0.0.0.0/0"]
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  description       = "Public HTTP entry point for the Host API; put HTTPS in front before production"
}

resource "aws_lb" "host" {
  name               = "${var.name_prefix}-host"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids
}

resource "aws_lb_target_group" "host" {
  name        = "${var.name_prefix}-host"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    enabled  = true
    path     = "/healthz"
    protocol = "HTTP"
    matcher  = "200"
  }
}

resource "aws_lb_listener" "host" {
  load_balancer_arn = aws_lb.host.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.host.arn
  }
}

resource "aws_ecs_cluster" "agents" {
  name = "${var.name_prefix}-agents"
}

resource "aws_ecs_task_definition" "agent" {
  for_each = local.agents

  family                   = "${var.name_prefix}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.container_cpu
  memory                   = var.container_memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([{
    name      = each.key
    image     = "${data.aws_ecr_repository.agent[each.key].repository_url}:${var.image_tag}"
    essential = true

    portMappings = [{
      containerPort = each.value.port
      hostPort      = each.value.port
      protocol      = "tcp"
    }]

    environment = concat([
      {
        name  = "APP_MODULE"
        value = each.value.module
      },
      {
        name  = "PORT"
        value = tostring(each.value.port)
      }
    ], local.common_environment)

    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:${each.value.port}/healthz')\""]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 30
    }

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.agent[each.key].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
  }])
}

resource "aws_ecs_service" "agent" {
  for_each = local.agents

  name            = "${var.name_prefix}-${each.key}"
  cluster         = aws_ecs_cluster.agents.id
  task_definition = aws_ecs_task_definition.agent[each.key].arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  network_configuration {
    subnets          = var.task_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.agent[each.key].arn
  }

  dynamic "load_balancer" {
    for_each = each.key == "host" ? [1] : []

    content {
      target_group_arn = aws_lb_target_group.host.arn
      container_name   = "host"
      container_port   = 8000
    }
  }

  depends_on = [
    aws_security_group_rule.host_to_agents,
    aws_security_group_rule.ecs_host_to_agents,
    aws_security_group_rule.alb_to_host,
    aws_lb_listener.host
  ]
}
