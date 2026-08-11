variable "project_name" {
  description = "Name prefix applied to all resources"
  type        = string
  default     = "pulse"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-west-2"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "Number of availability zones to spread subnets across"
  type        = number
  default     = 2
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_name" {
  type    = string
  default = "pulse"
}

variable "db_username" {
  type    = string
  default = "pulse"
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "api_image" {
  description = "Container image URI for the API service (built and pushed by CI)"
  type        = string
}

variable "worker_image" {
  description = "Container image URI for the worker service (built and pushed by CI)"
  type        = string
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "worker_desired_count" {
  type    = number
  default = 2
}

variable "api_min_count" {
  type    = number
  default = 2
}

variable "api_max_count" {
  type    = number
  default = 10
}

variable "worker_min_count" {
  type    = number
  default = 1
}

variable "worker_max_count" {
  type    = number
  default = 20
}

variable "alarm_notification_email" {
  description = "Email address to notify on DLQ / failure alarms"
  type        = string
  default     = ""
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for the ALB HTTPS listener. Provision via `aws acm request-certificate` (or a Terraform aws_acm_certificate resource with DNS validation, omitted here since it requires a Route53 zone this project doesn't own) and pass the resulting ARN in terraform.tfvars."
  type        = string
}
