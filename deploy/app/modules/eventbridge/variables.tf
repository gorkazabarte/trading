variable "app_name" {
  description = "The name of the application."
  type        = string
}

variable "app_version" {
  description = "The version of the application."
  type        = string
}

variable "aws_account_id" {
  description = "The AWS account ID where resources will be created."
  type        = string
}

variable "aws_region" {
  description = "The AWS region where resources will be created."
  type        = string
}

variable "environment" {
  description = "The deployment environment (e.g., dev, staging, prod)."
  type        = string
}

variable "lambda_filter_info_arn" {
  description = "The ARN of the Lambda function to filter info."
  type        = string
}
