locals {
  app_name    = var.app_name
  environment = var.environment
}

module "dynamodb_table_tradding_settings" {
  source   = "terraform-aws-modules/dynamodb-table/aws"

  name     = "${local.environment}-${local.app_name}-settings"
  hash_key = "Setting"

  attributes = [
    {
      name = "Setting"
      type = "S"
    }
  ]
}
