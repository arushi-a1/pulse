resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-${var.environment}"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.project_name}-${var.environment}/api"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.project_name}-${var.environment}/worker"
  retention_in_days = 14
}

# --- API service -------------------------------------------------------------

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.project_name}-${var.environment}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = var.ecs_task_execution_role_arn
  task_role_arn            = var.api_task_role_arn

  container_definitions = jsonencode([{
    name         = "api"
    image        = var.api_image
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    environment = [
      { name = "ENVIRONMENT", value = var.environment },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "SQS_QUEUE_URL", value = var.sqs_queue_url },
      { name = "S3_BUCKET", value = var.s3_bucket_name },
      { name = "REDIS_URL", value = "redis://${var.redis_endpoint}:6379/0" },
    ]
    secrets = [
      { name = "DATABASE_URL", valueFrom = var.db_secret_arn },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "api"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval    = 15
      timeout     = 3
      retries     = 3
      startPeriod = 10
    }
  }])
}

resource "aws_lb" "api" {
  name               = "${var.project_name}-${var.environment}-api"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids
}

resource "aws_lb_target_group" "api" {
  name        = "${var.project_name}-${var.environment}-api"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health/ready"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 15
    timeout             = 5
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# Plain-HTTP listener exists only to redirect to HTTPS -- the API is never
# served over unencrypted HTTP.
resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_ecs_service" "api" {
  name            = "${var.project_name}-${var.environment}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [var.ecs_api_security_group_id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200 # rolling deploy: spin up new before killing old

  depends_on = [aws_lb_listener.https]
}

resource "aws_appautoscaling_target" "api" {
  min_capacity       = var.api_min_count
  max_capacity       = var.api_max_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# API scales on request load, since that's what actually drives its resource
# needs -- CPU alone lags request bursts by a scrape interval or two.
resource "aws_appautoscaling_policy" "api_request_count" {
  name               = "${var.project_name}-${var.environment}-api-scale-on-requests"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ALBRequestCountPerTarget"
      resource_label         = "${aws_lb.api.arn_suffix}/${aws_lb_target_group.api.arn_suffix}"
    }
    target_value       = 500 # requests/target/min before scaling out
    scale_in_cooldown  = 120
    scale_out_cooldown = 30 # scale out fast, scale in slow -- avoid flapping
  }
}

# --- Worker service ------------------------------------------------------

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project_name}-${var.environment}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = var.ecs_task_execution_role_arn
  task_role_arn            = var.worker_task_role_arn

  container_definitions = jsonencode([{
    name  = "worker"
    image = var.worker_image
    environment = [
      { name = "ENVIRONMENT", value = var.environment },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "SQS_QUEUE_URL", value = var.sqs_queue_url },
      { name = "S3_BUCKET", value = var.s3_bucket_name },
      { name = "REDIS_URL", value = "redis://${var.redis_endpoint}:6379/0" },
    ]
    secrets = [
      { name = "DATABASE_URL", valueFrom = var.db_secret_arn },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.worker.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "worker"
      }
    }
  }])
}

resource "aws_ecs_service" "worker" {
  name            = "${var.project_name}-${var.environment}-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [var.ecs_worker_security_group_id]
  }
}

resource "aws_appautoscaling_target" "worker" {
  min_capacity       = var.worker_min_count
  max_capacity       = var.worker_max_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.worker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# Worker scales on queue depth -- the metric that actually reflects its
# workload, independent of API traffic shape. This is the crux of "API and
# workers scale independently": a request spike alone doesn't scale workers,
# only a growing backlog does.
resource "aws_appautoscaling_policy" "worker_queue_depth" {
  name               = "${var.project_name}-${var.environment}-worker-scale-on-queue"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker.service_namespace

  target_tracking_scaling_policy_configuration {
    customized_metric_specification {
      metric_name = "ApproximateNumberOfMessagesVisible"
      namespace   = "AWS/SQS"
      statistic   = "Average"
      dimensions {
        name  = "QueueName"
        value = var.sqs_queue_name
      }
    }
    target_value       = 100 # messages per task before scaling out
    scale_in_cooldown  = 180
    scale_out_cooldown = 30
  }
}
