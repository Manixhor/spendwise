# SpendWise — Personal Finance Tracker

## Overview

**SpendWise** is a Django-based personal finance management PWA that helps users track expenses, manage budgets, and set savings goals. It features a polished Apple-inspired glassmorphic UI, a spending coach, AI-powered motivation messages, and full export capabilities.

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Django 6.0.4 with Python |
| Database | SQLite (dev) / PostgreSQL (production) |
| Server | Gunicorn |
| Platform | Render (primary), Heroku, Northflank |
| Frontend | HTML/CSS/JavaScript (PWA-enabled) |
| Auth | django-allauth (email + Google OAuth) |
| Static | WhiteNoise |
| AI | OpenAI API (motivation messages, optional) |
| Exports | ReportLab-style PDF, CSV, openpyxl (XLSX) |

---

## Features

### Authentication
- Email + password signup with 6-digit OTP verification
- Login / Logout
- Forgot password flow with OTP reset
- Google OAuth sign-in (via django-allauth)
- Session management with CSRF protection

### Core Functionality

| Feature | Description |
|---------|-------------|
| **Transactions** | Track income & expenses across 10 categories (rent, transport, health, groceries, entertainment, shopping, food, utilities, lend, other) |
| **Salary Management** | Set monthly salary for budget calculations |
| **Target Savings** | Set monthly savings target |
| **Excess Income** | Track additional income beyond salary per month |
| **Savings Goals** | Create multiple goals with priority-based auto-allocation (high/medium/low) |
| **Dashboard** | Real-time summary with spending ring, category breakdown, 6-month trend chart, daily spending bar chart, expense insights donut, stock-style trend card, and motivation quotes |
| **Monthly Analysis** | Detailed monthly breakdown with weekly bar chart, category donut, top spending days, month-over-month comparison, and financial health score |
| **Lend Tracker** | Track money lent to others with pending/paid status and mark-as-paid functionality |
| **Profile** | User profile with name, email, and avatar upload |

### Smart Features

| Feature | Description |
|---------|-------------|
| **Spending Coach** | Contextual messages based on salary spend percentage (excellent/good/warning/high/critical) |
| **Motivation Quotes** | AI-powered or locally-generated quotes based on savings progress, with context-aware buckets (broke, just started, making progress, almost there, goal reached, no goals) |
| **Dad Jokes** | Fun dad jokes from icanhazdadjoke.com with local fallbacks |
| **Auto-Allocation** | Automatic monthly allocation of available savings to goals based on priority weights (high=3x, medium=2x, low=1x) |
| **Chatbot Nudges** | Real-time salary-aware messages after recording expenses |

### Export & Reporting

| Feature | Description |
|---------|-------------|
| **PDF Export** | Download monthly analysis as PDF |
| **CSV Export** | Download monthly transactions as CSV |
| **XLSX Export** | Download monthly report as Excel spreadsheet |
| **Email Reports** | Send monthly analysis report via email |
| **Scheduled Mailer** | Management command to batch-send monthly emails to all users |

### PWA Features

| Feature | Description |
|---------|-------------|
| **Installable** | Add to home screen on iOS and Android |
| **Standalone Mode** | Full-screen app-like experience with safe area handling |
| **Responsive** | Optimized for all screen sizes with iOS keyboard-aware layout |
| **Offline Support** | Service worker for basic offline capability |
| **App Shortcuts** | Quick access to Dashboard, Monthly, and Savings from home screen |

### Pages

| URL | Description |
|-----|-------------|
| `/` | Onboarding / landing page |
| `/signup/` | User registration |
| `/signup/verify/` | OTP email verification |
| `/login/` | User login |
| `/logout/` | User logout |
| `/forgot-password/` | Password reset (email entry) |
| `/forgot-password/verify/` | Password reset (OTP verification) |
| `/forgot-password/reset/` | Password reset (new password) |
| `/dashboard/` | Main dashboard |
| `/monthly/` | Monthly analysis view |
| `/savings/` | Savings goals page |
| `/lend/` | Lend tracker |
| `/profile/` | User profile |

---

## API Endpoints

### Transactions
```
POST      /api/transactions/                - Add transaction
PUT       /api/transactions/<id>/update/    - Update transaction
DELETE    /api/transactions/<id>/delete/    - Delete transaction
POST      /api/transactions/<id>/mark-paid/ - Mark lend as paid back
```

