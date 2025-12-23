locals {
  app_name                    = get_env("APP_NAME")
  aws_iam_role                = get_env("AWS_IAM_ROLE")
  aws_region                  = get_env("AWS_REGION")
  environment                 = get_env("ENVIRONMENT")
  google_service_account_json = get_env("SVC_ACCOUNT_JSON")
  tf_bucket                   = get_env("TF_BUCKET")
}

inputs = {
  app_name     = local.app_name
  aws_iam_role = local.aws_iam_role
  environment  = local.environment
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
