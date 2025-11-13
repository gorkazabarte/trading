variable "app_name" {
  description = "The name of the application."
  type        = string
}

variable "aws_iam_role" {
  description = "The ARN of the IAM role that will have read/write access to the ECR repositories."
  type        = string
}

variable "environment" {
  description = "The deployment environment (e.g., dev, staging, prod)."
  type        = string
}
