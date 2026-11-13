# UI dell'asta offline

La UI legge esclusivamente uno snapshot SQLite locale e non usa servizi o asset Internet.

Prima dell'asta, genera gli artefatti della stagione e prepara (o sostituisci) lo snapshot:

```powershell
python src/run_ranking.py --season 2026_27
python src/connectors/unified_auction_guide.py --season 2026_27
python src/build_snapshot.py
```

Gli artefatti generati sono in `output/2026-27/`; lo snapshot è
`output/fantastat.sqlite3` e non è versionato. La costruzione convalida ogni
stagione scoperta e sostituisce il vecchio file solo al termine riuscito.

Durante l'asta avvia il solo server locale:

```powershell
python src/auction_ui.py
```

Apri l'indirizzo `http://127.0.0.1:8765`. Il server è in sola lettura e si
lega unicamente alla macchina locale. Non ricostruisce né modifica lo snapshot.

Se lo snapshot manca, è incompatibile o non contiene stagioni, rigeneralo con
`python src/build_snapshot.py`; il messaggio di avvio indica lo stesso rimedio.

## Lingua

La UI è in inglese per impostazione predefinita; il selettore in alto
permette di passare all'italiano. La scelta è salvata nel browser
(`localStorage`). Le traduzioni sono in `src/ui_assets/i18n.js`; i messaggi
di errore del server sono in inglese e vengono tradotti dal client. I
documenti Markdown di `docs/` restano nella loro lingua originale.
