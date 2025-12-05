module "dynamodb_table_tradding_settings" {
  source   = "terraform-aws-modules/dynamodb-table/aws"

  name     = "dev-trading-settings"
  hash_key = "setting"

  attributes = [
    {
      name = "setting"
      type = "S"
    },
    {
      name = "value"
      type = "S"
    }
  ]
}
