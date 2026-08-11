output "endpoint" {
  value     = aws_db_instance.main.address
  sensitive = true
}

output "secret_arn" {
  description = "Secrets Manager ARN holding DB credentials, injected into ECS task definitions as a secret (never as a plaintext env var)"
  value       = aws_secretsmanager_secret.db_credentials.arn
}
