output "api_gateway_url" {
  description = "The URL of the API Gateway"
  value       = module.api_gateway.stage_invoke_url
}

output "api_gateway_id" {
  description = "The ID of the API Gateway"
  value       = module.api_gateway.api_id
}

output "api_gateway_arn" {
  description = "The ARN of the API Gateway"
  value       = module.api_gateway.api_arn
}

output "api_gateway_execution_arn" {
  description = "The execution ARN of the API Gateway"
  value       = module.api_gateway.api_execution_arn
}

