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

  # The Host only fans out to the other agents; it never calls an LLM.
  llm_agents = toset(["stay", "activities"])

  provider_environment = var.llm_provider == "openai" ? [
    {
      name  = "OPENAI_MODEL"
      value = var.openai_model
    }
    ] : [
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
    }
  ]

  common_environment = concat([
    {
      name  = "LLM_PROVIDER"
      value = var.llm_provider
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
  ], local.provider_environment)
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

resource "aws_lb" "host" {
  name               = "${var.name_prefix}-host"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids

  # POST /run can wait up to DOWNSTREAM_TIMEOUT_SECONDS (150s) on the agents.
  idle_timeout = 180
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

resource "aws_ecs_cluster_capacity_providers" "agents" {
  cluster_name       = aws_ecs_cluster.agents.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]
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

  lifecycle {
    precondition {
      condition     = var.llm_provider != "openai" || var.openai_api_key_parameter_arn != ""
      error_message = "Set openai_api_key_parameter_arn when llm_provider = openai."
    }
    precondition {
      condition     = var.llm_provider != "ollama" || var.ollama_base_url != ""
      error_message = "Set ollama_base_url when llm_provider = ollama."
    }
  }

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

    secrets = var.llm_provider == "openai" && contains(local.llm_agents, each.key) ? [{
      name      = "OPENAI_API_KEY"
      valueFrom = var.openai_api_key_parameter_arn
    }] : []

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

  capacity_provider_strategy {
    capacity_provider = var.use_fargate_spot ? "FARGATE_SPOT" : "FARGATE"
    weight            = 1
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  network_configuration {
    subnets          = var.task_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = true
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

  # The schedule below owns desired_count once the service exists.
  lifecycle {
    ignore_changes = [desired_count]
  }

  depends_on = [
    aws_lb_listener.host,
    aws_ecs_cluster_capacity_providers.agents
  ]
}

resource "aws_appautoscaling_target" "agent" {
  for_each = var.schedule_enabled ? local.agents : {}

  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.agents.name}/${aws_ecs_service.agent[each.key].name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = 0
  max_capacity       = var.desired_count

  # The scheduled actions rewrite these bounds every start and stop.
  lifecycle {
    ignore_changes = [min_capacity, max_capacity]
  }
}

resource "aws_appautoscaling_scheduled_action" "start" {
  for_each = aws_appautoscaling_target.agent

  name               = "${var.name_prefix}-${each.key}-start"
  service_namespace  = each.value.service_namespace
  resource_id        = each.value.resource_id
  scalable_dimension = each.value.scalable_dimension
  schedule           = var.schedule_start_cron
  timezone           = var.schedule_timezone

  scalable_target_action {
    min_capacity = var.desired_count
    max_capacity = var.desired_count
  }
}

# Scaling to zero stops the tasks, which releases their public IPv4 addresses.
resource "aws_appautoscaling_scheduled_action" "stop" {
  for_each = aws_appautoscaling_target.agent

  name               = "${var.name_prefix}-${each.key}-stop"
  service_namespace  = each.value.service_namespace
  resource_id        = each.value.resource_id
  scalable_dimension = each.value.scalable_dimension
  schedule           = var.schedule_stop_cron
  timezone           = var.schedule_timezone

  scalable_target_action {
    min_capacity = 0
    max_capacity = 0
  }

  depends_on = [aws_appautoscaling_scheduled_action.start]
}
