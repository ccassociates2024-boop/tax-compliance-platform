# TaxCompliance AI Platform — Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    CLIENT BROWSERS / APP                          │
│              React + TypeScript (Vite + Tailwind)                │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼───────────────────────────────────────┐
│                    NGINX (Reverse Proxy + SSL)                    │
│                    api.taxcomplianceai.in                        │
└──────┬───────────────────────────────────────┬───────────────────┘
       │ /api/*                                │ /*
┌──────▼──────────┐                  ┌────────▼────────┐
│  FastAPI Backend │                  │  React Frontend │
│  (Python 3.12)  │                  │  (Static files) │
│  Port 8000      │                  │  Port 80        │
└──────┬──────────┘                  └─────────────────┘
       │
       ├── PostgreSQL (RDS, ap-south-1, Multi-AZ, Encrypted)
       ├── Redis (ElastiCache, sessions + Celery broker)
       ├── S3 (ap-south-1, KMS encrypted, documents)
       │
       ├── Celery Workers (background portal automation tasks)
       │       ├── IT Portal Bot (Playwright → Chromium)
       │       ├── TRACES Bot   (Playwright → Chromium)
       │       └── GST Bot      (Playwright → Chromium)
       │
       └── AI Engine → Anthropic Claude API
```

## Security Architecture

### Credential Vault
```
User enters portal password
         ↓
  AES-256-GCM encrypt
  Key = PBKDF2(VAULT_MASTER_KEY, client_id + VAULT_SALT, 600,000 iterations)
  Nonce = random 12 bytes per encryption
  Auth tag = 16 bytes (tamper detection)
         ↓
  Store: {encrypted_hex, nonce_hex, auth_tag_hex} in PostgreSQL
  Plaintext password → NEVER persisted
         ↓
  At automation time: decrypt in memory → pass to Playwright → discard
```

### Data Residency
- All infrastructure in `ap-south-1` (Mumbai)
- RDS encrypted at rest (AES-256)
- S3 encrypted at rest (SSE-KMS)
- TLS 1.3 in transit
- No client financial data leaves India

## Module Map

| Module | Files | Purpose |
|--------|-------|---------|
| **Models** | `backend/models/` | SQLAlchemy ORM — User, Client, Credentials, ITR, GST, TDS |
| **Credential Vault** | `backend/services/credential_vault.py` | AES-256-GCM encrypt/decrypt |
| **IT Bot** | `backend/automation/it_portal_bot.py` | Playwright: AIS, 26AS, e-Pay, ITR status |
| **TRACES Bot** | `backend/automation/traces_bot.py` | Playwright: Form 16, defaults, challans, deductions |
| **GST Bot** | `backend/automation/gst_portal_bot.py` | Playwright: GSTR-2B, ledgers, GSTR-1 upload |
| **AI Engine** | `backend/ai/` | Claude-powered analysis, prompts, streaming |
| **API** | `backend/api/` | FastAPI routes: auth, clients, IT, GST, TDS, AI |
| **Frontend** | `frontend/src/` | React dashboard: clients, AI chat, filings |
| **Infrastructure** | `infrastructure/terraform/` | AWS ECS + RDS + ElastiCache + S3 + Secrets Manager |

## API Endpoints

### Authentication
```
POST /api/v1/auth/register    — Register CA/firm
POST /api/v1/auth/login       — Login → JWT token
GET  /api/v1/auth/me          — Current user
```

### Clients
```
GET    /api/v1/clients         — List all clients (paginated, searchable)
POST   /api/v1/clients         — Add new client
GET    /api/v1/clients/{id}    — Client detail
PATCH  /api/v1/clients/{id}    — Update client
DELETE /api/v1/clients/{id}    — Soft delete
```

### Income Tax
```
POST /api/v1/income-tax/credentials   — Store encrypted IT portal credentials
POST /api/v1/income-tax/fetch         — Trigger portal fetch (background)
GET  /api/v1/income-tax/data/{id}     — Get fetched data status
GET  /api/v1/income-tax/itr/{id}      — ITR filings list
```

### GST
```
POST /api/v1/gst/credentials          — Store GST portal credentials
POST /api/v1/gst/fetch                — Fetch GSTR-2B, ledgers (background)
POST /api/v1/gst/upload-invoices      — Upload invoices → auto GSTR-1
POST /api/v1/gst/gstr3b-working       — AI-powered GSTR-3B computation (streaming)
GET  /api/v1/gst/filings/{id}         — Filing history
POST /api/v1/gst/reconcile/{id}       — GSTR-2B vs books reconciliation
```

### TDS
```
POST /api/v1/tds/credentials          — Store TRACES credentials
POST /api/v1/tds/fetch                — Fetch from TRACES (background)
POST /api/v1/tds/compliance-check     — AI TDS compliance analysis
GET  /api/v1/tds/filings/{id}         — TDS filing history
```

### AI Engine
```
POST /api/v1/ai/chat                  — Streaming AI chat (SSE)
POST /api/v1/ai/analyze-itr          — Full ITR AI analysis (streaming)
POST /api/v1/ai/risk-score/{id}       — Audit risk score 0-100
POST /api/v1/ai/optimize-deductions   — Deduction optimizer
```

## Database Schema

```
users                    — CA firms, staff, business owners
  └── clients            — Taxpayer records (PAN, GSTIN, TAN)
       ├── portal_credentials    — AES-256 encrypted portal passwords
       ├── portal_fetched_data   — Raw data from IT/TRACES/GST portals
       ├── itr_filings           — Income tax return data + AI analysis
       ├── gst_filings           — GSTR-1/3B data + reconciliation
       └── tds_filings           — TDS return data + compliance status
audit_logs               — All user actions for compliance trail
```

## Getting Started

```bash
# 1. Copy environment file
cp .env.example .env
# Edit .env with your keys

# 2. Start all services
docker-compose up -d

# 3. Run DB migrations
docker-compose exec backend alembic upgrade head

# 4. Install Playwright browsers (already done in Dockerfile)
docker-compose exec backend playwright install chromium

# 5. Access app
# Frontend: http://localhost:3000
# API docs:  http://localhost:8000/api/docs (DEBUG mode only)
```

## Production Deployment (AWS)

```bash
# 1. Configure Terraform
cd infrastructure/terraform
terraform init
terraform plan -var="db_password=STRONG_PASSWORD"
terraform apply

# 2. Build and push Docker images
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin <ECR_URL>
docker build -t taxcompliance-api ./backend
docker tag taxcompliance-api:latest <ECR_URL>/taxcompliance-api:latest
docker push <ECR_URL>/taxcompliance-api:latest

# 3. Store secrets in AWS Secrets Manager
aws secretsmanager put-secret-value --secret-id taxcompliance/vault-master-key --secret-string "YOUR_64_HEX_KEY"
aws secretsmanager put-secret-value --secret-id taxcompliance/anthropic-api-key --secret-string "sk-ant-..."
```
