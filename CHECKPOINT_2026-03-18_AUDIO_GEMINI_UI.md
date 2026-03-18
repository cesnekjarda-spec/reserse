# CHECKPOINT 2026-03-18 – audio research UX + Gemini visibility

## Změny
- Dashboard už nečte prostřední tlačítko z krátkého preview, ale z plné audio rešerše.
- Prostřední tlačítko je nově pojmenované `Přečíst poslechovou rešerši`.
- Na dashboardu i na stránce `Poslechový model` je nově vidět zdroj audio textu:
  - `Gemini`
  - `Fallback`
- U fallbacku se zobrazuje i stručný důvod:
  - chybí `GEMINI_API_KEY`
  - chybí veřejné URL článků
  - Gemini nevrátilo použitelný text
- Fallback text byl přepracován tak, aby zněl víc jako souvislá operativní rešerše a méně jako výčet hesel.

## Upravené soubory
- `app/services/audio_service.py`
- `app/routes/user.py`
- `app/templates/user_dashboard.html`
- `app/templates/brief_listen_script.html`

## Nasazení bez Codespaces
1. rozbal ZIP lokálně
2. v GitHub repu použij `Add file -> Upload files`
3. přetáhni jen změněné soubory a checkpoint
4. commitni do `main`
5. v Renderu dej `Manual Deploy -> Deploy latest commit`

## Co zkontrolovat po deployi
- Na dashboardu je tlačítko `Přečíst poslechovou rešerši`.
- U briefu je řádek `Zdroj audio textu: Gemini` nebo `Fallback`.
- Na stránce `Poslechový model` je vidět stejný zdroj.
