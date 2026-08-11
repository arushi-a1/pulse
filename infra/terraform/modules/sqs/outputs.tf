output "queue_url" { value = aws_sqs_queue.events.id }
output "queue_arn" { value = aws_sqs_queue.events.arn }
output "dlq_url" { value = aws_sqs_queue.dlq.id }
output "dlq_arn" { value = aws_sqs_queue.dlq.arn }
