---
id: api-keys
title: Provider API keys
sidebar_position: 4
description: How provider API keys (OpenAI) are added, stored encrypted, read and revoked, and the security measures around them.
---

# Provider API keys

Staff add provider API keys in the admin under **Configuration > API Keys**. The code
that calls a provider reads the key with `core.services.credentials.get_openai_key()`.
Decision: [ADR 0014](../architecture/decisions/0014-encrypted-api-keys.md).

## Lifecycle

1. **Add**: provider, name and the key on the add page. The service strips the key,
   checks its format and that it was never added before, encrypts it, and revokes the
   provider's previous active key in the same transaction.
2. **Use**: `get_openai_key()` returns the active key, else `OPENAI_API_KEY` from the
   environment, else an empty string.
3. **Revoke**: the "Revoke selected API keys" action (needs the delete permission).
   Revoking twice changes nothing. Keys can also be deleted.
4. **Rotate**: add the new key; the old one is revoked automatically.

Keys are never edited: there is no change permission (an edit returns 403).

## Security measures

| Measure | Implementation |
| --- | --- |
| Encryption at rest | Fernet (AES-128-CBC + HMAC-SHA256) via `core/crypto.py`, keys from `FIELD_ENCRYPTION_KEYS`, never `SECRET_KEY`. |
| Key rotation | `MultiFernet`: the first key encrypts, all keys decrypt. Add a new key first, keep the old ones until their secrets are re-added. |
| Masking | Only `prefix` (3 characters) and `last_four` are stored in clear; pages show `sk-...abcd`. `__str__` and `__repr__` show only the masked form. |
| Duplicate detection | SHA-256 `fingerprint` (unique), so a key added once is refused again, even after revocation. |
| Write-only input | Password widget with `render_value=False`: an invalid submission never echoes the key. |
| No browser autofill | Key field `autocomplete="new-password"`, name field `autocomplete="off"`, both `data-1p-ignore` and `data-lpignore`: browsers and password managers do not fill the admin's own credentials in. |
| No logging | No secret is logged, printed, displayed or put in an error message; `sensitive_variables` on every function holding one and `sensitive_post_parameters("secret")` on the add view keep it out of Django error reports. |
| Revoke-only changes | No edit; revocation is recorded (`revoked_at`, `revoked_by`) and constraints keep one active key per provider. |
| Format check | OpenAI keys must start with `sk-`, have at least 20 characters, no whitespace (`invalid_format`). |

## Configuration

| Variable | Meaning |
| --- | --- |
| `FIELD_ENCRYPTION_KEYS` | Fernet keys, comma-separated, newest first. Required to add or read stored keys. |
| `OPENAI_API_KEY` | Fallback key when none is active in the admin. |

Generate an encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Losing every key in `FIELD_ENCRYPTION_KEYS` makes stored API keys unreadable; they must
then be added again.
