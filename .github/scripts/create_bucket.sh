#!/bin/bash
set -e

# ----- Create S3 backend for Terraform -----
echo "[INFO] Creating S3 bucket: ${BUCKET}"
if aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
  echo "[INFO] Bucket already exists: ${BUCKET}"
else
  aws s3api create-bucket \
    --bucket "${BUCKET}" \
    --region "us-west-2" \
    --create-bucket-configuration LocationConstraint="us-west-2"
  fi
echo "[INFO] Bucket created: ${BUCKET}"

# ----- Enabling versioning -----
echo "[INFO] Enabling versioning on the bucket"
aws s3api put-bucket-versioning \
  --bucket "${BUCKET}" \
  --versioning-configuration Status=Enabled

echo "[INFO] Backend ready with bucket: ${BUCKET}"
