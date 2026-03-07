# Research Feed App v1

Jednoduchá samostatná webová aplikace pro:
- registraci a přihlášení uživatelů,
- role `admin` / `user`,
- správu okruhů a RSS zdrojů,
- pravidelné načítání RSS zpráv,
- zobrazení nových rešerží přihlášenému uživateli.

## Použité technologie

- FastAPI
- Jinja2 šablony
- SQLAlchemy
- Neon Postgres
- Render.com
- GitHub Actions pro plánovaný RSS sync

## Co tato verze umí

- veřejná registrace běžného uživatele,
- bezpečné hashování hesel pomocí Argon2,
- session cookie přihlášení,
- admin dashboard,
- správa okruhů a zdrojů,
- dashboard uživatele s novými články,
- interní RSS sync endpoint chráněný tajným klíčem.

## Lokální spuštění

1. Vytvoř virtuální prostředí:
   ```bash
   python -m venv .venv
   ```

2. Aktivuj ho:
   - Windows:
     ```bash
     .venv\Scripts\activate
     ```
   - macOS / Linux:
     ```bash
     source .venv/bin/activate
     ```

3. Nainstaluj závislosti:
   ```bash
   pip install -r requirements.txt
   ```

4. Zkopíruj `.env.example` na `.env` a doplň údaje.

5. Spusť aplikaci:
   ```bash
   uvicorn app.main:app --reload
   ```

6. Otevři:
   - http://127.0.0.1:8000
   - admin se vytvoří automaticky při startu, pokud vyplníš `ADMIN_EMAIL` a `ADMIN_PASSWORD`.

## Nasazení na Render

1. Nahraj tento projekt do GitHub repozitáře.
2. Na Renderu vytvoř novou web service z GitHub repa.
3. Přidej environment variables:
   - `DATABASE_URL`
   - `SYNC_SECRET`
   - `ADMIN_EMAIL`
   - `ADMIN_PASSWORD`
4. Render při startu vytvoří databázové tabulky a případně prvního admina.

## Plánovaný RSS sync přes GitHub Actions

Workflow `.github/workflows/sync-rss.yml` volá endpoint:
`POST /internal/sync-rss`

Musíš nastavit GitHub secrets:
- `SYNC_URL`
- `SYNC_SECRET`

Příklad:
- `SYNC_URL=https://tvoje-aplikace.onrender.com/internal/sync-rss`
- `SYNC_SECRET=stejná hodnota jako na Renderu`

## Poznámka k RSS zdrojům

Do seed dat jsem záměrně nedal velké množství českých feedů natvrdo. U každého zdroje je lepší ověřit konkrétní RSS URL před nasazením. Například Měšec.cz na své stránce „Exporty“ veřejně uvádí RSS adresy pro články a aktuality. Peníze.cz má veřejnou RSS sekci, ale konkrétní feed URL je vhodné ověřit zvlášť při přidávání do adminu. citeturn1view1turn1view0

## Doporučené první testy

1. Spusť aplikaci.
2. Přihlas se jako admin.
3. Vytvoř okruh `Finance`.
4. Přidej RSS zdroj například z Měšce.
5. Spusť ruční sync v adminu.
6. Zaregistruj běžného uživatele.
7. Přihlas se jako user a přidej si okruh.
8. Zkontroluj nové články na dashboardu.

## Další rozvoj

Další logický krok:
- přidat editaci uživatelů,
- přidat filtrování článků,
- přidat e-mailové notifikace,
- přidat lepší admin formuláře,
- přidat migrace přes Alembic,
- připravit iframe variantu pro vložení do hlavní aplikace.
