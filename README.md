# Research Feed App – clean rebuild

Tato verze je postavená jako čistší a odolnější základ pro rešeršní aplikaci ve stacku FastAPI + Jinja2 + SQLAlchemy + Neon/Render. Původní veřejné repo už používalo právě tuto kombinaci a současně samo přiznávalo, že seed data jsou záměrně velmi malá; navíc bootstrap admina v aktuálním kódu jen povyšoval existujícího uživatele na admina, ale nepřepisoval mu heslo. To byl hlavní důvod, proč se přihlášení umělo zaseknout na starém záznamu. Tento balík to řeší robustněji.


## Co je připravené hned po startu

- automatické vytvoření / dorovnání účtů:
  - **Admin** / **Ahojky12345**
  - **User** / **Ahojky54321**
- login funguje přes **uživatelské jméno i e-mail**,
- při každém startu se hesla těchto dvou účtů znovu sladí s nastavením,
- automaticky se založí **20 témat**,
- automaticky se založí **200 RSS zdrojů**,
- testovací účet `User` je po startu přihlásitelný a má předplacena všechna seed témata,
- admin může ručně spouštět RSS sync a přidávat další témata i zdroje.

## Proč jsou zdroje řešené přes Google News RSS vyhledávání

Pro seed data je použitý vzor `https://news.google.com/rss/search?q=...`, protože umožňuje rychle vytvořit mnoho tematických RSS zdrojů nad jedním stabilním formátem. Feedly i další technické návody ukazují Google News RSS pattern pro top headlines i topic/search feeds. To je pro první funkční nasazení praktičtější než ručně skládat stovky publisher-specific feedů. Později můžeš jednotlivé zdroje v adminu nahradit čistě publisher-native RSS URL.


## Lokální spuštění

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload
```

Aplikace poběží na `http://127.0.0.1:8000`.

## Render / Neon

1. Nahraj projekt do GitHub repa.
2. Na Renderu vytvoř web service z tohoto repa.
3. Nastav minimálně `DATABASE_URL` a `SYNC_SECRET`.
4. Ostatní bootstrap proměnné můžeš ponechat, nebo si je změnit.

Pokud `DATABASE_URL` nevyplníš, app použije lokální SQLite `app.db`, takže nespadne už při bootu.

## Jednorázové dorovnání seed dat

```bash
python -m scripts.seed_all
```

## Důležité

Tahle verze je záměrně stavěná jako odolnější základ proti točení v kruhu:

- defaultně **nespadne kvůli chybějícímu DATABASE_URL**, protože má fallback na SQLite,
- systémové účty se **při startu opravují/upsertují**, ne jen jednorázově zakládají,
- login nepředpokládá jen e-mail,
- seed dat je velký už od začátku,
- RSS sync neblokuje boot.
