$CLUSTER_NAME  = "flight-tracker-cluster"
$NODEGROUP     = "flight-tracker-nodes"
$REGION        = "us-east-1"
$ACCOUNT_ID    = "627330319786"
$INSTANCE_TYPE = "t3.medium"
$NODE_MIN      = 2
$NODE_MAX      = 3
$NODE_DESIRED  = 2

$EKS_ROLE_ARN  = "arn:aws:iam::${ACCOUNT_ID}:role/flight-tracker-eks-role"
$NODE_ROLE_ARN = "arn:aws:iam::${ACCOUNT_ID}:role/flight-tracker-node-role"
$ECR_REGISTRY  = "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
$K8S_DIR       = "k8s"

# --- Preflight checks ---
Write-Host ""
Write-Host "Preflight checks..." -ForegroundColor Cyan

$missing = @()
if (-not (Get-Command aws -ErrorAction SilentlyContinue))       { $missing += "aws" }
if (-not (Get-Command kubectl -ErrorAction SilentlyContinue))    { $missing += "kubectl" }
if (-not (Get-Command istioctl -ErrorAction SilentlyContinue))   { $missing += "istioctl" }

if ($missing.Count -gt 0) {
    Write-Host "Missing required tools: $($missing -join ', ')" -ForegroundColor Red
    exit 1
}

$identity = aws sts get-caller-identity --query "Account" --output text 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "AWS credentials not configured. Run 'aws configure' first." -ForegroundColor Red
    exit 1
}
Write-Host "  AWS account: $identity" -ForegroundColor Green

# --- Check if cluster already exists ---
$clusterCheck = aws eks describe-cluster --name $CLUSTER_NAME --query "cluster.status" --output text --region $REGION 2>&1
$clusterExists = ($LASTEXITCODE -eq 0)

if ($clusterExists) {
    Write-Host "  Cluster already exists (status: $clusterCheck). Skipping cluster creation." -ForegroundColor Yellow
} else {
    Write-Host "  Cluster does not exist - will create." -ForegroundColor Green
}

# --- Step 1: Look up VPC networking ---
Write-Host ""
Write-Host "[1/7] Looking up VPC, subnets, and security group..." -ForegroundColor Cyan

$VPC_ID = aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text --region $REGION

if (-not $VPC_ID -or $VPC_ID -eq "None") {
    Write-Host "  No default VPC found." -ForegroundColor Red
    exit 1
}
Write-Host "  VPC: $VPC_ID"

$SUBNETS = aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query "Subnets[*].SubnetId" --output text --region $REGION
$SUBNET_LIST = $SUBNETS -split "\s+"

if ($SUBNET_LIST.Count -lt 2) {
    Write-Host "  Need at least 2 subnets, found $($SUBNET_LIST.Count)." -ForegroundColor Red
    exit 1
}

$SUBNET_CSV = ($SUBNET_LIST[0..1]) -join ","
$sub0 = $SUBNET_LIST[0]
$sub1 = $SUBNET_LIST[1]
Write-Host "  Subnets: $SUBNET_CSV"

$SG_ID = aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=default" --query "SecurityGroups[0].GroupId" --output text --region $REGION
Write-Host "  Security group: $SG_ID"

# --- Step 2: Create EKS cluster (skip if exists) ---
Write-Host ""
Write-Host "[2/7] EKS cluster..." -ForegroundColor Cyan

if ($clusterExists) {
    Write-Host "  Already exists - skipping." -ForegroundColor Yellow
} else {
    Write-Host "  Creating cluster (10-15 min)..."

    $createResult = aws eks create-cluster --name $CLUSTER_NAME --role-arn $EKS_ROLE_ARN --resources-vpc-config "subnetIds=$SUBNET_CSV,securityGroupIds=$SG_ID" --region $REGION 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Failed to create cluster:" -ForegroundColor Red
        Write-Host "  $createResult" -ForegroundColor Red
        exit 1
    }

    while ($true) {
        $status = aws eks describe-cluster --name $CLUSTER_NAME --query "cluster.status" --output text --region $REGION
        if ($status -eq "ACTIVE") {
            Write-Host "  Cluster is ACTIVE." -ForegroundColor Green
            break
        }
        if ($status -eq "FAILED") {
            Write-Host "  Cluster creation FAILED." -ForegroundColor Red
            exit 1
        }
        Write-Host "  Status: $status - waiting 30s..."
        Start-Sleep -Seconds 30
    }
}

# --- Step 3: Create node group (skip if exists) ---
Write-Host ""
Write-Host "[3/7] Node group..." -ForegroundColor Cyan

$ngCheck = aws eks describe-nodegroup --cluster-name $CLUSTER_NAME --nodegroup-name $NODEGROUP --query "nodegroup.status" --output text --region $REGION 2>&1
$ngExists = ($LASTEXITCODE -eq 0)

