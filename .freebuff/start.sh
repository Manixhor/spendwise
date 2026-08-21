#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export DB_ENGINE=sqlite
cd /Users/mani/Documents/production1
exec /Users/mani/Documents/production1/.venv/bin/python manage.py runserver 0.0.0.0:8000
