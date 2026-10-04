---
id: technology-stack
title: Technology stack
sidebar_position: 3
description: Every runtime, service and Python dependency, with its exact version, role and license.
---

# Technology stack

Every dependency is pinned to an exact version. Adding or upgrading one requires
updating this page in the same commit.

## Runtime and services

| Component | Version | Role | License |
| --- | --- | --- | --- |
| Python | 3.12 (image `python:3.12-slim`) | Language runtime. Version chosen in [ADR 0001](architecture/decisions/0001-python-3-12.md). | PSF-2.0 |
| PostgreSQL with pgvector | image `pgvector/pgvector:pg17` (pgvector 0.8.7 measured) | Primary database; pgvector stores and searches embeddings. | PostgreSQL License |
| GNU gettext | 0.26 on the development machine | `makemessages` and `compilemessages`; development only, not in the image. | GPL-3.0-or-later |
| Docker Compose | v2 | Runs the `db` and `web` services locally. | Apache-2.0 |

## Python packages

Installed from `requirements.txt` with `pip install --only-binary=:all: -r requirements.txt`.
The file is the output of `pip freeze`, so it also pins transitive dependencies.

| Package | Version | Role | License |
| --- | --- | --- | --- |
| `Django` | 6.0.8 | Web framework: ORM, admin, migrations, test runner. | BSD-3-Clause |
| `cryptography` | 48.0.1 | Fernet encryption of stored API keys ([ADR 0014](architecture/decisions/0014-encrypted-api-keys.md)). | Apache-2.0 OR BSD-3-Clause |
| `cffi` | 2.1.1 | Transitive: C bindings for cryptography. | MIT-0 |
| `pycparser` | 3.0 | Transitive: for cffi. | BSD-3-Clause |
| `djangorestframework` | 3.18.1 | REST API framework ([ADR 0011](architecture/decisions/0011-api-design.md)). | BSD-3-Clause |
| `djangorestframework_simplejwt` | 5.5.1 | JWT access and refresh tokens, with its `token_blacklist` app ([ADR 0010](architecture/decisions/0010-jwt-authentication.md)). | MIT |
| `drf-spectacular` | 0.30.0 | OpenAPI 3 schema at `/api/schema/` and Swagger UI at `/api/docs/`. | BSD-3-Clause |
| `drf-spectacular-sidecar` | 2026.10.1 | Self-hosted Swagger UI and Redoc assets (no CDN). | BSD |
| `django-cors-headers` | 4.9.0 | CORS for `/api/` ([ADR 0012](architecture/decisions/0012-cors-policy.md)). | MIT |
| `PyJWT` | 2.15.1 | Transitive: token encoding for SimpleJWT. | MIT |
| `PyYAML` | 6.0.3 | Transitive: YAML schema output for drf-spectacular. | MIT |
| `jsonschema` | 4.26.0 | Transitive: schema validation for drf-spectacular. | MIT |
| `jsonschema-specifications` | 2025.9.1 | Transitive: for jsonschema. | MIT |
| `referencing` | 0.37.0 | Transitive: for jsonschema. | MIT |
| `rpds-py` | 2026.6.3 | Transitive: for referencing. | MIT |
| `attrs` | 26.1.0 | Transitive: for jsonschema and referencing. | MIT |
| `inflection` | 0.5.1 | Transitive: for drf-spectacular. | MIT |
| `uritemplate` | 4.2.0 | Transitive: for drf-spectacular. | BSD-3-Clause OR Apache-2.0 |
| `django-unfold` | 0.108.0 | Admin theme: styled templates, sidebar, language switcher ([ADR 0008](architecture/decisions/0008-unfold-admin-theme.md)). Ships no ar/fr translations; see `locale_vendor/unfold`. | MIT |
| `django-countries` | 9.1.0 | `CountryField` (ISO 3166-1 codes) for `Center.country`, with country names translated into Arabic and French. | MIT |
| `Pillow` | 12.3.0 | Image processing required by Django's `ImageField` (`User.avatar`, `Center.logo`). | MIT-CMU |
| `asgiref` | 3.12.1 | ASGI support; required by Django. | BSD-3-Clause |
| `sqlparse` | 0.6.0 | SQL formatting; required by Django. | BSD-3-Clause |
| `psycopg` | 3.3.6 | PostgreSQL driver (psycopg 3) used by Django's PostgreSQL backend. | LGPL-3.0-only |
| `psycopg-binary` | 3.3.6 | Precompiled implementation of psycopg, bundling libpq; avoids a system libpq and a compiler. | LGPL-3.0-only |
| `pgvector` | 0.5.0 | `VectorField`, distance functions and indexes for Django (`pgvector.django`). | MIT |
| `gunicorn` | 26.2.0 | WSGI server in the `web` container. | MIT |
| `python-dotenv` | 1.1.1 | Loads `.env` into the process environment. Must stay on 1.1.x: CrewAI 1.9.3 requires `python-dotenv~=1.1.1`. | BSD-3-Clause |
| `typing_extensions` | 4.16.0 | Transitive: required by psycopg on Python versions before 3.13 (`typing-extensions>=4.6`). | PSF-2.0 |