### Financials
```
POST      /api/salary/                      - Set monthly salary
POST      /api/excess-income/               - Track extra income
POST      /api/target-savings/              - Set savings target
GET       /api/dashboard/summary/           - Dashboard data
GET       /api/expenses-by-date/?date=      - Expenses filtered by date
```

### Savings Goals
```
POST      /api/goals/                       - Create goal
PUT       /api/goals/<id>/                  - Update goal
DELETE    /api/goals/<id>/delete/           - Delete goal
POST      /api/goals/<id>/contribute/       - Contribute to goal
GET       /api/goals/allocations/           - Allocation breakdown (read-only)
```

### Fun & Motivation
```
GET       /api/dad-joke/                    - Random dad joke
GET       /api/motivation-message/          - Spending coach message
GET       /api/motivation-quote/            - Motivation quote
```

### Export & Reports
```
POST      /monthly/email/                   - Email monthly analysis
GET       /monthly/export/pdf/              - Download PDF report
GET       /monthly/export/csv/              - Download CSV report
GET       /monthly/export/xlsx/             - Download Excel report
```

---

## Database Models

### UserProfile
- One-to-one with Django User
- Fields: salary, target_savings, priority, avatar, email verification code/status, password reset code/status

### Transaction
- Fields: user, title, amount, txn_type (income/expense), category (10 choices), date, note, is_settled (for lend tracking), created_at

### SavingsGoal
- Fields: user, name, target_amount, saved_amount, priority (high/medium/low), allocation_percentage, is_active, last_allocated_month, current_month_auto_allocation
- Properties: progress_pct, is_complete, remaining, is_active_goal

### ExcessIncome
- Fields: user, month (YYYY-MM), amount, note
- Unique together: user + month

### MonthlyAnalysisMailSetting
- Fields: enabled, send_day (1-28), send_time, last_sent_month, last_sent_at

### PageView
- Fields: user, path, view_count, last_viewed
- Tracks page views per user for analytics

---

## Project Structure

```
production1/
├── config/                      # Django configuration
│   ├── settings.py             # Settings (DEBUG, ALLOWED_HOSTS, DB, etc.)
│   ├── urls.py                 # Root URL configuration
│   ├── wsgi.py                 # WSGI application
│   └── asgi.py                 # ASGI application
├── login/                      # Main application
│   ├── models.py              # Database models (UserProfile, Transaction, SavingsGoal, etc.)
│   ├── views.py               # View functions & all API endpoints
│   ├── urls.py                # App URL routing
│   ├── admin.py               # Django admin configuration
│   ├── admin_views.py         # Admin analytics views
│   ├── adapters.py            # django-allauth social account adapter
│   ├── middleware.py           # PageView tracking middleware
│   ├── signals.py             # Django signals
│   ├── spending_coach.py      # Spending coach & motivation logic
│   ├── monthly_mailer.py      # Scheduled monthly email batch sender
│   ├── apps.py                # App configuration
│   ├── tests.py               # Test suite
│   ├── templatetags/           # Custom template filters (currency, etc.)
│   ├── management/             # Management commands (monthly mailer)
│   └── migrations/             # Database migrations
├── templates/                  # HTML templates
│   └── login/
│       ├── base_app.html      # Base app template (dashboard, monthly, savings, etc.)
│       ├── base_auth.html     # Auth pages template (glassmorphic card layout)
│       ├── onboarding.html    # Landing/onboarding page
│       ├── signup.html        # User registration
│       ├── signup_verify.html # OTP verification
│       ├── login.html         # User login
│       ├── forgot_password.html
│       ├── forgot_password_verify.html
│       ├── forgot_password_reset.html
│       ├── dashboard.html     # Main dashboard
│       ├── monthly.html       # Monthly analysis view
│       ├── savings.html       # Savings goals
│       ├── lend.html          # Lend tracker
│       ├── profile.html       # User profile
│       ├── emails/            # Email templates (OTP, monthly analysis)
│       └── includes/          # Reusable components
├── static/                     # Static files
│   ├── login/
│   │   ├── auth.css           # Auth pages styling (glassmorphic, PWA-responsive)
│   │   ├── dashboard.css      # Dashboard styling
│   │   ├── monthly.css        # Monthly view styling
│   │   ├── savings.css        # Savings page styling
│   │   ├── lend.css           # Lend tracker styling
│   │   ├── profile.css        # Profile page styling
│   │   ├── auth_enter.js      # Enter key navigation for forms
│   │   ├── ios_keyboard.js    # iOS PWA keyboard handling
│   │   └── expense_chatbot.js # Expense chatbot interaction
│   ├── dist/                  # Build output
│   ├── icons/                 # PWA icons (192px, 512px, maskable)
│   ├── images/                # App images
│   └── manifest.json          # PWA manifest
├── generated_pdfs/            # Generated PDF reports
├── media/                     # User uploads (avatars)
├── staticfiles/               # Collected static files (production)
├── db.sqlite3                 # SQLite database (dev)
├── manage.py                  # Django management CLI
├── Procfile                   # Heroku deployment config
├── requirements.txt           # Python dependencies
├── build.sh                   # Build script
├── render.yaml                # Render.com deployment config
└── .env                       # Environment variables (local)
```

