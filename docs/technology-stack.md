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
| Docker Compose | v2 | Runs the `db` and `web` services locally and on the VPS. | Apache-2.0 |
| Docker Engine | 29.8.2 on the VPS (Docker's apt repository) | Runs the Compose services in production. | Apache-2.0 |
| Ubuntu | 22.04 LTS | Production VPS operating system ([Deployment](getting-started/deployment.md)). | Various (mostly GPL) |
| nginx | 1.18.0 (Ubuntu 22.04 package) | Production reverse proxy and TLS termination on the host ([ADR 0018](architecture/decisions/0018-single-vps-deployment.md)). | BSD-2-Clause |
| certbot (with `python3-certbot-nginx`) | Ubuntu 22.04 package | Let's Encrypt certificate for `api.musnid.online` and its renewal timer. | Apache-2.0 |

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
| `whitenoise` | 6.12.0 | Serves collected static files from gunicorn, gzip-compressed ([ADR 0018](architecture/decisions/0018-single-vps-deployment.md)). Pure Python (`py3-none-any`). | MIT |
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

## Tools (not installed in production)

| Package | Version | Role | License |
| --- | --- | --- | --- |
| `PyMuPDF` | 1.28.2 | PDF text extraction in `extract_bayyinat`, from `requirements-tools.txt` only. | AGPL-3.0 (dual-licensed): never in `requirements.txt` or the Docker image |

## External services

| Service | Model | Role |
| --- | --- | --- |
| OpenAI embeddings | `text-embedding-3-small` (1536 dimensions) | Embeddings of chunks and queries ([ADR 0015](architecture/decisions/0015-knowledge-base-and-retrieval.md)); called over HTTPS with the standard library. |

## Bundled assets

| Asset | Version | Role | License |
| --- | --- | --- | --- |
| Readex Pro (Thomas Jockin, Nadine Chahine, Bonnie Shaver-Troup, Santiago Orozco, Héctor Gómez) | Google Fonts v27, variable WOFF2, weight 160 to 700; Arabic, Latin and Latin Extended subsets | Admin typeface, self-hosted in `core/static/core/fonts/readex-pro/` | SIL Open Font License 1.1 (`OFL.txt` alongside the fonts) |

## Planned

| Package | Version | Role | Notes |
| --- | --- | --- | --- |
| `crewai` | 1.9.3 | AI agent orchestration. | Not installed yet. Constrains Python to `>=3.10,<3.14` and python-dotenv to `~=1.1.1`. |


## CrewAI and its dependencies

`crewai` 1.9.3 runs the agents ([ADR 0016](architecture/decisions/0016-question-answering-flow.md)).
Installing it added the 118 packages below (generated from each package's metadata on
2026-10-04). All have wheels for macOS 12 Intel, Linux x86_64 and Linux aarch64; on macOS 12
`onnxruntime` resolves to 1.19.2 as predicted by ADR 0001. Except `crewai`, `openai` and
`pydantic`, they are transitive. Telemetry and tracing are disabled in settings.

| Package | Version | License |
| --- | --- | --- |
| `aiohappyeyeballs` | 2.7.1 | Python Software Foundation License |
| `aiohttp` | 3.14.3 | Apache-2.0 AND MIT |
| `aiosignal` | 1.4.0 | Apache Software License |
| `aiosqlite` | 0.21.0 | MIT License |
| `annotated-doc` | 0.0.5 | MIT |
| `annotated-types` | 0.8.0 | MIT |
| `anyio` | 4.15.1 | MIT |
| `appdirs` | 1.4.4 | MIT License |
| `backoff` | 2.2.1 | MIT License |
| `bcrypt` | 5.0.0 | Apache Software License |
| `build` | 1.6.1 | MIT |
| `certifi` | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) |
| `cfgv` | 3.5.0 | MIT |
| `charset-normalizer` | 3.5.2 | MIT |
| `chromadb` | 1.1.1 | Apache Software License |
| `click` | 8.1.8 | BSD License |
| `coloredlogs` | 15.0.1 | MIT License |
| `crewai` | 1.9.3 | MIT (from the repository's LICENSE; the wheel declares none) |
| `diskcache` | 5.6.3 | Apache Software License |
| `distlib` | 0.4.3 | Python Software Foundation License |
| `distro` | 1.9.0 | Apache Software License |
| `docstring_parser` | 0.18.0 | MIT License |
| `durationpy` | 0.11 | MIT |
| `et_xmlfile` | 2.0.0 | MIT License |
| `filelock` | 4.0.10 | MIT |
| `flatbuffers` | 25.12.19 | Apache Software License |
| `frozenlist` | 1.8.0 | Apache-2.0 |
| `fsspec` | 2026.9.0 | BSD-3-Clause |
| `googleapis-common-protos` | 1.75.0 | Apache Software License |
| `grpcio` | 1.84.0 | Apache-2.0 |
| `h11` | 0.16.0 | MIT License |
| `hf-xet` | 1.6.0 | Apache-2.0 |
| `httpcore` | 1.0.9 | BSD-3-Clause |
| `httptools` | 0.8.0 | MIT |
| `httpx` | 0.28.1 | BSD License |
| `httpx-sse` | 0.4.3 | MIT |
| `huggingface_hub` | 0.36.2 | Apache Software License |
| `humanfriendly` | 10.0 | MIT License |
| `identify` | 2.6.20 | MIT |
| `idna` | 3.20 | BSD-3-Clause |
| `importlib_metadata` | 8.7.1 | Apache-2.0 |
| `importlib_resources` | 7.1.0 | Apache-2.0 |
| `instructor` | 1.12.0 | MIT |
| `Jinja2` | 3.1.6 | BSD License |
| `jiter` | 0.10.0 | MIT License |
| `json5` | 0.10.0 | Apache Software License |
| `json_repair` | 0.25.3 | MIT License |
| `jsonref` | 1.1.0 | MIT |
| `kubernetes` | 36.0.3 | Apache Software License |
| `markdown-it-py` | 4.2.0 | MIT License |
| `MarkupSafe` | 3.0.4 | BSD-3-Clause |
| `mcp` | 1.23.3 | MIT License |
| `mdurl` | 0.1.2 | MIT License |
| `mmh3` | 5.3.1 | MIT License |
| `mpmath` | 1.3.0 | BSD License |
| `multidict` | 6.9.1 | Apache License 2.0 |
| `nodeenv` | 1.11.0 | BSD License |
| `numpy` | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| `oauthlib` | 4.0.0 | BSD-3-Clause |
| `onnxruntime` | 1.19.2 | MIT License |
| `openai` | 1.83.0 | Apache Software License |
| `openpyxl` | 3.1.5 | MIT License |
| `opentelemetry-api` | 1.34.1 | Apache Software License |
| `opentelemetry-exporter-otlp-proto-common` | 1.34.1 | Apache Software License |
| `opentelemetry-exporter-otlp-proto-grpc` | 1.34.1 | Apache Software License |
| `opentelemetry-exporter-otlp-proto-http` | 1.34.1 | Apache Software License |
| `opentelemetry-proto` | 1.34.1 | Apache Software License |
| `opentelemetry-sdk` | 1.34.1 | Apache Software License |
| `opentelemetry-semantic-conventions` | 0.55b1 | Apache Software License |
| `orjson` | 3.12.0 | MPL-2.0 AND (Apache-2.0 OR MIT) |
| `overrides` | 7.7.0 | Apache License, Version 2.0 |
| `packaging` | 26.3 | Apache-2.0 OR BSD-2-Clause |
| `pdfminer.six` | 20260107 | MIT |
| `pdfplumber` | 0.11.10 | MIT License |
| `platformdirs` | 4.12.3 | MIT |
| `portalocker` | 2.7.0 | BSD-3-Clause |
| `posthog` | 5.4.0 | MIT License |
| `pre_commit` | 4.6.2 | MIT |
| `propcache` | 0.5.4 | Apache-2.0 |
| `protobuf` | 5.29.6 | 3-Clause BSD License |
| `pybase64` | 1.5.0 | BSD-2-Clause |
| `pydantic` | 2.11.10 | MIT |
| `pydantic-settings` | 2.10.1 | MIT |
| `pydantic_core` | 2.33.2 | MIT License |
| `Pygments` | 2.21.0 | BSD-2-Clause |
| `pypdfium2` | 5.11.0 | BSD-3-Clause, Apache-2.0, dependency lic |
| `PyPika` | 0.51.1 | Apache Software License |
| `pyproject_hooks` | 1.3.3 | MIT |
| `python-dateutil` | 2.9.0.post0 | BSD License, Apache Software License |
| `python-discovery` | 1.6.1 | MIT License |
| `python-multipart` | 0.0.32 | Apache-2.0 |
| `regex` | 2024.9.11 | Apache Software License |
| `requests` | 2.34.2 | Apache Software License |
| `requests-oauthlib` | 2.0.0 | BSD License |
| `rich` | 14.3.4 | MIT License |
| `shellingham` | 1.5.4 | ISC License (ISCL) |
| `six` | 1.17.0 | MIT License |
| `sniffio` | 1.3.1 | MIT License, Apache Software License |
| `sse-starlette` | 3.5.0 | BSD-3-Clause |
| `starlette` | 1.7.0 | BSD-3-Clause |
| `sympy` | 1.14.0 | BSD License |
| `tenacity` | 9.1.4 | Apache Software License |
| `tokenizers` | 0.20.3 | Apache Software License |
| `tomli` | 2.0.2 | MIT License |
| `tomli_w` | 1.1.0 | MIT License |
| `tqdm` | 4.70.1 | MPL-2.0 AND MIT |
| `typer` | 0.27.2 | MIT |
| `typing-inspection` | 0.4.4 | MIT |
| `urllib3` | 2.8.0 | MIT |
| `uv` | 0.9.30 | MIT License, Apache Software License |
| `uvicorn` | 0.54.0 | BSD-3-Clause |
| `uvloop` | 0.23.0 | Apache Software License, MIT License |
| `virtualenv` | 21.14.5 | MIT |
| `watchfiles` | 1.3.0 | MIT License |
| `websocket-client` | 1.9.2 | Apache-2.0 |
| `websockets` | 17.2 | BSD-3-Clause |
| `yarl` | 1.25.1 | Apache-2.0 |
| `zipp` | 4.1.1 | MIT |
