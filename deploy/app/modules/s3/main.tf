locals {
  app_name    = var.app_name
  environment = var.environment
}

resource "aws_s3_bucket" "data" {
  bucket = "${var.environment}-${var.app_name}-data-storage"
}

resource "aws_s3_bucket_acl" "example" {
  bucket = aws_s3_bucket.data.id
  acl    = "private"
}

resource "aws_s3_bucket_versioning" "versioning_example" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}
