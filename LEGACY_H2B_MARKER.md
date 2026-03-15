# Legacy H2B marker

This checkpoint keeps the old VIP -> Reserse internal upsert bridge in code, but visibly marks it as legacy.

Preferred active integration branch: **H2C-R**

- VIP generates signed SSO URL
- Reserse handles `/sso/consume`
- Reserse upserts user and starts session

Legacy code intentionally preserved only for rollback safety:

- `app/routes/internal.py`
  - `VipUpsertUserPayload`
  - `/internal/vip/upsert-user`
- `app/config.py`
  - `vip_internal_shared_secret`

No runtime logic was removed in this checkpoint; only comments/markers were added.