Licenses are taken from each installed package's metadata (`License-Expression`, or the
license classifier where no expression is declared). The LGPL-3.0 license of psycopg
applies to the library itself; using it as an unmodified dependency places no
obligations on this project's own code.

## Platform wheel coverage

Every pin was checked for a prebuilt CPython 3.12 wheel with
`pip download --only-binary=:all: --no-deps --python-version 3.12 --platform ...`
on 2026-10-04. All packages resolved on all three platforms; the native ones added in
the API step (`PyYAML`, `rpds-py`) ship `macosx_10_12`/`10_13_x86_64`, `manylinux_2_17_x86_64`
and `manylinux_2_17_aarch64` wheels.

| Platform | Platform tag passed | `psycopg-binary` wheel found | Other packages |
| --- | --- | --- | --- |
| macOS 12 Intel | `macosx_12_0_x86_64` | `macosx_10_13_x86_64` | Pillow `macosx_10_13_x86_64`; others pure Python (`py3-none-any`, django-unfold included) |
| Linux x86_64 | `manylinux_2_17` to `manylinux_2_36`, `manylinux2014` | `manylinux_2_17_x86_64` | Pillow `manylinux_2_28_x86_64`; others pure Python |
| Linux aarch64 | `manylinux_2_17` to `manylinux_2_36`, `manylinux2014` | `manylinux_2_28_aarch64` | Pillow `manylinux_2_28_aarch64`; others pure Python |

`pip download --platform` accepts only the exact tags given and does not expand to
older glibc tags. A single `--platform manylinux_2_28_x86_64` therefore misses the
`manylinux_2_17_x86_64` wheel even though it is installable there. The Linux checks pass
the full tag range up to glibc 2.36. The `python:3.12-slim` image measured at glibc 2.41,
which satisfies every wheel listed.

## Bundled assets

| Asset | Version | Role | License |
| --- | --- | --- | --- |
| Readex Pro (Thomas Jockin, Nadine Chahine, Bonnie Shaver-Troup, Santiago Orozco, Héctor Gómez) | Google Fonts v27, variable WOFF2, weight 160 to 700; Arabic, Latin and Latin Extended subsets | Admin typeface, self-hosted in `core/static/core/fonts/readex-pro/` | SIL Open Font License 1.1 (`OFL.txt` alongside the fonts) |

## Planned

| Package | Version | Role | Notes |
| --- | --- | --- | --- |
| `crewai` | 1.9.3 | AI agent orchestration. | Not installed yet. Constrains Python to `>=3.10,<3.14` and python-dotenv to `~=1.1.1`. |
