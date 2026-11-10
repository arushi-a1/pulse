data "aws_caller_identity" "current" {}

# --- Networking --------------------------------------------------------------
module "networking" {
  source = "./modules/networking"

  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr
  az_count     = var.az_count
}

# --- Data layer ----------------------------------------------------------------
module "rds" {
  source = "./modules/rds"

  project_name       = var.project_name
  environment        = var.environment
  instance_class     = var.db_instance_class
  db_name            = var.db_name
  db_username        = var.db_username
  private_subnet_ids = module.networking.private_subnet_ids
  security_group_id  = module.networking.rds_security_group_id
}

module "redis" {
  source = "./modules/redis"

  project_name       = var.project_name
  environment        = var.environment
  node_type          = var.redis_node_type
  private_subnet_ids = module.networking.private_subnet_ids
  security_group_id  = module.networking.redis_security_group_id
}

module "sqs" {
  source = "./modules/sqs"

  project_name = var.project_name
  environment  = var.environment
}

module "s3" {
  source = "./modules/s3"

  project_name   = var.project_name
  environment    = var.environment
  account_suffix = data.aws_caller_identity.current.account_id
}

# --- IAM (needs the SNS topic ARN from cloudwatch and the SQS/S3 ARNs
# created above; does NOT depend on ECS or Lambda, so no cycle) -------------
module "iam" {
  source = "./modules/iam"

  project_name    = var.project_name
  environment     = var.environment
  sqs_queue_arn   = module.sqs.queue_arn
  sqs_dlq_arn     = module.sqs.dlq_arn
  s3_bucket_arn   = module.s3.bucket_arn
  db_secret_arn   = module.rds.secret_arn
  alarm_topic_arn = module.cloudwatch.sns_topic_arn
}

# --- Compute -------------------------------------------------------------------
module "ecs" {
  source = "./modules/ecs"

  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region

  vpc_id                       = module.networking.vpc_id
  public_subnet_ids            = module.networking.public_subnet_ids
  private_subnet_ids           = module.networking.private_subnet_ids
  alb_security_group_id        = module.networking.alb_security_group_id
  ecs_api_security_group_id    = module.networking.ecs_api_security_group_id
  ecs_worker_security_group_id = module.networking.ecs_worker_security_group_id

  api_image    = var.api_image
  worker_image = var.worker_image

  ecs_task_execution_role_arn = module.iam.ecs_task_execution_role_arn
  api_task_role_arn           = module.iam.api_task_role_arn
  worker_task_role_arn        = module.iam.worker_task_role_arn

  db_secret_arn  = module.rds.secret_arn
  sqs_queue_url  = module.sqs.queue_url
  sqs_dlq_url    = module.sqs.dlq_url
  sqs_queue_name = "${var.project_name}-${var.environment}-events"
  s3_bucket_name = module.s3.bucket_name
  redis_endpoint = module.redis.primary_endpoint

  acm_certificate_arn = var.acm_certificate_arn

  api_desired_count    = var.api_desired_count
  worker_desired_count = var.worker_desired_count
  api_min_count        = var.api_min_count
  api_max_count        = var.api_max_count
  worker_min_count     = var.worker_min_count
  worker_max_count     = var.worker_max_count
}

# --- Observability -------------------------------------------------------------
# Creates the SNS alarm topic (used by iam above) plus every alarm/dashboard
# widget that reads ECS/ALB/RDS metrics -- so it depends on ecs, but nothing
# downstream of ecs depends back on the SNS topic itself, so this isn't a
# cycle even though iam (created earlier) also reads this module's output.
module "cloudwatch" {
  source = "./modules/cloudwatch"

  project_name             = var.project_name
  environment              = var.environment
  aws_region               = var.aws_region
  alarm_notification_email = var.alarm_notification_email
  queue_name               = "${var.project_name}-${var.environment}-events"
  dlq_name                 = "${var.project_name}-${var.environment}-events-dlq"
  alb_arn_suffix           = module.ecs.api_load_balancer_dns
  rds_instance_id          = "${var.project_name}-${var.environment}"
  ecs_cluster_name         = module.ecs.cluster_name
  api_service_name         = module.ecs.api_service_name
  worker_service_name      = module.ecs.worker_service_name
}

# --- Async processing (Lambda, only place it's used -- see README) -----------
module "lambda" {
  source = "./modules/lambda"

  project_name    = var.project_name
  environment     = var.environment
  lambda_role_arn = module.iam.dlq_notifier_lambda_role_arn
  dlq_alarm_arn   = module.cloudwatch.dlq_alarm_arn
  sns_topic_arn   = module.cloudwatch.sns_topic_arn
}
