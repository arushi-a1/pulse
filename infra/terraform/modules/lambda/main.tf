data "archive_file" "dlq_notifier" {
  type        = "zip"
  source_file = "${path.module}/src/dlq_notifier.py"
  output_path = "${path.module}/build/dlq_notifier.zip"
}

resource "aws_lambda_function" "dlq_notifier" {
  function_name    = "${var.project_name}-${var.environment}-dlq-notifier"
  role             = var.lambda_role_arn
  handler          = "dlq_notifier.handler"
  runtime          = "python3.12"
  timeout          = 10
  filename         = data.archive_file.dlq_notifier.output_path
  source_code_hash = data.archive_file.dlq_notifier.output_base64sha256

  environment {
    variables = {
      SNS_TOPIC_ARN = var.sns_topic_arn
    }
  }
}

# Lightweight, event-driven, and cold-start latency doesn't matter here --
# exactly the profile Lambda is good at, unlike the steady-state API/worker
# traffic which belongs on always-on Fargate tasks.
resource "aws_cloudwatch_event_rule" "dlq_alarm" {
  name        = "${var.project_name}-${var.environment}-dlq-alarm-trigger"
  description = "Fires when the DLQ depth alarm changes state"
  event_pattern = jsonencode({
    source      = ["aws.cloudwatch"]
    detail-type = ["CloudWatch Alarm State Change"]
    resources   = [var.dlq_alarm_arn]
  })
}

resource "aws_cloudwatch_event_target" "dlq_alarm_lambda" {
  rule = aws_cloudwatch_event_rule.dlq_alarm.name
  arn  = aws_lambda_function.dlq_notifier.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.dlq_notifier.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.dlq_alarm.arn
}
