variable "project_name" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }
variable "alarm_notification_email" {
  type    = string
  default = ""
}
variable "queue_name" { type = string }
variable "dlq_name" { type = string }
variable "alb_arn_suffix" { type = string }
variable "rds_instance_id" { type = string }
variable "ecs_cluster_name" { type = string }
variable "api_service_name" { type = string }
variable "worker_service_name" { type = string }
