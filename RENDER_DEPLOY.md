# Render Deployment

This project can be deployed on Render with MySQL.

Important note:
- Render does support MySQL, but not as a first-class managed database like Postgres.
- On Render, MySQL runs as a private image-backed service with a persistent disk.

Files added for deploy:
- `render.yaml`
- `build.sh`
- `requirements.txt`

## What the blueprint creates

`render.yaml` defines:
- `spendwise-web`: the Django web service
- `spendwise-mysql`: a private MySQL 8 service with a persistent disk

The web service reads these database values from the MySQL service automatically:
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

## Render setup

1. Push this repo to GitHub.
2. In Render, open `Blueprints`.
3. Create a new blueprint from this repository.
4. Review the generated services:
   - web service: `spendwise-web`
   - private MySQL service: `spendwise-mysql`
5. Apply the blueprint.

## Build and start

Web service commands:
- Build: `./build.sh`
- Pre-deploy: `python manage.py migrate --noinput`
- Start: `gunicorn config.wsgi:application`

## Environment variables

These are already handled in `render.yaml`:
- `SECRET_KEY`
- `DEBUG=false`
- `USE_WHITENOISE=1`
- MySQL connection variables from the private database service

Optional variables you can add later:
- `OPENAI_API_KEY`
- `OPENAI_MOTIVATION_MODEL`
- `MAILTRAP_SMTP_HOST`
- `MAILTRAP_SMTP_PORT`
- `MAILTRAP_SMTP_USER`
- `MAILTRAP_SMTP_PASSWORD`
- `MAILTRAP_FROM_EMAIL`

## Static files

Production static files are collected into `staticfiles/` and served with WhiteNoise.

## Notes

- Media uploads are not persisted yet. Render's web filesystem is ephemeral.
- If you want persistent user-uploaded media, use S3-compatible storage later.
- The MySQL private service uses a disk mounted at `/var/lib/mysql`, which is required by the official MySQL image.
