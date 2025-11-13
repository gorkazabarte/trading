echo "Deploy"#!/bin/bash
set -e

echo "[INFO] ${APP_NAME} deployment is starting"
cd ./deploy/app || exit

echo "[INFO] Deploying infrastructure: ${APP_NAME} in environment: ${ENVIRONMENT}"
terragrunt --log-level=trace --non-interactive stack generate
terragrunt --log-level=trace --non-interactive stack run apply
