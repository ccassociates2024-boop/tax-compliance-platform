# 🚀 QuickStart — Run Locally in 5 Minutes

## Step 1 — Copy environment file

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
# Must change these 3:
SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
VAULT_MASTER_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
GEMINI_API_KEY=AIza...               # Free tier, from aistudio.google.com/apikey

# These can stay as-is for local dev:
DB_PASSWORD=strongpassword123
REDIS_PASSWORD=redispassword
VAULT_SALT=taxcompliance-local-salt-2025

# Optional for local dev (leave blank — payments won't work but everything else will):
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=

# Leave blank for local dev:
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
```

## Step 2 — Install Docker Desktop

Download from https://www.docker.com/products/docker-desktop/
Make sure Docker is running (whale icon in taskbar).

## Step 3 — Start everything

```bash
docker compose up --build
```

First run takes ~5 minutes (downloads images, installs Playwright).
Subsequent runs take ~30 seconds.

## Step 4 — Open in browser

| URL | What |
|-----|------|
| http://localhost | Full app (via Nginx) |
| http://localhost:3000 | Frontend direct |
| http://localhost:8000/api/docs | API docs (Swagger) |
| http://localhost:8000/api/health | Health check |

## Step 5 — Create your first account

Go to http://localhost/register → fill in your details → you're in!

---

## Common Issues

**Port 80 already in use:**
```bash
# Windows: find what's using port 80
netstat -ano | findstr :80
# Change nginx port in docker-compose.yml: "8080:80" instead of "80:80"
```

**Backend crashes on startup:**
```bash
docker compose logs backend
# Usually a missing .env variable — check the error message
```

**"Cannot connect to database":**
```bash
docker compose restart backend
# DB takes ~10s to be ready on first boot — backend retries automatically
```

**Rebuild after code changes:**
```bash
docker compose up --build
# Or for backend only:
docker compose up --build backend
```

**Reset everything (fresh start):**
```bash
docker compose down -v   # -v removes volumes (deletes DB data!)
docker compose up --build
```

---

## Going Live on AWS

See [DEPLOYMENT.md](./DEPLOYMENT.md) for the full AWS step-by-step guide.

**Quick version:**
1. Buy domain (e.g., `yourapp.in`) on GoDaddy or Route 53
2. Get Razorpay live keys from dashboard.razorpay.com
3. Run `terraform apply` in `infrastructure/terraform/`
4. Push Docker images to ECR
5. Deploy ECS services
6. Point domain DNS to ALB

**Estimated time:** 2–4 hours for first deployment.
**Monthly cost:** ~₹21,000 for production (100 clients).
