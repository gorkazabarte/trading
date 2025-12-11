output "lambda_get_calendar_arn" {
  description = "ARN of the Lambda function for getting calendar data"
  value       = module.lambda_function_get_calendar.lambda_function_arn
}

output "lambda_get_calendar_name" {
  description = "Name of the Lambda function for getting calendar data"
  value       = module.lambda_function_get_calendar.lambda_function_name
}

output "lambda_get_calendar_invoke_arn" {
  description = "Invoke ARN of the Lambda function for getting calendar data"
  value       = module.lambda_function_get_calendar.lambda_function_invoke_arn
}

output "lambda_select_companies_arn" {
  description = "ARN of the Lambda function for selecting companies"
  value       = module.lambda_function_select_companies.lambda_function_arn
}

output "lambda_select_companies_name" {
  description = "Name of the Lambda function for selecting companies"
  value       = module.lambda_function_select_companies.lambda_function_name
}

output "lambda_select_companies_invoke_arn" {
  description = "Invoke ARN of the Lambda function for selecting companies"
  value       = module.lambda_function_select_companies.lambda_function_invoke_arn
}

output "lambda_update_settings_arn" {
  description = "ARN of the Lambda function for updating settings"
  value       = module.lambda_function_update_settings.lambda_function_arn
}

output "lambda_update_settings_name" {
  description = "Name of the Lambda function for updating settings"
  value       = module.lambda_function_update_settings.lambda_function_name
}

output "lambda_update_settings_invoke_arn" {
  description = "Invoke ARN of the Lambda function for updating settings"
  value       = module.lambda_function_update_settings.lambda_function_invoke_arn
}
