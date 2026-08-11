data "aws_caller_identity" "current" {}

# --- ECS task execution role (pulls image, writes logs, reads secrets) -----
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project_name}-${var.environment}-ecs-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_managed" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_task_execution_secrets" {
  name = "read-db-secret"
  role = aws_iam_role.ecs_task_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [var.db_secret_arn]
    }]
  })
}

# --- API task role: enqueue only, never touches the DB directly for events -
resource "aws_iam_role" "api_task" {
  name = "${var.project_name}-${var.environment}-api-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "api_task_policy" {
  name = "api-least-privilege"
  role = aws_iam_role.api_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "SendToEventQueueOnly"
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = [var.sqs_queue_arn]
      },
      {
        Sid      = "ReadQueueDepthForAnalytics"
        Effect   = "Allow"
        Action   = ["sqs:GetQueueAttributes"]
        Resource = [var.sqs_queue_arn]
      }
    ]
  })
}

# --- Worker task role: consume queue, write DB via secret, archive to S3 ---
resource "aws_iam_role" "worker_task" {
  name = "${var.project_name}-${var.environment}-worker-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "worker_task_policy" {
  name = "worker-least-privilege"
  role = aws_iam_role.worker_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ConsumeEventQueue"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
        ]
        Resource = [var.sqs_queue_arn]
      },
      {
        Sid      = "ArchiveRawEventsToOwnPrefixOnly"
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = ["${var.s3_bucket_arn}/raw-events/*"]
      }
    ]
  })
}

# --- Lambda role: DLQ-alarm notifier only -----------------------------------
resource "aws_iam_role" "dlq_notifier_lambda" {
  name = "${var.project_name}-${var.environment}-dlq-notifier"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "dlq_notifier_basic" {
  role       = aws_iam_role.dlq_notifier_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "dlq_notifier_sns" {
  name = "publish-alarm-notification"
  role = aws_iam_role.dlq_notifier_lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sns:Publish"]
      Resource = [var.alarm_topic_arn]
    }]
  })
}
