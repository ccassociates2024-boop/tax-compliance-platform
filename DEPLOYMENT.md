# AWS Deployment Guide — TaxCompliance AI Platform
**Region: ap-south-1 (Mumbai) | Indian data residency compliant**

---

## Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [AWS Account Setup](#2-aws-account-setup)
3. [Domain & SSL](#3-domain--ssl)
4. [Infrastructure (Terraform)](#4-infrastructure-terraform)
5. [Secrets Manager](#5-secrets-manager)
6. [Docker Images & ECR](#6-docker-images--ecr)
7. [Database Migration](#7-database-migration)
8. [ECS Fargate Deployment](#8-ecs-fargate-deployment)
9. [CI/CD Pipeline (GitHub Actions)](#9-cicd-pipeline-github-actions)
10. [Monitoring & Alerts](#10-monitoring--alerts)
11. [Razorpay Webhook Configuration](#11-razorpay-webhook-configuration)
12. [Post-Deployment Checklist](#12-post-deployment-checklist)

---

## 1. Prerequisites

```bash
# Install required tools
brew install awscli terraform docker gh     # macOS
# or
apt-get install awscli terraform docker.io  # Ubuntu

# Verify versions
aws --version          # >= 2.x
terraform --version    # >= 1.6
docker --version       # >= 24.x
```

**Required accounts:**
- AWS account with billing enabled
- Domain name (e.g., `taxcomplianceai.in`) — register on Route 53 or GoDaddy
- Razorpay account (live keys)
- Anthropic API key (Claude API)

---

## 2. AWS Account Setup

```bash
# Configure AWS CLI
aws configure
# AWS Access Key ID: <your-key>
# AWS Secret Access Key: <your-secret>
# Default region: ap-south-1
# Default output: json

# Create IAM user for deployments (least privilege)
aws iam create-user --user-name taxcompliance-deploy
aws iam attach-user-policy \
  --user-name taxcompliance-deploy \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess   # Narrow down in production

# Create access keys
aws iam create-access-key --user-name taxcompliance-deploy
```

---

## 3. Domain & SSL

### Route 53 Setup
```bash
# Create hosted zone (if domain registered elsewhere, update NS records)
aws route53 create-hosted-zone \
  --name taxcomplianceai.in \
  --caller-reference $(date +%s)

# Note the 4 nameservers — update at your registrar
aws route53 list-hosted-zones --query "HostedZones[0].DelegationSet.NameServers"
```

### ACM Certificate (Mumbai region — required for ALB)
```bash
# Request wildcard certificate
aws acm request-certificate \
  --domain-name "taxcomplianceai.in" \
  --subject-alternative-names "*.taxcomplianceai.in" \
  --validation-method DNS \
  --region ap-south-1

# Get the CNAME validation record
aws acm describe-certificate \
  --certificate-arn <your-cert-arn> \
  --query "Certificate.DomainValidationOptions"

# Add the CNAME to Route 53 (DNS validation — usually auto-done if Route 53 is used)
# Wait for ISSUED status (1-30 minutes)
aws acm wait certificate-validated --certificate-arn <your-cert-arn>
echo "✅ Certificate issued"
```

---

## 4. Infrastructure (Terraform)

```bash
cd infrastructure/terraform
terraform init
terraform plan -var-file="production.tfvars"
terraform apply -var-file="production.tfvars"
```

### `infrastructure/terraform/main.tf`
```hcl
terraform {
  required_version = ">= 1.6"
  backend "s3" {
    bucket = "taxcompliance-terraform-state"
    key    = "production/terraform.tfstate"
    region = "ap-south-1"
  }
}

provider "aws" { region = "ap-south-1" }

# ── VPC ──────────────────────────────────────────────────────────────────────

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "taxcompliance-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["ap-south-1a", "ap-south-1b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = false   # HA: one per AZ
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = { Project = "TaxCompliance" }
}

# ── RDS PostgreSQL (Multi-AZ) ─────────────────────────────────────────────────

resource "aws_db_instance" "postgres" {
  identifier             = "taxcompliance-db"
  engine                 = "postgres"
  engine_version         = "16.2"
  instance_class         = "db.t3.medium"   # Upgrade to db.r6g.large for >50 users
  allocated_storage      = 100
  max_allocated_storage  = 1000
  storage_type           = "gp3"
  storage_encrypted      = true
  kms_key_id             = aws_kms_key.rds.arn

  db_name  = "taxcompliance"
  username = "taxadmin"
  password = random_password.db_password.result

  multi_az               = true
  backup_retention_period = 7
  backup_window          = "02:00-03:00"   # IST 7:30–8:30 AM
  maintenance_window     = "Sun:03:00-Sun:04:00"

  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  deletion_protection = true
  skip_final_snapshot = false
  final_snapshot_identifier = "taxcompliance-final-snapshot"

  tags = { Name = "taxcompliance-postgres" }
}

# ── ElastiCache Redis ─────────────────────────────────────────────────────────

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "taxcompliance-redis"
  description          = "Redis for Celery + rate limiting"

  node_type            = "cache.t3.small"
  num_cache_clusters   = 2   # Primary + replica
  engine_version       = "7.0"
  port                 = 6379

  automatic_failover_enabled = true
  multi_az_enabled           = true
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  tags = { Name = "taxcompliance-redis" }
}

# ── ECS Cluster ───────────────────────────────────────────────────────────────

resource "aws_ecs_cluster" "main" {
  name = "taxcompliance"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ── S3 Bucket (KMS encrypted) ─────────────────────────────────────────────────

resource "aws_s3_bucket" "documents" {
  bucket = "taxcompliance-docs-india"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "docs" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
  }
}

resource "aws_s3_bucket_versioning" "docs" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_public_access_block" "docs" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── KMS Keys ─────────────────────────────────────────────────────────────────

resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS encryption"
  deletion_window_in_days = 30
}

resource "aws_kms_key" "s3" {
  description             = "KMS key for S3 document encryption"
  deletion_window_in_days = 30
}

resource "aws_kms_key" "secrets" {
  description             = "KMS key for Secrets Manager"
  deletion_window_in_days = 30
}

# ── ALB ──────────────────────────────────────────────────────────────────────

resource "aws_lb" "main" {
  name               = "taxcompliance-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets

  enable_deletion_protection = true
  enable_http2               = true
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}

resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}
```

### `infrastructure/terraform/production.tfvars`
```hcl
acm_certificate_arn = "arn:aws:acm:ap-south-1:ACCOUNT_ID:certificate/YOUR-CERT-ID"
domain_name         = "taxcomplianceai.in"
```

---

## 5. Secrets Manager

```bash
# Store all secrets in AWS Secrets Manager (never in .env in production)

# Database
aws secretsmanager create-secret \
  --name "taxcompliance/prod/database-url" \
  --secret-string "postgresql+asyncpg://taxadmin:PASSWORD@DB_HOST:5432/taxcompliance" \
  --kms-key-id alias/taxcompliance-secrets \
  --region ap-south-1

# Vault master key (generate a strong key)
python3 -c "import secrets; print(secrets.token_hex(32))"
aws secretsmanager create-secret \
  --name "taxcompliance/prod/vault-master-key" \
  --secret-string "YOUR_64_CHAR_HEX_KEY" \
  --region ap-south-1

# Anthropic
aws secretsmanager create-secret \
  --name "taxcompliance/prod/anthropic-api-key" \
  --secret-string "sk-ant-..." \
  --region ap-south-1

# Razorpay
aws secretsmanager create-secret \
  --name "taxcompliance/prod/razorpay" \
  --secret-string '{"key_id":"rzp_live_...","key_secret":"...","webhook_secret":"..."}' \
  --region ap-south-1

# JWT secret
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
aws secretsmanager create-secret \
  --name "taxcompliance/prod/secret-key" \
  --secret-string "YOUR_JWT_SECRET" \
  --region ap-south-1
```

---

## 6. Docker Images & ECR

```bash
# Create ECR repositories
aws ecr create-repository --repository-name taxcompliance/backend --region ap-south-1
aws ecr create-repository --repository-name taxcompliance/frontend --region ap-south-1

# Login to ECR
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.ap-south-1.amazonaws.com

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_BASE="$ACCOUNT_ID.dkr.ecr.ap-south-1.amazonaws.com"

# Build & push backend
docker build -t taxcompliance/backend ./backend
docker tag taxcompliance/backend:latest $ECR_BASE/taxcompliance/backend:latest
docker push $ECR_BASE/taxcompliance/backend:latest

# Build & push frontend
docker build -t taxcompliance/frontend ./frontend \
  --build-arg VITE_API_URL=https://api.taxcomplianceai.in
docker tag taxcompliance/frontend:latest $ECR_BASE/taxcompliance/frontend:latest
docker push $ECR_BASE/taxcompliance/frontend:latest
```

### `backend/Dockerfile`
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install Playwright dependencies
RUN apt-get update && apt-get install -y \
    chromium chromium-driver \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium --with-deps

COPY . .

ENV PLAYWRIGHT_BROWSERS_PATH=/usr/bin
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "4", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

### `frontend/Dockerfile`
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### `frontend/nginx.conf`
```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # React Router — serve index.html for all routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
}
```

---

## 7. Database Migration

```bash
# Run Alembic migrations via a one-off ECS task (or from local with tunnel)

# Option A: From local machine using SSM Session Manager tunnel
aws ssm start-session \
  --target <bastion-instance-id> \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters host="DB_HOST",portNumber="5432",localPortNumber="5433"

# In another terminal:
DATABASE_URL="postgresql+asyncpg://taxadmin:PASSWORD@localhost:5433/taxcompliance" \
  alembic upgrade head

# Option B: One-off ECS Fargate task
aws ecs run-task \
  --cluster taxcompliance \
  --task-definition taxcompliance-migrate \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[SUBNET_ID],securityGroups=[SG_ID]}"
```

---

## 8. ECS Fargate Deployment

### Task Definition (backend)
```bash
cat > task-def-backend.json << 'EOF'
{
  "family": "taxcompliance-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/taxcompliance-task-role",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "ACCOUNT.dkr.ecr.ap-south-1.amazonaws.com/taxcompliance/backend:latest",
      "portMappings": [{"containerPort": 8000, "protocol": "tcp"}],
      "environment": [
        {"name": "AWS_REGION", "value": "ap-south-1"},
        {"name": "AI_MODEL", "value": "claude-sonnet-4-6"},
        {"name": "DEBUG", "value": "false"}
      ],
      "secrets": [
        {"name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:ap-south-1:ACCOUNT:secret:taxcompliance/prod/database-url"},
        {"name": "SECRET_KEY", "valueFrom": "arn:aws:secretsmanager:ap-south-1:ACCOUNT:secret:taxcompliance/prod/secret-key"},
        {"name": "VAULT_MASTER_KEY", "valueFrom": "arn:aws:secretsmanager:ap-south-1:ACCOUNT:secret:taxcompliance/prod/vault-master-key"},
        {"name": "ANTHROPIC_API_KEY", "valueFrom": "arn:aws:secretsmanager:ap-south-1:ACCOUNT:secret:taxcompliance/prod/anthropic-api-key"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/taxcompliance-backend",
          "awslogs-region": "ap-south-1",
          "awslogs-stream-prefix": "backend"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/api/health || exit 1"],
        "interval": 30,
        "timeout": 10,
        "retries": 3
      }
    }
  ]
}
EOF

aws ecs register-task-definition --cli-input-json file://task-def-backend.json
```

### ECS Service
```bash
aws ecs create-service \
  --cluster taxcompliance \
  --service-name taxcompliance-backend \
  --task-definition taxcompliance-backend:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[PRIVATE_SUBNET_1,PRIVATE_SUBNET_2],
    securityGroups=[BACKEND_SG],
    assignPublicIp=DISABLED
  }" \
  --load-balancers "targetGroupArn=TARGET_GROUP_ARN,containerName=backend,containerPort=8000" \
  --deployment-configuration "minimumHealthyPercent=100,maximumPercent=200" \
  --enable-execute-command

# Auto Scaling
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/taxcompliance/taxcompliance-backend \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 10

aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/taxcompliance/taxcompliance-backend \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name cpu-scaling \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {"PredefinedMetricType": "ECSServiceAverageCPUUtilization"}
  }'
```

---

## 9. CI/CD Pipeline (GitHub Actions)

### `.github/workflows/deploy.yml`
```yaml
name: Deploy to AWS

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  AWS_REGION: ap-south-1
  ECR_REGISTRY: ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.ap-south-1.amazonaws.com
  BACKEND_IMAGE: taxcompliance/backend
  FRONTEND_IMAGE: taxcompliance/frontend

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r backend/requirements.txt
      - run: cd backend && python -m pytest tests/ -v --tb=short

  deploy:
    needs: test
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to ECR
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push backend
        run: |
          docker build -t $ECR_REGISTRY/$BACKEND_IMAGE:$GITHUB_SHA ./backend
          docker push $ECR_REGISTRY/$BACKEND_IMAGE:$GITHUB_SHA
          docker tag $ECR_REGISTRY/$BACKEND_IMAGE:$GITHUB_SHA $ECR_REGISTRY/$BACKEND_IMAGE:latest
          docker push $ECR_REGISTRY/$BACKEND_IMAGE:latest

      - name: Build and push frontend
        run: |
          docker build \
            --build-arg VITE_API_URL=https://api.taxcomplianceai.in \
            -t $ECR_REGISTRY/$FRONTEND_IMAGE:$GITHUB_SHA ./frontend
          docker push $ECR_REGISTRY/$FRONTEND_IMAGE:$GITHUB_SHA

      - name: Deploy backend to ECS
        run: |
          aws ecs update-service \
            --cluster taxcompliance \
            --service taxcompliance-backend \
            --force-new-deployment

      - name: Deploy frontend to ECS
        run: |
          aws ecs update-service \
            --cluster taxcompliance \
            --service taxcompliance-frontend \
            --force-new-deployment

      - name: Wait for deployment
        run: |
          aws ecs wait services-stable \
            --cluster taxcompliance \
            --services taxcompliance-backend taxcompliance-frontend

      - name: Health check
        run: |
          sleep 30
          curl -f https://api.taxcomplianceai.in/api/health || exit 1
          echo "✅ Deployment successful!"

      - name: Notify on failure
        if: failure()
        run: |
          echo "❌ Deployment failed — check GitHub Actions logs"
```

---

## 10. Monitoring & Alerts

```bash
# CloudWatch Dashboard
aws cloudwatch put-dashboard --dashboard-name TaxCompliance --dashboard-body '{
  "widgets": [
    {"type": "metric", "properties": {
      "title": "API Latency",
      "metrics": [["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", "ALB_NAME"]],
      "period": 60
    }},
    {"type": "metric", "properties": {
      "title": "ECS CPU",
      "metrics": [["AWS/ECS", "CPUUtilization", "ClusterName", "taxcompliance"]],
      "period": 60
    }},
    {"type": "metric", "properties": {
      "title": "RDS Connections",
      "metrics": [["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", "taxcompliance-db"]],
      "period": 60
    }}
  ]
}'

# Alert: API errors > 5/min
aws cloudwatch put-metric-alarm \
  --alarm-name "taxcompliance-5xx-errors" \
  --alarm-description "High 5xx error rate" \
  --metric-name HTTPCode_Target_5XX_Count \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 60 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:ap-south-1:ACCOUNT:taxcompliance-alerts

# Alert: RDS CPU > 80%
aws cloudwatch put-metric-alarm \
  --alarm-name "taxcompliance-rds-cpu" \
  --metric-name CPUUtilization \
  --namespace AWS/RDS \
  --dimensions Name=DBInstanceIdentifier,Value=taxcompliance-db \
  --statistic Average --period 300 --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:ap-south-1:ACCOUNT:taxcompliance-alerts

# SNS for email alerts
aws sns create-topic --name taxcompliance-alerts
aws sns subscribe \
  --topic-arn arn:aws:sns:ap-south-1:ACCOUNT:taxcompliance-alerts \
  --protocol email \
  --notification-endpoint admin@taxcomplianceai.in
```

---

## 11. Razorpay Webhook Configuration

1. Log in to **Razorpay Dashboard** → Settings → Webhooks
2. Click **Add New Webhook**
3. **Webhook URL**: `https://api.taxcomplianceai.in/api/v1/subscriptions/webhook`
4. **Secret**: Generate and store in Secrets Manager as `taxcompliance/prod/razorpay`
5. **Events to enable:**
   - ✅ `payment.captured`
   - ✅ `payment.failed`
   - ✅ `subscription.activated`
   - ✅ `subscription.charged`
   - ✅ `subscription.halted`
   - ✅ `subscription.cancelled`
6. Click **Save**

### Test webhook locally (ngrok):
```bash
ngrok http 8000
# Copy the ngrok URL and set as webhook in Razorpay test dashboard
```

---

## 12. Post-Deployment Checklist

```bash
# ── Smoke Tests ───────────────────────────────────────────────────────────────

# API health
curl https://api.taxcomplianceai.in/api/health
# Expected: {"status":"healthy","version":"1.0.0"}

# Register a test user
curl -X POST https://api.taxcomplianceai.in/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Test CA","email":"test@test.in","password":"Test@1234"}'

# Login and get token
TOKEN=$(curl -s -X POST https://api.taxcomplianceai.in/api/v1/auth/login \
  -d "username=test@test.in&password=Test@1234" | jq -r '.access_token')

# Test ITR computation
curl -X POST https://api.taxcomplianceai.in/api/v1/income-tax/compute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"client_id":"test","age":30,"gross_salary":1500000,"epf":150000}'

# ── DNS Verification ──────────────────────────────────────────────────────────
dig api.taxcomplianceai.in
dig app.taxcomplianceai.in
curl -I https://app.taxcomplianceai.in   # Should redirect to React app

# ── SSL Check ─────────────────────────────────────────────────────────────────
echo | openssl s_client -connect api.taxcomplianceai.in:443 2>/dev/null | openssl x509 -noout -dates

# ── Security Headers ──────────────────────────────────────────────────────────
curl -I https://api.taxcomplianceai.in/api/health | grep -i "strict-transport\|x-frame\|x-content"

# ── Database Backup Test ──────────────────────────────────────────────────────
aws rds describe-automated-backups --db-instance-identifier taxcompliance-db

# ── Razorpay test payment ─────────────────────────────────────────────────────
# Use test card: 4111 1111 1111 1111, CVV: any 3 digits, Expiry: any future date

echo ""
echo "✅ Deployment checklist complete!"
echo "   App:    https://app.taxcomplianceai.in"
echo "   API:    https://api.taxcomplianceai.in/api/docs"
echo "   Pricing: https://app.taxcomplianceai.in/pricing"
```

---

## Monthly Cost Estimate (Production — 100 clients)

| Service | Config | ~Monthly Cost |
|---------|--------|--------------|
| ECS Fargate (backend 2×) | 1 vCPU, 2 GB | ₹3,200 |
| ECS Fargate (frontend 2×) | 0.5 vCPU, 1 GB | ₹1,600 |
| RDS PostgreSQL Multi-AZ | db.t3.medium | ₹8,000 |
| ElastiCache Redis | cache.t3.small × 2 | ₹2,500 |
| Application Load Balancer | — | ₹1,800 |
| NAT Gateway (2× AZ) | — | ₹2,500 |
| S3 + CloudWatch + ECR | — | ₹800 |
| Data Transfer | ~100 GB | ₹900 |
| **Total** | | **~₹21,300/month** |

> Scale up ECS tasks and upgrade to `db.r6g.large` when exceeding 500 concurrent users.

---

## Support

- **Docs**: `/api/docs` (enabled in DEBUG mode)
- **Logs**: CloudWatch → Log Groups → `/ecs/taxcompliance-backend`
- **SSH into container**: `aws ecs execute-command --cluster taxcompliance --task TASK_ID --container backend --interactive --command "/bin/bash"`
