H2C – Reserse side of SSO bridge from VIP

New env for Reserse:
ALLOW_PUBLIC_REGISTRATION=false
BOOTSTRAP_USER_ENABLED=false
VIP_SSO_ENABLED=true
VIP_SSO_SHARED_SECRET=CHANGE_ME_SHARED_SECRET
VIP_SSO_ISSUER=vip-klub
VIP_INTERNAL_SHARED_SECRET=CHANGE_ME_SHARED_SECRET

What it adds:
- public register disabled
- admin-only user management in /admin/users
- /sso/consume signed-token login bridge
- /internal/vip/upsert-user protected by shared secret
- admin can be launched in "user" or "admin" mode from VIP without breaking standalone mode
