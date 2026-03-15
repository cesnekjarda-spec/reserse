# Reserse — checkpoint layer1+layer2

Vlastní briefing engine doplněný o externí launchery s deep-link dotazy.

## Přihlášení
- veřejná registrace je vypnutá
- výchozí admin účet se bootstrapuje podle env
- další uživatele vytváří administrátor v `/admin/users`

## Co je v balíku
- FastAPI + Jinja2 webová aplikace
- Neon / SQLite kompatibilní SQLAlchemy backend
- bootstrap admin/user účtů
- 50 témat + seed RSS zdroje
- admin dashboard
- uživatelský dashboard

## Doporučené nasazení
1. nový GitHub repozitář nebo nová branch
2. nová prázdná Neon databáze
3. Render web service
4. env: DATABASE_URL, APP_ENV=production, SYNC_SECRET
5. deploy

## Důležité
Použij novou / čistou databázi. Tento checkpoint předpokládá čisté schema.


## Volitelné audio rešerše z URL

Aplikace umí na vyžádání vytvořit MP3 audio rešerši z publikovaného briefingu.
Pokud nastavíš `GEMINI_API_KEY`, použije se Gemini URL Context nad několika veřejnými URL článků spojených s briefem a výsledek se převede do MP3 bez trvalého ukládání na server.
Když API klíč nenastavíš, vygeneruje se audio z interního briefingu jako fallback.


## Rozšíření v tomto checkpointu
- původní funkční brief zůstal zachovaný
- přidaný poslechový model briefu (`/briefs/{id}/listen`)
- původní `Perplexity Search` zůstává zachovaná a nově jsou přidané launchery `Exa Research` a `Tavily Research`
- funkční rozhraní `ElevenLabs` pro per-user klíče a přímé MP3 generování
- seed rozšířen z 20 na 50 témat


## 2026-03-15 doplnění živého napojení

- Exa a Tavily teď umí skutečné serverové API volání místo pouhého launcheru.
- ElevenLabs umí přímé MP3 generování z poslechového scriptu i z externí rešerše přes uložený uživatelský účet.
- USER_SECRET_ENCRYPTION_KEY už může být libovolný dlouhý tajný řetězec; aplikace si z něj sama odvodí platný Fernet klíč.
