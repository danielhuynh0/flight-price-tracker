$CLUSTER_NAME  = "flight-tracker-cluster"
$NODEGROUP     = "flight-tracker-nodes"
$REGION        = "us-east-1"

Write-Host ""
Write-Host "This will DELETE:" -ForegroundColor Yellow
Write-Host "  - EKS node group: $NODEGROUP"
Write-Host "  - EKS cluster:    $CLUSTER_NAME"
Write-Host ""
Write-Host "DynamoDB tables, SQS queues, ECR repos, and IAM roles will be KEPT." -ForegroundColor Green
Write-Host ""

$confirm = Read-Host "Type 'yes' to proceed"
if ($confirm -ne "yes") {
    Write-Host "Aborted." -ForegroundColor Red
    exit 0
}

# Step 1: Delete namespace to clean up load balancers
Write-Host ""
Write-Host "[1/4] Deleting Kubernetes namespace (cleans up load balancer)..." -ForegroundColor Cyan

$kubeconfigResult = aws eks update-kubeconfig --name $CLUSTER_NAME --region $REGION 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Could not reach cluster - skipping namespace deletion." -ForegroundColor DarkYellow
    Write-Host "  WARNING: Load balancer may need manual cleanup in EC2 console." -ForegroundColor Yellow
} else {
    kubectl delete namespace flight-tracker --timeout=90s 2>&1
    Write-Host "  Namespace deleted. Waiting 60s for load balancer cleanup..."
    Start-Sleep -Seconds 60
}

# Step 2: Delete node group
Write-Host ""
Write-Host "[2/4] Deleting node group: $NODEGROUP ..." -ForegroundColor Cyan

$ngResult = aws eks delete-nodegroup --cluster-name $CLUSTER_NAME --nodegroup-name $NODEGROUP --region $REGION 2>&1
$ngExitCode = $LASTEXITCODE

if ($ngExitCode -ne 0) {
    Write-Host "  Node group not found or already deleted. Continuing..." -ForegroundColor DarkYellow
} else {
    Write-Host "  Delete initiated. Waiting for removal (3-5 min)..."

    while ($true) {
        $ngStatus = aws eks describe-nodegroup --cluster-name $CLUSTER_NAME --nodegroup-name $NODEGROUP --query "nodegroup.status" --output text --region $REGION 2>&1
        $ngCheckExit = $LASTEXITCODE

        if ($ngCheckExit -ne 0) {
            Write-Host "  Node group deleted." -ForegroundColor Green
            break
        }

        Write-Host "  Status: $ngStatus - waiting 30s..."
        Start-Sleep -Seconds 30
    }
}

# Step 3: Delete EKS cluster
Write-Host ""
Write-Host "[3/4] Deleting EKS cluster: $CLUSTER_NAME ..." -ForegroundColor Cyan

$clResult = aws eks delete-cluster --name $CLUSTER_NAME --region $REGION 2>&1
$clExitCode = $LASTEXITCODE

if ($clExitCode -ne 0) {
    Write-Host "  Cluster not found or already deleted. Continuing..." -ForegroundColor DarkYellow
    Write-Host "  Output: $clResult" -ForegroundColor DarkGray
} else {
    Write-Host "  Delete initiated. Waiting for removal (5-10 min)..."

    while ($true) {
        $clStatus = aws eks describe-cluster --name $CLUSTER_NAME --query "cluster.status" --output text --region $REGION 2>&1
        $clCheckExit = $LASTEXITCODE

        if ($clCheckExit -ne 0) {
            Write-Host "  Cluster deleted." -ForegroundColor Green
            break
        }

        Write-Host "  Status: $clStatus - waiting 30s..."
        Start-Sleep -Seconds 30
    }
}

# Step 4: Summary
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Infrastructure torn down." -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "DELETED:"
Write-Host "  - EKS cluster: $CLUSTER_NAME"
Write-Host "  - EKS node group: $NODEGROUP"
Write-Host "  - EC2 worker nodes"
Write-Host "  - Load balancer"
Write-Host ""
Write-Host "KEPT (free when idle):"
Write-Host "  - ECR repositories"
Write-Host "  - DynamoDB tables"
Write-Host "  - SQS queues"
Write-Host "  - IAM roles"
Write-Host ""
Write-Host "Run .\scripts\infra-up.ps1 to spin back up." -ForegroundColor Cyan
