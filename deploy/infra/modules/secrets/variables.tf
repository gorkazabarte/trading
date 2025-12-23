variable "app_name" {
  description = "The name of the application"
  type        = string
}

variable "environment" {
  description = "The deployment environment (e.g., dev, staging, prod)"
  type        = string
}

variable "google_service_account_json" {
  description = "Google service account credentials in JSON format"
  type        = string
  sensitive   = true
}

