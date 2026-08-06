$REGION = "us-east-1"
$STACK_NAME = "flight-tracker-gen3"
$ECR_REPO = "flight-tracker-searcher"
$PRICE_QUEUE = "flight-tracker-price-events"
$NOTIF_QUEUE = "flight-tracker-notifications"

$REPO_ROOT = Split-Path $PSScriptRoot -Parent
$secretsFile = Join-Path $PSScriptRoot "secrets.ps1"

if (Test-Path $secretsFile) {
    Write-Host "Loading secrets from secrets.ps1"
    . $secretsFile
} else {
    Write-Host "secrets.ps1 not found. Copy secrets.ps1.example to secrets.ps1 and fill in your values, or enter them now."
    $SMTP_USER = Read-Host "SMTP username (Gmail address)"
    $secPass = Read-Host "SMTP password (app password)" -AsSecureString
    $SMTP_PASSWORD = [System.Net.NetworkCredential]::new("", $secPass).Password
    $SMTP_FROM = Read-Host "SMTP from address (leave blank to use SMTP username)"
    if (-not $SMTP_FROM) { $SMTP_FROM = $SMTP_USER }
    $FLASK_SECRET_KEY = Read-Host "Flask secret key (any random string)"
}

Write-Host "Checking AWS credentials..."
$ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
if ($LASTEXITCODE -ne 0) { Write-Error "AWS CLI auth failed. Run 'aws configure' first."; exit 1 }

$ECR_REGISTRY = "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
$IMAGE_URI = "${ECR_REGISTRY}/${ECR_REPO}:latest"
$FRONTEND_BUCKET = "flight-tracker-frontend-$ACCOUNT_ID"

Write-Host ""
Write-Host "Account:  $ACCOUNT_ID"
Write-Host "Region:   $REGION"
Write-Host "Bucket:   $FRONTEND_BUCKET"
Write-Host "Image:    $IMAGE_URI"
Write-Host ""

# ECR
Write-Host "--- ECR ---"
aws ecr describe-repositories --repository-names $ECR_REPO --region $REGION 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating ECR repo $ECR_REPO..."
    aws ecr create-repository --repository-name $ECR_REPO --region $REGION | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create ECR repo"; exit 1 }
} else {
    Write-Host "$ECR_REPO already exists, skipping."
}

# DynamoDB
Write-Host ""
Write-Host "--- DynamoDB ---"

Write-Host "Checking monitoring_requests..."
aws dynamodb describe-table --table-name monitoring_requests --region $REGION 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating monitoring_requests..."
    aws dynamodb create-table `
        --table-name monitoring_requests `
        --attribute-definitions AttributeName=user_id,AttributeType=S AttributeName=request_id,AttributeType=S `
        --key-schema AttributeName=user_id,KeyType=HASH AttributeName=request_id,KeyType=RANGE `
        --billing-mode PAY_PER_REQUEST `
        --region $REGION | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create monitoring_requests"; exit 1 }
} else {
    Write-Host "monitoring_requests already exists, skipping."
}

Write-Host "Checking price_history..."
aws dynamodb describe-table --table-name price_history --region $REGION 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating price_history..."
    aws dynamodb create-table `
        --table-name price_history `
        --attribute-definitions AttributeName=route_key,AttributeType=S `
        --key-schema AttributeName=route_key,KeyType=HASH `
        --billing-mode PAY_PER_REQUEST `
        --region $REGION | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create price_history"; exit 1 }
} else {
    Write-Host "price_history already exists, skipping."
}

