output "api_url" {
  description = "Public URL of the load balancer fronting the API service"
  value       = module.ecs.api_load_balancer_dns
}

output "rds_endpoint" {
  value     = module.rds.endpoint
  sensitive = true
}

output "redis_endpoint" {
  value = module.redis.primary_endpoint
}

output "sqs_queue_url" {
  value = module.sqs.queue_url
}

output "sqs_dlq_url" {
  value = module.sqs.dlq_url
}

output "s3_bucket_name" {
  value = module.s3.bucket_name
}

output "cloudwatch_dashboard_url" {
  value = module.cloudwatch.dashboard_url
}
