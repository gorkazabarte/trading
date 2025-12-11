include "root" {
  path = find_in_parent_folders("root.hcl")
}

dependency "lambda" {
  config_path = "../lambda"
}

dependency "s3" {
  config_path = "../s3"
}

locals {
  root_config   = read_terragrunt_config(find_in_parent_folders("root.hcl"))
  s3_bucket_key = "${local.root_config.locals.app_name}/app/${local.root_config.locals.environment}/api/terraform.tfstate"
}

inputs = {
  lambda_get_calendar_arn      = dependency.lambda.outputs.lambda_get_calendar_invoke_arn
  lambda_get_calendar_name     = dependency.lambda.outputs.lambda_get_calendar_name
  lambda_select_companies_arn  = dependency.lambda.outputs.lambda_select_companies_invoke_arn
  lambda_select_companies_name = dependency.lambda.outputs.lambda_select_companies_name
  lambda_update_settings_arn   = dependency.lambda.outputs.lambda_update_settings_invoke_arn
  lambda_update_settings_name  = dependency.lambda.outputs.lambda_update_settings_name
  s3_bucket_name               = dependency.s3.outputs.s3_bucket_name
}

remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite"
  }
  config = {
    bucket         = local.root_config.locals.tf_bucket
    encrypt        = true
    key            = local.s3_bucket_key
    region         = local.root_config.locals.aws_region
    use_lockfile   = true
  }
}