Write-Host "Checking notification_history..."
aws dynamodb describe-table --table-name notification_history --region $REGION 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating notification_history..."
    aws dynamodb create-table `
        --table-name notification_history `
        --attribute-definitions AttributeName=route_key,AttributeType=S AttributeName=sent_at,AttributeType=S `
        --key-schema AttributeName=route_key,KeyType=HASH AttributeName=sent_at,KeyType=RANGE `
        --billing-mode PAY_PER_REQUEST `
        --region $REGION | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create notification_history"; exit 1 }
} else {
    Write-Host "notification_history already exists, skipping."
}

# SQS
Write-Host ""
Write-Host "--- SQS ---"

Write-Host "Checking $PRICE_QUEUE..."
aws sqs get-queue-url --queue-name $PRICE_QUEUE --region $REGION 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating $PRICE_QUEUE..."
    aws sqs create-queue --queue-name $PRICE_QUEUE --attributes VisibilityTimeout=600 --region $REGION | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create $PRICE_QUEUE"; exit 1 }
} else {
    Write-Host "$PRICE_QUEUE already exists, skipping."
}

Write-Host "Checking $NOTIF_QUEUE..."
aws sqs get-queue-url --queue-name $NOTIF_QUEUE --region $REGION 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating $NOTIF_QUEUE..."
    aws sqs create-queue --queue-name $NOTIF_QUEUE --attributes VisibilityTimeout=60 --region $REGION | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create $NOTIF_QUEUE"; exit 1 }
} else {
    Write-Host "$NOTIF_QUEUE already exists, skipping."
}

# S3 frontend bucket
Write-Host ""
Write-Host "--- S3 Frontend Bucket ---"

aws s3api head-bucket --bucket $FRONTEND_BUCKET 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating bucket $FRONTEND_BUCKET..."
    if ($REGION -eq "us-east-1") {
        aws s3api create-bucket --bucket $FRONTEND_BUCKET --region $REGION | Out-Null
    } else {
        aws s3api create-bucket --bucket $FRONTEND_BUCKET --region $REGION `
            --create-bucket-configuration LocationConstraint=$REGION | Out-Null
    }
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create S3 bucket"; exit 1 }

    aws s3api put-public-access-block --bucket $FRONTEND_BUCKET `
        --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false" | Out-Null

    $policyJson = "{`"Version`":`"2012-10-17`",`"Statement`":[{`"Effect`":`"Allow`",`"Principal`":`"*`",`"Action`":`"s3:GetObject`",`"Resource`":`"arn:aws:s3:::${FRONTEND_BUCKET}/*`"}]}"
    $policyFile = [System.IO.Path]::GetTempFileName()
    [System.IO.File]::WriteAllText($policyFile, $policyJson)
    aws s3api put-bucket-policy --bucket $FRONTEND_BUCKET --policy "file://$policyFile" | Out-Null
    Remove-Item $policyFile

    aws s3api put-bucket-website --bucket $FRONTEND_BUCKET `
        --website-configuration '{"IndexDocument":{"Suffix":"index.html"},"ErrorDocument":{"Key":"index.html"}}' | Out-Null

    Write-Host "Bucket created and configured for static website hosting."
} else {
    Write-Host "$FRONTEND_BUCKET already exists, skipping."
}

# Docker: build and push flight-searcher
Write-Host ""
Write-Host "--- Docker: flight-searcher ---"

Write-Host "Authenticating with ECR..."
$ecrToken = aws ecr get-login-password --region $REGION
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to get ECR token"; exit 1 }

$dockerConfigDir = Join-Path $env:TEMP "docker-ecr-$PID"
New-Item -ItemType Directory -Force -Path $dockerConfigDir | Out-Null
$b64Auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("AWS:$ecrToken"))
$authJson = '{"auths":{"' + $ECR_REGISTRY + '":{"auth":"' + $b64Auth + '"}}}'
[System.IO.File]::WriteAllText((Join-Path $dockerConfigDir "config.json"), $authJson)
Write-Host "ECR auth configured."

Write-Host "Building flight-searcher image..."
docker build -t $IMAGE_URI "$REPO_ROOT\lambda\flight_searcher"
if ($LASTEXITCODE -ne 0) { Write-Error "Docker build failed"; exit 1 }

Write-Host "Pushing image to ECR..."
$env:DOCKER_CONFIG = $dockerConfigDir
docker push $IMAGE_URI
$env:DOCKER_CONFIG = $null
Remove-Item -Recurse -Force $dockerConfigDir
if ($LASTEXITCODE -ne 0) { Write-Error "Docker push failed"; exit 1 }

# SAM build and deploy
Write-Host ""
Write-Host "--- SAM Build & Deploy ---"

Push-Location $REPO_ROOT
try {
    Write-Host "Running sam build..."
    sam build
    if ($LASTEXITCODE -ne 0) { Write-Error "sam build failed"; exit 1 }

    Write-Host "Resolving SQS queue details..."
    $PRICE_EVENTS_URL = aws sqs get-queue-url --queue-name $PRICE_QUEUE --query QueueUrl --output text --region $REGION
    $PRICE_EVENTS_ARN = aws sqs get-queue-attributes --queue-url $PRICE_EVENTS_URL --attribute-names QueueArn --query Attributes.QueueArn --output text --region $REGION
    $NOTIF_URL = aws sqs get-queue-url --queue-name $NOTIF_QUEUE --query QueueUrl --output text --region $REGION
    $NOTIF_ARN = aws sqs get-queue-attributes --queue-url $NOTIF_URL --attribute-names QueueArn --query Attributes.QueueArn --output text --region $REGION

    Write-Host "Running sam deploy..."
    $samArgs = @(
        "deploy",
        "--stack-name", $STACK_NAME,
        "--region", $REGION,
        "--resolve-s3",
        "--capabilities", "CAPABILITY_IAM", "CAPABILITY_NAMED_IAM",
        "--no-confirm-changeset",
        "--no-fail-on-empty-changeset",
        "--parameter-overrides",
        "SmtpUser=$SMTP_USER",
        "SmtpPassword=$SMTP_PASSWORD",
        "SmtpFrom=$SMTP_FROM",
        "FlaskSecretKey=$FLASK_SECRET_KEY",
        "FlightSearcherImageUri=$IMAGE_URI",
        "PriceEventsQueueUrl=$PRICE_EVENTS_URL",
        "PriceEventsQueueArn=$PRICE_EVENTS_ARN",
        "NotificationQueueUrl=$NOTIF_URL",
        "NotificationQueueArn=$NOTIF_ARN"
    )
    & sam @samArgs
    if ($LASTEXITCODE -ne 0) { Write-Error "sam deploy failed"; exit 1 }

    Write-Host "Getting API URL from CloudFormation outputs..."
    $API_URL = aws cloudformation describe-stacks `
        --stack-name $STACK_NAME `
        --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" `
        --output text `
        --region $REGION
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to get API URL"; exit 1 }

    Write-Host "Injecting API URL and syncing frontend to S3..."
    $tempFrontend = Join-Path $env:TEMP "flight-tracker-frontend-deploy"
    if (Test-Path $tempFrontend) { Remove-Item -Recurse -Force $tempFrontend }
    New-Item -ItemType Directory -Path $tempFrontend | Out-Null
    Copy-Item -Path "$REPO_ROOT\frontend\*" -Destination $tempFrontend -Recurse

    (Get-Content "$tempFrontend\config.js") -replace "__API_URL__", $API_URL | Set-Content "$tempFrontend\config.js"

    aws s3 sync $tempFrontend "s3://$FRONTEND_BUCKET/" --delete
    if ($LASTEXITCODE -ne 0) { Write-Error "S3 sync failed"; exit 1 }
    Remove-Item -Recurse -Force $tempFrontend

} finally {
    Pop-Location
}

$WEBSITE_URL = "http://${FRONTEND_BUCKET}.s3-website-${REGION}.amazonaws.com"

Write-Host ""
Write-Host "============================================"
Write-Host " Deployment complete!"
Write-Host "============================================"
Write-Host " API URL:    $API_URL"
Write-Host " Frontend:   $WEBSITE_URL"
Write-Host ""
Write-Host " Add these as GitHub Actions repository secrets:"
Write-Host "   FRONTEND_BUCKET = $FRONTEND_BUCKET"
Write-Host "   AWS_ACCOUNT_ID  = $ACCOUNT_ID"
Write-Host "============================================"
