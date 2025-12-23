include "root" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  google_service_account_json = get_env("GOOGLE_SERVICE_ACCOUNT_JSON", "")
  root_config                 = read_terragrunt_config(find_in_parent_folders("root.hcl"))
  s3_bucket_key               = "${local.root_config.locals.app_name}/infra/${local.root_config.locals.environment}/secrets/terraform.tfstate"
}

inputs = {
  google_service_account_json = local.google_service_account_json
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
