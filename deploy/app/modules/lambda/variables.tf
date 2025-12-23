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

variable "service_account_secret_name" {
  description = "Name of the AWS Secrets Manager secret containing Google service account JSON"
  type        = string
  default     = "service-account-trading"
}

variable "s3_bucket_name" {
  description = "The name of the S3 bucket for Lambda function code storage."
  type        = string
}
