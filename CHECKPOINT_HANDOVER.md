# CHECKPOINT HANDOVER — layer1+layer2

## Varianta
layer1+layer2

## Směr
Vlastní briefing engine doplněný o externí launchery s deep-link dotazy.

## Stav
Tento checkpoint je určen jako samostatně nasaditelná verze nad čistou databází.

## Přístupy
- Admin / Ahojky12345
- User / Ahojky54321

## Poznámky
- pokud používáš Render, ponech `.python-version`
- `DATABASE_URL` patří do Render Environment bez prefixu `DATABASE_URL=`
- při prvním startu se vytvoří tabulky a bootstrap data


## 2026-03-15 doplnění živého napojení

- Exa a Tavily teď umí skutečné serverové API volání místo pouhého launcheru.
- ElevenLabs umí přímé MP3 generování z poslechového scriptu i z externí rešerše přes uložený uživatelský účet.
- USER_SECRET_ENCRYPTION_KEY už může být libovolný dlouhý tajný řetězec; aplikace si z něj sama odvodí platný Fernet klíč.


- ElevenLabs debug: přidán test uloženého připojení a volba pro smazání starého uloženého API keye.
