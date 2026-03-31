# Inventory Management System (IMS)

A modern, production-ready Inventory Management System built with React, FastAPI, and PostgreSQL. Designed for Indian businesses with full GST compliance and comprehensive reporting.

---

## [START] Quick Start

### First Time? Start Here
1. **[Setup Guide](./docs/guides/SETUP.md)** — Complete installation steps (15 min)
2. **[Master Specification](./docs/MASTER_SPEC.md)** — Full system overview
3. **[Design System](./docs/design/DESIGN_SYSTEM_MASTER.md)** — UI/UX guidelines

### Want to Build a Feature?
1. Check the relevant **[Workflow](./docs/workflows/)** (WF_01 through WF_06)
2. Follow **[Coding Standards](./docs/guides/CODING_STANDARDS.md)**
3. Implement following the patterns in MASTER_SPEC.md

### Need Help?
- **System spec?** → [MASTER_SPEC.md](./docs/MASTER_SPEC.md)
- **How to?** → [Workflows](./docs/workflows/)
- **Database?** → [DATABASE.md](./docs/guides/DATABASE.md)
- **Code style?** → [CODING_STANDARDS.md](./docs/guides/CODING_STANDARDS.md)

---

## [LIST] What's Included

### Features
[OK] **Authentication & Authorization** — JWT + 4-role RBAC with admin overrides  
[OK] **Masters Management** — Company, Users, Products, Customers, Suppliers  
[OK] **Purchase Module** — PO → GRN → Returns with full stock tracking  
[OK] **Sales Module** — Quotation → SO → Invoice → Returns  
[OK] **Payment Tracking** — Receivables/Payables with invoice allocation  
[OK] **Inventory Management** — Real-time stock ledger with low-stock alerts  
[OK] **Reports** — Dashboard, Stock, Sales, Purchase, P&L, GSTR-1/3B  
[OK] **GST Compliance** — IGST/CGST/SGST auto-split, GSTR-1/3B export  
[OK] **PDF Generation** — Tax invoices with server-side WeasyPrint  
[OK] **Email Integration** — Send invoices via email  

### Technology Stack
| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18 + TypeScript + Tailwind CSS |
| **Backend** | FastAPI + SQLAlchemy + Alembic |
| **Database** | PostgreSQL 15+ |
| **Auth** | JWT + bcrypt |
| **State** | Zustand (frontend), SQLAlchemy ORM (backend) |
| **Design** | HMS (Healthcare Management System) design tokens |

---

## [FILES] Project Structure

```
ims1/
├── docs/                           # Complete documentation
│   ├── INDEX.md                    # Documentation hub (start here)
│   ├── MASTER_SPEC.md              # Full system specification
│   ├── guides/                     # How-to guides
│   │   ├── SETUP.md                # Installation instructions
│   │   ├── DATABASE.md             # Database management
│   │   └── CODING_STANDARDS.md     # Code quality rules
│   ├── workflows/                  # Business workflows
│   │   ├── WF_01_AUTH.md           # Authentication
│   │   ├── WF_02_MASTERS.md        # Master data setup
│   │   ├── WF_03_PURCHASE.md       # Purchase operations
│   │   ├── WF_04_SALES.md          # Sales operations
│   │   ├── WF_05_PAYMENTS.md       # Payment handling
│   │   └── WF_06_REPORTS.md        # Reporting workflows
│   └── design/                     # UI/UX guidelines
│       └── DESIGN_SYSTEM_MASTER.md # Design system
│
├── scripts/                        # Utility scripts
│   ├── setup_db.py                 # Database initialization
│   ├── seed_db.py                  # Sample data (dev only)
│   └── README.md                   # Scripts guide
│
├── backend/                        # FastAPI application
│   ├── app/                        # Main app code
│   │   ├── models/                 # SQLAlchemy models
│   │   ├── routers/                # API endpoints
│   │   ├── schemas/                # Pydantic schemas
│   │   ├── services/               # Business logic
│   │   ├── utils/                  # Helpers
│   │   ├── config.py               # Configuration
│   │   ├── database.py             # DB setup
│   │   └── main.py                 # FastAPI entry
│   ├── .env.example                # Environment template
│   ├── requirements.txt            # Python dependencies
│   └── venv/                       # Virtual environment
│
├── frontend/                       # React application
│   ├── src/                        # React source
│   │   ├── api/                    # API clients
│   │   ├── components/             # Reusable components
│   │   ├── pages/                  # Page components
│   │   ├── store/                  # Zustand stores
│   │   ├── types/                  # TypeScript types
│   │   └── hooks/                  # Custom hooks
│   ├── .env.example                # Environment template
│   ├── package.json                # npm dependencies
│   ├── tailwind.config.ts          # Tailwind config
│   └── vite.config.ts              # Vite config
│
├── database/                       # Database migrations
│   ├── alembic/                    # Alembic migration tool
│   │   ├── versions/               # Migration scripts
│   │   └── env.py                  # Alembic config
│   └── alembic.ini                 # Alembic settings
│
└── README.md                       # This file
```

