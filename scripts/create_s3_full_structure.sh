#!/bin/bash

# Script to create year/month/day folder structure in S3 bucket
# Usage: ./create_s3_full_structure.sh <s3-bucket> <start-year> <end-year>
# Example: ./create_s3_full_structure.sh dev-trading-data-storage 2026 2028

set -e

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <s3-bucket> <start-year> <end-year>"
    echo "Example: $0 dev-trading-data-storage 2026 2028"
    exit 1
fi

S3_BUCKET=$1
START_YEAR=$2
END_YEAR=$3

echo "=========================================================="
echo "Creating full folder structure in S3"
echo "=========================================================="
echo "Bucket: s3://${S3_BUCKET}"
echo "Years: ${START_YEAR} to ${END_YEAR}"
echo "Months: 01 to 12 (for each year)"
echo "Days: 01 to 31 (for each month)"
echo "=========================================================="
echo ""

total_folders=0
success_count=0
failed_count=0

for year in $(seq ${START_YEAR} ${END_YEAR}); do
    echo "Processing year: ${year}"
    echo "-------------------"

    for month in {1..12}; do
        MONTH=$(printf "%02d" $month)
        echo "  Month: ${MONTH}"

        for day in {1..31}; do
            DAY=$(printf "%02d" $day)
            S3_PATH="s3://${S3_BUCKET}/${year}/${MONTH}/${DAY}/"

            total_folders=$((total_folders + 1))

            aws s3api put-object \
                --bucket "${S3_BUCKET}" \
                --key "${year}/${MONTH}/${DAY}/" \
                --content-length 0 > /dev/null 2>&1

            if [ $? -eq 0 ]; then
                echo "    ✓ Created ${year}/${MONTH}/${DAY}/"
                success_count=$((success_count + 1))
            else
                echo "    ✗ Failed ${year}/${MONTH}/${DAY}/"
                failed_count=$((failed_count + 1))
            fi
        done
    done
    echo ""
done

echo "=========================================================="
echo "Completed!"
echo "=========================================================="
echo "Total folders processed: ${total_folders}"
echo "Successfully created: ${success_count}"
echo "Failed: ${failed_count}"
echo ""
echo "Verify with:"
echo "aws s3 ls s3://${S3_BUCKET}/"
echo "aws s3 ls s3://${S3_BUCKET}/${START_YEAR}/"
echo "aws s3 ls s3://${S3_BUCKET}/${START_YEAR}/01/"

