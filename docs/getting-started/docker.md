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
- On start it runs `migrate --noinput` and `createcachetable` (the throttle counters'
  table), then `exec gunicorn config.wsgi:application` on port 8000 with 3 workers of
  2 threads each and a 120 s timeout: answers take 19.8 to 45.6 s
  ([ADR 0017](../architecture/decisions/0017-anonymous-ask-api.md)). `exec` makes
  gunicorn PID 1 so it receives `SIGTERM` from `docker compose stop` directly.
- A proxy in front of port 8011 must allow at least 120 s per request, and
  `DJANGO_NUM_PROXIES` must count it so per-IP limits see the client's address.
- Static files are collected at build time and served by WhiteNoise inside gunicorn
  ([ADR 0018](../architecture/decisions/0018-single-vps-deployment.md)), so the admin keeps
  its styles with `DEBUG` off. Production setup: [Deployment](deployment.md).
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

With CrewAI (2026-10-04): image **1.18 GB** (375 MB before), build about 14 minutes
(pip install 558.8 s, layer export 252.0 s). PyMuPDF is not in the image (tools only).
Checked in the container: `migrate` (37 applied, none pending), admin on port 8011, and
`ask_test "هل انتشر الإسلام بالسيف؟"` (answer citing #229, 32,613 / 2,497 tokens, 32.2 s).

With the ask API (2026-10-04): image **1.18 GB**, build 13 min 10 s (pip install 558.3 s,
layer export 204.4 s; the dependency layer was rebuilt because the CrewAI `ENV` lines
precede it). Checked in the container:

| Check | Result |
| --- | --- |
| Start-up | `migrate` (nothing pending), `createcachetable`, admin 200 on port 8011 |
| gunicorn (`/proc/1/cmdline`) | `--workers 3 --threads 2 --timeout 120`, worker class `gthread`, 3 workers booted |
| `ask_test "هل انتشر الإسلام بالسيف؟"` in a new container | answer, level B, 6 sentences kept (all #229, key sentence "الإسلام لم ينتشر بالسيف" first), 0 dropped, 31,852 / 1,730 tokens, 32.2 s; command wall time 63 s including start-up |
| CrewAI trace prompt | not shown |

The first start of this image ran gunicorn without its options: the options sat on a
more-indented line of the folded `command: >` block in `docker-compose.yml`, which YAML
keeps as a separate line, so `sh` never passed them. The command is now on one line.

## Known limitations

- **CrewAI first-run prompt in containers (fixed, checked 2026-10-04).** In a fresh container CrewAI showed "view your execution traces? [y/N] (20s
  timeout)" on the first crew runs of each process (seen twice in one `ask_test`), adding
  up to 20 s each. CrewAI decides when it is imported, so the decline that `agents/flow.py`
  recorded came too late. `AgentsConfig.ready()` now records it in every process before
  CrewAI is imported (`agents/tracing.py`), and the image sets CrewAI's telemetry and
  tracing switches off ([Configuration](configuration.md#crewai-switches)). The decline
  lives in the home directory of user `app` (`~/.local/share/app/.crewai_user.json`); a
  fresh container writes it again on start. Checked in the rebuilt image: no prompt in a
  brand-new container whose first process was `ask_test`.

- **Migrations run on every start.** Acceptable with a single `web` container; with
  several replicas, migrations should move to a one-off job.
