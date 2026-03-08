# Reserse — checkpoint layer1+layer2

Vlastní briefing engine doplněný o externí launchery s deep-link dotazy.

## Přihlášení
- Admin / Ahojky12345
- User / Ahojky54321

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
