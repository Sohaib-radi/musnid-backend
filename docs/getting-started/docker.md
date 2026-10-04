---
id: docker
title: Docker
sidebar_position: 2
description: The Compose services, the application image and how they are wired together.
---

# Docker

`docker-compose.yml` defines two services. Both read `.env` from the repository root.
Ports are published on `127.0.0.1` only, so nothing is exposed to the local network.

| Service | Container | Image | Host port | Started by |
| --- | --- | --- | --- | --- |
| `db` | `musnid_backend_postgres` | `pgvector/pgvector:pg17` | `127.0.0.1:5435` to `5432` | `docker compose up -d db` (no profile: always) |
| `web` | `musnid_backend_web` | built from `Dockerfile` | `127.0.0.1:8011` to `8000` | `docker compose --profile web up -d --build` |

## Commands

```bash
docker compose up -d db                       # database only (local development)
docker compose --profile web up -d --build    # database and application
docker compose --profile web logs -f web      # application logs
docker compose --profile web down             # stop both; data is kept
```

The admin is then at `http://127.0.0.1:8011/admin/`.

## Service `db`

- PostgreSQL 17 with the pgvector extension installed (not yet enabled in any database;
  the first migration that needs it will run `CREATE EXTENSION vector`).
- `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD` from `.env` create the database
  and role on the first start of an empty volume. Changing them later has no effect on
  an existing volume.
- Data lives in the named volume `musnid_backend_pgdata`. The name is set explicitly
  because other projects on the development machine already use `musnid_db` and
  `musnid_backend_db`.
- Healthcheck: `pg_isready` every 5 seconds. The `web` service waits until it passes.

## Service `web`

- Overrides `POSTGRES_HOST=db` and `POSTGRES_PORT=5432`: inside the Compose network the
  database is reached by service name on its internal port, not on the host port 5435.
  Process environment variables take precedence over `.env`, and `.env` is not in the
  image in any case.
- On start it runs `migrate --noinput`, then `exec gunicorn config.wsgi:application`
  with 3 sync workers on port 8000. `exec` makes gunicorn PID 1 so it receives
  `SIGTERM` from `docker compose stop` directly.
- Only active under the `web` profile, so `docker compose up -d db` never builds it.

## Image

`Dockerfile`, based on `python:3.12-slim`:

1. Installs `requirements.txt` with `--only-binary=:all:` in its own layer, so code
   changes do not reinstall dependencies.
2. Copies the code (filtered by `.dockerignore`: no `.env`, `.venv`, `data/`, `media/`,
   `staticfiles/`, `docs/`, `.git`).
3. Runs `collectstatic` at build time into `/app/staticfiles`. Settings require
   `DJANGO_SECRET_KEY` and the `POSTGRES_*` variables at import time, so throwaway
   values are passed to that single `RUN` step only; they are not stored in the image
   environment and the real values come from `.env` at runtime.
4. Runs as the unprivileged user `app` (UID 1000).

Measured on the built image: Python 3.12.15, Debian glibc 2.41.

## Known limitations

- **Static files are not served by gunicorn yet.** `collectstatic` runs at build time,
  but gunicorn does not serve `/static/`, so `/static/admin/css/base.css` returns 404 and
  the admin renders without styling at port 8011. Use `manage.py runserver` with
  `DJANGO_DEBUG=True` for development (see [Local development](local-development.md)).
  Static file serving (WhiteNoise or nginx) comes with deployment.
- **Migrations run on every start.** Acceptable with a single `web` container; with
  several replicas, migrations should move to a one-off job.
