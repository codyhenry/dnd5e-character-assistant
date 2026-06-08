# dnd5e-character-assistant

AI powered Django foundation for a D&D 5e campaign-scoped character builder with DM/player roles.

## Quick start

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Environment configuration

This project supports two runtime stages via `DJANGO_ENV`:

- `development` (or `dev`): local defaults, permissive hosts, debug-friendly behavior.
- `production` (or `prod`): hardened settings and required env vars.

### Development

Defaults to SQLite when no DB env vars are provided.

Optional env vars:

- `DJANGO_ENV=development`
- `DEBUG=true` (default in development)
- `DEV_DATABASE_URL` for local Postgres, including Docker setups
- `ALLOWED_HOSTS` as comma-separated values (optional)

Example for Docker Postgres in development:

```bash
export DJANGO_ENV=development
export DEV_DATABASE_URL=postgres://postgres:postgres@db:5432/dnd5e_character_assistant
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

### Production

Required env vars:

- `DJANGO_ENV=production`
- `SECRET_KEY`
- `DATABASE_URL`
- `ALLOWED_HOSTS` (comma-separated)

Optional production env vars:

- `CSRF_TRUSTED_ORIGINS` (comma-separated full origins)
- `SECURE_SSL_REDIRECT` (`true` by default)
- `SECURE_HSTS_SECONDS` (`31536000` by default)
- `SECURE_HSTS_INCLUDE_SUBDOMAINS` (`true` by default)
- `SECURE_HSTS_PRELOAD` (`true` by default)

## Test

```bash
python manage.py test
```
