locals {
  app_name                    = var.app_name
  environment                 = var.environment
  google_service_account_json = var.google_service_account_json
}

resource "aws_secretsmanager_secret" "google_service_account" {
  name        = "${local.environment}-${local.app_name}-google-service-account"
  description = "Google service account credentials for trading CSV sync from Google Drive"
}

resource "aws_secretsmanager_secret_version" "google_service_account" {
  secret_id     = aws_secretsmanager_secret.google_service_account.id
  secret_string = local.google_service_account_json
}
