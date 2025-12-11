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

variable "s3_bucket_name" {
  description = "The name of the S3 bucket for Lambda function code storage."
  type        = string
}

variable "lambda_get_calendar_arn" {
  description = "ARN of the Lambda function for getting calendar data"
  type        = string
}

variable "lambda_get_calendar_name" {
  description = "Name of the Lambda function for getting calendar data"
  type        = string
}

variable "lambda_select_companies_arn" {
  description = "ARN of the Lambda function for selecting companies"
  type        = string
}

variable "lambda_select_companies_name" {
  description = "Name of the Lambda function for selecting companies"
  type        = string
}

variable "lambda_update_settings_arn" {
  description = "ARN of the Lambda function for updating settings"
  type        = string
}

variable "lambda_update_settings_name" {
  description = "Name of the Lambda function for updating settings"
  type        = string
}

