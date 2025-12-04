locals {
  app_name       = var.app_name
  app_version    = var.app_version
  aws_account_id = var.aws_account_id
  aws_region     = var.aws_region
  aws_s3_bucket  = var.s3_bucket_name
  environment    = var.environment
}

resource "aws_iam_policy" "lambda_policy_download_info" {
  name        = "${local.environment}-${local.app_name}-download-info"
  description = "Allow Lambda to put objects in specific S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:PutObject"]
      Resource = "arn:aws:s3:::${local.aws_s3_bucket}/*"
    }]
  })
}

module "lambda_function_download_info" {
  source         = "terraform-aws-modules/lambda/aws"
  attach_policy  = true
  create_package = false
  description    = "Donwload information using web scraping"
  environment_variables = {
    API_KEY   = "VF5Y4DWQGRZPIYY9"
    S3_BUCKET = "${local.aws_s3_bucket}"
  }
  function_name  = "${local.environment}-${local.app_name}-download-info"
  image_uri      = "${local.aws_account_id}.dkr.ecr.${local.aws_region}.amazonaws.com/${local.environment}-${local.app_name}-download-info:${local.app_version}"
  memory_size	 = 256
  timeout        = 180
  package_type   = "Image"
  policy         = aws_iam_policy.lambda_policy_download_info.arn
  version        = "8.1.2"
}

resource "aws_iam_policy" "lambda_policy_get_calendar" {
  name        = "${local.environment}-${local.app_name}-get-calendar"
  description = "Return calendar response to API Gateway"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "arn:aws:s3:::${local.aws_s3_bucket}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = "arn:aws:s3:::${local.aws_s3_bucket}"
      }
    ]
  })
}

module "lambda_function_get_calendar" {
  source         = "terraform-aws-modules/lambda/aws"
  attach_policy  = true
  create_package = false
  description    = "Return calendar response to API Gateway"
  environment_variables = {
    API_KEY   = "VF5Y4DWQGRZPIYY9"
    S3_BUCKET = "${local.aws_s3_bucket}"
  }
  function_name  = "${local.environment}-${local.app_name}-get-calendar"
  image_uri      = "${local.aws_account_id}.dkr.ecr.${local.aws_region}.amazonaws.com/${local.environment}-${local.app_name}-get-calendar:${local.app_version}"
  memory_size	 = 256
  timeout        = 180
  package_type   = "Image"
  policy         = aws_iam_policy.lambda_policy_get_calendar.arn
  version        = "8.1.2"
}

resource "aws_iam_policy" "lambda_policy_filter_info" {
  name        = "${local.environment}-${local.app_name}-filter-info"
  description = "Filter companies based on criteria and store in S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "arn:aws:s3:::${local.aws_s3_bucket}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = "arn:aws:s3:::${local.aws_s3_bucket}"
      }
    ]
  })
}

module "lambda_function_filter_info" {
  source         = "terraform-aws-modules/lambda/aws"
  attach_policy  = true
  create_package = false
  description    = "Filter companies based on criteria and store in S3"
  environment_variables = {
    API_KEY   = "VF5Y4DWQGRZPIYY9"
    S3_BUCKET = "${local.aws_s3_bucket}"
  }
  function_name  = "${local.environment}-${local.app_name}-filter-info"
  image_uri      = "${local.aws_account_id}.dkr.ecr.${local.aws_region}.amazonaws.com/${local.environment}-${local.app_name}-filter-info:${local.app_version}"
  memory_size	 = 256
  timeout        = 300
  package_type   = "Image"
  policy         = aws_iam_policy.lambda_policy_filter_info.arn
  version        = "8.1.2"
}
