output "api_load_balancer_dns" { value = aws_lb.api.dns_name }
output "cluster_name" { value = aws_ecs_cluster.main.name }
output "api_service_name" { value = aws_ecs_service.api.name }
output "worker_service_name" { value = aws_ecs_service.worker.name }
