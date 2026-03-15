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
- 20 témat + seed RSS zdroje
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
- přidané launchery `Exa Research` a `Perplexity Deep Research`
- připravené rozhraní `ElevenLabs` pro budoucí per-user klíče
- seed rozšířen z 20 na 50 témat
