# CHECKPOINT HANDOVER — rozšíření bez zásahu do stávající funkční logiky

## Princip
- původní funkční brief, dashboard, RSS sync i publikace zůstávají zachované
- nové věci jsou přidané jako samostatné rozšiřující větve
- žádná původní funkční větev nebyla odstraněna

## Nové přidané větve
1. **Poslechový model briefu**
   - `/briefs/{id}/listen`
   - `/briefs/{id}/listen.txt`
   - dashboard má nový preview text a nové tlačítko pro čtení poslechového scriptu

2. **Exa Research launcher**
   - nový provider `exa-research`
   - otevírá interní launcher `/research/launch/exa-research?q=...`
   - připravuje poctivý research prompt bez zásahu do původního briefu

3. **Perplexity Deep Research launcher**
   - nový provider `perplexity-deep-research`
   - otevírá interní launcher `/research/launch/perplexity-deep-research?q=...`
   - umožňuje prompt zkopírovat nebo otevřít v Perplexity jako externí pokračování rešerše

4. **ElevenLabs rozhraní pro budoucí per-user napojení**
   - nový model `user_tts_connections`
   - dashboard má samostatné UI pro `display_name`, `voice_id`, `model_id`, `note`, `api_key`
   - automatické TTS přes ElevenLabs zatím úmyslně nespouští žádnou novou aktivní větev
   - pokud bude doplněn `USER_SECRET_ENCRYPTION_KEY`, lze bezpečně uložit i API klíč

5. **Rozšíření katalogu témat**
   - seed rozšířen z 20 na 50 témat
   - nově přidané okruhy: vaření, hobby, cestování, sport, kultura, rodina, vzdělávání, fotografie, kosmonautika, obrana a další

## Nové env proměnné
- `EXA_API_KEY=`
- `PERPLEXITY_API_KEY=`
- `USER_SECRET_ENCRYPTION_KEY=`
- `PROVIDER_REQUEST_TIMEOUT_SECONDS=30`

## Důležitá poznámka k ElevenLabs klíči
Pokud není nastaven `USER_SECRET_ENCRYPTION_KEY`, rozhraní uloží metadata, ale neuloží samotný klíč. To je záměrné bezpečnostní chování.
