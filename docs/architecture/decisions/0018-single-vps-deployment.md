---
id: 0018-single-vps-deployment
title: "ADR 0018: Single-VPS deployment behind host nginx"
sidebar_position: 18
description: Production on one Ubuntu 22.04 VPS with Docker Compose, nginx and Let's Encrypt on the host, and WhiteNoise for static files.
---

# ADR 0018: Single-VPS deployment behind host nginx

## Status

Accepted, 2026-10-05.

## Context

The backend needs a public HTTPS address for the competition judges and for the
frontend, which is hosted on Vercel. The available server is one VPS with 4 cores, 6 GB
RAM and 120 GB SSD; of the images offered, Ubuntu 20.04 has left standard support, so
Ubuntu 22.04 LTS is used. The domain is `musnid.online`; Vercel serves the frontend.

The existing image and `docker-compose.yml` already run gunicorn, but with `DEBUG` off
nothing served `/static/`, so the admin had no styles, and Django had no HTTPS settings:
behind a TLS-terminating proxy it saw every request as HTTP and sent cookies without the
`Secure` flag. Local development (HTTP, `runserver`, `DEBUG=True`) must keep working
without changes to the developer's `.env`.

## Decision

- **Hostname**: the backend is `api.musnid.online`, leaving `musnid.online` to the
  Vercel frontend. CORS lists the Vercel origin ([ADR 0012](0012-cors-policy.md)).
- **One Compose file** for development and production. The VPS runs the same `db` and
  `web` services; only `.env` differs. Ports stay bound to `127.0.0.1`, which also keeps
  them out of reach despite Docker bypassing ufw.
- **nginx and certbot on the host**, from Ubuntu's packages, proxying to
  `127.0.0.1:8011` (`deploy/nginx/api.musnid.online.conf`). certbot's nginx plugin adds
  the certificate and its systemd renewal timer. Running them in Compose was rejected:
  certificate issuance and renewal need extra containers and shared volumes for no gain on
  one server. nginx overwrites `X-Forwarded-Proto`, appends to `X-Forwarded-For`
  (`DJANGO_NUM_PROXIES=1`) and waits 130 s, above gunicorn's 120 s timeout.
- **WhiteNoise for static files**, right after `SecurityMiddleware`, with
  `CompressedStaticFilesStorage`. Serving from an nginx volume was rejected: every deploy
  would have to copy files out of the image. The manifest (hashed names) variant was
  rejected because it raises for any static reference missing from the manifest, which
  breaks tests and local runs that never ran `collectstatic`; without hashed names
  WhiteNoise's default cache lifetime of 60 s applies.
- **HTTPS settings behind one flag**, `DJANGO_HTTPS`, strict like `DJANGO_DEBUG`. It sets
  `SECURE_PROXY_SSL_HEADER`, secure session and CSRF cookies and `SECURE_SSL_REDIRECT`.
  `DJANGO_HSTS_SECONDS` is separate, defaults to 0 and is raised in steps after HTTPS
  works, because browsers cannot be made to forget HSTS early. `includeSubDomains` and
  `preload` are not set: other hosts of the domain are not served from here.
- **Access**: the server exists only for the competition, so it runs as `root` with an
  SSH key; password login is turned off, and no separate deploy user was created.
- **Admin prerequisites**: production starts with an empty database, so the OpenAI key
  and an approved default center are added in the admin before the first question.
- **Knowledge base by data copy**: the two `knowledge_*` tables are dumped from the
  development database and restored data-only into the migrated production database.
  Source books are not in git and PyMuPDF stays out of production (AGPL), so re-running
  extraction on the server was rejected. Users, keys and questions are not copied.
- Steps, `.env` values, backups and updates: [Deployment](../../getting-started/deployment.md).

## Consequences

- With none of the new variables set, settings are exactly as before; local development
  needs no change. `core/tests/test_settings.py` checks both states.
- Admin and Swagger assets are served with `DEBUG` off, locally at port 8011 too.
- Static files are cached by browsers for 60 s only, as names are not hashed.
- One server is a single point of failure, and daily dumps stay on its disk until copied
  off. Restarting `web` for an update cuts answers in progress.
- A new dependency, `whitenoise` 6.12.0 (MIT, pure Python), listed in the
  [technology stack](../../technology-stack.md).
