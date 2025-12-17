locals {
  app_name               = var.app_name
  app_version            = var.app_version
  aws_account_id         = var.aws_account_id
  aws_region             = var.aws_region
  environment            = var.environment
  lambda_filter_info_arn = var.lambda_filter_info_arn
}

resource "aws_cloudwatch_event_rule" "filter_info" {
  name        = "${local.environment}-${local.app_name}-filter-info"
  description = "Capture each S3 Bucket Put Object"
  event_pattern = jsonencode({
    "source": ["aws.s3"],
    "detail-type": ["Object Created"],
    "detail": {
      "bucket": {
        "name": ["${local.environment}-${local.app_name}-data-storage"]
      },
      "object": {
        "key": [{
          "prefix": "2025"
        }, {
          "suffix": ".csv"
        }]
      }
    }
  })
}

resource "aws_iam_role" "eventbridge_invoke_lambda" {
  name = "${local.environment}-${local.app_name}-eventbridge-invoke-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "eventbridge_invoke_lambda" {
  name = "${local.environment}-${local.app_name}-eventbridge-invoke-lambda-policy"
  role = aws_iam_role.eventbridge_invoke_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "lambda:InvokeFunction"
        Effect = "Allow"
        Resource = local.lambda_filter_info_arn
      }
    ]
  })
}

resource "aws_cloudwatch_event_target" "filter_info" {
  rule      = aws_cloudwatch_event_rule.filter_info.name
  target_id = "TriggerAWSLambda"
  arn       = local.lambda_filter_info_arn
  role_arn  = aws_iam_role.eventbridge_invoke_lambda.arn
}
