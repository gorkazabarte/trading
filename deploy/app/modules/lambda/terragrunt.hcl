include "root" {
  path = find_in_parent_folders("root.hcl")
}

dependency "dynamodb" {
  config_path = "../dynamodb"
}

dependency "s3" {
  config_path = "../s3"
}

locals {
  root_config   = read_terragrunt_config(find_in_parent_folders("root.hcl"))
  s3_bucket_key = "${local.root_config.locals.app_name}/app/${local.root_config.locals.environment}/lambda/terraform.tfstate"
}

inputs = {
  dynamodb_table_name = dependency.dynamodb.outputs.dynamodb_table_tradding_settings_name
  s3_bucket_name      = dependency.s3.outputs.s3_bucket_name
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
