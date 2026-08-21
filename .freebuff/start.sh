#!/bin/bash
cd /Users/mani/Documents/production1
export DB_ENGINE=sqlite
exec .venv/bin/python manage.py runserver 0.0.0.0:8080
