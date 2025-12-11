output "api_gateway_url" {
  description = "The URL of the API Gateway"
  value       = module.api_gateway.default_apigatewayv2_stage_invoke_url
}

output "api_gateway_id" {
  description = "The ID of the API Gateway"
  value       = module.api_gateway.apigatewayv2_api_id
}

output "api_gateway_arn" {
  description = "The ARN of the API Gateway"
  value       = module.api_gateway.apigatewayv2_api_arn
}

output "api_gateway_execution_arn" {
  description = "The execution ARN of the API Gateway"
  value       = module.api_gateway.apigatewayv2_api_execution_arn
}

