locals {
  app_name       = get_env("APP_NAME")
  app_version    = get_env("APP_VERSION")
  aws_account_id = get_env("AWS_ACCOUNT_ID")
  aws_region     = get_env("AWS_REGION")
  environment    = get_env("ENVIRONMENT")
  tf_bucket      = get_env("TF_BUCKET")
}

inputs = {
  app_name       = local.app_name
  app_version    = local.app_version
  aws_account_id = local.aws_account_id
  aws_region     = local.aws_region
  environment    = local.environment
}

generate "provider" {
  path = "providers.tf"
  if_exists = "overwrite_terragrunt"
  contents = <<EOF
  data "aws_caller_identity" "main" {}
  provider "aws" {
    region = "${local.aws_region}"
  }
  terraform {
    required_version = "~> 1.10"
    required_providers {
      aws = {
        source  = "hashicorp/aws"
        version = "~> 6.10"
      }
    }
  }
  EOF
}

terraform {
  source = "${get_terragrunt_dir()}"
}
