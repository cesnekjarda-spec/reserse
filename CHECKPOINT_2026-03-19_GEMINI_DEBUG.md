Reserse checkpoint – Gemini debug layer

Změny:
- robustnější čtení Gemini odpovědi: nejdřív response.text, pak candidates.content.parts[].text
- u audio payloadu se ukládá debug meta:
  - model
  - počet znaků promptu
  - počet textových podkladů
  - počet kandidátů
  - finish reasons
  - kolik částí response obsahovalo text
  - délka response.text
  - token counts, pokud jsou k dispozici
- na dashboardu i na stránce Poslechový model je detail Gemini debug

Cíl:
- rychle poznat, jestli Gemini opravdu generuje text,
- nebo jestli vrací prázdnou odpověď / metadata bez použitelného textu.
