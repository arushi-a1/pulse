resource "random_password" "db" {
  length  = 24
  special = false # avoid characters that need URL-encoding in connection strings
}

resource "aws_secretsmanager_secret" "db_credentials" {
  name_prefix = "${var.project_name}-${var.environment}-db-"
  description = "Pulse RDS Postgres credentials -- never referenced in code, only injected as an ECS task secret"
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db.result
    dbname   = var.db_name
    host     = aws_db_instance.main.address
    port     = 5432
  })
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-db-subnets"
  subnet_ids = var.private_subnet_ids
}

resource "aws_db_instance" "main" {
  identifier     = "${var.project_name}-${var.environment}"
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.instance_class

  allocated_storage     = 20
  max_allocated_storage = 100 # storage autoscaling for growth without a manual resize
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.security_group_id]
  publicly_accessible    = false

  backup_retention_period = 7
  skip_final_snapshot     = var.environment != "prod"
  deletion_protection     = var.environment == "prod"

  # Single-AZ for this portfolio deployment to control cost -- see README
  # "Tradeoffs" for the Multi-AZ upgrade path in a real production setting.
  multi_az = false

  tags = { Name = "${var.project_name}-${var.environment}-postgres" }
}
