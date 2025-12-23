variable "app_name" {
  description = "The name of the application"
  type        = string
}

variable "environment" {
  description = "The deployment environment (e.g., dev, staging, prod)"
  type        = string
}

variable "svc_account_json" {
  description = "Service account credentials in JSON format"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.svc_account_json) > 0
    error_message = "The svc_account_json variable cannot be empty. Please set the SVC_ACCOUNT_JSON environment variable."
  }
}

