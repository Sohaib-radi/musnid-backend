---
id: intro
title: Introduction
sidebar_position: 1
description: Purpose of the Musnid backend and the current state of the implementation.
---

# Musnid backend

Musnid is the backend for the competition "AI Challenge – Serving Islamic Content". It
answers questions about Islam from vetted sources using retrieval-augmented generation
(RAG) and AI agents. Questions the AI must not answer are routed to centers of
specialists, who receive and answer them.

This documentation is reference material for engineers working on the backend. It is
written as Docusaurus content; this repository holds the Markdown only.

## Current status

| Area | Status | Notes |
| --- | --- | --- |
| Project skeleton | Done | Django 6.0 project `config`, app `core` (empty). |
| Configuration | Done | Environment variables, optional `.env`; see [Configuration](getting-started/configuration.md). |
| Database | Done | PostgreSQL 17 with pgvector, via Docker Compose on port 5435. |
| Docker | Done | `db` service always; `web` service (gunicorn) under the `web` profile on port 8011. |
| Tests | Done | 22 tests against a real PostgreSQL test database; see [Testing](development/testing.md). |
| Static files in Docker | Known limitation | gunicorn does not serve `/static/` yet; use `runserver` for development. WhiteNoise or nginx comes with deployment. |
| Internationalisation (Arabic, French) | Not started | Required for every user-facing string once such strings exist. |
| Source ingestion and RAG | Not started | Will be documented under `docs/rag/`. |
| AI agents (CrewAI) | Not started | CrewAI 1.9.3 is planned; it constrains the Python version (ADR 0001). |
| Specialist centers | Not started | |

## Where to go next

- [Local development](getting-started/local-development.md): run the project on your machine.
- [Docker](getting-started/docker.md): run the database and the application in containers.
- [Configuration](getting-started/configuration.md): every environment variable.
- [Technology stack](technology-stack.md): dependencies, versions and licenses.
- [ADR 0001](architecture/decisions/0001-python-3-12.md): why Python 3.12.
