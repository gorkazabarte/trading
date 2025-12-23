locals {
  app_name       = var.app_name
  app_version    = var.app_version
  aws_account_id = var.aws_account_id
  aws_region     = var.aws_region
  aws_s3_bucket  = var.s3_bucket_name
  environment    = var.environment
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

resource "aws_lambda_permission" "api_gateway_invoke_get_calendar" {
  statement_id  = "AllowAPIGatewayGetCalendarInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_function_get_calendar.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "arn:aws:execute-api:${local.aws_region}:${local.aws_account_id}:*/*"
}

resource "aws_iam_policy" "lambda_policy_get_positions" {
  name        = "${local.environment}-${local.app_name}-get-positions"
  description = "Return open positions response to API Gateway"

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

module "lambda_function_get_positions" {
  source         = "terraform-aws-modules/lambda/aws"
  attach_policy  = true
  create_package = false
  description    = "Return open position response to API Gateway"
  environment_variables = {
    S3_BUCKET = "${local.aws_s3_bucket}"
  }
  function_name  = "${local.environment}-${local.app_name}-get-positions"
  image_uri      = "${local.aws_account_id}.dkr.ecr.${local.aws_region}.amazonaws.com/${local.environment}-${local.app_name}-get-positions:${local.app_version}"
  memory_size	 = 256
  timeout        = 180
  package_type   = "Image"
  policy         = aws_iam_policy.lambda_policy_get_positions.arn
  version        = "8.1.2"
}

resource "aws_lambda_permission" "api_gateway_invoke_get_positions" {
  statement_id  = "AllowAPIGatewayGetPositionsInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_function_get_positions.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "arn:aws:execute-api:${local.aws_region}:${local.aws_account_id}:*/*"
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

resource "aws_lambda_permission" "api_gateway_invoke_select_companies" {
  statement_id  = "AllowAPIGatewaySelectCompaniesInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_function_select_companies.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "arn:aws:execute-api:${local.aws_region}:${local.aws_account_id}:*/*"
}

resource "aws_iam_policy" "lambda_policy_select_companies" {
  name        = "${local.environment}-${local.app_name}-select-companies"
  description = "Allow Lambda to create a S3 object with selected companies"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
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

module "lambda_function_select_companies" {
  source         = "terraform-aws-modules/lambda/aws"
  attach_policy  = true
  create_package = false
  description    = "AWS Lambda function to update selected companies in S3"
  environment_variables = {
    S3_BUCKET = "${local.aws_s3_bucket}"
    S3_KEY    = "selected_companies.json"
  }
  function_name  = "${local.environment}-${local.app_name}-select-companies"
  image_uri      = "${local.aws_account_id}.dkr.ecr.${local.aws_region}.amazonaws.com/${local.environment}-${local.app_name}-select-companies:${local.app_version}"
  memory_size	 = 256
  timeout        = 300
  package_type   = "Image"
  policy         = aws_iam_policy.lambda_policy_select_companies.arn
  version        = "8.1.2"
}

resource "aws_lambda_permission" "api_gateway_invoke_update_settings" {
  statement_id  = "AllowAPIGatewayUpdateSettingsInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_function_update_settings.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "arn:aws:execute-api:${local.aws_region}:${local.aws_account_id}:*/*"
}

resource "aws_iam_policy" "lambda_policy_update_settings" {
  name        = "${local.environment}-${local.app_name}-update-settings"
  description = "Allow Lambda to update items in DynamoDB table"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
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

resource "aws_iam_policy" "lambda_policy_sync_storage" {
  name        = "${local.environment}-${local.app_name}-sync-storage"
  description = "Sync Google Docs with Amazon S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "arn:aws:s3:::${local.aws_s3_bucket}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = "arn:aws:s3:::${local.aws_s3_bucket}"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${local.aws_region}:${local.aws_account_id}:secret:${local.environment}-${local.app_name}-google-service-account-*"
      }
    ]
  })
}

module "lambda_function_sync_storage" {
  source         = "terraform-aws-modules/lambda/aws"
  attach_policy  = true
  create_package = false
  description    = "Sync CSV files from Google Drive to S3"
  environment_variables = {
    GOOGLE_SERVICE_ACCOUNT_SECRET_NAME = var.google_service_account_secret_name
    S3_BUCKET                          = local.aws_s3_bucket
  }
  function_name  = "${local.environment}-${local.app_name}-sync-storage"
  image_uri      = "${local.aws_account_id}.dkr.ecr.${local.aws_region}.amazonaws.com/${local.environment}-${local.app_name}-sync-storage:${local.app_version}"
  memory_size    = 512
  timeout        = 300
  package_type   = "Image"
  policy         = aws_iam_policy.lambda_policy_sync_storage.arn
  version        = "8.1.2"
}

module "lambda_function_update_settings" {
  source         = "terraform-aws-modules/lambda/aws"
  attach_policy  = true
  create_package = false
  description    = "AWS Lambda function to update tradding settings in S3 bucket"
  environment_variables = {
    S3_BUCKET = "${local.aws_s3_bucket}"
    S3_KEY    = "settings.json"
  }
  function_name  = "${local.environment}-${local.app_name}-update-settings"
  image_uri      = "${local.aws_account_id}.dkr.ecr.${local.aws_region}.amazonaws.com/${local.environment}-${local.app_name}-update-settings:${local.app_version}"
  memory_size	 = 256
  timeout        = 450
  package_type   = "Image"
  policy         = aws_iam_policy.lambda_policy_update_settings.arn
  version        = "8.1.2"
}
