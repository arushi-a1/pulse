resource "aws_sqs_queue" "dlq" {
  name                      = "${var.project_name}-${var.environment}-events-dlq"
  message_retention_seconds = 1209600 # 14 days -- long enough to investigate and reprocess by hand
  tags                      = { Name = "${var.project_name}-${var.environment}-events-dlq" }
}

resource "aws_sqs_queue" "events" {
  name                       = "${var.project_name}-${var.environment}-events"
  visibility_timeout_seconds = 60     # > worst-case processing time, so a slow-but-successful run isn't redelivered mid-flight
  message_retention_seconds  = 345600 # 4 days
  receive_wait_time_seconds  = 10     # long polling -- fewer empty receives than short polling

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = { Name = "${var.project_name}-${var.environment}-events" }
}

# Lets operators requeue everything in the DLQ back onto the main queue after
# a fix ships, without writing a one-off script.
resource "aws_sqs_queue_redrive_allow_policy" "dlq_redrive" {
  queue_url = aws_sqs_queue.dlq.id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.events.arn]
  })
}
