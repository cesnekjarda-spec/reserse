# Reserse checkpoint — 2026-03-17 push sync

## Aktivní směr
- Reserse už neposílá ceny jen přes pull z VIP
- aktivní směr je teď push sync: Reserse -> VIP

## Co bylo doplněno
- nový service modul `app/services/vip_pricing_sync_service.py`
- při H2C-R `/sso/consume` se po JIT přihlášení odešle pricing sync do VIP
- při změně `/dashboard/subscriptions` se odešle nový pricing sync do VIP
- při admin změně ceny tématu se přepočtou a odešlou dotčení uživatelé
- při bulk změně cen se přepočtou a odešlou všichni odběratelé

## Nové env
- `VIP_PRICING_SYNC_URL` -> veřejný VIP endpoint pro sync
- `VIP_PRICING_SYNC_TIMEOUT_SECONDS` -> timeout push syncu

## Poznámka
- H2C-R login zůstává aktivní beze změny
- legacy H2B zůstává zachován
