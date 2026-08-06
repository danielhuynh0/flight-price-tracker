$REGION = "us-east-1"
$STACK_NAME = "flight-tracker-gen3"

Write-Host "Checking AWS credentials..."
$ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
if ($LASTEXITCODE -ne 0) { Write-Error "AWS CLI auth failed. Run 'aws configure' first."; exit 1 }

$FRONTEND_BUCKET = "flight-tracker-frontend-$ACCOUNT_ID"

Write-Host ""
Write-Host "This will delete:"
Write-Host "  CloudFormation stack: $STACK_NAME"
Write-Host "    (removes Lambda functions, API Gateway, EventBridge schedule, IAM role)"
Write-Host "  S3 bucket: $FRONTEND_BUCKET"
Write-Host ""
Write-Host "These will be kept (free when idle):"
Write-Host "  ECR repository:  flight-tracker-searcher"
Write-Host "  DynamoDB tables: monitoring_requests, price_history, notification_history"
Write-Host "  SQS queues:      flight-tracker-price-events, flight-tracker-notifications"
Write-Host ""
$confirm = Read-Host "Type 'yes' to proceed"
if ($confirm -ne "yes") { Write-Host "Aborted."; exit 0 }

# Delete CloudFormation stack
Write-Host ""
Write-Host "--- Deleting CloudFormation stack $STACK_NAME ---"
aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Stack $STACK_NAME not found, skipping."
} else {
    aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to initiate stack deletion"; exit 1 }
    Write-Host "Waiting for stack deletion (this can take 2-5 minutes)..."
    aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: Stack deletion timed out or failed. Check the AWS Console for status."
    } else {
        Write-Host "Stack deleted."
    }
}

# Empty and delete S3 frontend bucket
Write-Host ""
Write-Host "--- Deleting S3 bucket $FRONTEND_BUCKET ---"
aws s3api head-bucket --bucket $FRONTEND_BUCKET 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Bucket $FRONTEND_BUCKET not found, skipping."
} else {
    Write-Host "Emptying bucket..."
    aws s3 rm "s3://$FRONTEND_BUCKET" --recursive
    Write-Host "Deleting bucket..."
    aws s3api delete-bucket --bucket $FRONTEND_BUCKET --region $REGION
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: Failed to delete bucket. Check the AWS Console."
    } else {
        Write-Host "Bucket deleted."
    }
}

Write-Host ""
Write-Host "============================================"
Write-Host " Teardown complete."
Write-Host " ECR, DynamoDB, and SQS were kept."
Write-Host " Run infra-up-gen3.ps1 to redeploy."
Write-Host "============================================"
