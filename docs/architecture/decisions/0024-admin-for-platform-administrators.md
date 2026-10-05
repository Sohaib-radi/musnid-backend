---
id: 0024-admin-for-platform-administrators
title: "ADR 0024: The Django admin is for platform administrators only"
sidebar_position: 24
description: Only superusers can open the admin; users, specialists and center admins work in the frontend, which redirects superusers to the admin.
---

# ADR 0024: The Django admin is for platform administrators only

## Status

Accepted, 2026-10-05.

## Context

The admin already covers centers, memberships and questions, so serving centers from
it looked faster than building a center dashboard in the frontend. But the admins are not
scoped by center: any staff account with a model permission sees every center's rows, and
scoping every list, filter, search, lookup and action is error-prone. Django documents the
admin as an internal tool for trusted staff, not a site's user interface. A second
interface with its own login would also look unfinished to the competition's jury, who
test the frontend. The API for centers (settings, members, Telegram) already exists.

## Decision

- **Superusers only.** `core.sites.SuperuserAdminSite` (a subclass of Unfold's site)
  allows only active superusers on every admin page; `is_staff` alone is no longer
  enough. `core.sites.SuperuserAdminConfig` replaces `unfold` in `INSTALLED_APPS` and
  installs the site the way Unfold's own app config does.
- **Login**: `core.forms.SuperuserAuthenticationForm` refuses other accounts with "This
  page is for platform administrators. Please sign in on the Musnid website."
- **Redirect**: `GET /api/v1/me/` returns `is_platform_admin` (true for a superuser) and
  `admin_url` (`DJANGO_SITE_URL` + `/admin/`, null for everyone else); the frontend sends
  platform administrators there instead of showing a dashboard.
- **Split**: platform administrators use the admin (center review, every question, AI
  settings, Telegram log); askers, specialists and center admins use the frontend.

## Consequences

- Staff permissions in the admin no longer matter: per-model permissions stay in the
  code, but only superusers get in.
- Center work (questions list, answers) must be served by the API and the frontend
  center dashboard; that is the next step.
- The admin keeps its own session login; the frontend's JWT tokens do not open it.
