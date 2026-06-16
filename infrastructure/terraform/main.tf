# AWS Infrastructure for TaxCompliance AI Platform
# Region: ap-south-1 (Mumbai) — Indian data residency
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket = "taxcompliance-terraform-state"
    key    = "prod/terraform.tfstate"
    region = "ap-south-1"
  }
}

provider "aws" {
  region = "ap-south-1"
}

# ─── VPC ─────────────────────────────────────────────────────────────────────
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags = { Name = "taxcompliance-vpc" }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index}.0/24"
  availability_zone = "ap-south-1${count.index == 0 ? "a" : "b"}"
  tags              = { Name = "taxcompliance-private-${count.index}" }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.10${count.index}.0/24"
  availability_zone       = "ap-south-1${count.index == 0 ? "a" : "b"}"
  map_public_ip_on_launch = true
  tags                    = { Name = "taxcompliance-public-${count.index}" }
}

# ─── RDS PostgreSQL ──────────────────────────────────────────────────────────
resource "aws_db_instance" "postgres" {
  identifier             = "taxcompliance-db"
  engine                 = "postgres"
  engine_version         = "16.1"
  instance_class         = "db.t3.medium"
  allocated_storage      = 100
  max_allocated_storage  = 500
  storage_encrypted      = true    # Encrypted at rest
  db_name                = "taxcompliance"
  username               = "taxadmin"
  password               = var.db_password
  multi_az               = true    # High availability
  backup_retention_period = 30     # 30 days backup (compliance requirement)
  deletion_protection    = true
  skip_final_snapshot    = false
  vpc_security_group_ids = [aws_security_group.db.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  tags = { Name = "taxcompliance-postgres", DataClassification = "HIGHLY_CONFIDENTIAL" }
}

resource "aws_db_subnet_group" "main" {
  name       = "taxcompliance-db-subnet"
  subnet_ids = aws_subnet.private[*].id
}

# ─── ElastiCache Redis ────────────────────────────────────────────────────────
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "taxcompliance-redis"
  engine               = "redis"
  node_type            = "cache.t3.small"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "taxcompliance-redis-subnet"
  subnet_ids = aws_subnet.private[*].id
}

# ─── ECS Fargate (Backend API) ────────────────────────────────────────────────
resource "aws_ecs_cluster" "main" {
  name = "taxcompliance-cluster"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "taxcompliance-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "api"
      image = "${aws_ecr_repository.api.repository_url}:latest"
      portMappings = [{ containerPort = 8000 }]
      environment = [
        { name = "AWS_REGION", value = "ap-south-1" },
      ]
      secrets = [
        { name = "SECRET_KEY",       valueFrom = aws_secretsmanager_secret.app_secrets.arn },
        { name = "VAULT_MASTER_KEY", valueFrom = aws_secretsmanager_secret.vault_key.arn },
        { name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.ai_key.arn },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = "/ecs/taxcompliance-api"
          awslogs-region        = "ap-south-1"
          awslogs-stream-prefix = "api"
        }
      }
    }
  ])
}

# ─── S3 for Documents ─────────────────────────────────────────────────────────
resource "aws_s3_bucket" "documents" {
  bucket = "taxcompliance-docs-india"
  tags   = { DataClassification = "HIGHLY_CONFIDENTIAL", Region = "India" }
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ─── ECR Repositories ─────────────────────────────────────────────────────────
resource "aws_ecr_repository" "api" {
  name                 = "taxcompliance-api"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
}

# ─── Secrets Manager ─────────────────────────────────────────────────────────
resource "aws_secretsmanager_secret" "app_secrets"  { name = "taxcompliance/app-secrets" }
resource "aws_secretsmanager_secret" "vault_key"    { name = "taxcompliance/vault-master-key" }
resource "aws_secretsmanager_secret" "ai_key"       { name = "taxcompliance/anthropic-api-key" }

# ─── Security Groups ──────────────────────────────────────────────────────────
resource "aws_security_group" "db" {
  name   = "taxcompliance-db-sg"
  vpc_id = aws_vpc.main.id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }
}

resource "aws_security_group" "redis" {
  name   = "taxcompliance-redis-sg"
  vpc_id = aws_vpc.main.id
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }
}

resource "aws_security_group" "ecs" {
  name   = "taxcompliance-ecs-sg"
  vpc_id = aws_vpc.main.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

variable "db_password" {
  description = "RDS PostgreSQL password"
  type        = string
  sensitive   = true
}
