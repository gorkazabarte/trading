#!/bin/bash

cd "${HOME}/App/trading" || exit 1

export AWS_ACCESS_KEY_ID=""
export AWS_SECRET_ACCESS_KEY=" "
export AWS_DEFAULT_REGION="us-west-2"
export IB_USE_TWS=false
export APP_PATH="${HOME}/App/trading"

if [ -z "$AWS_ACCESS_KEY_ID" ]; then
    echo "ERROR: AWS_ACCESS_KEY_ID is not set. Please edit this script and add your AWS credentials."
    echo "Edit: ${APP_PATH}/scripts/run_with_tws.sh"
    exit 1
fi

if [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "ERROR: AWS_SECRET_ACCESS_KEY is not set. Please edit this script and add your AWS credentials."
    echo "Edit: ${APP_PATH}/scripts/run_with_tws.sh"
    exit 1
fi

echo "AWS Credentials: Configured (Access Key: ${AWS_ACCESS_KEY_ID:0:8}...)"
echo "AWS Region: $AWS_DEFAULT_REGION"
echo "Configuration: IB_USE_TWS=$IB_USE_TWS"
echo ""

if [ -f "${APP_PATH}/venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source "${APP_PATH}/venv/bin/activate"
fi

echo "Starting trading application..."
python "${APP_PATH}/app.py"
