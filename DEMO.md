# 🎭 Demo Mode — Run a Full Sandbox in 3 Minutes

Demo mode spins up the entire platform with **pre-loaded sample data** so you (or anyone you share it with) can test every feature without:

- ❌ Real government portal credentials
- ❌ An Anthropic API key
- ❌ Razorpay payment keys
- ❌ AWS setup
- ❌ Any real client data

---

## Step 1 — Start the demo stack

```bash
docker compose -f docker-compose.demo.yml up --build
```

First run: ~4 minutes (downloads images, builds React app).  
Subsequent runs: ~30 seconds.

---

## Step 2 — Open the app

| URL | What |
|-----|------|
| http://localhost | Full app (via Nginx) |
| http://localhost:3000 | Frontend direct |
| http://localhost:8000/api/docs | Swagger UI (all endpoints) |
| http://localhost:8000/api/v1/demo/status | Demo mode health check |

---

## Step 3 — Log in

On the login page you'll see an amber **"Enter Demo Mode"** button.

Click it — no email, no password needed.

**Or** use the pre-seeded credentials:
```
Email:    demo@taxcomplianceai.in
Password: demo123
```

---

## What You'll See

### 🧑‍💼 Demo Account
**C.A. Sourabh Bhimrao Chavan** · C C & Associates · Professional Plan

### 👥 5 Pre-Loaded Clients

| Client | PAN | Type | Key Feature |
|--------|-----|------|-------------|
| Rajesh Deshmukh | ABCPD1234R | Salaried | ITR-1 · Old regime saves ₹24,440 |
| Sunita Joshi | BFXPJ5678S | Freelancer | ITR-4 · GST ITC mismatch ₹12,000 |
| Sahyadri Software Solutions Pvt Ltd | AADCS3456M | Company | ITR-6 · TDS deductor · 234E penalty |
| Vikram Patil | CLHPP7890V | Business | ITR-3 · LTCG on equity MFs |
| Pushpa Kulkarni | DFZPK2345P | Senior Citizen | ITR-1 · Full ₹12,000 refund |

---

## Features to Test

### 📊 Income Tax
Go to **Income Tax** → Select a client → Click **"Compute Tax"**

Pre-computed results are returned instantly:
- Old vs New regime comparison with exact ₹ savings
- Correct ITR form recommendation with reason
- Quarterly advance tax schedule
- Deduction optimizer (what you're missing)

### 🧾 GST
Go to **GST** → Select Sunita Joshi

Pre-computed results:
- GSTR-2B ITC available: ₹42,000
- ITC in books: ₹54,000
- **Mismatch: ₹12,000 at risk** (3 invoices from Canva, Adobe, Zoom not in 2B)
- GSTR-3B working ready

### 📋 TDS
Go to **TDS** → Select Sahyadri Software Solutions Pvt Ltd

Pre-computed results:
- 3 TDS sections: 192 (salary), 194J (consultants), 194C (contractors)
- **234E penalty: ₹1,000** (Q2 26Q filed 5 days late)
- Challan mismatch warning on 194C

### 🤖 AI Assistant
Go to **AI Assistant** → Ask anything in plain English

The demo AI gives keyword-matched canned responses. Try:
- "Which tax regime saves Rajesh Deshmukh more?"
- "What deductions is Rajesh missing?"
- "Explain the GST ITC mismatch for Sunita"
- "Calculate 234E penalty for Sahyadri Software"
- "What is the advance tax schedule for this year?"
- "Explain 80TTB for senior citizens"

### 💳 Payments (Simulated)
Go to **Billing** → Click "Upgrade"

In demo mode, clicking any paid plan shows a **"Simulate Payment"** button. No real charge occurs. The plan upgrades instantly for 30 days.

### 🌐 Portal Fetch (Simulated)
Click "Fetch from Portal" on any client → returns mock Form 26AS / GSTR-2B / TRACES data with a note saying it's simulated.

---

## Demo API Endpoints

The demo exposes extra endpoints for testing:

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/demo/status` | Check if demo mode is active |
| POST | `/api/v1/demo/login` | One-click login (no form) |
| GET | `/api/v1/demo/clients` | List all 5 demo clients |
| GET | `/api/v1/demo/itr/{pan}` | Pre-computed ITR result |
| GET | `/api/v1/demo/gst/{pan}` | Pre-computed GST result |
| GET | `/api/v1/demo/tds/{pan}` | Pre-computed TDS result |
| POST | `/api/v1/demo/ai/chat` | Canned AI response (SSE stream) |
| POST | `/api/v1/demo/payment/simulate` | Simulate Razorpay payment |
| POST | `/api/v1/demo/portal/fetch/{pan}` | Mock portal fetch |

All endpoints require auth except `/demo/status` and `/demo/login`.

---

## Sharing the Demo

### With your team / investors

Just share this command:
```bash
git clone <repo>
cd tax-compliance-platform
docker compose -f docker-compose.demo.yml up --build
# Then open http://localhost
```

### As a hosted demo

Deploy the demo stack to any cloud VM (e.g., AWS EC2 t3.medium):
```bash
# On the VM
git clone <repo>
cd tax-compliance-platform
docker compose -f docker-compose.demo.yml up -d --build
```

Point a subdomain like `demo.taxcomplianceai.in` to the VM's IP.  
Update `nginx.conf` with the domain name. Done.

**Estimated cost:** ~₹1,500/month for a t3.medium EC2 + EBS.

---

## Switching to Production Mode

When you're ready to go live:

1. Copy `.env.example` → `.env`
2. Fill in real keys: `SECRET_KEY`, `VAULT_MASTER_KEY`, `GEMINI_API_KEY`
3. Add Razorpay keys for payments
4. Run: `docker compose up --build` (uses production compose, no demo mode)

See [QUICKSTART.md](./QUICKSTART.md) for local production setup.  
See [DEPLOYMENT.md](./DEPLOYMENT.md) for full AWS deployment.

---

## Reset Demo Data

```bash
# Stop and wipe demo data (fresh seed on next start)
docker compose -f docker-compose.demo.yml down -v

# Restart fresh
docker compose -f docker-compose.demo.yml up --build
```

---

## What's Different in Demo vs Production

| Feature | Demo | Production |
|---------|------|------------|
| Portal fetch | Mock data (instant) | Playwright browser automation (30–60s) |
| AI responses | Canned keyword answers | Live Claude API (streaming) |
| Payments | Simulated instantly | Real Razorpay checkout |
| AWS S3 | Skipped | Documents stored in encrypted S3 |
| Email alerts | Off | SendGrid / SES |
| Audit logs | Active | Active |
| DB encryption | Active | Active |
| JWT auth | Real | Real |
| All calculations | Real (same engine) | Real |

> 📌 The tax computation engine, TDS validator, GST reconciler, and all calculation logic is **identical** in demo and production. Only the data source changes (mock vs real portals).

---

*Built with ❤️ for Indian CAs and businesses · TaxCompliance AI · © 2025*
