locals {
  app_name    = var.app_name
  environment = var.environment
}

resource "aws_s3_bucket" "data" {
  bucket = "${var.environment}-${var.app_name}-data-storage"
}

resource "aws_s3_bucket_ownership_controls" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket      = aws_s3_bucket.data.id
  eventbridge = true
}

resource "aws_s3_bucket_public_access_block" "data" {
  block_public_acls       = true
  block_public_policy     = true
  bucket = aws_s3_bucket.data.id
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "versioning" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}
