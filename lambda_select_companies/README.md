# Lambda Select Companies - Test Examples

## API Gateway Request Format

### POST Request Body
```json
{
  "companies": ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
}
```

### Example with curl
```bash
curl -X POST https://your-api-gateway-url/select-companies \
  -H "Content-Type: application/json" \
  -d '{
    "companies": ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
  }'
```

### Expected Success Response (200)
```json
{
  "message": "Companies list uploaded successfully",
  "s3_bucket": "your-bucket-name",
  "s3_key": "2025/12/selected_companies_20251211_143022.txt",
  "companies_count": 5,
  "timestamp": "20251211_143022"
}
```

### Error Responses

#### Missing companies field (400)
```json
{
  "error": "Missing required field: 'companies'"
}
```

#### Empty companies array (400)
```json
{
  "error": "'companies' array cannot be empty"
}
```

#### Invalid companies type (400)
```json
{
  "error": "'companies' must be an array"
}
```

#### Internal Server Error (500)
```json
{
  "error": "Internal server error",
  "message": "Detailed error message"
}
```

## S3 Output Format

The function creates a text file in S3 with the following structure:
- **Path**: `{year}/{month}/selected_companies_{timestamp}.txt`
- **Format**: One ticker symbol per line

Example file content:
```
AAPL
GOOGL
MSFT
TSLA
AMZN
```

## Environment Variables Required

- `S3_BUCKET`: The name of the S3 bucket where the txt files will be stored

## Local Testing

To test locally, you can invoke the Lambda function with a test event:

```python
from lambda_function import lambda_handler

# Direct invocation (bypassing API Gateway)
event = {
    "companies": ["AAPL", "GOOGL", "MSFT"]
}
result = lambda_handler(event, None)
print(result)

# Simulating API Gateway invocation
api_gateway_event = {
    "httpMethod": "POST",
    "body": '{"companies": ["AAPL", "GOOGL", "MSFT"]}'
}
result = lambda_handler(api_gateway_event, None)
print(result)
```

## CORS Configuration

The function includes CORS headers to allow cross-origin requests:
- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: POST, OPTIONS, GET`
- `Access-Control-Allow-Headers: Content-Type, Authorization, X-Requested-With`

The function handles OPTIONS preflight requests automatically.

