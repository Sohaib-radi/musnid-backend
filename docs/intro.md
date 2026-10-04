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
| Project skeleton | Done | Django 6.0 project `config`, app `core`. |
| Configuration | Done | Environment variables, optional `.env`; see [Configuration](getting-started/configuration.md). |
| Database | Done | PostgreSQL 17 with pgvector, via Docker Compose on port 5435. |
| Docker | Done | `db` service always; `web` service (gunicorn) under the `web` profile on port 8011. |
| Domain models | Done | `User` (email login), `Center` (single default), `Membership` (roles, history); see [Models](reference/models.md). |
| Center scoping | Done | Explicit `for_center()`; see [Tenancy](architecture/tenancy.md). |
| Membership rules | Done | `add_member`, `change_role`, `offboard`; a center keeps one active admin. |
| Tests | Done | 177 tests against a real PostgreSQL test database; see [Testing](development/testing.md). |
| Static files in Docker | Known limitation | gunicorn does not serve `/static/` yet, so the themed admin renders unstyled at port 8011; use `runserver` for development. WhiteNoise or nginx comes with deployment. |
| Internationalisation (Arabic, French) | Done | Project catalog 67 strings and Unfold vendor catalog 131 strings, fully translated and enforced by tests; see [Translations](development/translations.md). |
| Source ingestion and RAG | Not started | Will be documented under `docs/rag/`. |
| AI agents (CrewAI) | Not started | CrewAI 1.9.3 is planned; it constrains the Python version (ADR 0001). |
| Admin | Done | Unfold theme with the Musnid brand, sidebar, language switcher; users, centers, memberships, groups; see [Admin](reference/admin.md). |
| API | Not started | |

## Where to go next

- [Local development](getting-started/local-development.md): run the project on your machine.
- [Docker](getting-started/docker.md): run the database and the application in containers.
- [Configuration](getting-started/configuration.md): every environment variable.
- [Technology stack](technology-stack.md): dependencies, versions and licenses.
- [Models](reference/models.md) and [Data model](architecture/data-model.md).
- [Tenancy](architecture/tenancy.md): how data is scoped to centers.
- [Admin](reference/admin.md): every admin page and the sidebar.
- [Decision records](architecture/decisions/0001-python-3-12.md): ADR 0001 to 0009.
