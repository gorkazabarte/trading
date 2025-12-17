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

resource "aws_cloudwatch_event_target" "filter_info" {
  rule      = aws_cloudwatch_event_rule.filter_info.name
  target_id = "TriggerAWSLambda"
  arn       = local.lambda_filter_info_arn
}
