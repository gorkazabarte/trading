# GET /settings API Endpoint - Implementation Complete

## ✅ Summary

I've successfully created a complete AWS Lambda function and API Gateway endpoint to retrieve settings from S3.

## 📁 Files Created

### 1. Lambda Function Code
**File:** `/Users/gzabarte/Repos/GZabarte/app/trading/lambda_get_settings/lambda_function.py`

**Features:**
- ✅ Retrieves `settings.json` from S3 bucket
- ✅ Returns JSON response for API Gateway
- ✅ CORS enabled (Access-Control-Allow-Origin: *)
- ✅ Proper error handling (404 if file not found, 500 for server errors)
- ✅ OPTIONS method support for CORS preflight
- ✅ Environment variable support for S3_BUCKET and S3_KEY

**Response Format:**
```json
{
  "stopLoss": 2,
  "takeProfit": 5,
  "nextInvestment": 1000,
  "opsPerDay": 5
}
```

### 2. Dockerfile
**File:** `/Users/gzabarte/Repos/GZabarte/app/trading/lambda_get_settings/Dockerfile`

- Uses Python 3.13 Lambda base image
- Installs boto3 for S3 access

### 3. Requirements
**File:** `/Users/gzabarte/Repos/GZabarte/app/trading/lambda_get_settings/requirements.txt`

- boto3 (AWS SDK for Python)

## 🔧 Infrastructure Changes

### Lambda Module (`deploy/app/modules/lambda/main.tf`)

**Added:**
1. ✅ IAM Policy: `lambda_policy_get_settings`
   - Allows S3 GetObject on `settings.json`
   
2. ✅ Lambda Function: `lambda_function_get_settings`
   - Function name: `dev-trading-get-settings`
   - Memory: 256 MB
   - Timeout: 30 seconds
   - Container image from ECR
   
3. ✅ Lambda Permission: API Gateway can invoke the function

**Updated:** `deploy/app/modules/lambda/outputs.tf`
- Added outputs for ARN, name, and invoke ARN of get_settings Lambda

### API Gateway Module (`deploy/app/modules/api/main.tf`)

**Added:**
- ✅ Route: `GET /settings`
  - Integrates with `lambda_get_settings`
  - Timeout: 30 seconds
  - Payload format: 2.0

**Updated Files:**
- `deploy/app/modules/api/variables.tf` - Added variables for Lambda ARN and name
- `deploy/app/modules/api/terragrunt.hcl` - Added dependency outputs

## 🚀 API Endpoint

### Endpoint URL
```
GET https://{api-gateway-url}/settings
```

### Request
```bash
curl -X GET https://your-api-gateway-url/settings
```

### Response (200 OK)
```json
{
  "stopLoss": 2,
  "takeProfit": 5,
  "nextInvestment": 1000,
  "opsPerDay": 5
}
```

### Error Response (404 Not Found)
```json
{
  "error": "Settings file not found",
  "message": "s3://dev-trading-data-storage/settings.json does not exist"
}
```

### Error Response (500 Internal Server Error)
```json
{
  "error": "Internal server error",
  "message": "Error details here"
}
```

## 📊 API Routes Overview

Your API now has the following endpoints:

| Method | Path | Lambda Function | Description |
|--------|------|----------------|-------------|
| GET | `/calendar/{year}/{month}/{day}` | get-calendar | Get calendar data |
| GET | `/positions` | get-positions | Get open positions |
| **GET** | **/settings** | **get-settings** | **Get trading settings** ✨ NEW |
| POST | `/companies` | select-companies | Select companies |
| POST | `/settings` | update-settings | Update settings |

## 🔐 IAM Permissions

The Lambda function has permissions to:
- ✅ Read `settings.json` from S3 bucket `dev-trading-data-storage`
- ❌ NO write permissions (read-only)
- ❌ NO other S3 objects accessible

## 🧪 Testing

### Test Locally (if you want)
```python
# test_get_settings.py
import json

# Simulate API Gateway event
event = {
    "httpMethod": "GET"
}

# Import and test
from lambda_get_settings.lambda_function import lambda_handler
response = lambda_handler(event, None)

print(json.dumps(response, indent=2))
```

### Test via API Gateway (after deployment)
```bash
# GET request
curl -X GET https://your-api-gateway-url/settings

# With headers
curl -X GET https://your-api-gateway-url/settings \
  -H "Content-Type: application/json"
```

## 📦 Deployment Steps

To deploy this new Lambda and API endpoint:

### 1. Build and Push Docker Image
```bash
cd lambda_get_settings

# Build
docker build -t dev-trading-get-settings .

# Tag
docker tag dev-trading-get-settings:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com/dev-trading-get-settings:latest

# Push to ECR
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.us-west-2.amazonaws.com/dev-trading-get-settings:latest
```

### 2. Deploy Infrastructure
```bash
cd deploy/app/modules/lambda
terragrunt apply

cd ../api
terragrunt apply
```

## ✅ Validation Checklist

After deployment, verify:
- [ ] Lambda function exists: `dev-trading-get-settings`
- [ ] Lambda has IAM role with S3 read permissions
- [ ] API Gateway route exists: `GET /settings`
- [ ] API Gateway integration points to Lambda
- [ ] Lambda permission allows API Gateway invocation
- [ ] Test GET request returns settings JSON
- [ ] CORS headers are present in response
- [ ] 404 error when file doesn't exist
- [ ] 500 error for S3 exceptions

## 🎯 Benefits

✅ **Read-only access** - Safe, can't modify settings
✅ **Fast response** - 30 second timeout (quick S3 read)
✅ **CORS enabled** - Can be called from web frontends
✅ **Error handling** - Proper HTTP status codes
✅ **Separate from POST** - GET for reading, POST for writing
✅ **Consistent with existing API** - Follows same patterns

Your GET /settings endpoint is now ready to deploy and use! 🎉

