variable "project_name" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "private_subnet_ids" { type = list(string) }
variable "alb_security_group_id" { type = string }
variable "ecs_api_security_group_id" { type = string }
variable "ecs_worker_security_group_id" { type = string }

variable "api_image" { type = string }
variable "worker_image" { type = string }

variable "ecs_task_execution_role_arn" { type = string }
variable "api_task_role_arn" { type = string }
variable "worker_task_role_arn" { type = string }

variable "db_secret_arn" { type = string }
variable "sqs_queue_url" { type = string }
variable "sqs_queue_name" { type = string }
variable "s3_bucket_name" { type = string }
variable "redis_endpoint" { type = string }

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for the ALB HTTPS listener (provisioned separately per domain)"
  type        = string
}

variable "api_desired_count" { type = number }
variable "worker_desired_count" { type = number }
variable "api_min_count" { type = number }
variable "api_max_count" { type = number }
variable "worker_min_count" { type = number }
variable "worker_max_count" { type = number }
