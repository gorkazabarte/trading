#!/bin/bash

# Script to create day subfolders (01-31) in an S3 bucket path
# Usage: ./create_s3_day_folders.sh <s3-bucket> <year> <month>
# Example: ./create_s3_day_folders.sh dev-trading-data-storage 2025 12

set -e

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <s3-bucket> <year> <month>"
    echo "Example: $0 dev-trading-data-storage 2025 12"
    exit 1
fi

S3_BUCKET=$1
YEAR=$2
MONTH=$(printf "%02d" $3)

echo "=================================================="
echo "Creating day folders in S3"
echo "=================================================="
echo "Bucket: s3://${S3_BUCKET}"
echo "Path: ${YEAR}/${MONTH}/"
echo "Folders: 01 to 31"
echo "=================================================="
echo ""

for day in {1..31}; do
    DAY=$(printf "%02d" $day)
    S3_PATH="s3://${S3_BUCKET}/${YEAR}/${MONTH}/${DAY}/"

    echo "Creating: ${S3_PATH}"

    aws s3api put-object \
        --bucket "${S3_BUCKET}" \
        --key "${YEAR}/${MONTH}/${DAY}/" \
        --content-length 0

    if [ $? -eq 0 ]; then
        echo "✓ Created ${S3_PATH}"
    else
        echo "✗ Failed to create ${S3_PATH}"
    fi
done

echo ""
echo "=================================================="
echo "Completed!"
echo "=================================================="
echo ""
echo "Verify with:"
echo "aws s3 ls s3://${S3_BUCKET}/${YEAR}/${MONTH}/"

