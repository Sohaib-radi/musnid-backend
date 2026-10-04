---
id: 0008-unfold-admin-theme
title: "ADR 0008: Unfold admin theme"
sidebar_position: 8
description: Why the admin uses django-unfold, how the brand colours and typeface are applied, and how contrast is kept at WCAG AA.
---

# ADR 0008: Unfold admin theme

## Status

Accepted, 2026-10-04.

## Context

Center administrators and staff use the Django admin daily, in Arabic, English and
French. Django's default admin is functional but dated, and adapting it to a brand means
overriding many templates. The admin must carry the Musnid identity (navy, blue-white,
violet, with a turquoise accent; the Readex Pro typeface, which covers Arabic and Latin)
and stay readable for everyone.

## Decision

Use **django-unfold 0.108.0** (MIT). It restyles the whole admin with Tailwind, keeps
Django's admin API, and is configured from one `UNFOLD` setting.

- `unfold` is listed before `django.contrib.admin` so its templates take precedence.
- Every admin inherits `unfold.admin.ModelAdmin`, every inline Unfold's inline classes;
  `Group` is re-registered. A test enforces this.
- **Colours live only in `config/unfold.py`**, as two 11-step scales. Three steps are the
  brand colours: `base-900` navy `#12183F`, `base-50` blue-white `#F2F4FF`,
  `primary-600` violet `#6150EA`. The other steps were derived in OKLCH (hue taken from
  the anchor, lightness stepped, chroma reduced until the colour fits sRGB).
  The one exception is the turquoise accent `#2EF2C2`, which Unfold has no setting for:
  it is defined in `core/static/core/css/admin.css` and used only on navy.
- **Contrast**: text/background pairs that Unfold uses were measured with the WCAG 2
  formula and must be at least 4.5:1 (AA, normal text). First derivation: subtle text
  (`base-500`) on `base-50` measured 4.37:1, so `base-500` was darkened. Final values:

  | Pair | Contrast |
  | --- | --- |
  | subtle text `base-500` on white | 5.22 |
  | subtle text `base-500` on `base-50` | 4.77 |
  | default text `base-600` on white | 7.23 |
  | important text `base-900` on white | 17.10 |
  | dark mode subtle `base-400` on `base-900` | 5.90 |
  | dark mode default `base-300` on `base-900` | 9.27 |
  | dark mode important `base-100` on `base-900` | 14.12 |
  | white on button `primary-600` | 5.46 |
  | link `primary-600` on `base-50` | 4.98 |
  | dark mode link `primary-400` on `base-900` | 6.42 |
  | turquoise accent on navy | 11.88 |

  Turquoise on white measures 1.44:1, which is why it is restricted to navy surfaces.
  `core/tests/test_unfold.py` recomputes these ratios on every run.
- **Typeface**: Readex Pro (SIL Open Font License 1.1), self-hosted in
  `core/static/core/fonts/readex-pro/` as three variable WOFF2 files (Arabic, Latin,
  Latin Extended subsets from Google Fonts; weight axis 160 to 700) with its licence.
  `admin.css` sets Unfold's `--font-sans` to it. Regular text uses weight 400 and headings
  700. Self-hosting avoids a request to a third party on every admin page.
- **Identity**: site title and header "Musnid" (not translated); a login brand panel
  from `core/static/core/img/login.svg`, a geometric eight-point-star pattern in navy,
  violet and turquoise, without text (a background image cannot load the web font).

## Consequences

- Upgrading Unfold may change template markup that `admin.css` targets (sidebar, login
  header). The right-to-left fixes in `admin.css` are tied to 0.108.0 and must be
  re-checked with screenshots on upgrade.
- Unfold ships no Arabic or French translations; the project maintains them
  ([ADR 0009](0009-translations-in-every-change.md)).
- Unfold's login panel appears only on screens at least 1280 px wide (`xl`).
- The login artwork embeds the brand colours as an image asset; it is not configuration.
- Static files are still not served by gunicorn in Docker, so the themed admin needs
  `runserver` locally until deployment adds WhiteNoise or nginx.
