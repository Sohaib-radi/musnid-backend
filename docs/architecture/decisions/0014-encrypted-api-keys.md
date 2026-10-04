---
id: 0014-encrypted-api-keys
title: "ADR 0014: Encrypted API keys"
sidebar_position: 14
description: Why provider API keys are stored encrypted with dedicated Fernet keys, masked, write-only and revoke-only.
---

# ADR 0014: Encrypted API keys

## Status

Accepted, 2026-10-04.

## Context

The AI features call OpenAI. Staff must be able to set and rotate the key without a
deployment, but a database dump, a log line, an error report or a browser autofill must
never reveal it.

## Decision

- Model `ApiCredential`: provider, name, `encrypted_secret`, SHA-256 `fingerprint`
  (unique), `prefix`, `last_four`, `is_active`, `revoked_at`, `revoked_by`. Only provider
  and name are editable. Constraints `one_active_credential_per_provider` and
  `credential_active_matches_revoked_at`.
- Encryption with `cryptography` 48.0.1 Fernet through `MultiFernet` over
  `FIELD_ENCRYPTION_KEYS` (newest first), separate from `SECRET_KEY` so each can be
  rotated alone.
- All access through `core.services.credentials`: `add_credential` (validate, encrypt,
  revoke the previous key atomically), `revoke` (idempotent), `get_secret` /
  `get_openai_key` (active key, else the `OPENAI_API_KEY` setting).
- Admin: write-only key field, no autofill, masked display only, no edit, revoke action,
  delete allowed. See the measures in [Provider API keys](../../reference/api-keys.md).

## Consequences

- Losing the encryption keys makes stored API keys unreadable; they must be re-added.
- Rotating `FIELD_ENCRYPTION_KEYS` needs re-adding keys (no automatic re-encryption yet).
- The fingerprint lets anyone with database access test whether a known key was stored;
  acceptable, since such a person would need the key itself.
- New providers need a `Provider` choice and, if relevant, a format rule.
