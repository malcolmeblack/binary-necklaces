#!/usr/bin/env bash
set -euo pipefail

: "${BNCT_CALC_FUNCTION:?Set BNCT_CALC_FUNCTION to the calculator Lambda function name}"
: "${BNCT_TESS_FUNCTION:?Set BNCT_TESS_FUNCTION to the tessellator Lambda function name}"
: "${BNCT_PUBLIC_BUCKET:?Set BNCT_PUBLIC_BUCKET to the public S3 bucket name}"
: "${BNCT_DISTRIBUTION:?Set BNCT_DISTRIBUTION to the CloudFront distribution ID}"

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Building Lambda packages..."
python3 "$DIR/build.py" --python-version 3.12 --architecture x86_64

echo "Deploying calculator Lambda..."
aws lambda update-function-code --function-name "$BNCT_CALC_FUNCTION" \
  --zip-file "fileb://$DIR/dist/calculator-lambda.zip" \
  --query 'FunctionName' --output text

echo "Deploying tessellator Lambda..."
aws lambda update-function-code --function-name "$BNCT_TESS_FUNCTION" \
  --zip-file "fileb://$DIR/dist/tessellator-lambda.zip" \
  --query 'FunctionName' --output text

echo "Uploading frontend to S3..."
aws s3 cp "$DIR/BNCT.html" "s3://$BNCT_PUBLIC_BUCKET/binary-necklaces/BNCT.html" \
  --content-type "text/html; charset=utf-8"

echo "Invalidating CloudFront cache..."
aws cloudfront create-invalidation --distribution-id "$BNCT_DISTRIBUTION" \
  --paths '/binary-necklaces/BNCT.html' \
  --query 'Invalidation.Id' --output text

echo "Done."
