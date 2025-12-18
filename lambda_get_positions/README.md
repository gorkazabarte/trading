# Lambda Get Positions

## Overview
This AWS Lambda function retrieves the current position data from S3.

## API Endpoint
`GET /positions`

## Request Format

**No body parameters required** - Simply call the GET endpoint.

## Response Format

### Success (200)
```json
{
  "count": 2,
  "positions": {
    "AEVA": {
      "ticker": "AEVA",
      "conid": 690184960,
      "quantity": 2.0,
      "average_price": 13.52315,
      "market_price": 13.20353985,
      "market_value": 26.41,
      "unrealized_pnl": -0.64,
      "currency": "USD",
      "timestamp": "2025-12-18T14:53:54.977799+00:00",
      "date": "2025-12-18"
    },
    "TSLA": {
      "ticker": "TSLA",
      "conid": 76792991,
      "quantity": 5.0,
      "average_price": 250.00,
      "market_price": 248.00,
      "market_value": 1240.00,
      "unrealized_pnl": -10.00,
      "currency": "USD",
      "timestamp": "2025-12-18T14:53:54.977799+00:00",
      "date": "2025-12-18"
    }
  }
}
```

### Error Responses

**404 - Not Found** (No positions file)
```json
{
  "error": "No positions file found"
}
```

**500 - Internal Server Error**
```json
{
  "error": "Internal server error: <details>"
}
```

## Environment Variables

- `S3_BUCKET` (default: `dev-trading-data-storage`) - S3 bucket containing position file

## S3 File Structure

The Lambda fetches the file from:
```
s3://{S3_BUCKET}/positions.json
```

Example:
```
s3://dev-trading-data-storage/positions.json
```

This file is continuously updated by the trading application with the latest position data.

## Position File Format

Each position in the JSON file contains:
- `ticker` - Stock symbol
- `conid` - IBKR contract ID
- `quantity` - Number of shares
- `average_price` - Average purchase price
- `market_price` - Current market price
- `market_value` - Total position value
- `unrealized_pnl` - Unrealized profit/loss
- `currency` - Trading currency
- `timestamp` - Last update timestamp (ISO 8601)
- `date` - Trading date

## Example Usage

### Using curl
```bash
curl https://your-api-gateway-url/positions
```

### Using Python
```python
import requests

response = requests.get('https://your-api-gateway-url/positions')
data = response.json()

print(f"Found {data['count']} position(s)")
for ticker, position in data['positions'].items():
    print(f"{ticker}: {position['quantity']} shares, P/L: ${position['unrealized_pnl']:.2f}")
```

### Using JavaScript (fetch)
```javascript
fetch('https://your-api-gateway-url/positions')
  .then(response => response.json())
  .then(data => {
    console.log(`Found ${data.count} position(s)`);
    Object.entries(data.positions).forEach(([ticker, position]) => {
      console.log(`${ticker}: ${position.quantity} shares, P/L: $${position.unrealized_pnl}`);
    });
  });
```

## Deployment

The Lambda is deployed as a Docker container using the included Dockerfile.

### Build Image
```bash
docker build -t lambda-get-positions .
```

### Test Locally
```bash
docker run -p 9000:8080 lambda-get-positions

# In another terminal
curl "http://localhost:9000/2015-03-31/functions/function/invocations"
```

## IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::dev-trading-data-storage/positions.json"
    }
  ]
}
```

## Integration

The trading application continuously updates the positions.json file in S3:
1. Fetches positions from IBKR every loop iteration
2. Saves to local file `./files/{year}/{month}/{day}/positions.json`
3. Uploads to S3 at `positions.json` (root folder)

The Lambda always returns the most current position data.

