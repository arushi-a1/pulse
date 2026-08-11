output "ecs_task_execution_role_arn" { value = aws_iam_role.ecs_task_execution.arn }
output "api_task_role_arn" { value = aws_iam_role.api_task.arn }
output "worker_task_role_arn" { value = aws_iam_role.worker_task.arn }
output "dlq_notifier_lambda_role_arn" { value = aws_iam_role.dlq_notifier_lambda.arn }
