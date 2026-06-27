# ============================================================================
# infra-down.ps1 — Tear down EKS cluster and nodes to stop billing
#
# What this DELETES (costs money when running):
#   - EKS node group (EC2 instances)
#   - EKS cluster (control plane)
#
# What this KEEPS (free or near-free when idle):
#   - ECR repositories (Docker images)
#   - DynamoDB tables (data preserved)
#   - SQS queues
#   - IAM roles
# ============================================================================

# --- Configuration (edit these if your names differ) ---
$CLUSTER_NAME  = "flight-tracker-cluster"
$NODEGROUP     = "flight-tracker-nodes"
$REGION        = "us-east-1"

# --- Confirmation ---
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

# --- Step 1: Delete the Kubernetes namespace (cleans up load balancers) ---
Write-Host ""
Write-Host "[1/4] Deleting Kubernetes namespace to clean up load balancers..." -ForegroundColor Cyan

# This may fail if kubeconfig is stale or cluster is already gone — that's fine
try {
    aws eks update-kubeconfig --name $CLUSTER_NAME --region $REGION 2>$null
    kubectl delete namespace flight-tracker --timeout=60s 2>$null
    Write-Host "  Namespace deleted. Waiting 30s for load balancer cleanup..."
    Start-Sleep -Seconds 30
} catch {
    Write-Host "  Skipped (cluster may not be reachable)." -ForegroundColor DarkYellow
}

# --- Step 2: Delete node group ---
Write-Host ""
Write-Host "[2/4] Deleting node group: $NODEGROUP ..." -ForegroundColor Cyan

aws eks delete-nodegroup `
    --cluster-name $CLUSTER_NAME `
    --nodegroup-name $NODEGROUP `
    --region $REGION 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Node group may already be deleted or not found. Continuing..." -ForegroundColor DarkYellow
} else {
    Write-Host "  Delete initiated. Waiting for node group to be fully removed..."
    Write-Host '  (This takes 3-5 minutes)' -ForegroundColor DarkGray

    while ($true) {
        $status = aws eks describe-nodegroup `
            --cluster-name $CLUSTER_NAME `
            --nodegroup-name $NODEGROUP `
            --query "nodegroup.status" `
            --output text `
            --region $REGION 2>$null

        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Node group deleted." -ForegroundColor Green
            break
        }

        Write-Host "  Status: $status — waiting 30s..."
        Start-Sleep -Seconds 30
    }
}

# --- Step 3: Delete EKS cluster ---
Write-Host ""
Write-Host "[3/4] Deleting EKS cluster: $CLUSTER_NAME ..." -ForegroundColor Cyan

aws eks delete-cluster --name $CLUSTER_NAME --region $REGION 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Cluster may already be deleted or not found. Continuing..." -ForegroundColor DarkYellow
} else {
    Write-Host "  Delete initiated. Waiting for cluster to be fully removed..."
    Write-Host '  (This takes 5-10 minutes)' -ForegroundColor DarkGray

    while ($true) {
        $status = aws eks describe-cluster `
            --name $CLUSTER_NAME `
            --query "cluster.status" `
            --output text `
            --region $REGION 2>$null

        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Cluster deleted." -ForegroundColor Green
            break
        }

        Write-Host "  Status: $status — waiting 30s..."
        Start-Sleep -Seconds 30
    }
}

# --- Step 4: Summary ---
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Infrastructure torn down successfully." -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "DELETED (no longer billing):"
Write-Host "  - EKS cluster:    $CLUSTER_NAME"
Write-Host "  - EKS node group: $NODEGROUP"
Write-Host "  - EC2 instances (worker nodes)"
Write-Host "  - Load balancer (from frontend Service)"
Write-Host ""
Write-Host "KEPT (free when idle):"
Write-Host "  - ECR repositories (Docker images)"
Write-Host "  - DynamoDB tables (monitoring_requests, price_history, notification_history)"
Write-Host "  - SQS queues (flight-tracker-price-events, flight-tracker-notifications)"
Write-Host "  - IAM roles (flight-tracker-eks-role, flight-tracker-node-role)"
Write-Host ""
Write-Host "Run .\scripts\infra-up.ps1 to spin everything back up." -ForegroundColor Cyan
