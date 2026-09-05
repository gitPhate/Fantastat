# UI dell'asta offline

La UI legge esclusivamente uno snapshot SQLite locale e non usa servizi o asset Internet.

Prima dell'asta, genera gli artefatti della stagione e prepara (o sostituisci) lo snapshot:

```powershell
python src/run_ranking.py --season 2026_27
python src/extract_auction_guide_players.py --season 2026_27 --guide output/guida_unificata_asta_2026_27.md
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