---

## Installation & Setup

### Prerequisites
- Python 3.10+
- pip
- Node.js (optional, for asset build)

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

# Create superuser (optional)
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### Environment Variables

Create a `.env` file in the project root:

```env
# Required
SECRET_KEY=your-secret-key
DEBUG=True

# Database (optional — defaults to SQLite)
DATABASE_URL=postgres://user:pass@localhost:5432/spendwise

# Email (optional — defaults to console backend)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=you@gmail.com
SMTP_PASSWORD=app-password
SMTP_FROM_EMAIL=SpendWise <you@gmail.com>

# Google OAuth (optional)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# OpenAI (optional — for AI motivation messages)
OPENAI_API_KEY=sk-...
```

### Deployment to Render

```bash
# Connect your GitHub repo to Render
# Render will automatically detect Django and run:
# - pip install -r requirements.txt
# - python manage.py migrate
# - gunicorn config.wsgi:application
```

### Deployment to Heroku

```bash
heroku login
heroku create your-app-name
heroku config:set SECRET_KEY=your-secret-key DEBUG=False
heroku config:set DATABASE_URL=your-postgres-url
git push heroku main
heroku run python manage.py migrate
```

---

## Usage Guide

### First Time Setup
1. Visit the app URL
2. Sign up with your email
3. Verify your account with the 6-digit OTP
4. Complete onboarding — set your salary and savings target
5. Start adding transactions

### Adding Transactions
- Use the dashboard to add income/expenses
- Select category and date
- For lending money, use the "Lend" category — you can mark it as paid back later
- Add notes for reference

### Managing Savings Goals
1. Go to Savings page
2. Create goals with target amounts
3. Set priority (high/medium/low) — higher priority goals receive more auto-allocation
4. Set allocation percentage for each goal
5. Auto-allocation runs monthly, distributing available savings proportionally by priority

### Lend Tracker
1. Go to Lend page
2. View all pending and paid-back lending records
3. Mark lent amounts as "paid back" when received
4. Settled lends are excluded from active expense calculations

### Monthly Review
- Navigate to Monthly Analysis
- Browse any month with the month picker
- Review weekly income vs expense bar chart
- Check category breakdown and top spending days
- View your monthly financial health score
- Export reports as PDF, CSV, or XLSX
- Email the report to yourself

---

## Configuration

### Key Settings (config/settings.py)

| Setting | Description |
|---------|-------------|
| `DEBUG` | Debug mode via `DEBUG` env var (default: True) |
| `ALLOWED_HOSTS` | 127.0.0.1, localhost, ngrok, render — configurable via env |
| `CSRF_TRUSTED_ORIGINS` | ngrok and render domains |
| `EMAIL_VERIFICATION_CODE_EXPIRY_MINUTES` | OTP expiry (default: 10 min) |
| `OPENAI_MOTIVATION_MODEL` | Model for AI motivation (default: gpt-4.1-mini) |

### Production Security

When `DEBUG=False`, the following are automatically enabled:
- Secure session and CSRF cookies
- SSL redirect
- SameSite=None cookies

---

## License

MIT License

---

## Support

For issues or questions, please open a GitHub issue.