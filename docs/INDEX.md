# Inventory Management System - Documentation Index

Welcome to the IMS documentation. This guide helps you navigate the entire project structure and find what you need.

---

## 📋 Quick Navigation

### Getting Started
- [Setup Guide](./guides/SETUP.md) — Complete installation and configuration
- [Coding Standards](./guides/CODING_STANDARDS.md) — Code quality rules
- [Project Specification](./MASTER_SPEC.md) — Complete system specification

### System Design
- [HMS Design System](./design/HMS_DESIGN_SYSTEM_MASTER.md) — UI/UX patterns and components
- [Master Specification](./MASTER_SPEC.md) — Complete technical specification

### Workflow Documentation
- [WF-01: Authentication](./workflows/WF_01_AUTH.md) — User login and JWT tokens
- [WF-02: Masters](./workflows/WF_02_MASTERS.md) — Company, users, products setup
- [WF-03: Purchase](./workflows/WF_03_PURCHASE.md) — PO → GRN → Payment
- [WF-04: Sales](./workflows/WF_04_SALES.md) — Quotation → Invoice → Payment
- [WF-05: Payments](./workflows/WF_05_PAYMENTS.md) — Receipt/Payment entries
- [WF-06: Reports](./workflows/WF_06_REPORTS.md) — Dashboard, stock, P&L reports

---

## 📂 Project Structure

```
ims1/
├── docs/                           # Documentation
│   ├── INDEX.md                    # This file - Navigation hub
│   ├── MASTER_SPEC.md              # Complete system specification
│   ├── guides/                     # How-to guides
│   │   ├── SETUP.md                # Installation & configuration
│   │   ├── CODING_STANDARDS.md     # Code quality standards
│   │   └── DATABASE.md             # Database setup & migration
│   ├── workflows/                  # Business workflow documentation
│   │   ├── WF_01_AUTH.md
│   │   ├── WF_02_MASTERS.md
│   │   ├── WF_03_PURCHASE.md
│   │   ├── WF_04_SALES.md
│   │   ├── WF_05_PAYMENTS.md
│   │   └── WF_06_REPORTS.md
│   └── design/                     # UI/UX guidelines
│       └── HMS_DESIGN_SYSTEM_MASTER.md
│
├── scripts/                        # Utility scripts
│   ├── setup_db.py                 # Database initialization
│   └── seed_db.py                  # Sample data seeding
│
├── backend/                        # FastAPI application
│   ├── app/                        # Main application code
│   │   ├── models/                 # SQLAlchemy models
│   │   ├── routers/                # API endpoints
│   │   ├── schemas/                # Pydantic validation schemas
│   │   ├── services/               # Business logic
│   │   ├── utils/                  # Utility functions
│   │   ├── config.py               # Configuration
│   │   ├── database.py             # Database setup
│   │   └── main.py                 # FastAPI app entry
│   ├── .env                        # Environment variables (local)
│   ├── .env.example                # Environment template
│   ├── requirements.txt            # Python dependencies
│   └── venv/                       # Virtual environment
│
├── frontend/                       # React application
│   ├── src/
│   │   ├── api/                    # API client functions
│   │   ├── components/             # Reusable components
│   │   ├── pages/                  # Page components
│   │   ├── store/                  # Zustand state management
│   │   ├── hooks/                  # Custom React hooks
│   │   ├── types/                  # TypeScript type definitions
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── .env                        # Frontend config (local)
│   ├── .env.example                # Frontend config template
│   ├── package.json
│   ├── tailwind.config.ts          # Tailwind CSS config
│   └── tsconfig.json               # TypeScript config
│
├── database/                       # Database migrations
│   ├── alembic/                    # Alembic migration tool
│   │   ├── versions/               # Migration scripts
│   │   ├── env.py                  # Alembic environment config
│   │   └── script.py.mako          # Migration template
│   └── alembic.ini                 # Alembic configuration
│
├── README.md                       # Project overview (start here)
├── .gitignore                      # Git ignore rules
└── .env.example                    # Environment template (root)
```

---

## 🚀 Quick Start

1. **First time setup?** → Read [Setup Guide](./guides/SETUP.md)
2. **Working on code?** → Check [Coding Standards](./guides/CODING_STANDARDS.md)
3. **Building a feature?** → Find related workflow in [Workflows](./workflows/)
4. **Designing UI?** → Use [HMS Design System](./design/HMS_DESIGN_SYSTEM_MASTER.md)
5. **Database issues?** → See [Database Guide](./guides/DATABASE.md)

---

## 📚 Key Documents

| Document | Purpose | Read Time |
|----------|---------|-----------|
| [MASTER_SPEC.md](./MASTER_SPEC.md) | Complete system specification | 30 min |
| [SETUP.md](./guides/SETUP.md) | Installation & configuration | 15 min |
| [CODING_STANDARDS.md](./guides/CODING_STANDARDS.md) | Code quality rules | 10 min |
| [HMS Design System](./design/HMS_DESIGN_SYSTEM_MASTER.md) | UI patterns | 20 min |
| Workflows (WF_*.md) | Feature workflows | 5-10 min each |

---

## 🔧 Development Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18 + TypeScript + Tailwind CSS |
| **Backend** | FastAPI + SQLAlchemy + PostgreSQL |
| **Database** | PostgreSQL 15+ (or SQLite for development) |
| **State Management** | Zustand (frontend) |
| **API Client** | React Query + Custom API layer |
| **Forms** | React Hook Form + Zod |
| **Authentication** | JWT (python-jose + passlib) |

---

## 💡 Common Tasks

### Add a New Feature
1. Read relevant workflow doc (WF_*.md)
2. Check [MASTER_SPEC.md](./MASTER_SPEC.md) for detailed requirements
3. Follow [Coding Standards](./guides/CODING_STANDARDS.md)
4. Use [HMS Design System](./design/HMS_DESIGN_SYSTEM_MASTER.md) for UI

### Set Up Development Environment
1. Follow [Setup Guide](./guides/SETUP.md)
2. Check environment variables in `.env.example`
3. Initialize database with scripts in `/scripts/`

### Deploy to Production
1. See production section in [SETUP.md](./guides/SETUP.md)
2. Configure environment variables securely
3. Run database migrations

---

## 📞 Support

- **Questions about the system?** → Check [MASTER_SPEC.md](./MASTER_SPEC.md)
- **How to implement something?** → Find workflow in [Workflows](./workflows/)
- **Code style issues?** → Review [Coding Standards](./guides/CODING_STANDARDS.md)
- **Design help?** → Use [HMS Design System](./design/HMS_DESIGN_SYSTEM_MASTER.md)

---

**Last Updated:** March 25, 2026  
**Version:** 1.0
