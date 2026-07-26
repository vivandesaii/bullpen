#!/bin/bash
# Runs automatically when LocalStack is ready
# Creates SQS queues and S3 bucket to match .env

echo "Creating SQS queues..."
awslocal sqs create-queue \
    --queue-name bullpen-trades-dev.fifo \
    --attributes FifoQueue=true,ContentBasedDeduplication=false \
    --region ca-central-1

awslocal sqs create-queue \
    --queue-name bullpen-trades-dev-dlq.fifo \
    --attributes FifoQueue=true,ContentBasedDeduplication=false \
    --region ca-central-1

echo "Creating S3 bucket..."
awslocal s3 mb s3://bullpen-documents-dev --region ca-central-1

echo "LocalStack init complete."