if ($ngExists) {
    Write-Host "  Already exists (status: $ngCheck) - skipping." -ForegroundColor Yellow
} else {
    Write-Host "  Creating node group (3-5 min)..."

    $ngResult = aws eks create-nodegroup --cluster-name $CLUSTER_NAME --nodegroup-name $NODEGROUP --node-role $NODE_ROLE_ARN --subnets $sub0 $sub1 --instance-types $INSTANCE_TYPE --scaling-config "minSize=$NODE_MIN,maxSize=$NODE_MAX,desiredSize=$NODE_DESIRED" --region $REGION 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Failed to create node group:" -ForegroundColor Red
        Write-Host "  $ngResult" -ForegroundColor Red
        exit 1
    }

    while ($true) {
        $status = aws eks describe-nodegroup --cluster-name $CLUSTER_NAME --nodegroup-name $NODEGROUP --query "nodegroup.status" --output text --region $REGION
        if ($status -eq "ACTIVE") {
            Write-Host "  Node group is ACTIVE." -ForegroundColor Green
            break
        }
        if ($status -eq "CREATE_FAILED") {
            Write-Host "  Node group creation FAILED." -ForegroundColor Red
            exit 1
        }
        Write-Host "  Status: $status - waiting 30s..."
        Start-Sleep -Seconds 30
    }
}

# --- Step 4: Configure kubectl ---
Write-Host ""
Write-Host "[4/7] Configuring kubectl..." -ForegroundColor Cyan

aws eks update-kubeconfig --name $CLUSTER_NAME --region $REGION

$nodeCount = (kubectl get nodes --no-headers 2>&1 | Measure-Object -Line).Lines
Write-Host "  Connected. $nodeCount node(s) ready." -ForegroundColor Green

# --- Step 5: Install Istio ---
Write-Host ""
Write-Host "[5/7] Installing Istio service mesh..." -ForegroundColor Cyan

istioctl install --set profile=demo -y

Write-Host "  Waiting for Istio pods..."
kubectl wait --for=condition=Ready pods --all -n istio-system --timeout=120s 2>&1 | Out-Null
Write-Host "  Istio installed." -ForegroundColor Green

# --- Step 6: Deploy application ---
Write-Host ""
Write-Host "[6/7] Deploying application..." -ForegroundColor Cyan

kubectl apply -f "$K8S_DIR/namespace.yaml"
kubectl apply -f "$K8S_DIR/configmap.yaml"
kubectl apply -f "$K8S_DIR/secret.yaml"

$services = @(
    @{ File = "frontend.yaml";         Placeholder = "IMAGE_PLACEHOLDER_FRONTEND";         Repo = "flight-tracker-frontend" },
    @{ File = "flight-searcher.yaml";  Placeholder = "IMAGE_PLACEHOLDER_FLIGHT_SEARCHER";  Repo = "flight-tracker-flight-searcher" },
    @{ File = "price-analyzer.yaml";   Placeholder = "IMAGE_PLACEHOLDER_PRICE_ANALYZER";   Repo = "flight-tracker-price-analyzer" },
    @{ File = "notif-sender.yaml";     Placeholder = "IMAGE_PLACEHOLDER_NOTIF_SENDER";     Repo = "flight-tracker-notif-sender" }
)

$tempFile = [System.IO.Path]::GetTempFileName()

foreach ($svc in $services) {
    $filePath = "$K8S_DIR/$($svc.File)"
    $image = "$ECR_REGISTRY/$($svc.Repo):latest"
    $content = Get-Content $filePath -Raw
    $patched = $content -replace [regex]::Escape($svc.Placeholder), $image
    $ecrPattern = [regex]::Escape("$ECR_REGISTRY/$($svc.Repo)") + ":\S+"
    $patched = $patched -replace $ecrPattern, $image

    $patched | Out-File -FilePath $tempFile -Encoding utf8
    kubectl apply -f $tempFile
    Write-Host "  Applied $($svc.File) with image $image"
}

Remove-Item $tempFile -Force -ErrorAction SilentlyContinue

# --- Step 7: Wait for rollout ---
Write-Host ""
Write-Host "[7/7] Waiting for deployments..." -ForegroundColor Cyan

$deployments = @("frontend", "flight-searcher", "price-analyzer", "notif-sender")
foreach ($dep in $deployments) {
    $rollout = kubectl rollout status "deployment/$dep" -n flight-tracker --timeout=120s 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  WARNING: $dep not ready. Check: kubectl logs deployment/$dep -n flight-tracker" -ForegroundColor Yellow
    } else {
        Write-Host "  $dep is running." -ForegroundColor Green
    }
}

# --- Summary ---
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Infrastructure is up and running!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

kubectl get pods -n flight-tracker
Write-Host ""

$frontendUrl = kubectl get svc frontend -n flight-tracker -o jsonpath="{.status.loadBalancer.ingress[0].hostname}" 2>&1
if ($frontendUrl -and $frontendUrl -notmatch "error") {
    Write-Host "Frontend URL: http://$frontendUrl" -ForegroundColor Cyan
} else {
    Write-Host "Frontend LoadBalancer still provisioning. Check with:" -ForegroundColor Yellow
    Write-Host "  kubectl get svc frontend -n flight-tracker"
}

Write-Host ""
Write-Host "Run .\scripts\infra-down.ps1 when done to stop billing." -ForegroundColor Cyan
