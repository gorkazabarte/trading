locals {
  app_name         = var.app_name
  environment      = var.environment
  svc_account_json = var.svc_account_json
}

resource "aws_secretsmanager_secret" "svc_account" {
  name        = "${local.environment}-${local.app_name}-service-account"
  description = "Service account credentials for trading CSV sync from Google Drive"
}

resource "aws_secretsmanager_secret_version" "svc_account" {
  secret_id     = aws_secretsmanager_secret.svc_account.id
  secret_string = local.svc_account_json
}