---

## [FIX]️ Development

### Prerequisites
- Node.js 20.x LTS
- Python 3.11+
- PostgreSQL 15+
- Git

### Setup (5 minutes)
```bash
# Clone and navigate
git clone <repo-url>
cd inventory-management-system-full-project

# One-command backend bootstrap (env + deps + db compatibility migration + seed)
python setup_db.py

# Start backend
cd backend
.venv\Scripts\activate             # Windows
# source .venv/bin/activate         # Linux/macOS
uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
---

Default login after setup:
- Email: admin@company.com
- Password: Admin@123


## [DOCS] Documentation Structure

```
docs/
├── INDEX.md                    # [PIN] START HERE - Navigation hub
├── MASTER_SPEC.md              # Complete system blueprint
├── guides/
│   ├── SETUP.md                # Installation (15 min)
│   ├── DATABASE.md             # DB setup & migration
│   └── CODING_STANDARDS.md     # Code quality rules
├── workflows/
│   ├── WF_01_AUTH.md           # Login & permissions
│   ├── WF_02_MASTERS.md        # Company, Users, Products setup
│   ├── WF_03_PURCHASE.md       # PO → GRN → Returns
│   ├── WF_04_SALES.md          # Quotation → Invoice → Returns
│   ├── WF_05_PAYMENTS.md       # Receivables/Payables
│   └── WF_06_REPORTS.md        # All reports & exports
└── design/
    └── DESIGN_SYSTEM_MASTER.md # Colors, typography, components
```

---

## [TARGET] Common Tasks

### Add a Customer
1. Read: [WF_02_MASTERS.md](./docs/workflows/WF_02_MASTERS.md)
2. Navigate to: Masters → Customers
3. Click "New Customer"
4. Fill form → Save

### Create a Sales Invoice
1. Read: [WF_04_SALES.md](./docs/workflows/WF_04_SALES.md)
2. Navigate to: Sales → Invoices
3. Select customer, add items, issue
4. System deducts stock, generates PDF

### Check Stock
1. Navigate to: Inventory → Stock
2. View real-time quantities
3. Red badge = stock below minimum

### Generate GST Report
1. Navigate to: Reports → GST Report
2. Select date range
3. Export as CSV

---

## [SECURITY] Security Notes

### Never Commit to Git
- `.env` files with credentials
- Database dumps
- API keys or secrets

### Production Checklist
- [ ] Change default admin password
- [ ] Use strong SECRET_KEY
- [ ] Configure SSL/HTTPS
- [ ] Set secure database password
- [ ] Enable database backups
- [ ] Use environment variables for secrets

---

## [METRICS] Database Overview

Core tables: `users`, `company`, `customers`, `suppliers`, `products`, `purchase_orders`, `sales_invoices`, `payments`, `stock_ledger`.

Full schema in [MASTER_SPEC.md](./docs/MASTER_SPEC.md).

---

## [TEST] Testing

```bash
# Backend tests
cd backend && pytest

# Frontend tests
cd frontend && npm run test
```

---

## [START] Production

See [SETUP.md](./docs/guides/SETUP.md) for production deployment with:
- Gunicorn backend setup
- Nginx frontend serving
- Database backup strategy
- Environment configuration

---

## [SUPPORT] Support

- **System spec?** → [MASTER_SPEC.md](./docs/MASTER_SPEC.md)
- **How to?** → [Workflows](./docs/workflows/)
- **Database?** → [DATABASE.md](./docs/guides/DATABASE.md)
- **Code style?** → [CODING_STANDARDS.md](./docs/guides/CODING_STANDARDS.md)
- **Everything?** → [Documentation Index](./docs/INDEX.md)

---

## [FILE] License

Proprietary. All rights reserved.

---

**Last Updated:** March 25, 2026  
**Status:** Production Ready [DONE]

[NEXT] **[Start with the Documentation Index →](./docs/INDEX.md)**


