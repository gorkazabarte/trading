locals {
  app_name                    = var.app_name
  app_version                 = var.app_version
  aws_account_id              = var.aws_account_id
  aws_region                  = var.aws_region
  environment                 = var.environment
  lambda_get_calendar_arn     = var.lambda_get_calendar_arn
  lambda_select_companies_arn = var.lambda_select_companies_arn
  lambda_update_settings_arn  = var.lambda_update_settings_arn
  s3_bucket_name              = var.s3_bucket_name
}

module "api_gateway" {
  source = "terraform-aws-modules/apigateway-v2/aws"
  version = "6.0.0"

  cors_configuration = {
    allow_headers = ["accept", "content-type", "x-amz-date", "authorization", "x-api-key", "x-amz-security-token", "x-amz-user-agent", "x-requested-with"]
    allow_methods = ["GET", "OPTIONS", "POST"]
    allow_origins = ["*"]
  }

  description   = "HTTP API Gateway for ${local.app_name} application in ${local.environment} environment"
  name          = "${local.environment}-${local.app_name}-api"
  protocol_type = "HTTP"

  routes = {
    "GET /calendar/{year}/{month}/{day}" = {
      integration = {
        uri                    = local.lambda_get_calendar_arn
        payload_format_version = "2.0"
        timeout_milliseconds   = 30000
      }
    }

    "POST /companies" = {
      integration = {
        uri                    = local.lambda_select_companies_arn
        payload_format_version = "2.0"
        timeout_milliseconds   = 30000
      }
    }

    "POST /settings" = {
      integration = {
        uri                    = local.lambda_update_settings_arn
        payload_format_version = "2.0"
        timeout_milliseconds   = 30000
      }
    }
  }
}
