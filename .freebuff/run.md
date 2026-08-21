# SpendWise Preview

## Reproduce artifacts

No special build step. Django serves templates and static files directly.

- The `.env` file is already in the repo root.
- `db.sqlite3` already exists with data.
- Run `python manage.py collectstatic --no-input` if static files changed.

## Run the server

An existing Django dev server is already running on **port 8000** (PID 42220, session s000).

```bash
cd /Users/mani/Documents/production1
.venv/bin/python manage.py runserver 0.0.0.0:8000
```

No `DATABASE_URL` in `.env`, so the fallback SQLite config is used.
