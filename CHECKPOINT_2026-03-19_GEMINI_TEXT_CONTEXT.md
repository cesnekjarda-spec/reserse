CHECKPOINT 2026-03-19 – Gemini text-context audio

Změny:
- Gemini pro audio rešerši už nepracuje primárně s URL contextem, ale s interními textovými podklady z článků (title + summary + full_text).
- Dashboardové tlačítko „Přečíst poslechovou rešerši“ čte plný audio text místo krátkého preview.
- Dashboard i Poslechový model ukazují, zda výstup vznikl přes Gemini nebo Fallback, včetně stručného důvodu fallbacku.

Upravené soubory:
- app/services/audio_service.py
- app/routes/user.py
- app/templates/user_dashboard.html
- app/templates/brief_listen_script.html
