output "dashboard_url" {
  value = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

output "dlq_alarm_arn" { value = aws_cloudwatch_metric_alarm.dlq_depth.arn }
output "sns_topic_arn" { value = aws_sns_topic.alarms.arn }
