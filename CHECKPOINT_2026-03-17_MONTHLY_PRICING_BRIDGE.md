# Reserse checkpoint — 2026-03-17 monthly pricing bridge

## Co bylo doplněno
- ceny okruhů jsou v UI popsány jako měsíční (`Kč / měsíc`)
- dashboard uživatele zobrazuje součet aktivních okruhů za měsíc
- přidán zabezpečený VIP endpoint `GET /internal/vip/user-pricing`
- výpočet vychází z `user_topic_subscriptions` + aktivních `topics`
- H2C-R `/sso/consume` zůstal beze změny
- legacy H2B zůstal zachovaný
