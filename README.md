# SpendWise - Personal Finance Tracker

## Overview

**SpendWise** is a Django-based personal finance management web application that helps users track expenses, manage budgets, and set savings goals.

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Django 5.x with Python |
| Database | SQLite (dev) / PostgreSQL (production) |
| Server | Gunicorn |
| Platform | Heroku, Render, Northflank |
| Frontend | HTML/CSS/JavaScript (PWA-enabled) |

---

## Features

### Authentication
- User signup/login/logout
- Email verification (optional)
- Session management

### Core Functionality

| Feature | Description |
|---------|-------------|
| **Transactions** | Track income & expenses by category (rent, transport, health, groceries, entertainment, shopping, food, utilities, other) |
| **Salary Management** | Set monthly salary |
| **Target Savings** | Set monthly savings target |
| **Excess Income** | Track additional income beyond salary |
| **Savings Goals** | Create, track, and auto-allocate funds to multiple goals with priority levels |
| **Dashboard** | Summary view with spending insights and motivation messages |
| **Monthly View** | Detailed monthly expense breakdown |
| **Profile** | User profile management with avatar support |

### API Endpoints

```
GET/POST  /api/transactions/           - Manage transactions
GET/PUT/DELETE /api/transactions/<id>/ - Transaction CRUD
POST       /api/transactions/<id>/update/   - Update transaction
POST       /api/transactions/<id>/delete/   - Delete transaction
GET/POST  /api/salary/                 - Set/query salary
GET/POST  /api/excess-income/         - Track extra income
GET/POST  /api/target-savings/        - Set savings target
GET       /api/dashboard/summary/     - Dashboard data
GET       /api/expenses-by-date/      - Expense breakdown by date
GET       /api/dad-joke/              - Random dad joke
GET       /api/motivation-message/    - Spending coach message
GET       /api/motivation-quote/      - Motivation quote
GET/POST  /api/goals/                 - Create/list savings goals
GET/PUT/DELETE /api/goals/<id>/       - Goal CRUD
POST       /api/goals/<id>/contribute/ - Contribute to goal
GET       /api/goals/allocations/     - Auto-allocation status
```

### Pages (URL Routes)

| URL | View | Description |
|-----|------|-------------|
| `/` | onboarding | Landing/onboarding page |
| `/signup/` | signup | User registration |
| `/login/` | login_view | User login |
| `/logout/` | logout_view | User logout |
| `/dashboard/` | dashboard | Main dashboard |
| `/monthly/` | monthly | Monthly expense view |
| `/savings/` | savings | Savings goals page |
| `/profile/` | profile_view | User profile |

---

## Database Models

### UserProfile
- One-to-one with Django User
- Fields: salary, target_savings, priority, avatar, email verification status

### Transaction
- Fields: user, title, amount, txn_type (income/expense), category, date, note, created_at

### SavingsGoal
- Fields: user, name, target_amount, saved_amount, priority, allocation_percentage, is_active, auto-allocation tracking

### ExcessIncome
- Fields: user, month (YYYY-MM), amount, note

---

## Project Structure

```
production1/
├── config/                  # Django configuration
│   ├── settings.py         # Settings (DEBUG, ALLOWED_HOSTS, DB, etc.)
│   ├── urls.py             # Root URL configuration
│   ├── wsgi.py             # WSGI application
│   └── asgi.py             # ASGI application
├── login/                  # Main application
│   ├── models.py           # Database models
│   ├── views.py            # View functions & API endpoints
│   ├── urls.py             # App URL routing
│   ├── admin.py            # Django admin configuration
│   ├── spending_coach.py   # Motivation/joke logic
│   └── templatetags/       # Custom template filters
├── templates/              # HTML templates
│   └── login/
│       ├── base_app.html   # Base app template
│       ├── base_auth.html  # Auth pages template
│       ├── dashboard.html  # Dashboard
│       ├── monthly.html    # Monthly view
│       ├── savings.html    # Savings goals
│       ├── profile.html    # Profile page
│       └── includes/       # Reusable components
├── static/                 # Static files
│   ├── login/              # App CSS
│   └── manifest.json       # PWA manifest
├── db.sqlite3/             # SQLite database (dev)
├── manage.py               # Django management CLI
├── Procfile                # Heroku deployment config
├── requirements.txt        # Python dependencies
├── build.sh                # Build script
└── render.yaml             # Render.com config
```

---

## Installation & Setup

### Prerequisites
- Python 3.10+
- pip or poetry

### Local Development

```bash
# Clone and navigate to project
cd production1

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver
```

### Deployment to Heroku

```bash
# Login to Heroku
heroku login

# Create new app
heroku create your-app-name

# Set environment variables
heroku config:set SECRET_KEY=your-secret-key
heroku config:set DEBUG=False

# Deploy
git push heroku main

# Run migrations
heroku run python manage.py migrate
```

### Deployment to Render

```bash
# Connect your GitHub repo to Render
# Render will automatically detect Django and run:
# - pip install -r requirements.txt
# - python manage.py migrate
# - gunicorn config.wsgi:application
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | Auto-generated (dev) |
| `DEBUG` | Debug mode | True (dev) |
| `ALLOWED_HOSTS` | Allowed hostnames | Local + ngrok + render |
| `DATABASE_URL` | PostgreSQL connection string | SQLite (dev) |
| `RENDER_EXTERNAL_HOSTNAME` | Render app hostname | - |

### Key Settings (config/settings.py)

- **DEBUG**: Set via `DEBUG` env var
- **ALLOWED_HOSTS**: 127.0.0.1, localhost, ngrok, render, configurable via env
- **CSRF_TRUSTED_ORIGINS**: ngrok and render domains

---

## Usage Guide

### First Time Setup
1. Visit the app URL
2. Complete onboarding
3. Set your salary
4. Set your target savings
5. Start adding transactions

### Adding Transactions
- Use the dashboard to add income/expenses
- Select category and date
- Add notes for reference

### Managing Savings Goals
1. Go to Savings page
2. Create new goal with target amount
3. Set priority (high/medium/low)
4. Allocate percentage of available savings
5. Auto-allocation runs monthly

### Monthly Review
- Check Monthly view for expense breakdown
- Review excess income
- Track progress towards savings goals

---

## PWA Features

The app is a Progressive Web App (PWA) with:
- Installable on mobile devices
- Offline capability (basic)
- Custom app icon and theme
- Mobile-optimized UI

---

## License

MIT License

---

## Support

For issues or questions, please open a GitHub issue.