locals {
  app_name    = var.app_name
  environment = var.environment
}

resource "aws_s3_bucket" "data" {
  bucket = "${var.environment}-${var.app_name}-data-storage"
}
