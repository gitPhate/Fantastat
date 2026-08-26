# Ranking Fantacalcio Serie A — Specifica operativa

## 1. Obiettivo

Costruire un ranking storico dei calciatori di Serie A per il fantacalcio, partendo dalle statistiche storiche disponibili e dalla lista dei giocatori disponibili per la stagione corrente 2026/27.

Sono disponibili 10 stagioni di statistiche (2016/17 → 2025/26) e 11 di quotazioni (2016/17 → 2026/27, sezione 2). Questa finestra serve innanzitutto a **calibrare i parametri del modello** tramite backtest rolling (sezione 20): quante stagioni di storico usare (`train_window`), il decadimento temporale, la forma della Reliability, il peso del BonusProfile. Il ranking di **produzione** per il 2026/27 userà poi solo la finestra di stagioni indicata dal backtest come `train_window` (plausibilmente 3-5, sezione 4 del piano di revisione), non tutte e 10 le stagioni: più storico non significa automaticamente un rating migliore, ed è esattamente ciò che il backtest deve stabilire (sezione 20.2, B8).

Il ranking deve:

- utilizzare le performance storiche, dando più peso alle stagioni recenti;
- distinguere qualità del rendimento (Performance) e affidabilità (Reliability) come dimensioni separate, mai moltiplicate tra loro;
- tenere conto della produzione di bonus/malus (gol, assist, rigori) come modulatore, non come somma aggiuntiva alla Fm;
- distinguere i giocatori per ruolo Classic (P/D/C/A) — **il Mantra (colonna Rm) non viene usato in questa versione**;
- escludere dal ranking finale i giocatori non più in Serie A 2026/27;
- gestire separatamente i giocatori senza storico sufficiente (NEW / LIMITED_HISTORY, sezione 6);
- mantenere la Mv separata dalla Fm, perché base del Modificatore Difesa;
- distinguere "non era in Serie A" da "era in Serie A e non ha giocato" (quest'ultimo direttamente dalle righe a `Pv = 0` del file statistiche, sezione 4), perché ai fini della disponibilità le due cose hanno significato opposto (sezione 9.1bis);
- distinguere, dentro "era in Serie A e non ha giocato", chi è rimasto in rosa tutta la stagione da chi ne è uscito in corsa (flag `left_mid_season`, sezione 9.1bis), perché è la maggioranza dei casi a `Pv = 0`, non una coda (sezione 9.1bis);
- produrre un output leggibile sia da un foglio di calcolo sia da Claude in chat durante l'asta;
- essere facilmente ricalcolabile ogni stagione (pipeline, non classifica statica).

Fuori scope per questa versione (rimandato a fasi future):
- Ruoli Mantra e relativi ranking.
- Età anagrafica dei giocatori (dato non disponibile al momento).
- Contesto squadra 2026/27 come fattore di rating (nessun dato utile disponibile ora; per i giocatori NEW è comunque accettabile non averlo).
- Modello predittivo (Projected Rating) — la struttura deve però permettere di aggiungerlo senza refactor.

## 2. Input

### 2.1 File storici (statistiche consuntive)

```
data/stats/Statistiche_Fantacalcio_Stagione_2016_17.xlsx
data/stats/Statistiche_Fantacalcio_Stagione_2017_18.xlsx
data/stats/Statistiche_Fantacalcio_Stagione_2018_19.xlsx
data/stats/Statistiche_Fantacalcio_Stagione_2019_20.xlsx
data/stats/Statistiche_Fantacalcio_Stagione_2020_21.xlsx
data/stats/Statistiche_Fantacalcio_Stagione_2021_22.xlsx
data/stats/Statistiche_Fantacalcio_Stagione_2022_23.xlsx
data/stats/Statistiche_Fantacalcio_Stagione_2023_24.xlsx
data/stats/Statistiche_Fantacalcio_Stagione_2024_25.xlsx
data/stats/Statistiche_Fantacalcio_Stagione_2025_26.xlsx
```

Ogni file contiene un foglio `Tutti` con **una riga per ogni giocatore che è stato in Serie A in quella stagione, indipendentemente da quante partite abbia giocato** — non solo chi ha ricevuto almeno un voto. Verificato su tutte e 10 le stagioni: 107-153 giocatori a stagione hanno `Pv = 0` (nessun voto mai ricevuto) e sono comunque presenti in `Tutti`. **Non esiste un'assunzione "le righe hanno `Pv ≥ 1`"**: è falsa e non va reintrodotta in fase di implementazione (piano di revisione §2.4). Questo è il fatto che guida la tassonomia delle righe della sezione 4.

Si legge **sempre e solo** il foglio `Tutti`: nessun altro foglio è presente nei file statistiche (verificato su tutte e 10 le stagioni — non esistono né fogli per ruolo né un foglio `Ceduti` in questi file).

Il foglio `Ceduti` **non appartiene ai file statistiche**: si trova nei file **quotazioni** (sezione 2.3bis), dove è popolato su tutte e 10 le stagioni storiche, non solo fino al 2021/22, ed è la fonte del flag `left_mid_season` (sezione 4.0bis).

Colonne:

| Colonna | Significato |
|---|---|
| Id | ID giocatore nel database Fantacalcio.it |
| R | Ruolo classico: P/D/C/A |
| Rm | Ruolo Mantra (non usato in questa versione, ma va comunque letto e conservato) |
| Nome | Nome/cognome |
| Squadra | Squadra Serie A in quella stagione |
| Pv | Partite a voto |
| Mv | Media voto (senza bonus/malus) |
| Fm | FantaMedia (con bonus/malus) |
| Gf | Gol fatti |
| Gs | Gol subiti |
| Rp | Rigori parati |
| Rc | Rigori calciati |
| R+ | Rigori realizzati |
| R- | Rigori sbagliati |
| Ass | Assist |
| Amm | Ammonizioni |
| Esp | Espulsioni |
| Au | Autogol |

Schema stabile su tutte e 10 le stagioni: stessa intestazione, nessun parser condizionale per stagione.

### 2.2 Lista giocatori corrente

L'universo dei giocatori da valutare nel ranking finale di produzione 2026/27 **è** il file quotazioni 2026/27 (sezione 2.3): a differenza di tutti i file storici, quello è un listone di **inizio** stagione (verificato, sezione 2.3), quindi rappresenta esattamente l'universo acquistabile in asta. Non serve un file separato. Colonne minime usate: `Id`, `Nome`, `R`, `Squadra`.

### 2.3 Quotazioni (input di produzione **e** di validazione)

```
data/player_lists/Quotazioni_Fantacalcio_Stagione_2016_17.xlsx
data/player_lists/Quotazioni_Fantacalcio_Stagione_2017_18.xlsx
data/player_lists/Quotazioni_Fantacalcio_Stagione_2018_19.xlsx
data/player_lists/Quotazioni_Fantacalcio_Stagione_2019_20.xlsx
data/player_lists/Quotazioni_Fantacalcio_Stagione_2020_21.xlsx
data/player_lists/Quotazioni_Fantacalcio_Stagione_2021_22.xlsx
data/player_lists/Quotazioni_Fantacalcio_Stagione_2022_23.xlsx
data/player_lists/Quotazioni_Fantacalcio_Stagione_2023_24.xlsx
data/player_lists/Quotazioni_Fantacalcio_Stagione_2024_25.xlsx
data/player_lists/Quotazioni_Fantacalcio_Stagione_2025_26.xlsx
data/player_lists/Quotazioni_Fantacalcio_Stagione_2026_27.xlsx
```

Colonne: `Id R RM Nome Squadra Qt.A Qt.I Diff. Qt.A M Qt.I M Diff.M FVM FVM M`, più il foglio `Ceduti` (sezione 2.3bis). `FVM`/`FVM M` valgono 0 in tutte le stagioni fino al 2021/22 incluso (campo esistente ma non popolato): utilizzabile solo dal 2022/23.

**Attenzione — i file storici NON sono liste pre-stagione.** `Qt.A` (attuale) diverge da `Qt.I` (iniziale) per ~85% delle righe in tutti i file dal 2016/17 al 2025/26, e solo per il 17% delle righe nel file 2026/27 (516 righe, 90 con `Qt.A ≠ Qt.I`). Conclusione verificata: **i file storici sono snapshot di fine stagione**; solo `Quotazioni_Fantacalcio_Stagione_2026_27.xlsx` è un listone di inizio stagione. Conseguenze obbligatorie:

- **`Qt.I` non viene sovrascritto** dagli aggiornamenti in corso d'anno, su tutte le 11 stagioni: questo è verificato, e lo rende utilizzabile come baseline esterna (sezione 20.4.3, B9) e come prezzo di produzione. **Non è verificato**, invece, che `Qt.I` sia sempre il "prezzo di agosto": per un giocatore entrato in Serie A a stagione già iniziata (arrivo di gennaio), `Qt.I` è più plausibilmente il prezzo del suo ingresso, non quello di inizio stagione — un'affermazione più forte dell'evidenza disponibile, e per giunta su un sottoinsieme che non si riesce a quantificare con questi dati (arrivi tardivi, non misurabili su questa finestra — sezione 20.1/22). Non cambia l'uso di `Qt.I` come baseline (resta valido, sezione 20.4.3), ma il README non deve descriverlo come "il prezzo che il mercato aveva già messo sul giocatore prima dell'inizio della stagione" per l'intera popolazione, solo per chi era già in Serie A ad agosto.
- **Il foglio `Tutti` è il roster di fine stagione**, non quello d'asta: include gli arrivi di gennaio. Per la costruzione dell'universo di test (sezione 20.1) questo non è più necessario — vedi sotto — ma va tenuto presente ovunque il foglio `Tutti` di un file storico venga letto per altri scopi (es. `left_mid_season`, sezione 2.3bis).
- Per il 2026/27 il problema non esiste per il roster `Tutti`: quel file è pre-stagione, ed è la fonte della lista giocatori corrente (sezione 2.2). Il file 2026/27 ha comunque un foglio `Ceduti` di 31 righe — sezione 2.3bis spiega perché è un caso diverso, da non confondere con quello delle stagioni storiche.

Questa fonte ha **usi distinti, tutti obbligatori**:

1. **Produzione — prezzo `Qt.I`**, esposto nel dataset come baseline e informazione di prezzo (sezione 20.4.3), letto da `Tutti ∪ Ceduti` (sezione 2.3bis): `Qt.I` è popolato al 100% anche sulle righe `Ceduti`, quindi leggerlo da entrambi i fogli non lascia buchi.
2. **Validazione — baseline esterna `Qt.I`/`FVM`** (sezione 20.4.3, B9), stessa fonte `Tutti ∪ Ceduti`: il ranking deve battere il prezzo che il mercato aveva già assegnato al giocatore prima della stagione, e la baseline va confrontata con il modello sullo stesso sottoinsieme di Id — mai su universi diversi (sezione 20.4.3).

**Non un uso di questa fonte**: la costruzione dell'universo di test (vecchia sezione 20.1) non passa dalle quotazioni. Il file statistiche stesso, con le righe a `Pv = 0` (sezione 4), è già l'universo Serie A completo di ogni stagione — è la stessa scoperta che ha eliminato `QUOTED_ONLY` (sezione 4) applicata alla validazione (sezione 20.1).

**Limite dichiarato, non risolto, sulle 10 stagioni storiche**: le quotazioni pre-stagione autentiche (agosto) di quelle stagioni non sono recuperabili con questi dati — solo il 2026/27 lo è. Non si tenta di ricostruirle. Perché la prossima revisione non trovi lo stesso limite sulla stagione appena conclusa, l'archiviazione cambia da questa stagione in poi: due snapshot per stagione, non uno (sezione 26).

### 2.3bis Il foglio `Ceduti` — dove si trova e a cosa serve

**`Ceduti` è un foglio delle quotazioni, non delle statistiche.** Verificato su tutti i file: i 10 file statistiche hanno solo il foglio `Tutti`; tutti gli 11 file quotazioni hanno `Tutti` **e** `Ceduti`. Non va letto né unito al foglio `Tutti` delle statistiche — errore delle versioni precedenti di questa spec.

**Esiste ed è popolato su tutte le 10 stagioni storiche**, non solo fino al 2021/22 (114-155 righe a stagione). Identità verificata su tutte e 10, esatta in entrambe le direzioni:

```
quotazioni_Tutti ∩ quotazioni_Ceduti = ∅
quotazioni_Tutti ∪ quotazioni_Ceduti = stats     (= file statistiche della stessa stagione, foglio Tutti)
⇒ stats \ quotazioni_Tutti ≡ quotazioni_Ceduti
```

Fonte unica e uniforme per tutte le 10 stagioni: **foglio `Ceduti` delle quotazioni della stagione**, letto direttamente — nessun parser condizionale per stagione (sezione 2.1). Non è un fallback per le stagioni recenti: la differenza `stats \ quotazioni_Tutti` è lo stesso identico insieme, quindi una derivazione ridondante di un dato già leggibile direttamente. Il foglio serve a due cose e nessun'altra:

- popolare il flag `left_mid_season` sulle righe `IN_SQUAD_NO_PLAY` del dataset long (sezione 4.0bis);
- fornire `Qt.I` per i giocatori assenti da `quotazioni!Tutti` (punto 1 sopra).

**2026/27 — non applicabile al flag, ma il foglio esiste.** Il file 2026/27 (pre-stagione) ha un `Ceduti` di **31** righe — un ordine di grandezza sotto le 114-155 dei file di fine stagione, perché è un'altra cosa: giocatori già ceduti **prima** dell'inizio della stagione, non durante. Vanno esclusi dall'universo di produzione (sezione 2.2) o dichiarati esplicitamente, non incontrati per caso in fase di implementazione.

## 3. Identificazione dei giocatori

### 3.1 Chiave primaria

Usare **Id** come chiave di join, **mai** il Nome, in nessun punto della pipeline — né per il join né come fallback quando l'Id sembra mancante. Verificato su 10 stagioni (2306 Id distinti, piano di revisione §2.2): l'Id è stabile e affidabile su tutta la finestra (0 duplicati intra-stagione), ma **4 Nomi sono associati a più Id diversi** (omonimi reali: Vergara, Gori, Buksa, Ndiaye). Un fallback per nome sarebbe scorretto esattamente nei casi in cui sembra più comodo usarlo. La normalizzazione della grafia (accenti, apostrofi, abbreviazioni — 24 Id hanno grafie multiple del nome, tutte varianti tipografiche) è ammessa **solo** per la leggibilità dell'output, mai per il match.

### 3.2 Controlli pre-merge

Prima del merge, verificare e loggare in un file di controllo:
- Id duplicati all'interno dello stesso file stagionale;
- Id presenti in una stagione ma assenti nelle altre;
- Id presenti nella lista 2026/27 ma senza storico nella finestra di train;
- eventuali cambiamenti anomali di Id per lo stesso Nome (possibile errore di dati);
- Nomi associati a più Id diversi (omonimi, sezione 3.1): da elencare esplicitamente, non solo contare — sono i casi in cui un fallback per nome produrrebbe un errore silenzioso.

## 4. Struttura del dataset storico

Dataset trasformato in formato long, una riga per giocatore/stagione:

| Id | Nome | Stagione | R | Squadra | Pv | Mv | Fm | Gf | Gs | Rp | Rc | R+ | R- | Ass | Amm | Esp | Au | RowType | left_mid_season |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

(Rm viene mantenuto in una colonna a parte per uso futuro, ma non entra in nessun calcolo di questa versione.)

### 4.0 Tassonomia delle righe

**Ogni riga viene dal file statistiche** (foglio `Tutti`, l'unico foglio presente — sezione 2.1): il file statistiche contiene già, da solo, l'intero universo Serie A della stagione, non solo chi ha ricevuto un voto. Il foglio `Ceduti` non entra in questa costruzione: appartiene alle quotazioni (sezione 2.3bis) e serve solo al flag `left_mid_season` (sezione 4.0bis) e a `Qt.I` (sezione 2.3), non alla tassonomia delle righe. Non esiste una categoria di riga sintetizzata dalle quotazioni: la vecchia categoria `QUOTED_ONLY` (righe costruite per differenza rispetto alle quotazioni pre-stagione) è **eliminata**, perché quella differenza è risultata vuota su tutte le 10 stagioni verificate — le quotazioni non aggiungono alcun Id che le statistiche non abbiano già.

| `RowType` | Condizione | Contenuto |
|---|---|---|
| `PLAYED` | `Pv >= 1` | riga completa, tutte le metriche popolate |
| `IN_SQUAD_NO_PLAY` | `Pv = 0`, riga presente nel file statistiche | `Mv`, `Fm` e tutti i conteggi bonus/malus a `null`, **non a zero**: per quella stagione non esiste alcuna osservazione di rendimento |

Un Id **assente** dal file statistiche di una stagione (nessuna riga `PLAYED` né `IN_SQUAD_NO_PLAY`) significa semplicemente "non era in Serie A quella stagione": non genera alcuna riga nel dataset long per quella stagione.

Le righe `IN_SQUAD_NO_PLAY` servono esclusivamente al calcolo della Reliability (sezione 9.1bis) e alla contabilizzazione delle stagioni in Serie A. **Non entrano in nessun calcolo di Performance, BonusProfile, Mv_Weighted, Fm_Weighted, Gf_Rate, Ass_Rate o Trend**, perché per quella stagione non esiste alcuna osservazione di rendimento: `Fm = null` non è `Fm = 0`.

### 4.0bis Flag `left_mid_season`

Booleano su ogni riga, popolato a partire dal foglio `Ceduti` delle quotazioni (sezione 2.3bis), **fonte unica e uniforme per tutte le 10 stagioni storiche** — non due rami (foglio esplicito vs. differenza), ma lo stesso insieme letto direttamente in ogni stagione:

| Stagioni | Fonte |
|---|---|
| 2016/17 - 2025/26 | appartenenza al foglio `Ceduti` delle quotazioni di quella stagione (identico, per costruzione, a `stats \ quotazioni_Tutti` — sezione 2.3bis) |
| 2026/27 (stagione corrente, non ancora conclusa) | non applicabile: il file 2026/27 è pre-stagione e il suo `Ceduti` (31 righe) misura chi era già ceduto prima dell'inizio della stagione, non chi ne è uscito in corsa (sezione 2.3bis) |

Il flag è definito per costruzione anche sulle righe `PLAYED` (un giocatore può uscire dalla Serie A a stagione già ampiamente giocata), ma **cambia il trattamento della riga solo quando combinato con `RowType = IN_SQUAD_NO_PLAY`** (sezione 9.1bis, B3): chi è uscito in corsa con `Pv >= 1` resta una riga `PLAYED` normale, a peso pieno, in tutti i calcoli.

### 4.1 Ruolo del giocatore — quale R si usa e dove (vincolo esplicito)

Il ruolo `R` può cambiare tra stagioni (riclassificazioni Fantacalcio.it, spostamenti di posizione: un C che diventa A). Verificato su 10 stagioni: 74 Id su 2306 (3.2%) cambiano `R` almeno una volta nella finestra — un fenomeno marginale su 3 stagioni, non più marginale su 10. Il controllo QC `role_change` (sezione 22) è quindi **obbligatorio nel report**, non facoltativo. Quale ruolo usare in quale calcolo non va lasciato all'implementazione:

| Calcolo | Ruolo usato |
|---|---|
| Percentile Fm per ruolo/stagione (sezione 10) | `R` **della stagione in esame** |
| Percentile GoalRate/AssistRate per ruolo/stagione (sezione 11) | `R` **della stagione in esame** |
| Performance del portiere (sezione 13) | `R` **della stagione in esame**: un giocatore è valutato con la formula portiere solo nelle stagioni in cui era P |
| Pesi della formula di rating (sezione 12) | `R` **della lista 2026/27** (sezione 2.2) |
| `goal_weight` / `assist_weight` del BonusProfile (sezione 11.3) | `R` **della lista 2026/27** |
| `Rank_Role` e raggruppamenti dell'output (sezione 21) | `R` **della lista 2026/27** |

Razionale: le feature stagionali devono essere confrontate con il gruppo di riferimento corretto *di quell'anno*, mentre il rating deve rispondere alla domanda "quanto vale questo giocatore nel ruolo in cui lo compro oggi".

Conseguenze operative obbligatorie:
- ogni cambio di `R` tra stagioni per lo stesso Id genera una riga `WARNING role_change` nel qc_log (sezione 22): si stanno aggregando percentili calcolati su popolazioni diverse, cosa legittima ma da rendere visibile;
- il cambio da o verso `P` è il caso critico, perché la Performance del portiere usa una formula diversa (sezione 13) e non è confrontabile con quella degli altri ruoli nemmeno dopo normalizzazione a percentile — non è la stessa distribuzione con pesi diversi, è una formula strutturalmente diversa (Gs/Rp al posto di BonusProfile). **Regola, non solo avviso**: per un giocatore il cui cambio di ruolo attraversa il confine portiere (`P → non-P` o `non-P → P`), `Performance_Storica` (sezione 8) aggrega **solo le stagioni giocate nel ruolo corrente** (quello della lista 2026/27, sezione 4.1), ripesando proporzionalmente come da sezione 8 anche se questo lascia una sola stagione disponibile o nessuna (in quel caso il giocatore ricade nella classificazione di sezione 6 in base al `Pv_Totale` delle sole stagioni nel ruolo corrente). Per i cambi di ruolo che non attraversano il confine portiere (es. C → A) resta l'approccio corrente: tutte le stagioni disponibili contribuiscono, ciascuna già confrontata al proprio gruppo di ruolo/stagione tramite percentile — un cambio C → A è meno critico dopo normalizzazione a percentile, ma va comunque segnalato per controllo manuale. In entrambi i casi il qc_log riporta comunque `WARNING role_change_gk` per revisione manuale — la regola sopra è il comportamento di default della pipeline, non un sostituto della verifica umana su un caso raro. **Verificato: 0 Id su 2306 attraversano il confine portiere nelle 10 stagioni disponibili** — la regola resta come difesa (un cambio è plausibile e potrebbe presentarsi in futuro), ma l'insieme è vuoto su questa finestra: una lista `role_change_gk` non vuota nel qc_log segnala un problema nei dati sorgente (es. errore di ruolo), non un caso reale di modellazione da gestire subito;
- il campo `R_Storico` (sequenza dei ruoli per stagione, es. `C/C/A`) va esposto nel CSV finale quando differisce dal ruolo corrente.

## 5. Join con la stagione corrente

```
   statistiche (train_window stagioni, foglio Tutti — unico foglio presente, sez. 2.1)
                          ↓
      righe PLAYED (Pv >= 1) + righe IN_SQUAD_NO_PLAY (Pv = 0)
                          ↓
   quotazioni delle stesse stagioni (Tutti + Ceduti) → flag left_mid_season (sez. 2.3bis/4.0bis) + Qt.I
                          ↓
          dataset storico unico (long format, sezione 4)
                          ↓
             JOIN con lista 2026/27 tramite Id
                          ↓
               universo giocatori 2026/27
```

- La Squadra storica per ogni stagione resta invariata (campo storico).
- Nel dataset finale si riporta anche la Squadra_2026_27 (se disponibile dalla lista corrente), usata solo come informazione, non come fattore di rating in questa versione.
- Giocatori nella lista 2026/27 ma assenti dallo storico: non eliminati, vedi sezione 6.
- Giocatori nello storico ma NON nella lista 2026/27: esclusi dal ranking finale (persi/ritirati/all'estero).

## 6. Giocatori senza storico sufficiente

Classificazione a tre livelli, basata sul totale di Pv sommato sulle stagioni disponibili nella finestra di train (`train_window`, sezione 20.2):

| Categoria | Condizione | Trattamento |
|---|---|---|
| PV_SUFFICIENTI | `Pv_Totale >= historical_min_pv_total` (default 15) | Rating calcolato normalmente |
| LIMITED_HISTORY | `1 <= Pv_Totale < historical_min_pv_total` | Rating calcolato, tipicamente con Confidence bassa (sezione 19) |
| NEW | `Pv_Totale = 0`: nessun voto ricevuto in nessuna delle stagioni della finestra di train | Nessun rating storico; `HistoricalRating = null`, categoria esplicita (vedi sezione 21.3 per il trattamento in output) |

(Il nome `PV_SUFFICIENTI` sostituisce il precedente `STORICO`: quest'ultimo lasciava intendere che sopra soglia il dato diventasse "affidabile" in senso pieno, cosa che la soglia — un semplice conteggio di presenze — non misura. Cambio cosmetico, nessun impatto sulla condizione.)

dove `Pv_Totale = Σ Pv` sulle sole righe `PLAYED` (le righe `IN_SQUAD_NO_PLAY` hanno per definizione Pv = 0 e non contribuiscono al totale, ma contribuiscono a `Seasons_In_Squad`, sezione 21).

`historical_min_pv_total` è un **unico** parametro configurabile: la soglia superiore di LIMITED_HISTORY è derivata da esso (`< historical_min_pv_total`), non configurata separatamente. Due parametri per la stessa soglia sono due fonti di verità che prima o poi divergono.

Nota sul caso limite: un giocatore in rosa in tutte le stagioni della finestra di train ma mai impiegato risulta `NEW` per categoria (nessun dato di rendimento) pur avendo `Seasons_In_Squad = train_window` e una Reliability calcolabile e molto bassa (se non è mai uscito in corsa; sezione 9.1bis). È raro ma legittimo, ed è il motivo per cui il CSV espone `Seasons_Available` (stagioni con `Pv >= 1`), `Seasons_In_Squad` (stagioni con una riga nel file statistiche, `PLAYED` o `IN_SQUAD_NO_PLAY`) e `Seasons_Quoted` (stagioni presenti nelle quotazioni, sezione 21) come campi distinti.

## 7. Performance vs Affidabilità (principio cardine)

**Non moltiplicare mai Fm × Pv.** Le due dimensioni restano separate e vengono combinate solo nella formula finale del rating, ciascuna con il proprio peso:

- **Performance**: quanto è stato forte quando ha giocato → basata su Fm (percentile per ruolo) e Mv.
- **Reliability**: quanto spesso è stato disponibile → basata su Pv, con una funzione non lineare.

Nota terminologica: il nome "Reliability" è mantenuto per uso pratico/colloquiale (è il nome che comparirà nel CSV finale), ma va documentato nel README che tecnicamente misura la **disponibilità/numerosità del campione** (quante partite ha giocato), non l'affidabilità caratteriale del giocatore in senso pieno. Non ha impatto sulla formula, solo sulla comprensione del dato.

## 8. Pesi temporali — decadimento esponenziale

Le stagioni più recenti pesano di più. Usare decadimento esponenziale invece di pesi fissi arbitrari, per generalizzare facilmente ad anni futuri (N stagioni):

```
peso_stagione_i = base^i / (somma di base^i su tutte le stagioni disponibili)
```

dove `base` è `time_decay.base` (parametro configurabile, default 1.5 — sezione 24), non fissato a 2. Il numero di stagioni su cui si applica è `train_window` (parametro configurabile, sezione 20.2/20.5 — non più fissato a 3). Esempio illustrativo con `base = 2` (non il default) e `train_window = 3` (dalla più vecchia alla più recente), pesi relativi 1 : 2 : 4, normalizzati:

| Stagione (esempio, base=2, train_window=3) | Peso |
|---|---|
| t-2 | 1/7 ≈ 14.3% |
| t-1 | 2/7 ≈ 28.6% |
| t (più recente) | 4/7 ≈ 57.1% |

```
Performance_Storica = Σ (peso_stagione_i × Performance_stagione_i)
```

**Gestione stagioni mancanti — regola differenziata per famiglia di feature.** È il punto in cui è più facile introdurre una distorsione sistematica, quindi la regola è esplicita e non unica:

| Famiglia di feature | Stagioni incluse | Trattamento delle stagioni mancanti |
|---|---|---|
| **Performance** (percentile Fm), `Fm_Weighted`, `Mv_Weighted`, BonusProfile, `Gf_Rate`, `Ass_Rate`, Trend | solo righe `PLAYED` (`Pv >= 1`) | pesi **ripesati proporzionalmente** (rinormalizzati a somma 1) |
| **Reliability** | righe `PLAYED` **e** righe `IN_SQUAD_NO_PLAY` (`Pv = 0`) esclusi i casi `left_mid_season` (sezione 9.1bis) | vedi sezione 9.1bis: una stagione in rosa senza presenze, in cui il giocatore è rimasto tutto l'anno, entra con `Reliability_stagione = 0` e **peso pieno** |

Razionale: la Performance è una misura **condizionata** ("quanto era forte quando giocava"), quindi una stagione senza osservazioni non è un valore basso, è un dato assente e va esclusa. La Reliability è una misura **non condizionata** ("quanto è stato disponibile"), quindi una stagione in cui era in Serie A e non ha giocato è l'osservazione più informativa che esista e non va esclusa.

Esempio (famiglia Performance): solo 2024/25 e 2025/26 con `Pv >= 1` → pesi ripesati a 2/6 ≈ 33.3% e 4/6 ≈ 66.7%.

**Insieme di ripesatura vuoto — regola obbligatoria.** Se, per un giocatore, **tutte** le stagioni della finestra di train sono escluse dalla famiglia Performance (nessuna riga `PLAYED`) — caso possibile per un giocatore in rosa ma mai schierato — la ripesatura non ha nulla su cui operare: `Performance_Storica`, `Fm_Weighted`, `Mv_Weighted`, `BonusProfile`, `Gf_Rate`, `Ass_Rate` e `Trend` restano `null`, non `0`. Lo stesso vale per la famiglia Reliability se **tutte** le stagioni di train sono `IN_SQUAD_NO_PLAY` con `left_mid_season = true` (tutte escluse dalla regola della sezione 9.1bis): `Reliability` resta `null`, non `0`. È lo stesso principio della sezione 4.0 (`Fm = null` non è `Fm = 0`) applicato a un insieme vuoto invece che a una singola riga; il conteggio di questi casi è un controllo QC in sezione 22, e la sezione 12 definisce cosa succede a `HistoricalRating` quando una delle due componenti è nulla.

I pesi (base 2, o eventualmente altra base) devono essere un parametro configurabile nel codice, non hard-coded.

## 9. Reliability — score continuo + soglia categorica

Due meccanismi distinti che convivono, con scopi diversi:

### 9.1 Reliability score (continuo, entra nella formula del rating)

Per singola stagione:

```
Reliability_stagione = min(1, sqrt(Pv / reference_pv))
```

con `reference_pv = 30` come parametro configurabile in config.yaml. Documentare esplicitamente che questo valore non rappresenta "una stagione completa" in senso calcistico letterale, ma è il punto di saturazione scelto per la metrica — utile per chi calibra il modello in futuro.

| Pv | Reliability (reference_pv=30) |
|---|---|
| 5 | 0.41 |
| 10 | 0.58 |
| 15 | 0.71 |
| 20 | 0.82 |
| 25 | 0.91 |
| 30+ | 1.00 |

La Reliability storica complessiva è la media pesata (stessi pesi temporali della sezione 8) delle Reliability di stagione, con il perimetro di stagioni definito nella sezione 9.1bis.

Questo score è solo un punto di partenza: va validato e calibrato nella validazione retrospettiva (sezione 20), che include un test **diretto** del suo potere predittivo sulla disponibilità futura (sezione 20.6bis) e non solo il contributo indiretto misurato dall'ablation.

**La forma della funzione, non solo `reference_pv`, va testata.** `sqrt` è una forma scelta per costruzione, non derivata dai dati: implica che passare da 5 a 10 presenze valga quanto passare da 20 a 30, un'assunzione che il backtest può verificare direttamente. `reliability.function` è quindi un parametro configurabile (`sqrt` di default; alternative da testare: `linear` — `min(1, Pv / reference_pv)` — e, se il tempo lo consente, una forma logistica), e va validato **esclusivamente** tramite il test diretto della sezione 20.6bis (`Spearman(Reliability_train, Pv_target)` e sulla disponibilità binaria), non facendolo passare attraverso `HistoricalRating`: il test diretto ha un target pulito e usa l'intero universo Serie A del target, mentre passare per il rating ne diluirebbe il segnale con Performance e BonusProfile.

### 9.1bis Perimetro delle stagioni per la Reliability (correzione della distorsione da storico corto)

**Problema.** Se le stagioni mancanti vengono escluse e ripesate come per la Performance, due giocatori molto diversi risultano identici:

| Giocatore | t-2 | t-1 | t | Reliability (ripesatura semplice) |
|---|---|---|---|---|
| A | 30 Pv | 30 Pv | 30 Pv | 1.00 |
| B | assente | assente | 30 Pv | 1.00 |

Il giocatore B ha dimostrato la propria disponibilità su un terzo dei dati di A; e se le due stagioni assenti erano stagioni in Serie A senza impiego, la sua disponibilità reale è pessima. Poiché `Confidence` per vincolo esplicito non entra nel rating (sezione 19.1), senza una correzione questa distorsione arriverebbe intatta dentro `HistoricalRating` — cioè esattamente nel numero che si guarda in asta.

**Regola (aggiornata — B1/B3).** Per ogni giocatore e ciascuna delle stagioni della finestra di train:

| Situazione | Riconoscibile da | Reliability_stagione | Entra nella media pesata |
|---|---|---|---|
| Ha giocato | `RowType = PLAYED`, `Pv >= 1` | `min(1, sqrt(Pv / reference_pv))` | sì, peso pieno |
| In rosa, nessun voto, rimasto tutta la stagione | `RowType = IN_SQUAD_NO_PLAY`, `left_mid_season = false` | `0` | **sì, peso pieno** |
| In rosa, nessun voto, uscito dalla Serie A in corsa | `RowType = IN_SQUAD_NO_PLAY`, `left_mid_season = true` | non definita | no, escluso e peso ripesato (sezione 8) — comportamento di default, disattivabile (vedi sotto) |
| Non era in Serie A | nessuna riga per quella stagione | non definita | no, peso ripesato (sezione 8) |

Con questa regola il giocatore B dell'esempio mantiene `Reliability = 1.00` solo se davvero non era in Serie A (caso legittimo: acquisto dall'estero), e scende a `0` se era presente e inutilizzato per l'intera stagione (infortunio lungo, esclusione tecnica). Se invece era presente e inutilizzato ma è uscito dalla Serie A in corsa, la stagione viene **esclusa** anziché contargli come `0`: non ha avuto la stagione intera per dimostrare (o non dimostrare) disponibilità.

**Perché l'esclusione, e non più `Reliability_stagione = 0` a peso pieno per tutte le `IN_SQUAD_NO_PLAY`.** La versione precedente di questa regola trattava il caso "uscito in corsa" come un limite dichiarato e accettato ("le cessioni in uscita non sono ricostruibili con i dati di questa versione"). Verifica eseguita sui 10 anni di dati (piano di revisione §2.9): **fra il 55.9% e il 74.5% dei giocatori con `Pv = 0`, a seconda della stagione, sono usciti dalla Serie A durante l'anno** — non è una coda, è il caso prevalente fra i `Pv = 0`. Penalizzare con `Reliability_stagione = 0` chi non ha avuto l'occasione di giocare per essere stato ceduto a settembre non è più una distorsione marginale accettabile; il flag `left_mid_season` (sezione 4.0bis) rende ora possibile distinguere i due casi, quindi la distorsione si corregge invece di dichiararla.

Restano genuini "in Serie A tutto l'anno, mai un voto" — cioè il caso a cui questa sezione applica davvero `Reliability_stagione = 0` — solo 35-52 giocatori a stagione: è un sottoinsieme minoritario di tutte le righe `IN_SQUAD_NO_PLAY`, ma è quello per cui la regola ha senso.

Il comportamento è configurabile (`reliability.exclude_left_mid_season`, default `true`), così che l'impatto della scelta sia misurabile confrontando le due varianti in ablation (sezione 20.4.4, Model 3a): a `false` si torna al comportamento precedente (`Reliability_stagione = 0` a peso pieno anche per gli usciti in corsa).

### 9.2 Categoria di storico (etichetta, per filtro/comunicazione)

Vedi tabella sezione 6 (PV_SUFFICIENTI / LIMITED_HISTORY / NEW), basata sul Pv totale cumulato. Serve a etichettare e filtrare, non entra nella formula numerica del rating.

## 10. Performance score stagionale

Calcolata come percentile della Fm rispetto agli altri giocatori **dello stesso ruolo R** nella stessa stagione (non usare Fm assoluta, che si sposta di stagione in stagione):

```
FmPercentile_stagione = percentile(Fm, rispetto a tutti i giocatori con lo stesso R in quella stagione)   # range 0-100
Performance_stagione = FmPercentile_stagione / 100                                                         # range 0-1
```

**Importante — scale esplicite**: tutte le componenti che entrano nella formula del rating finale (sezione 12) devono avere una scala esplicitamente definita e coerente:
- `Performance ∈ [0, 1]`
- `Reliability ∈ [0, 1]`
- `BonusProfile ∈ [-1, +1]`

Il calcolo del percentile restituisce nativamente un valore 0-100: va sempre diviso per 100 prima di entrare in qualunque formula pesata, altrimenti domina numericamente le altre componenti (es. 85 invece di 0.85 renderebbe irrilevante il contributo di Reliability e BonusProfile). Questo vincolo di scala si applica identicamente al calcolo della Performance dei portieri (sezione 13).

**Metodo del percentile**: usare una funzione standardizzata e deterministica (es. `rank(pct=True)` di pandas), documentata esplicitamente nel codice per garantire riproducibilità.

**Gruppo di riferimento — parametro configurabile**: includere nel calcolo del percentile solo i giocatori con `Pv ≥ min_pv_for_percentile` (parametro in config.yaml, valore di partenza: 1). Questo evita che un giocatore con 2 presenze e una Fm anomala (es. 9.50 su un exploit isolato) distorca la distribuzione di riferimento. Non fissare questo valore a priori: testare in fase di validazione (sezione 20) almeno le varianti 1, 3, 5 e scegliere quella che massimizza il potere predittivo del modello, non quella che sembra "più corretta" a intuito. Questo stesso parametro (eventualmente con valore ottimale diverso) si applica anche al calcolo del BonusProfile — vedi sezione 11.1bis.

**Gruppo di riferimento ≠ gruppo valutato (vincolo esplicito).** Il filtro definisce chi *costruisce* la distribuzione, non chi *riceve* un punteggio. Un giocatore con `Pv` sotto la soglia:
- **riceve comunque** una `Performance_stagione`, calcolata come sua posizione rispetto alla distribuzione filtrata (interpolazione della sua Fm nella distribuzione di riferimento del suo ruolo in quella stagione);
- **non contribuisce** alla costruzione di quella distribuzione.

Senza questa distinzione, un `min_pv_for_percentile = 5` renderebbe non calcolabile la Performance per buona parte della popolazione LIMITED_HISTORY — che è invece esattamente la popolazione su cui la Confidence deve poter dire qualcosa. Implementativamente: calcolare i percentili sul gruppo filtrato e poi mappare *tutti* i giocatori su quella scala; **non** applicare `rank(pct=True)` al dataframe filtrato e fare un join che lascia `null` sugli esclusi.

La Mv viene mantenuta come metrica separata (pesata con gli stessi pesi temporali → `Mv_Weighted`), usata esclusivamente per il Modificatore Difesa (sezione 13), mai fusa nel Performance score.

## 11. Bonus Profile

Il Bonus Profile non deve sommarsi alla Fm (che già incorpora bonus/malus) — funziona come **modulatore basato sullo scarto dalla mediana di ruolo**, con peso e comportamento diversi per ruolo. Deve avere una formula matematica precisa (non un "eventuale contributo" vago) e va normalizzato sulla stessa scala di Performance/Reliability prima di entrare nella formula del rating.

### 11.1 Calcolo base

Per ogni stagione, calcolare tassi normalizzati sulle presenze (in assenza dei minuti giocati):

```
GoalRate           = Gf / Pv
NonPenaltyGoalRate = (Gf - R+) / Pv
AssistRate         = Ass / Pv
```

Le righe `IN_SQUAD_NO_PLAY` (`Pv = 0`, sezione 4) sono escluse per costruzione da questo calcolo: il risultato è `null`/non calcolabile, **non zero**. Nessuna divisione per zero deve poter avvenire; se avviene è un bug nel filtro sulle righe, non un caso da tamponare con un valore di default.

**`GoalRate` vs `NonPenaltyGoalRate` (da calibrare, non da scegliere a priori).** `Gf` include i gol su rigore, quindi `GoalRate` premia il rigorista designato. Quel ruolo è però il meno trasferibile di tutti: cambia con la cessione, con l'arrivo di un compagno, con una decisione dell'allenatore. `NonPenaltyGoalRate` isola la produzione realizzativa indipendente dai rigori.

Entrambe le metriche vanno calcolate e conservate nel dataset. Quale delle due alimenta il BonusProfile è un parametro:

```yaml
bonus_profile:
  goal_rate_metric: GoalRate   # oppure NonPenaltyGoalRate
```

Da testare in validazione come variante alternativa (sezione 20.4.4, Model 3b): sui rigoristi stabili `GoalRate` può essere più predittivo, su chi cambia squadra è plausibile il contrario. La dipendenza da rigori resta comunque esposta come flag informativo (sezione 18.2).

### 11.1bis Filtro sul campione (stesso problema della sezione 10, applicato qui)

Un giocatore con `Pv = 1, Gf = 1` avrebbe `GoalRate = 1.00`, un valore matematicamente enorme ma privo di significato statistico — un singolo episodio, non un tasso stabile. Applicare lo stesso filtro della sezione 10:

```
bonus_profile:
  min_pv_for_percentile: 1   # parametro indipendente da performance.min_pv_for_percentile, da calibrare separatamente
```

Includere nel calcolo del percentile di GoalRate/AssistRate solo i giocatori con `Pv ≥ min_pv_for_percentile` (parametro configurabile, non necessariamente uguale a quello usato per la Performance in sezione 10 — vanno testati e calibrati indipendentemente in validazione). Per questa v1 non sono richieste tecniche più sofisticate (shrinkage bayesiano, winsorization): il filtro sul Pv minimo è sufficiente e più semplice da validare; eventuali raffinamenti sono rimandati a versioni future. Il filtro non risolve però un problema diverso e complementare — la massa di giocatori con `rate = 0` esatto, che sposta la mediana di ruolo — trattato nella sezione 11.2 con `zero_handling`.

Calcolare il percentile di GoalRate e AssistRate **rispetto ai soli giocatori dello stesso ruolo R** (che superano il filtro) in quella stagione (stesso metodo deterministico della sezione 10), poi combinarli con pesi espliciti e configurabili per ruolo:

```
BonusProfile_stagione = goal_weight_R × (percentile(GoalRate) - 50)
                       + assist_weight_R × (percentile(AssistRate) - 50)
```

con `goal_weight_R + assist_weight_R = 1` per ciascun ruolo R.

### 11.2 Normalizzazione (obbligatoria)

Il risultato del calcolo precedente ha range teorico -50/+50, mentre Performance e Reliability hanno range 0-1. Prima di entrare nella formula del rating, normalizzare:

```
BonusProfile_normalized = BonusProfile_stagione / 50
```

ottenendo un range **-1/+1**, dove 0 = mediana di ruolo. Valori prossimi a +1 rappresentano la parte alta della distribuzione di ruolo, valori prossimi a -1 la parte bassa — non necessariamente esattamente il massimo/minimo assoluto, dato che il metodo del percentile con pareggi (`rank(pct=True)`) non garantisce di toccare esattamente 0 e 100. Aggregare su più stagioni con gli stessi pesi temporali della sezione 8, ottenendo `BonusProfile` finale nel range -1/+1.

Questa normalizzazione è necessaria per evitare che il BonusProfile domini artificialmente la formula del rating solo per una questione di scala numerica, non di peso voluto.

**Attenzione — "0 = mediana di ruolo" non è vero per i difensori.** Con `min_pv_for_percentile` basso, una quota molto grande di difensori ha `GoalRate = 0` **esatto**, e una quota consistente ha anche `AssistRate = 0`. Quel blocco di pareggi riceve un unico percentile di midrank collocato nella parte bassa della distribuzione: il risultato è che il difensore *modale* — quello normale, senza bonus — ottiene un `BonusProfile` **negativo**, non zero. Il modulatore smette così di essere centrato e diventa una penalizzazione sistematica di quasi tutto il ruolo, con una manciata di difensori che si stacca verso l'alto.

Due contromisure obbligatorie:

1. **Controllo QC bloccante** (sezione 22): per ogni ruolo e stagione, riportare la quota di giocatori nel blocco a `rate = 0` e la mediana risultante di `BonusProfile_normalized`. Se la quota a zero supera `bonus_profile.max_zero_share` (default 0.30) **oppure** la mediana si discosta da 0 più di 0.10, il comportamento va corretto prima di usare il ranking.

2. **Metodo di centratura**, di cui il default `recenter` garantisce il criterio del controllo QC per costruzione:

```
zero_handling = recenter (default):
  BonusProfile_stagione centrato = BonusProfile_stagione grezzo
                                    - mediana_ruolo_stagione(BonusProfile_stagione grezzo)
  applicato prima della normalizzazione /50 di sezione 11.2, sullo stesso gruppo/ruolo/stagione
  usato per calcolare il percentile. Non modifica la forma della distribuzione (nessuna
  chirurgia sui pareggi), sposta solo la sua posizione: la mediana risultante è
  esattamente 0 per costruzione, indipendentemente da quanto grande sia il blocco a rate = 0.

zero_handling = split:
  percentile calcolato solo sui giocatori con rate > 0, mappato su [50, 100]
  giocatori con rate = 0 → valore fisso al centro del blocco a zero, non midrank
                            sulla distribuzione completa

zero_handling = midrank:
  comportamento standard (midrank sull'intera distribuzione, zeri inclusi)
```

**Perché `recenter` come default.** Risolve direttamente il sintomo misurato dal controllo QC (mediana spostata da 0) con una singola sottrazione, senza introdurre la complessità aggiuntiva di `split` (percentile calcolato su un sotto-campione diverso per stagione) finché quella complessità non è dimostrata necessaria. Non risolve un problema diverso — la concentrazione del blocco a zero in sé, indipendente dalla sua posizione — che resta osservabile tramite la quota a zero riportata dal controllo QC e affrontabile con `split` se il backtest lo richiede. `split` e `midrank` restano parametri configurabili e testati esplicitamente in ablation (sezione 20.4.4, Model 3c e 3d). Come per tutto il resto, la scelta finale la decide la validazione, non l'intuizione.

### 11.3 Peso e configurazione per ruolo

| Ruolo | Peso nel rating finale | goal_weight | assist_weight | Comportamento |
|---|---|---|---|---|
| Portieri | 0% (non usato come componente separata) | — | — | Gs/Pv e Rp restano nella Performance del portiere, sezione 13 |
| Difensori | 15% (default rivisto, B12) | 0.60 | 0.40 | Anche un tasso di gol/assist modesto in assoluto vale molto perché la mediana di ruolo è vicina a zero — il percentile cattura questo automaticamente |
| Centrocampisti | 15% (invariato) | 0.60 | 0.40 | Nessuna distinzione tra centrocampisti offensivi/di rottura (rimandata a eventuale uso futuro di Rm) |
| Attaccanti | 15% (default rivisto, B12), bidirezionale | 0.70 | 0.30 | Sotto la mediana di ruolo = malus reale, non "assenza di bonus". Segnare è il loro mestiere |

Tutti i pesi (sia il peso del BonusProfile nel rating, sia goal_weight/assist_weight interni) sono parametri configurabili in config.yaml, da confermare/calibrare con la validazione retrospettiva (sezione 20).

**Default di `bonus_weight` per D/A rivisto da 0.25 a 0.15 (B12, decisione presa).** Con 10 stagioni disponibili la potenza per calibrare il peso del BonusProfile è sufficiente per una griglia vera: `bonus_weight ∈ {0, 0.10, 0.15, 0.25, 0.35}` per D e A, dove **0 è l'ablation** ("serve?") e gli altri valori rispondono a "quanto pesa?" — un solo test invece di due (sezione 20.4.4/20.5a). Il valore **0.15 è pre-registrato come nuovo default**, prima di vedere i risultati del backtest, allineandolo al peso già usato per i Centrocampisti. Performance e Reliability per D e A si **allineano alla stessa distribuzione già usata per C** (Performance 0.60, Reliability 0.25) invece di essere riscalate da un rapporto previo: la scelta più semplice e difendibile, non il risultato di una riscalatura proporzionale dello spazio residuo (0.85 × 55/75 darebbe 0.6233/0.2267, non 0.60/0.25 — l'aritmetica "mantenendo il rapporto 55:20" non torna e non va usata come motivazione). Risultato: **Performance 0.60, Reliability 0.25, Bonus 0.15** per D/C/A (sezione 12). Resta un valore di partenza da confermare con la calibrazione (ordine fisso di sezione 20.5), non un risultato del backtest.

**Nota di calibrazione — "modulatore" va verificato, non assunto.** Il termine "modulatore" (sezione 11) descrive un'intenzione, non una proprietà garantita dai numeri. Perché `Performance ∈ [0,1]` e `BonusProfile ∈ [-1,+1]`, l'escursione (span) realizzabile da ciascun termine nella formula del rating (sezione 12) è `peso × ampiezza_range`, non solo il peso nominale:

| Ruolo | Span Performance (peso × 1) | Span BonusProfile (peso × 2) |
|---|---|---|
| D | 0.60 | 0.15 × 2 = 0.30 |
| A | 0.60 | 0.15 × 2 = 0.30 |
| C | 0.60 | 0.15 × 2 = 0.30 |

Con il default rivisto (0.15), D, C e A hanno ora lo stesso rapporto Performance:BonusProfile (2:1): il BonusProfile resta un contributo significativo ma non più quasi co-primario come con il vecchio default 0.25 (dove lo span era quasi 1:1 con Performance per D/A). Questo era il problema che la nota di calibrazione segnalava nella revisione precedente; il nuovo default lo riduce ma non lo elimina come domanda aperta — il controllo doppio conteggio della sezione 11.4 e l'ablation della sezione 20.4.4 restano le sedi in cui il peso effettivo va confermato o ulteriormente ridimensionato, non la descrizione testuale del componente.

### 11.4 Controllo doppio conteggio (obbligatorio in fase di validazione)

Poiché la Fm incorpora già gol/assist/rigori/malus, il BonusProfile rischia di essere un secondo conteggio mascherato dello stesso segnale se il suo peso è troppo alto. In fase di validazione, calcolare esplicitamente:

```
Rating_senza_BonusProfile  vs  Rating_con_BonusProfile
```

e misurare quanto cambia l'ordinamento risultante (es. quanti giocatori cambiano posizione di oltre N posti). Se il BonusProfile sposta drasticamente la classifica, è un segnale che il suo peso è troppo alto rispetto al ruolo di "modulatore" che deve avere. Collegare questo controllo all'ablation test della sezione 20.

## 12. Formula del rating finale — per ruolo

Il rating calcolato in questa versione è uno **storico** (basato solo su dati passati), da trattare esplicitamente come `HistoricalRating` — mai come "Rating" generico indifferenziato — per lasciare spazio futuro a `ProjectedRating` e `AuctionRating` senza dover rifare l'architettura (vedi sezione 12.1).

Con le scale definite nelle sezioni 9-11 (`Performance ∈ [0,1]`, `Reliability ∈ [0,1]`, `BonusProfile ∈ [-1,+1]`), la formula interna produce un valore raw:

```
HistoricalRatingRaw_Portiere       = 0.75 × Performance + 0.25 × Reliability                                    # range [0, 1]
HistoricalRatingRaw_Difensore      = 0.60 × Performance + 0.25 × Reliability + 0.15 × BonusProfile               # range [-0.15, 1]
HistoricalRatingRaw_Centrocampista = 0.60 × Performance + 0.25 × Reliability + 0.15 × BonusProfile               # range [-0.15, 1]
HistoricalRatingRaw_Attaccante     = 0.60 × Performance + 0.25 × Reliability + 0.15 × BonusProfile               # range [-0.15, 1]
```

Pesi D/C/A allineati con il nuovo default `bonus_weight = 0.15` (sezione 11.3, B12) — provvisorio, da confermare con la calibrazione (sezione 20.5).

Nota: essendo BonusProfile potenzialmente negativo (un giocatore sotto la mediana di ruolo su gol/assist), `HistoricalRatingRaw` può essere negativo per difensori/centrocampisti/attaccanti con BonusProfile fortemente negativo. Questo è un comportamento accettato e voluto (sezione 11.3: per gli attaccanti in particolare, un rendimento realizzativo scarso deve pesare come malus reale).

**Trasformazione di presentazione** (solo per il CSV finale, non altera la matematica interna):

```
HistoricalRating = HistoricalRatingRaw × 100
```

Questo produce valori leggibili (es. 78.4, 72.1, 64.8) mantenendo tutti i calcoli interni sulle scale normalizzate 0-1/-1-+1. Tutti i confronti, ranking e test statistici vanno eseguiti su `HistoricalRatingRaw` con piena precisione decimale (almeno 4-6 decimali), non sul valore arrotondato ×100 esposto nel CSV.

**Range effettivo di `HistoricalRating`**, coerente con i range raw sopra:

| Ruolo | Range `HistoricalRating` |
|---|---|
| P | 0 → 100 |
| D | -15 → 100 |
| C | -15 → 100 |
| A | -15 → 100 |

Questa colonna **non va descritta come "scala 0-100"** in nessun punto della documentazione, del CSV o dell'interfaccia: un valore negativo è un output valido e previsto, non un errore di calcolo.

Tutti i pesi sono configurabili in un unico punto del codice (config.yaml), non sparsi/hard-coded nella logica.

Il rating è calcolato solo per giocatori PV_SUFFICIENTI o LIMITED_HISTORY. Per i NEW il campo resta nullo con categoria esplicita.

**Componenti nulle (insieme di ripesatura vuoto, sezione 8/9.1bis).** Se `Performance` o `Reliability` sono `null` per un giocatore PV_SUFFICIENTI/LIMITED_HISTORY (nessuna stagione di train contribuisce a quella famiglia), `HistoricalRatingRaw` e quindi `HistoricalRating` sono anch'essi `null` — non calcolati sostituendo la componente mancante con `0`, che produrrebbe un numero silenziosamente distorto verso il basso. Il campo `Note` del CSV finale (sezione 21) riporta esplicitamente il motivo (es. `Reliability non definita: tutte le stagioni in rosa sono left_mid_season`).

### 12.0bis Tie-break deterministico per il Rank

Il calcolo di `Rank`/`Rank_Role` (sezione 21) deve usare un ordinamento con criteri di spareggio espliciti e deterministici, per garantire che la stessa pipeline produca sempre lo stesso risultato anche in presenza di valori di rating identici o molto vicini:

```
ORDER BY HistoricalRatingRaw DESC, Performance DESC, Reliability DESC, Id ASC
```

Per i giocatori con `Categoria = NEW` (HistoricalRating nullo), `Rank` e `Rank_Role` restano `null` — non vanno inseriti in coda con un numero convenzionale, per non suggerire un ordinamento che non è stato realmente calcolato (vedi sezione 21.3).

**`Rank_Role` è il ranking valido; `Rank` globale è solo una comodità di ordinamento.** Il rating è costruito su percentili calcolati *dentro* il ruolo e con formule diverse per ruolo (i portieri non hanno il termine BonusProfile e usano pesi 0.75/0.25). Ne segue che un portiere a 78 e un attaccante a 78 **non** sono equivalenti in alcun senso verificato: significano soltanto "78° percentile del proprio ruolo, secondo la formula di quel ruolo". Un confronto inter-ruolo richiederebbe scarsità di ruolo e prezzi, cioè esattamente ciò che questa versione dichiara fuori scope (sezione 12.1).

Conseguenze obbligatorie:
- il README dichiara che `Rank` non è utilizzabile per decidere tra due giocatori di ruolo diverso;
- tutte le metriche di validazione (sezione 20.4) si calcolano **per ruolo**, mai sull'universo indifferenziato;
- l'ordinamento di default di `ranking_dataset.csv` è per `R`, poi `Rank_Role` crescente.

### 12.1 Nomenclatura per estensioni future (importante per l'architettura, non solo per il naming)

Il codice deve trattare concettualmente 4 livelli distinti, anche se in questa versione solo il primo è implementato:

```
raw metrics (Fm, Mv, Pv, Gf, Ass, ...)
        ↓
normalized features (Performance, Reliability, BonusProfile)
        ↓
HistoricalRating (output di questa versione)
        ↓
AuctionRating (in questa versione: AuctionRating = HistoricalRating)
```

In futuro, quando sarà introdotto un modello predittivo (sezione 25), si aggiungerà `ProjectedRating` e `AuctionRating` potrà diventare una combinazione dei due, senza che questo richieda di rinominare o ristrutturare le colonne già esistenti.

**Rimossa dal CSV (B11, revisione corrente).** Le versioni precedenti esponevano anche `AuctionRating`, identico a `HistoricalRating` in questa versione, come segnaposto architetturale. Una colonna duplicata con un nome che promette più di quanto contenga (`AuctionRating` suggerisce una decisione d'asta compiuta: prezzo, budget, scarsità di ruolo, rosa già acquistata — nessuno di questi fattori è nel modello) è un rischio concreto in asta, dove si legge veloce. La colonna **non va nel CSV** finché non porta informazione realmente distinta da `HistoricalRating`; il livello concettuale resta nell'architettura (schema sopra) per non dover ristrutturare quando arriverà `ProjectedRating`, ma non nell'output.

## 13. Portieri — dettagli specifici

La Performance del portiere è una combinazione esplicita e pesata di tre componenti percentile (stesso metodo deterministico della sezione 10), espressa direttamente in scala 0-1 (coerente con la sezione 10 e con la formula del rating in sezione 12):

```
FmPercentile_norm     = percentile(Fm) / 100
GsRatePercentile_norm = percentile(GoalsConcededRate) / 100
RpRatePercentile_norm = percentile(RpRate) / 100

Performance_Portiere = fm_weight × FmPercentile_norm
                      + gs_weight × (1 - GsRatePercentile_norm)
                      + rp_weight × RpRatePercentile_norm
```

dove `GoalsConcededRate = Gs / Pv` (percentile invertito: meno gol subiti per presenza = meglio, rispetto agli altri portieri della stessa stagione) e `RpRate = Rp / Pv`. Il risultato è in range [0, 1], coerente con la Performance degli altri ruoli.

**Coerenza sull'uso dei tassi**: anche `Rp` va normalizzato per presenza, per lo stesso motivo per cui lo si fa con `Gs` — un portiere con 35 presenze ha più occasioni di parare un rigore di uno con 15. Usare `Rp` assoluto qui e vietare `Gs` assoluto poche righe sotto sarebbe incoerente.

**Pesi di partenza** (configurabili in config.yaml):

| Componente | Peso |
|---|---|
| fm_weight | 0.75 |
| goals_conceded_weight | 0.20 |
| penalty_save_weight | 0.05 |

**Attenzione a Rp (rigori parati)**: è un segnale statisticamente rumoroso su due fronti — non essendo disponibile il numero di rigori affrontati, `RpRate` resta una proxy e non una vera percentuale di parate; e trattandosi di un evento raro e discreto (spesso 0, 1 o 2 in una stagione) il percentile è instabile, con una massa molto grande di portieri a `RpRate = 0` esatto, lo stesso problema di blocco di pareggi descritto nella sezione 11.2. Il peso di partenza è stato abbassato a 0.05 (rispetto a una prima ipotesi di 0.10) proprio per questo motivo. In fase di validazione, applicare la stessa logica di ablation della sezione 20: testare esplicitamente `penalty_save_weight = 0.00 / 0.05 / 0.10` e verificare se il contributo migliora davvero il potere predittivo del backtest o va rimosso.

Non usare Gs assoluti (un portiere con 35 presenze subirà naturalmente più gol di uno con 15).

**Limite dichiarato**: `GoalsConcededRate` è una proxy della performance del portiere **non corretta per la forza della difesa/squadra** (il contesto squadra è esplicitamente fuori scope in questa versione, sezione 1). Un portiere in una squadra con difesa debole avrà un GoalsConcededRate peggiore indipendentemente dal proprio merito individuale. Questo limite deve essere scritto nel README del progetto, per evitare di trattare questa metrica come una misura "pura" del portiere.

## 14. Difensori — dettagli specifici

- Fm, Mv, Pv come base;
- GoalRate e AssistRate normalizzati per presenza, con logica Bonus Profile (sezione 11);
- Amm, Esp, Au: tracciati nel dataset per riferimento, non pesati esplicitamente nel rating in questa versione (possibile raffinamento futuro).
- Mv_Weighted mantenuta separata per il Modificatore Difesa.

## 15. Centrocampisti — dettagli specifici

- Fm, Mv, Pv come base;
- GoalRate e AssistRate con Bonus Profile peso medio;
- Nessuna sotto-distinzione di ruolo in campo (mediano/mezzala/trequartista) in questa versione, essendo Rm escluso.

## 16. Attaccanti — dettagli specifici

- Fm, Mv, Pv come base;
- GoalRate e AssistRate con Bonus Profile peso alto e bidirezionale;
- Tracciare anche `R+/Pv` e `R-/Pv` (rigori realizzati/sbagliati per presenza) come indicatore di dipendenza dai rigori — campo informativo nel dataset finale, usato per un flag di rischio (sezione 18), non per modificare direttamente il Rating.

## 17. Modificatore Difesa (Mv)

In questa versione, `DefenseScore = Mv_Weighted` direttamente (nessuna trasformazione aggiuntiva). Non convertire in percentile: se il regolamento della lega applica il Modificatore Difesa su soglie assolute di Mv (es. "Mv ≥ 6" dà un bonus), un percentile relativo al gruppo sarebbe fuorviante e incompatibile con quel tipo di regola. Un'eventuale normalizzazione a percentile va considerata solo come colonna aggiuntiva opzionale in futuro, mai in sostituzione di `Mv_Weighted`.

Questo campo resta indipendente da `HistoricalRating`.

## 18. Trend e flag di rischio

### 18.1 Trend

Il Trend si calcola sulla `Performance_stagione` (scala 0-1) delle sole stagioni con `Pv >= 1` (righe `PLAYED`), usando **tutti** i punti disponibili e non soltanto il primo e l'ultimo:

```
Trend_Value = pendenza della regressione lineare OLS di Performance_stagione
              sull'indice progressivo di stagione (0, 1, 2, ...)
              → interpretabile come "variazione di Performance per stagione"
```

Con 2 stagioni la pendenza coincide con la semplice differenza; con 3 usa anche la stagione centrale, che una differenza prima↔ultima ignorerebbe (un giocatore 0.40 → 0.90 → 0.45 non è "in crescita").

**Definizione dell'indice — vincolo esplicito.** "Indice progressivo di stagione" è ambiguo quando ci sono stagioni mancanti tra due stagioni con `Pv >= 1`, e le due letture possibili non sono equivalenti: l'indice è la posizione della stagione nella finestra di train effettivamente in uso (le `train_window` stagioni più recenti dell'elenco `seasons` di config.yaml, sezione 24 — non l'intero elenco delle 10 disponibili, che serve solo a definire il pool da cui `train_window` estrae la finestra), **buchi inclusi**, non la posizione compattata tra le sole stagioni disponibili per quel giocatore. Esempio con `train_window = 3`, finestra 2023/24-2025/26: un giocatore con dati in 2023/24 e 2025/26 ma non in 2024/25 usa indici `[0, 2]`, non `[0, 1]`. Compattare gli indici raddoppierebbe la pendenza calcolata (una variazione avvenuta su due stagioni verrebbe letta come una variazione per singola stagione), contraddicendo la comparabilità che questo stesso campo dichiara di garantire più sotto.

**Casi non calcolabili — regola obbligatoria:**

| Stagioni con `Pv >= 1` | `Trend_Value` | `Trend_Label` |
|---|---|---|
| 0 | `null` | `null` |
| 1 | `null` | `N/D` (**non** "Stabile") |
| >= 2 | pendenza OLS | come da soglie sotto |

Un giocatore con una sola stagione non ha un trend pari a zero: **non ha un trend**. La formulazione "ultima − prima" restituiva `0` in questo caso, producendo l'etichetta "Stabile" su un giocatore di cui non si sa nulla di evolutivo — l'errore opposto a quello che il campo dovrebbe segnalare.

**Comparabilità**: essendo una pendenza *per stagione*, `Trend_Value` è confrontabile tra giocatori con storico di lunghezza diversa, cosa che la differenza grezza non era (un delta su due anni e un delta su un anno non sono la stessa quantità). Le soglie di `Trend_Label` in config.yaml vanno quindi lette come variazione annua di Performance.

Nel CSV finale esporre `Trend_Value`, l'etichetta `Trend_Label` e il numero di punti usati `Trend_Points`: una pendenza su 2 punti e una su 3 non meritano la stessa fiducia.

Classificazione indicativa per `Trend_Label` (soglie configurabili in config.yaml):
- ↑ Forte crescita
- ↗ Crescita
- → Stabile
- ↘ Calo
- ↓ Forte calo

Il Trend è una variabile informativa aggiuntiva, non modifica `HistoricalRating`.

### 18.2 Flag di rischio (informativi, non numerici nel rating)

Da esporre come colonne/note testuali nel dataset finale, per uso conversazionale durante l'asta:
- **Dipendenza da rigori** (attaccanti/centrocampisti con alto R+/Pv rispetto al totale gol);
- **Storico volatile** (alta varianza di Fm tra stagioni disponibili);
- **Poche presenze recenti** (Pv basso nell'ultima stagione anche se lo storico complessivo è PV_SUFFICIENTI).

## 19. Confidence Score

Non implementare direttamente una serie di soglie if/else arbitrarie (es. `if seasons==3 and pv>50: "Alta"`) senza prima aver verificato se quelle soglie hanno senso. Costruire prima uno **score continuo interno**, poi discretizzarlo in categoria solo per l'esposizione nel CSV finale.

**Formula di partenza per la v1** (semplice e trasparente, non un sotto-progetto a parte):

```
SeasonCoverage    = seasons_available / train_window                       # stagioni con Pv >= 1, range 0-1
AvailabilityScore = min(1, Pv_Totale / (train_window × reference_pv))      # range 0-1
StabilityScore    = 1 - min(1, sd(Performance_stagione) / sd_reference)    # range 0-1, definizione sotto

ConfidenceScore = 0.40 × SeasonCoverage + 0.40 × AvailabilityScore + 0.20 × StabilityScore
```

**Normalizzato su `train_window`, non su 3 (B14).** Con N=3 stagioni fisse, `SeasonCoverage` e `AvailabilityScore` erano normalizzati su costanti (3 e 90 = 3 × reference_pv). Con `train_window` parametrico (sezione 20.2, ora testato fino a 5) una costante fissa a 3 farebbe saturare la Confidence per finestre più lunghe e smetterebbe di discriminare. La normalizzazione usa quindi sempre `train_window`, il valore effettivamente configurato per il ranking in corso — che sia la finestra di produzione o quella di un fold di backtest.

**Definizione di `StabilityScore`.** `Fm_variance_normalizzata` non era una quantità definita, e senza specifica diventa una scelta arbitraria e non tracciata fatta in fase di implementazione. La definizione richiesta è:

```
StabilityScore = 1 - min(1, sd(Performance_stagione) / sd_reference)
        # deviazione standard di Performance_stagione (scala 0-1, sezione 10),
        # sulle sole stagioni con Pv >= 1
        # sd_reference = 0.20, configurabile (punto di saturazione: sd >= 0.20 → stabilità 0)
```

**Perché su `Performance_stagione` e non su `Fm`.** La formula precedente usava il coefficiente di variazione della Fm (`sd(Fm) / media(Fm)`) per ottenere una misura adimensionale, confrontabile tra giocatori con livelli di Fm diversi (un attaccante che oscilla tra 7.0 e 8.0 non è instabile quanto uno che oscilla tra 5.0 e 6.0 pur avendo la stessa varianza assoluta). Ma la Fm — come documentato in sezione 22 — può essere legittimamente **negativa o vicina a zero** (una presenza, voto basso, autogol ed espulsione). Con una media vicina a zero il coefficiente di variazione esplode o cambia segno in modo incontrollato, e `StabilityScore` può uscire dal range `[0, 1]` (es. media Fm = -0.5, sd = 1.0 → CV = -2.0 → `StabilityScore = 11`): il massimo di stabilità assegnato esattamente al caso più rumoroso, l'errore opposto a quello che il punteggio deve evitare. `Performance_stagione` risolve lo stesso problema di confrontabilità (è già adimensionale, scala 0-1 per costruzione, sezione 10) senza il rischio di dividere per una media vicina a zero: `sd(Performance_stagione)` da sola è sufficiente, senza bisogno del rapporto CV. `sd_reference` è il punto di saturazione e va calibrato osservando la distribuzione reale, non fissato a intuito.

**Caso `seasons_available < 2` — regola obbligatoria.** Con una sola stagione la deviazione standard è `0` o `NaN`. Se il codice la tratta come `0`, allora `StabilityScore = 1`: il **massimo punteggio di stabilità assegnato al giocatore di cui si sa meno**, esattamente il contrario di ciò che la Confidence deve esprimere. La regola è:

```
seasons_available < 2  →  StabilityScore non definito
                          → escluso dalla media, pesi rinormalizzati:
                            ConfidenceScore = (0.40 × SeasonCoverage
                                             + 0.40 × AvailabilityScore) / 0.80
```

La rinormalizzazione è preferibile a `StabilityScore = 0` perché non penalizza due volte lo stesso fenomeno: la scarsità di storico è già catturata da `SeasonCoverage` e `AvailabilityScore`, entrambi bassi in quel caso.

Verifica di sanità obbligatoria (sezione 22, **livello ERROR**): nessun giocatore con `seasons_available = 1` può risultare `Confidence = Alta`. Esempio con `train_window = 3`: il massimo raggiungibile è `(0.40 × 0.33 + 0.40 × 0.42) / 0.80 ≈ 0.38` → Bassa. Con `train_window` maggiore il caso `seasons_available = 1` diventa ancora più penalizzato (`SeasonCoverage` più basso), quindi la verifica resta valida a maggior ragione. **Il caso limite della griglia è `train_window = 2`** (sezione 20.2/20.5b, B8), non coperto dall'argomento sopra perché va nella direzione opposta: qui il massimo raggiungibile è `(0.40 × 0.5 + 0.40 × 38/60) / 0.80 ≈ 0.57` → **Media**, non Bassa. L'invariante "mai Alta" tiene comunque (0.57 < 0.75), ma il margine si restringe rispetto a `train_window` maggiori: la verifica va eseguita per ogni `train_window` effettivamente in uso, non assunta valida per estrapolazione dal solo caso `train_window = 3`.

Poi, discretizzazione per il CSV:

| ConfidenceScore | Confidence |
|---|---|
| ≥ 0.75 | Alta |
| ≥ 0.50 e < 0.75 | Media |
| < 0.50 | Bassa |

Questa è una **ipotesi di partenza dichiarata**, non un calcolo definitivo — sia i pesi (0.40/0.40/0.20) sia le soglie (0.75/0.50) vanno validati ed eventualmente ricalibrati con l'evidenza del backtest (sezione 20), esattamente come gli altri parametri del modello. L'obiettivo qui è avere qualcosa di semplice e trasparente da cui partire, non di ottimizzare la Confidence come se fosse essa stessa un modello separato da mesi di lavoro.

Il CSV finale espone **entrambi**: la categoria discreta `Confidence` per la lettura rapida e lo score continuo `ConfidenceScore` per ordinare i casi di frontiera. Un 0.74 e un 0.51 sono entrambi "Media" ma non sono la stessa cosa, e le soglie di questa versione sono dichiaratamente arbitrarie: nascondere il continuo significherebbe far sembrare netta una separazione che non lo è.

### 19.1 Confidence non entra mai nel calcolo del Rating (vincolo esplicito)

`Confidence` è un indicatore della robustezza informativa del rating, calcolato a valle e in parallelo a `HistoricalRating` — non entra in nessuna formula che produce `HistoricalRating`, `Performance`, `Reliability` o `BonusProfile`. In particolare, **non è ammessa alcuna forma di `Rating × Confidence`** o simili combinazioni moltiplicative: questo reintrodurrebbe esattamente il tipo di accoppiamento arbitrario tra dimensioni concettualmente distinte che il principio della sezione 7 vieta esplicitamente. Confidence serve a rispondere a "quanto mi fido di questo numero", non a modificare il numero stesso.

## 20. Validazione retrospettiva (il cuore del progetto, non una fase finale)

Questa fase non va trattata come un controllo a posteriori, ma come il criterio che decide se il modello merita di essere usato così com'è o va semplificato. Un modello che "sembra ragionevole" ma non prevede meglio di una baseline banale non ha valore aggiunto.

### 20.1 Universo di test — evitare il survivorship bias

**Problema**: se l'universo di test per un fold "train → target T" viene costruito usando solo i giocatori che hanno effettivamente ricevuto un voto in T (Pv≥1), si introduce informazione futura — si esclude implicitamente chi era in rosa e atteso in campo ma poi non ha giocato (infortuni, esclusioni, cessioni), rendendo il test artificialmente più pulito di quanto sarebbe stato in tempo reale.

**Soluzione (aggiornata — B4).** La versione precedente di questa sezione costruiva l'universo di test dalle quotazioni pre-stagione, per differenza rispetto alle statistiche consuntive. Quel meccanismo è lo stesso che generava la categoria `QUOTED_ONLY`, risultata vuota su tutte le 10 stagioni (sezione 4): il file statistiche contiene già, per costruzione, l'intero universo Serie A della stagione — incluse le righe `IN_SQUAD_NO_PLAY` a `Pv = 0` (sezione 4). **L'universo di test per il fold con target T è quindi direttamente `PLAYED ∪ IN_SQUAD_NO_PLAY` della stagione T**, letto dal file statistiche di T: non serve più passare dalle quotazioni per evitare il survivorship bias, perché il file statistiche non lo introduce.

Le quotazioni restano necessarie per altri due scopi, entrambi diversi dalla costruzione dell'universo: la baseline esterna `Qt.I`/`FVM` (sezione 20.4.3, B9) e il flag `left_mid_season` usato dalla Reliability (sezione 9.1bis) — quest'ultimo però è calcolato sulle stagioni di **train**, non sulla stagione target.

**Limite dichiarato, non misurabile su questa finestra (§2.6).** Il file statistiche di fine stagione include anche gli arrivi di gennaio: l'universo di test "chiunque sia stato in Serie A in un qualche momento della stagione T" non coincide esattamente con "chiunque fosse acquistabile all'asta di agosto di T" (è comunque molto meglio del bias che questa sezione vuole evitare, perché include comunque i quotati che non hanno mai giocato). La quota esatta di arrivi tardivi si misurerebbe contando, per ogni fold, gli Id dell'universo di test T assenti dalla quotazione pre-stagione di T — ma nessuna quotazione pre-stagione storica esiste (sezione 2.3): l'unico file pre-stagione è il 2026/27, che non è un fold (non ha statistiche). La misura **non è quindi calcolabile su nessuno dei 7 fold** di questa finestra, non "quando disponibile": il QC (sezione 22) deve dirlo esplicitamente, non promettere una misura che non arriva. Il controllo si attiva a partire dalla prima stagione archiviata secondo la nuova procedura a due snapshot (sezione 26).

**Coverage del test — da riportare sempre.** L'universo di test è `PLAYED ∪ IN_SQUAD_NO_PLAY` della stagione target, ma il rating è calcolabile solo per chi ha storico nelle stagioni di train: i `NEW` non ricevono un rating e restano necessariamente fuori dalle metriche. Il report deve quindi dichiarare, per ogni fold e **per ruolo**:

```
Coverage = (giocatori dell'universo Serie A target con HistoricalRating non nullo) / (universo Serie A target)
```

Se il coverage è, per esempio, 0.62, tutte le metriche della sezione 20.4 vanno lette come "valide sul 62% dei giocatori acquistabili". Non è un dettaglio metodologico: è la misura di quanto il ranking sia effettivamente utile in un'asta reale, dove il 38% restante va comunque comprato da qualcuno.

### 20.2 Backtest rolling, parametrico

Non implementare una funzione hard-coded "predici una singola stagione". Strutturare `validate.py` con parametri espliciti:

```
train_seasons: lista di stagioni usate per calcolare il rating
train_window: len(train_seasons) — parametro esso stesso (B8, sotto)
target_season: stagione su cui si valuta la previsione (statistiche consuntive; le quotazioni della stessa stagione
                servono solo alla baseline Qt.I/FVM e al QC arrivi tardivi, sezione 20.1/20.4.3)
```

**Rolling window a 7 target (B6, decisione presa).** Con 10 stagioni di statistiche (2016/17 → 2025/26) e `train_window = 3`, la finestra rolling produce 7 fold:

| # | Target | Finestra di train | Ruolo |
|---|---|---|---|
| 1 | 2019/20 | 2016/17-2018/19 | selezione |
| 2 | 2020/21 | 2017/18-2019/20 | selezione |
| 3 | 2021/22 | 2018/19-2020/21 | selezione |
| 4 | 2022/23 | 2019/20-2021/22 | selezione |
| 5 | 2023/24 | 2020/21-2022/23 | selezione |
| 6 | 2024/25 | 2021/22-2023/24 | selezione |
| 7 | **2025/26** | 2022/23-2024/25 | **lock-box** |

Il fold 7 (target 2025/26) è un **lock-box**: non va guardato durante la calibrazione, si apre una sola volta a configurazione congelata (sezione 20.5, B10). La sua finestra di training (2022/23-2024/25) è strutturalmente identica, per lunghezza e posizione relativa, a quella che userà la produzione 2026/27 (2023/24-2025/26 con `train_window = 3`): è per questo che la conferma avviene esattamente sullo scenario d'uso reale, non su un fold scelto a caso.

**Nessuna esclusione a priori di stagioni.** La stagione 2019/20 (stop di tre mesi, cinque sostituzioni dal giugno 2020) è inclusa come tutti gli altri target: **verifica eseguita, esito negativo** — la distribuzione dei `Pv` non mostra alcuno scalino nel 2019/20 né in corrispondenza del cambio regime sostituzioni (mediana, media e quota `Pv≥30` restano nel range delle altre 9 stagioni; l'unico scostamento è la quota di `Pv=0`, 22.4% contro ~18%, coerente con i 155 giocatori usciti in corsa quell'anno e già gestiti dal flag `left_mid_season`, sezione 9.1bis). Questo è un fatto verificato da riportare nella spec, non un controllo da ripetere: se un fold emerge come outlier nelle metriche per fold (sezione 20.5), lo si constata a posteriori dai numeri, non lo si esclude in anticipo su un'ipotesi che i dati non confermano.

**`train_window` è esso stesso un parametro da testare (B8).** Con N=3 la domanda "quante stagioni di storico servono" non era ponibile con potenza sufficiente. Con 10 stagioni si testa `train_window ∈ {2, 3, 4, 5}`, in griglia con `time_decay.base` perché i due parametri interagiscono direttamente (una finestra lunga con decadimento aggressivo equivale in pratica a una finestra corta). `train_window` maggiore riduce il numero di target disponibili (`target = 10 − train_window`, mantenendo comunque 2025/26 come lock-box finale e gli altri come selezione): il confronto fra finestre diverse va quindi fatto **sui soli target comuni a tutte le varianti testate**, altrimenti si confrontano medie calcolate su fold diversi.

Nota per l'aggiornamento annuale (collegamento con sezione 26): a differenza della pipeline di produzione (che ogni anno richiede solo il nuovo file statistiche + la nuova lista giocatori), la pipeline di *validazione* richiede in più, ogni anno, anche la nuova quotazione pre-stagione corrispondente. Sono due flussi di aggiornamento leggermente diversi, da tenere distinti nella documentazione.

### 20.3 Separare performance prediction e availability outcome (giocatori con Pv=0 nel target)

Un giocatore in rosa (`IN_SQUAD_NO_PLAY`, sezione 4) ma con `Pv = 0` nella stagione target ha `Fm = null`: non può entrare in un calcolo di correlazione o errore rispetto alla Fm, perché quella Fm semplicemente non esiste. Questo non significa scartarlo dal test — significa smettere di trattare "previsione della performance" e "il giocatore ha effettivamente giocato" come lo stesso tipo di errore. Il backtest calcola quindi due famiglie di metriche distinte:

**a) Performance outcome** (solo su giocatori con `Pv ≥ 1` nella stagione target, righe `PLAYED`): tutte le metriche della sezione 20.4 (Pearson, Spearman, MAE, precision@N) si calcolano esclusivamente su questo sottoinsieme osservabile.

**b) Availability outcome** (su tutto l'universo Serie A della stagione target, `PLAYED ∪ IN_SQUAD_NO_PLAY`, sezione 20.1): misura quanti dei giocatori con rating alto/nel top-N previsto hanno effettivamente prodotto una stagione osservabile. Definire:

```
Top-N Availability Rate = (giocatori nel Top-N previsto con Pv ≥ 1 nel target) / N
```

Esempio: Top 20 previsto → 18 con Pv > 0, 2 con Pv = 0 → Availability Rate = 90%. Questo è un test distinto e complementare: misura un limite noto e accettato del modello (non essendo previsti infortuni/esclusioni/cessioni nella sezione 1, un'Availability Rate imperfetta non è un fallimento del modello, ma va comunque misurata e riportata, perché è informazione rilevante per chi userà il ranking in un'asta).

### 20.4 Metriche da calcolare (su performance outcome, sezione 20.3a)

#### 20.4.0 Definizione del target — da fissare prima di qualunque metrica

`HistoricalRating` **non è una previsione di Fm**. È un composito di percentili calcolati dentro il ruolo, in scala 0-1 (esposta ×100). La Fm reale è una quantità in scala ~4-9 la cui distribuzione dipende fortemente dal ruolo. Confrontare direttamente le due cose produce due errori gravi:

- **MAE e Median AE diventano privi di significato.** L'errore medio tra un rating a 78 e una Fm a 6.8 misura una differenza di unità di misura, non un errore di previsione. Nella tabella di sintesi la baseline `Fm_Weighted` (che predice Fm in unità di Fm, errore ~0.4) risulterebbe migliore del modello (errore ~70) per ragioni puramente dimensionali, e il Test C darebbe un verdetto falso.
- **precision@N e Spearman cross-ruolo risultano distorti.** Il rating è deliberatamente role-neutral, mentre il top-N reale per Fm assoluta è dominato da attaccanti e trequartisti: si confronterebbe un ranking normalizzato con uno non normalizzato.

**Target A — performance condizionata (primario)**:

```
Target_A = percentile della Fm nella stagione target, calcolato dentro il ruolo R
           della stagione target, sui soli giocatori con Pv >= 1 nel target
           (stesso metodo deterministico della sezione 10, stesso min_pv_for_percentile)
           → scala 0-1
```

Con questa definizione tutte le quantità confrontate vivono in [0, 1], `MAE` e `Median AE` sono interpretabili come errore di posizionamento percentile, e il confronto con le baseline è equo.

**Target B — produzione totale, intero universo Serie A del target (secondario, obbligatorio).** Il Target A rimuove la disponibilità dal bersaglio per costruzione (è calcolato solo su chi ha effettivamente giocato, `Pv >= 1`). Questo rende strutturalmente sfavorevole qualunque test che, come il Test C (sezione 20.4.3), chieda al modello **completo** — che include Reliability al 25% di peso su tutti i ruoli (sezione 12) — di battere una baseline sul Target A: se Reliability ha poco potere predittivo sulla Fm condizionata (misura una cosa diversa, la disponibilità, sezione 7), includerla può solo peggiorare il punteggio su un bersaglio da cui la disponibilità è stata rimossa a monte. Serve quindi un secondo target che tratti la disponibilità come parte del valore, non come rumore da scartare:

```
Target_B = percentile di (Fm_target × Pv_target) nella stagione target, calcolato
           dentro il ruolo R della stagione target, sull'intero universo Serie A
           della stagione target (sezione 20.1: PLAYED ∪ IN_SQUAD_NO_PLAY, non solo
           su chi ha Pv >= 1)
           → scala 0-1; un giocatore con Pv_target = 0 riceve prodotto 0
             e si colloca in fondo alla distribuzione del proprio ruolo
```

Lo `0` qui è una **convenzione di target**, definita sul solo `Pv_target` per il solo scopo di calcolare `Target_B` — non va implementata come `Fm.fillna(0)` a monte: la regola "`Fm = null` non è `Fm = 0`" (sezione 4.0) resta valida per il dataset e per ogni altro calcolo (Performance, BonusProfile, ecc.); qui si sta solo definendo cosa vale il prodotto `Fm × Pv` quando `Pv = 0` rende il prodotto stesso banalmente zero, indipendentemente da cosa valga `Fm`.

Nota: `Fm × Pv` resta vietato come **feature** in ingresso al modello (sezione 7, principio cardine) — qui è usato come **target** di validazione, un ruolo diverso. È la proxy più diretta disponibile con questi dati di "quanti punti fantacalcio ha effettivamente prodotto il giocatore", che è ciò che conta in una lega reale. È una proxy imperfetta e va dichiarata come tale nel report: un giocatore assente viene sostituito da una riserva di panchina, quindi il costo reale di un `Pv = 0` non è "zero punti" ma "zero punti meno quello che avrebbe fatto la riserva" — Target B tende quindi a **sovrastimare** il valore della disponibilità, così come Target A lo **sottostima** azzerandolo. Il peso corretto di Reliability nella formula del rating si colloca tra le due stime, non a un estremo.

Il Test C (sezione 20.4.3) va quindi eseguito e riportato **su entrambi i target**, separatamente per ruolo, senza fondere i due risultati in un unico numero.

**Conversione obbligatoria delle baseline.** `Fm_Last_Season` e `Fm_Weighted` sono in unità di Fm e vanno portate nello stesso spazio prima del confronto: percentile per ruolo (calcolato sulle stagioni di train) della metrica di baseline. Una baseline non convertita non è una baseline più semplice, è una baseline in un'altra unità di misura. Le stesse tre baseline (sezione 20.4.3) si confrontano contro **entrambi** i target, senza ridefinirle: contro Target B, `Baseline 2` (`percentile(Pv_Last_Season)`) diventa naturalmente più competitiva, il che è informativo, non un errore da correggere.

**Tutte le metriche sono per ruolo.** Nessuna metrica di questa sezione va calcolata sull'universo indifferenziato (motivo in sezione 12.0bis). Il report riporta una riga per ruolo (P/D/C/A) e, opzionalmente, la media dei quattro valori come sintesi — mai una metrica calcolata su tutti i giocatori insieme.

#### 20.4.1 Test A — accuratezza generale (per ruolo)

- Pearson tra `HistoricalRatingRaw` previsto e percentile di Fm nella stagione target;
- Spearman (correlazione di rango): è la **metrica primaria**, perché il prodotto finale è un ordinamento;
- MAE e Median AE nello spazio percentile 0-1.

#### 20.4.2 Test B — accuratezza di classifica (per ruolo)

- `precision@N`, con N dimensionato sulla numerosità del ruolo e non identico per tutti: `N ∈ {5, 10, 20}` per i P, `N ∈ {10, 20, 30}` per D/C/A. Un `precision@30` sui portieri sarebbe calcolato su una popolazione di poche decine di giocatori e non misurerebbe nulla di utile.
- Da affiancare sempre alla Top-N Availability Rate (sezione 20.3b) per lo stesso N e lo stesso ruolo, così da distinguere "ho sbagliato la valutazione" da "il giocatore scelto non ha semplicemente giocato".

#### 20.4.3 Test C — baseline obbligatorie (bloccante)

Prima di valutare le componenti del modello, verificare che l'intero approccio batta baseline banali, tutte espresse nello spazio percentile definito in 20.4.0:

```
Baseline 0: percentile(Fm_Last_Season)    — ultima stagione disponibile, nessuna elaborazione
Baseline 1: percentile(Fm_Weighted)       — media pesata delle Fm storiche (decadimento, sez. 8)
Baseline 2: percentile(Pv_Last_Season)    — solo disponibilità recente, nessun dato di rendimento
Baseline 3: percentile(Qt.I_target)       — prezzo di mercato pre-stagione del target (B9, tutti i fold)
Baseline 4: percentile(FVM_target)        — valore di mercato Fantacalcio.it (B9, solo fold con target dal 2022/23 in poi:
                                             FVM non è popolato prima, sezione 2.3)
```

`Baseline 2` è aggiunta perché una parte importante del valore in asta è semplicemente "questo giocatore gioca". Se il modello completo non batte una baseline che ignora del tutto il rendimento, il problema non è la calibrazione dei pesi.

**Baseline 3/4 — il prezzo di mercato (B9, nuova).** `Qt.I` è ora disponibile per tutte le 11 stagioni di quotazioni ed è la baseline più severa e più onesta che si possa chiedere al modello: il mercato aveva già messo un prezzo sul giocatore prima dell'inizio della stagione target, senza vedere il resto della finestra di train usata dal modello. `FVM` (dal 2022/23) è un'ulteriore stima di mercato indipendente. Un modello che non batte `Qt.I` ha un problema che nessuna metrica interna (Baseline 0-2) avrebbe potuto rivelare, perché tutte le baseline interne condividono gli stessi dati di input del modello.

**`Qt.I` e `FVM` si leggono da `Tutti ∪ Ceduti` (sezione 2.3bis), mai dal solo `Tutti`.** L'universo di test è `stats = Tutti ⊎ Ceduti` (sezione 20.1): leggere la baseline dal solo `Tutti` la calcolerebbe su una popolazione ripulita di chi è uscito dalla Serie A in corsa — proprio il survivorship bias che la sezione 20.1 è stata riscritta per eliminare, reintrodotto dalla baseline. Il buco è evitabile del tutto: le righe `Ceduti` hanno `Qt.I` popolato al 100% su tutte le 10 stagioni. Il report per fold deve quindi riportare, accanto alle metriche, la **coverage della baseline** (quota dell'universo di test con `Qt.I`/`FVM` disponibile), e vale sempre la regola che **modello e baseline si confrontano sullo stesso sottoinsieme di Id** — mai su universi diversi.

**Criterio di superamento (bloccante, su Target A)**: il modello completo (Performance + Reliability + BonusProfile) deve battere `Fm_Weighted` su **Spearman e precision@20, in almeno 3 ruoli su 4**, misurato su **Target A** (sezione 20.4.0), **su ciascuno dei 6 fold di selezione** (sezione 20.2). Il criterio è per ruolo e non aggregato perché un modello che funziona bene su D e C e male su P e A non è un modello valido: in asta i ruoli si comprano tutti. Se il criterio non è soddisfatto su ciascuno dei fold di selezione, tutta la complessità aggiuntiva (percentili per ruolo, Reliability, BonusProfile) non sta dimostrando valore reale e va rivista — indipendentemente da quanto sia concettualmente ben giustificata. (Formulazione unificata su "ciascuno dei 6 fold di selezione", coerente con §20.7 e con la Fase 4 di §25 — non "la maggioranza": trattandosi del test che decide se il progetto ha senso così com'è, un'ambiguità sul denominatore non è tollerabile.) Il confronto con `Qt.I` (Baseline 3) è diagnostico e riportato nella stessa tabella, ma non sostituisce il gate su `Fm_Weighted`: sono domande diverse ("il modello batte una baseline interna più semplice" vs "il modello batte il mercato"). Il fold di lock-box (2025/26) **non entra in questo criterio**: ha il proprio criterio di fallimento indipendente, fissato prima di aprirlo (sezione 20.5, B10). Questo test decide se il progetto ha senso così com'è, non è un dettaglio opzionale.

**Stesso test, ripetuto su Target B (obbligatorio, non bloccante).** Eseguire lo stesso confronto contro le stesse baseline misurando su **Target B** (produzione totale, intero universo Serie A della stagione target, sezione 20.4.0), e riportarlo nella stessa tabella di sintesi, senza fonderlo con l'esito su Target A. Questo secondo risultato non sostituisce né allenta il criterio bloccante sopra — resta l'unico gate che decide se il progetto procede — ma cambia la lettura di un eventuale fallimento: **se il modello non supera il criterio su Target A ma lo supera nettamente su Target B**, e l'ablation (sezione 20.4.4, Model 2 vs Model 1) mostra che è proprio l'aggiunta di Reliability a peggiorare il punteggio su Target A, la conclusione corretta non è "il modello non funziona" ma "Reliability pesa più di quanto la sua capacità predittiva sulla Fm condizionata giustifichi, e va ridotta" — una revisione del peso, non un rigetto dell'impianto (sezione 7 e 20.6bis restano comunque il test diretto della Reliability). Se invece il modello fallisce su **entrambi** i target, il problema è nel modello, non nella scelta del bersaglio.

#### 20.4.4 Test D — ablation test (obbligatorio prima di considerare il modello definitivo)

Confrontare il potere predittivo di versioni progressive del modello, nella stessa tabella delle baseline:

```
Model 1: Performance only
Model 2: Performance + Reliability
Model 3: Performance + Reliability + BonusProfile          (modello base)
```

Se il passaggio 2 non migliora sensibilmente rispetto a 1, o il passaggio 3 non migliora rispetto a 2, il componente aggiuntivo non sta portando valore predittivo reale e va rivalutato (peso ridotto o rimosso), indipendentemente da quanto sembri sensato concettualmente.

**Varianti di modellazione**, ciascuna ottenuta cambiando **una sola** scelta rispetto al Model 3, per attribuire l'effetto senza ambiguità:

```
Model 3a: reliability.exclude_left_mid_season = false              (sezione 9.1bis, B3)
Model 3b: bonus_profile.goal_rate_metric = NonPenaltyGoalRate      (sezione 11.1)
Model 3c: bonus_profile.zero_handling = split per tutti i ruoli    (sezione 11.2, alternativa al default recenter)
Model 3d: bonus_profile.zero_handling = midrank per tutti i ruoli  (sezione 11.2, comportamento pre-correzione)
```

La griglia `bonus_weight ∈ {0, 0.10, 0.15, 0.25, 0.35}` per D/A (sezione 11.3, B12) è testata a parte, nell'ordine di calibrazione fisso della sezione 20.5, e non come ulteriore variante di questa tabella: a differenza di 3a-3d (una scelta binaria/discreta), è un parametro continuo con un default pre-registrato (0.15) da confermare o correggere, non un semplice on/off.

**Tabella di sintesi attesa** (una tabella **per ruolo, per ciascun target (A e B), per fold** — sezione 20.5 vieta di mediare fra fold, report finale sezione 20.7 — 8 tabelle per fold con 4 ruoli × 2 target, 56 in tutto su 7 fold, non una tabella con doppie colonne o mediata: mescolare le due unità di misura in una sola tabella reintrodurrebbe l'errore di scala che il Target A è stato introdotto per evitare, e mediare fra fold nasconderebbe la varianza che il criterio di accettazione di B10 deve poter vedere):

| Model | Pearson | Spearman | MAE | Median AE | Prec@10 | Prec@20 | Prec@30 | Avail@20 |
|---|---|---|---|---|---|---|---|---|
| Baseline 0: percentile(Fm_Last_Season) | | | | | | | | |
| Baseline 1: percentile(Fm_Weighted) | | | | | | | | |
| Baseline 2: percentile(Pv_Last_Season) | | | | | | | | |
| Baseline 3: percentile(Qt.I_target) | | | | | | | | |
| Baseline 4: percentile(FVM_target) — solo fold dal 2022/23 | | | | | | | | |
| Model 1: Performance | | | | | | | | |
| Model 2: + Reliability | | | | | | | | |
| Model 3: + BonusProfile (base) | | | | | | | | |
| Model 3a: exclude_left_mid_season = false (stagioni left_mid_season contate a 0 a peso pieno) | | | | | | | | |
| Model 3b: NonPenaltyGoalRate | | | | | | | | |
| Model 3c: zero_handling = split | | | | | | | | |
| Model 3d: zero_handling = midrank | | | | | | | | |

#### 20.4.5 Test E — calibrazione per fascia (bucket)

Spearman e precision@N misurano l'ordinamento, non se il numero stesso è calibrato: un rating al 90° percentile dovrebbe corrispondere, in media, a un giocatore che realmente performa vicino al 90° percentile nel target, non solo "più in alto di uno all'80°". Da riportare, per ruolo e per target (A e B):

```
Bucket predetto (HistoricalRatingRaw, in percentile di ruolo)  →  Target medio osservato nel bucket
90-100  →  ...
80-90   →  ...
70-80   →  ...
...
```

**Interpretazione — attenzione alla compressione fisiologica.** È normale osservare regressione verso la media (il bucket 90-100 mostra un target medio osservato inferiore a 90, es. ~75): con un solo anno di dati storici e stagioni successive rumorose, nessun modello onesto raggiunge una calibrazione 1:1. Non è di per sé un difetto da correggere. Ciò che segnala un problema reale è **la non-monotonicità**: se il target medio osservato in un bucket è inferiore a quello di un bucket sottostante (es. il bucket 70-80 supera l'80-90), il modello sta invertendo l'ordine tra fasce di rating in modo sistematico — un'informazione che Spearman aggregato può nascondere se l'inversione è localizzata in una fascia stretta.

### 20.5 Regola di selezione — lock-box, ordine di calibrazione, criterio di accettazione (B10)

Con 10 stagioni disponibili e 7 fold (6 di selezione + 1 lock-box, sezione 20.2) la potenza per calibrare è molto maggiore di quella disponibile con N=3, ma resta finita. Il vincolo della versione precedente di questa spec ("solo `time_decay.base` e `reference_pv` sono candidati a modifica") era la risposta corretta a 2 fold; con 6 va **rilassato, non rimosso**.

**Lock-box su 2025/26.** La selezione dei parametri usa esclusivamente i 6 fold con target 2019/20 → 2024/25 (sezione 20.2). Il fold con target 2025/26 **non viene mai guardato durante la calibrazione** — non nei test C/D, non nella sensitivity analysis — e si apre una sola volta, a configurazione congelata, come passo finale.

**Criterio di fallimento del lock-box (da fissare ora, prima di aprirlo).** Copia esatta del gate bloccante di §20.4.3, applicato al fold di conferma: se sul fold 2025/26 il modello configurato (Performance + Reliability + BonusProfile) non batte **Baseline 1 (`Fm_Weighted`)** su **Spearman e precision@20**, misurato su **Target A**, in almeno 3 ruoli su 4, la risposta **non è ritoccare un parametro**: è tornare alla struttura del modello (sezione 12 e oltre). Baseline 3 (`Qt.I`) resta **diagnostica e non bloccante** anche qui, per coerenza con §20.4.3 e con la sua natura di baseline esterna (sezione 20.4.3, R9 del documento di verifica) — il suo esito va comunque riportato nella sezione lock-box del report (sezione 20.7), ma non fa parte del criterio pass/fail. Fissarlo adesso, prima di vedere il risultato, è ciò che rende il lock-box qualcosa di diverso da un settimo fold di selezione qualunque.

**Regola di accettazione per un cambio di default.** Un default (di questa sezione o della 20.4.4) si cambia solo se il miglioramento è **concorde in segno in almeno 4 dei 6 fold di selezione** **e** vale in **almeno 3 dei 4 ruoli**. Le 24 combinazioni ruolo×fold di selezione sono trattate come quasi-repliche (non indipendenti, ma un controllo più severo di un singolo numero aggregato).

**Eccezione — passo 1 dell'ordine di calibrazione.** Al passo 1 (`train_window × time_decay.base`, sotto) i 6 fold di selezione non esistono ancora tutti: `train_window = 5` lascia solo i target comuni a tutte le finestre testate (2021/22 → 2024/25, tolto il lock-box), cioè **4 fold**, non 6 (sezione 20.2, B8). La regola "≥ 4 su 6" non è applicabile a un denominatore di 4. Il denominatore è quindi esplicito per passo:

| Passo | Fold disponibili | Regola di accordo |
|---|---|---|
| 1 — `train_window × time_decay.base` | 4 fold comuni (target 2021/22-2024/25) | concorde in segno in ≥ 3 dei 4 fold **e** in ≥ 3 dei 4 ruoli |
| 2-6 — tutti gli altri parametri | 6 fold di selezione (target 2019/20-2024/25) | concorde in segno in ≥ 4 dei 6 fold **e** in ≥ 3 dei 4 ruoli |

**Metriche sempre per fold e per ruolo.** La mediana può essere riportata, ma **solo affiancata** ai valori per singolo fold e a una misura di dispersione (es. IQR o min-max fra i 6 fold di selezione). Fra due configurazioni con mediana simile va preferita quella con dispersione minore fra fold: un parametro che vince "in media" ma con varianza alta fra fold è meno affidabile di uno che vince ovunque per un margine più piccolo.

**Ordine fisso di calibrazione**, dal più strutturale al meno — un parametro si fissa e non si ritocca dopo aver visto i risultati dei successivi, per non introdurre overfitting sequenziale mascherato da "abbiamo già deciso quello":

1. `train_window × time_decay.base` (griglia congiunta, sezione 20.2/B8: `train_window ∈ {2,3,4,5}` × `time_decay.base ∈ {1.3, 1.5, 2.0, 2.5}`, sui soli target comuni a tutte le finestre testate);
2. `reliability.function × reference_pv` (sqrt/linear × 25/30/34, validati esclusivamente tramite il test diretto della sezione 20.6bis, non tramite `HistoricalRating`);
3. `bonus_weight` (griglia B12, sezione 11.3: `{0, 0.10, 0.15, 0.25, 0.35}` per D e A, tenendo fisso il rapporto Performance:Reliability, sezione 20.5a);
4. `min_pv_for_percentile` (performance e bonus_profile, indipendenti, sezione 20.5c);
5. `penalty_save_weight` (goalkeeping, sezione 20.5c);
6. pesi della formula di rating (redistribuzione fine Performance/Reliability/BonusProfile per ruolo, sezione 20.5a).

#### 20.5a Pesi della formula di rating

Isolare il peso del BonusProfile stesso, tenendo fisso il rapporto tra Performance e Reliability (sezione 11.3, B12):

```
bonus_weight: 0, 0.10, 0.15 (default pre-registrato), 0.25, 0.35   — per D e A
```

`0` è l'ablation (BonusProfile serve?), gli altri valori rispondono a "quanto pesa?" — con 6 fold di selezione la griglia ha potenza sufficiente per un solo test invece di due, cosa che con 2 fold non sarebbe stata difendibile. Con `bonus_weight = 0.15` (default), Performance e Reliability per D/A diventano **0.60 : 0.25** (rapporto tenuto costante, allineate a C, sezione 12) — non una riscalatura proporzionale del vecchio 55:20, un'aritmetica che non torna (sezione 11.3). La griglia di `bonus_weight` va quindi esplorata a rapporto Performance:Reliability fissato a 0.60:0.25: variazioni indipendenti di redistribuzione Performance↔Reliability a `bonus_weight` fisso, se necessarie, si esplorano solo dopo aver fissato `bonus_weight` (punto 6 dell'ordine di calibrazione).

#### 20.5b Parametri strutturali del modello temporale

```
train_window:               2, 3 (base), 4, 5                    (sezione 20.2, B8 — in griglia con time_decay.base)
time_decay.base:            1.3, 1.5, 2.0, 2.5
reliability.reference_pv:   25, 30 (base), 34
```

`time_decay.base = 2` assegna il 57% del peso complessivo a una singola stagione; con base 1.5 i pesi diventano ≈ 26/33/41 e con base 1.3 ≈ 30/33/37. La differenza tra "il modello guarda soprattutto l'ultimo anno" e "il modello media più stagioni" è una scelta di modellazione sostanziale, non un dettaglio di configurazione, e va decisa dai dati — insieme a `train_window`, con cui interagisce direttamente.

#### 20.5c Filtri sul campione

```
performance.min_pv_for_percentile:    1, 3, 5
bonus_profile.min_pv_for_percentile:  1, 3, 5   (indipendente dal precedente)
goalkeeping.penalty_save_weight:      0.00, 0.05, 0.10
```

Per ciascuna variazione, calcolare:
- Spearman e precision@20 rispetto al target, per fold e per ruolo (per capire se la variazione migliora o peggiora, sezione 20.5 sopra);
- **rank correlation tra la configurazione base e la configurazione variata** (`Spearman(Rank_base, Rank_variazione)`) — più intuitiva delle sole metriche predittive per capire quanto il ranking finale "si muove" al variare dei pesi. Un valore alto (es. 0.95+) indica un modello robusto; un valore basso indica che il ranking è instabile e sensibile a scelte arbitrarie dei pesi, cosa da segnalare esplicitamente prima di usarlo per un'asta reale.

Questa fase è importante ma non bloccante quanto i test C/D: va eseguita dopo aver verificato che il modello base supera le baseline sui fold di selezione, non prima.

**Il paragrafo del `validation_report.md` che dichiara i limiti** resta obbligatorio, ma cambia natura: da "non ho potenza statistica per calibrare quasi nulla" (versione a 2 fold) a "ecco l'ordine in cui ho calibrato, su quali dei 6 fold di selezione, con quale criterio di accettazione, cosa ho lasciato al default pre-registrato per mancanza di segnale concorde, e l'esito — pass/fail — del lock-box aperto una sola volta alla fine".

### 20.6 Nota informativa: correlazione tra Performance e Reliability

Aggiungere nel report, per ciascun ruolo, il calcolo di `corr(Performance, Reliability)`. Le due dimensioni sono concettualmente separate (sezione 7), ma nella realtà è plausibile che siano correlate (i giocatori più forti tendono a giocare di più, quelli fragili meno). Non è un errore da correggere, ma un'informazione da riportare: una correlazione molto alta (es. > 0.85) significa che il modello sta dando peso, indirettamente, due volte a un fenomeno in parte sovrapposto — utile saperlo per interpretare correttamente i pesi scelti, senza che questo richieda necessariamente un intervento.

**Aggiungere anche `corr(Performance, BonusProfile)` per ruolo (D/C/A).** È il test più diretto per il rischio di doppio conteggio della sezione 11.4: la Fm che alimenta Performance già incorpora gol e assist, quindi una correlazione alta con BonusProfile (che li ripesa separatamente) è evidenza quantitativa diretta — più diretta del confronto sull'ordinamento della sezione 11.4 — che il "modulatore" sta in parte ripetendo lo stesso segnale, e va letta insieme alla nota di calibrazione della sezione 11.3.

### 20.6bis Test diretto della Reliability (non solo indiretto)

Oggi la Reliability sarebbe validata soltanto di rimbalzo, tramite l'ablation sulla previsione di Fm. Ma il suo compito dichiarato non è predire il rendimento: è predire la **disponibilità**. Va quindi misurata su quello, direttamente:

```
Spearman(Reliability_train, Pv_target)          per ruolo, su performance outcome
Spearman(Reliability_train, [Pv_target >= 1])   per ruolo, su TUTTO l'universo Serie A del target
```

Il secondo test si calcola sull'intero universo Serie A della stagione target (sezione 20.1: `PLAYED ∪ IN_SQUAD_NO_PLAY`), non sul solo performance outcome: escludere i `Pv = 0` da un test sulla disponibilità significherebbe rimuovere esattamente i casi che il test deve spiegare.

**Baseline obbligatoria**: `Spearman(Pv_Last_Season, Pv_target)`. Se la Reliability elaborata (radice, saturazione a `reference_pv`, media pesata su `train_window` stagioni, stagioni a zero identificate dalle righe `IN_SQUAD_NO_PLAY`) non batte il semplice numero di presenze dell'ultima stagione, la sua costruzione è sovrastruttura e va semplificata.

Questo test è anche la verifica quantitativa della correzione della sezione 9.1bis: eseguirlo con `reliability.exclude_left_mid_season` a `true` e a `false` e riportare entrambi i valori. Se la correzione non migliora nulla su questa metrica, il problema conoscitivo che risolve resta reale ma il peso della Reliability nel rating va rivisto al ribasso.

### 20.7 Output della validazione

Un report (`validation_report.md`, con eventuale export CSV delle tabelle) contenente tutte le metriche delle sezioni 20.1 e 20.3-20.6bis, per ciascuno dei 7 fold eseguiti (6 di selezione + 1 lock-box, sezione 20.2), **riportato per fold separatamente (mai mediato tra fold, sezione 20.5)** e **con una tabella per ruolo per ciascun target A e B** (sezione 20.4.0), da consultare prima di considerare definitivi i parametri di config.yaml. Il report deve aprirsi con: coverage per ruolo (sezione 20.1), esito del Test C bloccante ruolo per ruolo su Target A su ciascuno dei 6 fold di selezione **e** l'esito informativo su Target B affiancato, e in caso di mancato superamento del criterio bloccante su un fold una riga esplicita che lo dichiari — un report che seppellisce un fallimento del Test C dentro una tabella è inutile. Segue, separata e ben visibile, la sezione dedicata al **lock-box**: la configurazione congelata usata, l'esito pass/fail rispetto al criterio fissato in anticipo (sezione 20.5), e — solo in caso di fail — la conclusione che ne segue (rivedere la struttura, non ritoccare un parametro). Il report chiude con il paragrafo sull'ordine di calibrazione e i parametri effettivamente calibrati vs. lasciati al default pre-registrato (sezione 20.5). Questa fase serve anche a calibrare empiricamente i pesi delle sezioni 8, 9, 10, 11, 12, 13, 19 — che partono come ipotesi dichiarate, non verità.

## 21. Output finale

**Un solo file CSV** (`ranking_dataset.csv`), pensato per essere:
- riaperto/filtrato in un foglio di calcolo;
- caricato in una conversazione con Claude durante l'asta per interrogazioni live (confronti, budget, alternative).

Colonne minime richieste:

| Campo | Descrizione |
|---|---|
| Rank | Posizione nel ranking generale (per HistoricalRatingRaw decrescente, tie-break sezione 12.0bis); null se Categoria=NEW |
| Rank_Role | Posizione nel ranking all'interno del proprio ruolo R; null se Categoria=NEW |
| Id | ID Fantacalcio |
| Nome | Nome giocatore |
| R | Ruolo Classic della lista 2026/27, quello usato per i pesi della formula (sezione 4.1) |
| R_Storico | Sequenza dei ruoli per stagione (es. `C/C/A`); popolato solo se differisce da R |
| Squadra_2026_27 | Squadra stagione corrente (se disponibile) |
| Categoria | PV_SUFFICIENTI / LIMITED_HISTORY / NEW |
| Seasons_Available | Numero di stagioni con `Pv >= 1` (righe `PLAYED`) per il giocatore, nella finestra di train (0-train_window) |
| Seasons_In_Squad | Numero di stagioni con una riga nel file statistiche (`PLAYED` o `IN_SQUAD_NO_PLAY`), nella finestra di train (0-train_window). Se > Seasons_Available esistono stagioni in Serie A senza presenze, che entrano nella Reliability secondo la regola della sezione 9.1bis (a `0` se rimasto in rosa tutta la stagione, escluse se `left_mid_season`) |
| Seasons_Quoted | Numero di stagioni in cui il giocatore compare nel foglio `quotazioni!Tutti` (roster di fine stagione, sezione 2.3) — **non** `Tutti ∪ Ceduti` — nella finestra di train (0-train_window). Per costruzione esclude i `left_mid_season`: `Seasons_Quoted < Seasons_In_Squad` per loro, sistematicamente. Non entra nella Reliability (quel ruolo è di `Seasons_In_Squad`, sezione 6/9.1bis) ed è puramente informativo |
| HistoricalRating | Rating storico finale (= HistoricalRatingRaw × 100, sezione 12). Range per ruolo: P 0→100, D/C/A -15→100. **Non è una scala 0-100**: i valori negativi sono validi. Null se NEW |
| Confidence | Alta / Media / Bassa (sezione 19) |
| ConfidenceScore | Score continuo 0-1 da cui deriva Confidence. Esposto e non solo in debug: le soglie 0.75/0.50 sono arbitrarie in v1 e il continuo permette di ordinare i casi di frontiera |
| Performance | Performance storica pesata, scala 0-1 |
| Reliability | Reliability score, scala 0-1 (vedi nota terminologica sezione 7) |
| BonusProfile | Score bonus/malus per ruolo, normalizzato -1/+1 (sezione 11.2) |
| DefenseScore | = Mv_Weighted, per Modificatore Difesa |
| Trend_Value | Pendenza OLS di Performance per stagione (sezione 18.1); null se meno di 2 stagioni con `Pv >= 1` |
| Trend_Label | Etichetta/simbolo andamento; `N/D` se Trend_Value è null |
| Trend_Points | Numero di stagioni usate per calcolare Trend_Value (da 2 a train_window) |
| Mv_Weighted | Mv storica pesata (decadimento esponenziale). Non è una "Mv media" in senso tradizionale, è una feature pesata a fini di modello — vedi nota 21.1 |
| Fm_Weighted | Fm storica pesata (decadimento esponenziale) |
| Pv_Weighted | Pv storiche pesate (decadimento esponenziale). **Non rappresenta una stima di partite giocate** — è una feature temporale derivata, usata solo a fini informativi/debug, non entra nel calcolo di Reliability (che usa il Pv di ogni singola stagione, sezione 9.1) |
| Pv_Totale | Somma reale di Pv sulle stagioni della finestra di train (usato per la categoria, sezione 6) |
| Pv_Last_Season | Pv dell'ultima stagione disponibile per il giocatore (dato grezzo, non pesato) |
| Fm_Last_Season | Fm dell'ultima stagione disponibile (dato grezzo, coincide con Baseline 0 della sezione 20.4) |
| Mv_Last_Season | Mv dell'ultima stagione disponibile (dato grezzo) |
| Gf_Rate | Gol per presenza, rigori inclusi; media pesata dei rate stagionali (vedi nota 21.2 sul metodo) |
| NonPenaltyGf_Rate | Gol su azione per presenza, `(Gf - R+) / Pv`; media pesata (sezione 11.1) |
| Ass_Rate | Assist per presenza, media pesata dei rate stagionali (vedi nota 21.2) |
| RigoriDipendenza | Flag/valore su dipendenza da rigori (attaccanti/centrocampisti) |
| RoleMedianRating | Mediana di HistoricalRating del proprio ruolo, su tutti i giocatori con rating. Popolata per tutti, NEW inclusi; **non è un rating personale** (sezione 21.3) |
| Qt.I_2026_27 | Prezzo iniziale dalla quotazione 2026/27 (sezione 2.3), per riferimento in asta — non entra in nessun calcolo del rating |
| Squadra storiche (una colonna per stagione della finestra di train) | Storico squadre, per riferimento |
| Note | Testo libero per i casi che richiedono contesto (es. `nessuno storico Serie A nella finestra di train`) |

Nota: `Rating_Band` (es. Elite/A/B/C/D) è volutamente escluso da questa versione — è una classificazione decisionale che va introdotta solo dopo aver validato che `HistoricalRating` è ben calibrato (sezione 20).

**Ordinamento di default del file**: per `R`, poi `Rank_Role` crescente. Non per `Rank` globale, che non è un confronto valido tra ruoli diversi (sezione 12.0bis).

### 21.1 Chiarimento su Pv_Weighted vs Pv_Totale

Da documentare esplicitamente nel README, perché sono due numeri che possono sembrare in contraddizione a chi legge il CSV senza contesto (es. `Pv_Totale = 70` ma `Pv_Weighted = 26.8`): *"Pv_Weighted non è una stima di partite giocate; è una feature temporale pesata (stesso decadimento esponenziale delle altre metriche storiche) usata a fini di analisi/debug. Pv_Totale è la somma reale e non pesata delle presenze disponibili, usata per determinare la categoria PV_SUFFICIENTI/LIMITED_HISTORY/NEW."*

### 21.2 Chiarimento sul metodo di aggregazione di Gf_Rate e Ass_Rate

Esistono due metodi matematicamente diversi per aggregare un tasso su più stagioni, e vanno tenuti distinti esplicitamente:

```
Metodo 1 (usato in questa spec): media pesata dei rate stagionali
WeightedGoalRate = Σ (peso_stagione_i × GoalRate_i)     dove GoalRate_i = Gf_i / Pv_i

Metodo 2 (NON usato): rate aggregato sul totale
GoalRate_aggregato = Σ Gf_i / Σ Pv_i
```

Il **Metodo 1** è quello richiesto, per coerenza con il resto del modello temporale (stessi pesi di decadimento esponenziale usati per Performance, Reliability, Mv_Weighted, Fm_Weighted — sezione 8). Il Metodo 2 darebbe un risultato numericamente diverso e non andrebbe usato al suo posto, né scambiato con esso in fase di implementazione.

Lo stesso Metodo 1 si applica a `NonPenaltyGf_Rate` (sezione 11.1). E in entrambi i casi valgono le sole righe `PLAYED`: una stagione a `Pv = 0` non contribuisce con un rate pari a zero, non contribuisce affatto (sezioni 4 e 8).

Non serve un file Excel separato per la vista sintetica in questa versione — un CSV unico, ben ordinabile per HistoricalRating decrescente e filtrabile per R, è sufficiente sia per la consultazione manuale sia per l'uso conversazionale.

### 21.3 Giocatori NEW — cosa fare del vuoto

I `NEW` non sono un caso marginale: neopromosse e acquisti dall'estero possono rappresentare una quota rilevante dei giocatori acquistabili, e in asta una cella vuota è indistinguibile da un giocatore scarso. Questa versione non produce un rating per loro (nessun dato, sezione 6) e non lo inventa, ma espone l'informazione in modo utilizzabile:

| Campo | Contenuto per un NEW |
|---|---|
| `Categoria` | `NEW` |
| `HistoricalRating`, `Rank`, `Rank_Role` | `null` — mai un valore convenzionale, mai messi in coda alla classifica |
| `Seasons_In_Squad` | può essere > 0: era in rosa in passato e mai impiegato, informazione tutt'altro che neutra |
| `Reliability` | calcolabile se `Seasons_In_Squad > 0` (sarà molto bassa); `null` se mai stato in rosa nella finestra di train, **oppure** se tutte le stagioni in rosa sono `IN_SQUAD_NO_PLAY` con `left_mid_season = true` — insieme di ripesatura vuoto, sezione 8/9.1bis |
| `RoleMedianRating` | mediana di ruolo, come termine di paragone |
| `Note` | es. `nessuno storico Serie A nella finestra di train` |

`RoleMedianRating` serve a un solo scopo: dare un punto di riferimento in asta ("questo sconosciuto va confrontato con un ruolo la cui mediana è 48"), senza attribuire al giocatore un valore che nessun dato supporta. Non entra in nessun calcolo, non è un'imputazione, e non va usata per ordinare i NEW tra loro.

La quota di NEW sull'universo 2026/27, per ruolo, va misurata e riportata (sezione 22): è la misura diretta della parte dell'asta che questo ranking non copre, e va conosciuta *prima* dell'asta, non scoperta durante.

## 22. Controlli di qualità

Il file di log (`qc_log.csv`) deve avere struttura tabellare con livello di severità esplicito, non un semplice elenco testuale:

| Colonna | Descrizione |
|---|---|
| severity | ERROR / WARNING / INFO |
| check | Nome del controllo (es. `duplicate_id`, `name_change`, `new_player`) |
| Id | Id coinvolto |
| season | Stagione coinvolta |
| value | Valore riscontrato |
| expected | Valore atteso (se applicabile) |
| message | Descrizione leggibile |

Esempio:
```
ERROR   | duplicate_id  | 12345 | 2025/26 | 2 | 1 | Id duplicato nel file sorgente
WARNING | name_change   | 12345 | 2024/25 | Marco Rossi | Mario Rossi | nome diverso per stesso Id
INFO    | new_player    | 99999 | 2026/27 | -  | -  | nessuno storico disponibile
```

Prima di considerare valido il dataset, eseguire:

**Dati**
- nessun Id duplicato all'interno dello stesso file/stagione (ERROR);
- nessun Pv negativo (ERROR);
- `Mv` fuori dall'intervallo 0-10 (ERROR);
- `Fm` fuori dall'intervallo -10 / +20 (WARNING), fuori da -30 / +30 (ERROR). **La Fm può essere negativa**: un giocatore con una sola presenza, voto 4, autogol ed espulsione ha una Fm negativa perfettamente legittima. Un controllo `Fm ∈ [0, 10] → ERROR` scarterebbe dati veri, ed è un errore da non commettere;
- nessun ruolo R mancante per giocatori con storico (ERROR);
- nessun campo numerico interpretato come stringa (ERROR);
- coerenza rigori: `Rc = R+ + R-` per ogni riga (WARNING se non torna — indica un problema nel file sorgente, non nella pipeline);
- `Gf >= R+` per ogni riga (ERROR: i gol su rigore sono un sottoinsieme dei gol fatti, e altrimenti `NonPenaltyGoalRate` diventa negativo);
- `Gs > 0` su giocatori con `R ≠ P` (WARNING: nel dataset i gol subiti riguardano i portieri; un valore popolato altrove va verificato prima di usarlo).

**Righe `IN_SQUAD_NO_PLAY` e `left_mid_season` (sezione 4)**
- ogni riga `IN_SQUAD_NO_PLAY` ha `Pv = 0` e `Fm`/`Mv` a null, mai a zero (ERROR);
- numero di righe `IN_SQUAD_NO_PLAY` generate per stagione (INFO): un valore fuori dal range storico atteso (107-153 su 10 stagioni verificate) segnala un problema nella lettura del foglio `Tutti` delle statistiche;
- **controllo bloccante sull'identità `stats`/quotazioni (ERROR)**: per ogni stagione, `quotazioni_Tutti ∩ quotazioni_Ceduti = ∅`, `quotazioni_Tutti ∪ quotazioni_Ceduti = stats` e quindi `stats \ quotazioni_Tutti == quotazioni_Ceduti` (sezione 2.3bis). È il presidio più forte contro un file quotazioni della versione sbagliata (es. pre-stagione al posto di fine stagione, sezione 2.3) — va eseguito prima di calcolare `left_mid_season`, non dopo;
- quota di righe `IN_SQUAD_NO_PLAY` con `left_mid_season = true` per stagione (INFO): il range storico atteso è 55-75% dei `Pv = 0` — un valore molto fuori da quel range segnala un problema nella lettura del foglio `Ceduti` (sezione 4.0bis/2.3bis), non un dato reale;
- Id presenti nelle statistiche di una stagione ma **assenti** dalla quotazione della stessa stagione, esclusi quelli già marcati `left_mid_season` (WARNING): può indicare un problema di versione del file quotazioni, non necessariamente un errore;
- conteggio dei casi con insieme di ripesatura vuoto per Performance o per Reliability (sezione 8, 9.1bis, 12) — un giocatore le cui stagioni di train sono tutte escluse dalla famiglia in questione (INFO): questi casi ricevono componente `null` e `HistoricalRating = null` con `Note` esplicita (sezione 12), non uno zero silenzioso.

**Universo di test / arrivi tardivi (sezione 20.1, B4)**
- la quota di arrivi tardivi non è misurabile su nessuno dei 7 fold di questa finestra: nessuna quotazione pre-stagione storica esiste (l'unica è il 2026/27, che non è un fold). Il controllo si attiva a partire dalla prima stagione archiviata secondo la nuova procedura a due snapshot (sezione 26/R7); fino ad allora il qc_log riporta una riga INFO che dichiara esplicitamente il limite come non misurato, non una metrica vuota o a zero.

**Ruoli (sezione 4.1)**
- cambio di `R` tra stagioni per lo stesso Id (WARNING `role_change`, **obbligatorio nel report**: 74/2306 Id, 3.2%, cambiano ruolo su 10 stagioni — non un caso raro da poter ignorare, sezione 4.1);
- cambio di `R` da o verso `P` (WARNING `role_change_gk`, da elencare per controllo manuale) — insieme verificato **vuoto** su tutte e 10 le stagioni (sezione 4.1): una riga non vuota segnala più probabilmente un errore nei dati sorgente che un caso reale;
- `R` della lista 2026/27 diverso da `R` dell'ultima stagione disponibile (INFO: frequente e legittimo, ma utile da sapere in asta).

**Distribuzioni delle feature (bloccanti)**
- per ogni ruolo e stagione: quota di giocatori nel blocco a `rate = 0` e mediana di `BonusProfile_normalized`. Se la quota supera `bonus_profile.max_zero_share` o la mediana si discosta da 0 più di 0.10 → ERROR: il modulatore non è centrato (sezione 11.2);
- `Performance ∈ [0, 1]`, `Reliability ∈ [0, 1]`, `BonusProfile ∈ [-1, +1]`, `ConfidenceScore ∈ [0, 1]` su ogni riga (ERROR se fuori range: tipicamente una divisione per 100 dimenticata, sezione 10 — o, per `ConfidenceScore`, un caso limite non gestito in sezione 19);
- nessun giocatore con `Seasons_Available = 1` e `Confidence = Alta` (ERROR, sezione 19);
- nessun giocatore con `Seasons_Available = 1` e `Trend_Label` diverso da `N/D` (ERROR, sezione 18.1);
- quota di giocatori con almeno una stagione a `Reliability_stagione = 0` (righe `IN_SQUAD_NO_PLAY` con `left_mid_season = false`, sezione 9.1bis) (INFO, con elenco da verificare a campione).

**Coerenza Id ↔ Nome**
- stesso Id con Nome che cambia tra stagioni (WARNING — puà rivelare un errore nel dataset sorgente, non necessariamente un problema, ma va segnalato; 24 Id nella finestra verificata hanno grafie multiple, tutte varianti tipografiche);
- stesso Nome associato a più Id diversi (WARNING, stesso motivo — 4 casi noti nella finestra verificata: Vergara, Gori, Buksa, Ndiaye, sezione 3.1). Questo controllo è il presidio diretto contro un join per nome mai fatto per errore.

**Join**
- quanti giocatori storici sono presenti nella lista 2026/27 (INFO);
- quanti giocatori 2026/27 risultano NEW, senza storico (INFO);
- quanti Id presenti nei file storici mostrano anomalie di identità/continuità tra stagioni, es. lo stesso Id con Nome diverso o viceversa (WARNING — collegato al controllo di coerenza Id↔Nome sopra, non una categoria QC a sé).

**Ranking**
- distribuzione di HistoricalRating per ruolo (nessun ruolo con valori anomali);
- top 20 **per ruolo**, controllo di sensatezza manuale (un top 20 globale non è un controllo valido, sezione 12.0bis);
- giocatori con Confidence bassa ma HistoricalRating alto (segnalare esplicitamente: sono i casi da guardare con più attenzione durante l'asta);
- quota di `NEW` sull'universo 2026/27, per ruolo (INFO): misura la parte dell'asta che il ranking non copre (sezione 21.3).

## 23. Struttura del progetto

```
project/
│
├── data/
│   ├── stats/
│   │   ├── Statistiche_Fantacalcio_Stagione_2016_17.xlsx
│   │   ├── ...
│   │   └── Statistiche_Fantacalcio_Stagione_2025_26.xlsx   (10 file)
│   ├── player_lists/
│   │   ├── Quotazioni_Fantacalcio_Stagione_2016_17.xlsx
│   │   ├── ...
│   │   └── Quotazioni_Fantacalcio_Stagione_2026_27.xlsx    (11 file — l'ultimo è anche
│   │                                                          la lista giocatori corrente, sez. 2.2)
│   ├── historical.csv          # dataset long, tutte le stagioni disponibili (sezione 4)
│   ├── merged.csv              # dopo join con la lista corrente
│   └── qc_log.csv              # controlli qualità/join (sezione 22)
│
├── output/
│   ├── ranking_dataset.csv     # output finale unico (sezione 21)
│   └── validation_report.md    # metriche di backtest, per fold e per ruolo (sezione 20.7)
│
├── src/
│   ├── load_data.py            # statistiche + quotazioni
│   ├── build_universe.py       # righe PLAYED/IN_SQUAD_NO_PLAY, left_mid_season, join, categorie (sezioni 4, 6)
│   ├── merge_seasons.py
│   ├── calculate_features.py   # performance, reliability, bonus profile, goalkeeping
│   ├── calculate_rating.py
│   ├── validate.py             # validazione retrospettiva rolling, sezione 20
│   └── export_ranking.py
│
├── config.yaml                 # tutti i pesi/soglie configurabili
└── README.md                   # limiti dichiarati: sezioni 7, 9.1bis, 12.0bis, 13, 17, 20.1, 21.3
```

## 24. Esempio config.yaml (indicativo, non esaustivo)

```yaml
seasons:                           # tutte le stagioni disponibili; train_window seleziona la finestra
  - "2016/17"
  - "2017/18"
  - "2018/19"
  - "2019/20"
  - "2020/21"
  - "2021/22"
  - "2022/23"
  - "2023/24"
  - "2024/25"
  - "2025/26"

train_window: 3                    # numero di stagioni usate per il rating (sez. 8, 20.2) — parametro, non
                                    # costante; da testare 2/3/4/5 in griglia con time_decay.base (sez. 20.5b, B8);
                                    # la produzione 2026/27 usa il valore selezionato dal backtest

paths:
  stats: "data/stats"
  player_lists: "data/player_lists"   # quotazioni; l'ultimo file della serie è anche la lista corrente (sez. 2.2)

time_decay:
  base: 1.5                        # con base=2 l'ultima stagione pesa 57%, rendendo il modello quasi
                                    # ridondante con Baseline 0 (sez. 20.4.3/27) — da testare: 1.3/1.5/2.0/2.5
                                    # (max_seasons rimosso: nessuna semantica definita, sez. 26.1 — lavoro futuro)

reliability:
  reference_pv: 30                 # da testare: 25 / 30 / 34 (sez. 20.5b)
  function: sqrt                   # alternative da testare: linear (sez. 9.1) — validato solo via 20.6bis
  exclude_left_mid_season: true    # sez. 9.1bis, B3; false = variante Model 3a in ablation

history:
  historical_min_pv_total: 15      # unico parametro: LIMITED_HISTORY = 1..(soglia-1), sez. 6

performance:
  min_pv_for_percentile: 1         # gruppo di RIFERIMENTO, non gruppo valutato (sez. 10)

bonus_profile:
  min_pv_for_percentile: 1         # indipendente da performance.min_pv_for_percentile (sez. 11.1bis)
  goal_rate_metric: GoalRate       # oppure NonPenaltyGoalRate (sez. 11.1)
  max_zero_share: 0.30             # soglia del controllo QC bloccante (sez. 11.2 / 22)
  zero_handling:                   # sez. 11.2 — default recenter per tutti i ruoli;
    D: recenter                    # split (Model 3c) e midrank (Model 3d) testati in ablation
    C: recenter
    A: recenter
  roles:
    D:
      weight_in_rating: 0.15       # default rivisto da 0.25 (B12) — griglia {0, 0.10, 0.15, 0.25, 0.35}
      goal_weight: 0.60
      assist_weight: 0.40
    C:
      weight_in_rating: 0.15
      goal_weight: 0.60
      assist_weight: 0.40
    A:
      weight_in_rating: 0.15       # default rivisto da 0.25 (B12) — griglia {0, 0.10, 0.15, 0.25, 0.35}
      goal_weight: 0.70
      assist_weight: 0.30

rating:
  P:
    performance: 0.75
    reliability: 0.25
    bonus: 0.00
  D:
    performance: 0.60              # rivisto da 0.55 (B12): allineato a C, non una riscalatura proporzionale
    reliability: 0.25              # del vecchio rapporto 55:20 (quell'aritmetica non torna, sezione 11.3)
    bonus: 0.15
  C:
    performance: 0.60
    reliability: 0.25
    bonus: 0.15
  A:
    performance: 0.60              # rivisto da 0.55 (B12), stessa logica di D
    reliability: 0.25
    bonus: 0.15

goalkeeping:
  fm_weight: 0.75
  goals_conceded_weight: 0.20
  penalty_save_weight: 0.05        # applicato a RpRate = Rp/Pv, non a Rp assoluto (sez. 13)
                                   # testare anche 0.00 e 0.10 in validazione

confidence:
  season_coverage_weight: 0.40
  availability_weight: 0.40
  stability_weight: 0.20           # escluso, con pesi rinormalizzati, se seasons_available < 2 (sez. 19)
  # availability_reference_pv_total non è più una costante: è train_window × reliability.reference_pv (sez. 19, B14)
  sd_reference: 0.20                # saturazione della deviazione standard di Performance_stagione (sez. 19)
  threshold_alta: 0.75
  threshold_media: 0.50

trend:
  method: ols_slope                # pendenza per stagione (sez. 18.1)
  min_seasons: 2                   # sotto questa soglia Trend_Value = null e Trend_Label = N/D
  strong_up: 0.20
  up: 0.08
  down: -0.08
  strong_down: -0.20

validation:
  train_window_grid: [2, 3, 4, 5]          # sez. 20.2/20.5b, B8 — in griglia con time_decay.base
  target_a: fm_percentile_by_role          # sez. 20.4.0 — mai la Fm assoluta; solo Pv >= 1 nel target
  target_b: fm_x_pv_percentile_by_role     # sez. 20.4.0 — intero universo Serie A del target, Pv = 0 incluso
  metrics_by_role: true              # sez. 20.4.0 — nessuna metrica cross-ruolo
  baseline_in_percentile_space: true
  external_baselines: [qt_i, fvm]    # sez. 20.4.3, B9 — fvm valido solo su fold con target >= 2022/23
  lockbox_target: "2025/26"          # sez. 20.2/20.5, B10 — mai usato in calibrazione
  precision_n:
    P: [5, 10, 20]
    D: [10, 20, 30]
    C: [10, 20, 30]
    A: [10, 20, 30]
```

## 25. Roadmap di implementazione

**Fase 1 — Dataset**
- [ ] Importare i 10 Excel statistiche (solo foglio `Tutti`) **e** gli 11 Excel quotazioni (foglio `Tutti` **e** `Ceduti`, sezione 2.1/2.3/2.3bis).
- [ ] Uniformare nomi colonne, aggiungere campo Stagione e campo `RowType` (`PLAYED` / `IN_SQUAD_NO_PLAY`, sezione 4).
- [ ] Eseguire il controllo bloccante `quotazioni_Tutti ∩ Ceduti = ∅`, `quotazioni_Tutti ∪ Ceduti = stats` (sezione 22) prima di procedere.
- [ ] Popolare il flag `left_mid_season` dal foglio `Ceduti` delle quotazioni, fonte unica per tutte le 10 stagioni (sezione 4.0bis/2.3bis).
- [ ] Eseguire i controlli sugli Id (sezione 3.2) e sui ruoli (sezione 4.1), produrre qc_log.
- [ ] Costruire il dataset storico in formato long, su tutte le stagioni disponibili.
- [ ] Importare la lista giocatori corrente (= quotazione 2026/27, sezione 2.2).
- [ ] Join tramite Id; classificare PV_SUFFICIENTI / LIMITED_HISTORY / NEW e popolare `Seasons_Available`, `Seasons_In_Squad` e `Seasons_Quoted` (sezione 6, 21).

**Fase 2 — Feature**
- [ ] Calcolare Fm/Mv/Pv pesate (decadimento esponenziale, sezione 8, su `train_window` stagioni), ripesando le stagioni mancanti sulle sole righe `PLAYED`.
- [ ] Calcolare Reliability per stagione e aggregata: righe `PLAYED` a peso pieno, righe `IN_SQUAD_NO_PLAY` con `left_mid_season = false` a `Reliability_stagione = 0` peso pieno, righe `IN_SQUAD_NO_PLAY` con `left_mid_season = true` escluse e ripesate (sezioni 9.1 e 9.1bis, B3).
- [ ] Calcolare Performance come percentile Fm per ruolo/stagione, mappando **anche** i giocatori sotto `min_pv` sulla distribuzione filtrata (sezione 10).
- [ ] Calcolare GoalRate, NonPenaltyGoalRate, AssistRate e BonusProfile per ruolo, con il trattamento dei blocchi a zero (sezioni 11.1, 11.2).
- [ ] Verificare la centratura di BonusProfile per ruolo — controllo bloccante (sezioni 11.2, 22).
- [ ] Calcolare Trend come pendenza OLS con la regola dei casi non calcolabili (sezione 18.1) e i flag di rischio (sezione 18.2).

**Fase 3 — Rating**
- [ ] Applicare le formule per ruolo usando `R` della lista corrente per i pesi (sezioni 12, 4.1), con `bonus_weight` di default 0.15 per D/A (sezione 11.3, B12).
- [ ] Calcolare ConfidenceScore con `StabilityScore` definito, normalizzato su `train_window` (sezione 19, B14) e la regola per `seasons_available < 2`.
- [ ] Calcolare DefenseScore da Mv_Weighted (sezione 17).
- [ ] Calcolare `Rank_Role` (primario) e `Rank` globale (informativo) con tie-break deterministico (sezione 12.0bis).
- [ ] Popolare `RoleMedianRating` e i campi previsti per i NEW (sezione 21.3).
- [ ] Eseguire i controlli di qualità, inclusi quelli bloccanti su range e distribuzioni (sezione 22).
- [ ] Esportare `ranking_dataset.csv`, ordinato per R + Rank_Role, **senza** colonna `AuctionRating` (sezione 21, B11).

**Fase 4 — Validazione**
- [ ] Costruire l'universo di test per ogni fold direttamente dal file statistiche del target (`PLAYED ∪ IN_SQUAD_NO_PLAY`, sezione 20.1, B4) — non più dalle quotazioni.
- [ ] Calcolare e riportare il Coverage del test, per ruolo e per fold (sezione 20.1), e la quota di arrivi tardivi rispetto alla quotazione pre-stagione del target quando disponibile.
- [ ] Implementare Target A (percentile di Fm per ruolo, solo Pv≥1 nel target) e Target B (percentile di Fm×Pv per ruolo, intero universo Serie A del target) e convertire le baseline nello stesso spazio (sezione 20.4.0) — **prima** di calcolare qualunque metrica.
- [ ] Eseguire il backtest rolling sui 7 fold (6 di selezione, target 2019/20→2024/25, 1 lock-box target 2025/26 mai guardato in calibrazione — sezione 20.2, B6).
- [ ] Separare performance outcome (Pv≥1 nel target) da availability outcome (intero universo Serie A del target, inclusi Pv=0) — sezione 20.3.
- [ ] Calcolare Pearson, Spearman, MAE, Median AE **per ruolo e per fold** nello spazio percentile (sezione 20.4.1, Test A).
- [ ] Calcolare precision@N con N dimensionato sul ruolo e la Top-N Availability Rate corrispondente (sezione 20.4.2, Test B).
- [ ] Calcolare le baseline 0/1/2/3/4 (incluse `Qt.I` su tutti i fold e `FVM` sui fold con target dal 2022/23, B9) su Target A e verificare che il modello batta `Fm_Weighted` in almeno 3 ruoli su 4 su ciascuno dei 6 fold di selezione (sezione 20.4.3, Test C — bloccante); ripetere lo stesso confronto su Target B, obbligatorio ma non bloccante.
- [ ] Eseguire l'ablation Model 1/2/3 e le varianti 3a (ora `exclude_left_mid_season`)/3b/3c/3d (sezione 20.4.4, Test D) su entrambi i target, e il controllo doppio conteggio del BonusProfile: `Rating_senza_BonusProfile` vs `con_BonusProfile` e `corr(Performance, BonusProfile)` per ruolo (sezione 11.4, sezione 20.6).
- [ ] Eseguire il test diretto della Reliability contro `Pv_target` e contro la baseline `Pv_Last_Season` (sezione 20.6bis), incluso il confronto tra `reliability.function = sqrt` e `linear`, e fra `exclude_left_mid_season = true/false`.
- [ ] Calcolare la calibrazione per fascia (bucket) per ruolo e per target, segnalando eventuali inversioni di monotonicità (sezione 20.4.5, Test E).
- [ ] Calibrare nell'ordine fisso della sezione 20.5 (B10), sui 6 fold di selezione: `train_window × time_decay.base` (griglia 2/3/4/5 × 1.3/1.5/2.0/2.5, sui target comuni, B8) → `reliability.function × reference_pv` (via 20.6bis) → `bonus_weight` (griglia B12) → `min_pv_for_percentile` (performance e bonus_profile, indipendenti) → `penalty_save_weight` (0.00/0.05/0.10) → pesi della formula. Un parametro si fissa e non si ritocca dopo aver visto i successivi.
- [ ] Accettare un cambio di default solo se concorde in segno in ≥4 dei 6 fold di selezione **e** in ≥3 dei 4 ruoli (sezione 20.5).
- [ ] Produrre `validation_report.md`: coverage e Test C per ruolo/fold in apertura, tabelle sempre per fold (mai mediate) con mediana + dispersione quando riportata in sintesi, sezione dedicata al lock-box (esito pass/fail rispetto al criterio fissato in anticipo), paragrafo di chiusura sull'ordine di calibrazione e sui parametri lasciati al default (sezione 20.7).
- [ ] **Aprire il lock-box (target 2025/26) una sola volta**, a configurazione congelata: se il criterio di fallimento scatta (non batte le baseline in ≥3 ruoli su 4), tornare alla struttura del modello, non ritoccare un parametro (sezione 20.5, B10).

**Fase 5 — futuro (fuori scope ora)**
- [ ] Aggiungere ruoli Mantra.
- [ ] Aggiungere età anagrafica come metadato.
- [ ] Aggiungere contesto squadra 2026/27 come fattore.
- [ ] Modello predittivo (Projected Rating).

## 26. Aggiornamento annuale

Ogni stagione la pipeline deve poter essere rieseguita aggiungendo file nuovi, senza modifiche strutturali al codice. **Servono due snapshot delle quotazioni per stagione, non uno**: la spec precedente assegnava a un singolo file archiviato due requisiti che si escludono a vicenda — calcolare `left_mid_season` (che richiede lo snapshot di **fine** stagione, per costruire `stats \ Tutti_fine-stagione`) e fare da listone pre-asta (che richiede lo snapshot di **inizio** stagione). Sono insiemi opposti (`stats_T \ Tutti_pre-stagione_T` = arrivi di gennaio; `stats_T \ Tutti_fine-stagione_T` = usciti in corsa) e nessun singolo file può servire entrambi gli scopi. Le 10 stagioni storiche sono calcolabili solo perché sono, per caso, tutte snapshot di fine stagione — non per progetto (sezione 2.3).

| File | Serve a | Quando archiviarlo |
|---|---|---|
| statistiche della stagione conclusa | storico, Performance, BonusProfile, righe `IN_SQUAD_NO_PLAY` (sezione 4) | a fine stagione |
| quotazioni — **listone pre-asta** della stagione (snapshot 1) | `Qt.I`/`FVM` come baseline esterna (sezione 20.4.3), universo di produzione se è la stagione corrente (sezione 2.2), QC arrivi tardivi (sezione 20.1/22) | alla pubblicazione (agosto), quando è ancora un listone pre-asta — **non dopo**: recuperata mesi dopo è già uno snapshot di fine stagione (sezione 2.3, verificato su 10 stagioni: l'errore già commesso in questa finestra) |
| quotazioni — **snapshot di fine stagione** della stessa stagione (snapshot 2) | foglio `Ceduti` → flag `left_mid_season` per Reliability (sezione 9.1bis/2.3bis) | a stagione conclusa |

Il listone pre-asta della *nuova* stagione (snapshot 1 dell'anno successivo) è anche la fonte della lista giocatori corrente (sezione 2.2): non è un quarto file, è lo stesso file letto con due ruoli in due cicli annuali consecutivi.

**Nota operativa importante**: le quotazioni sono un dato **deperibile**, e questa revisione ne ha la controprova diretta: delle 11 stagioni disponibili, solo l'ultima (2026/27) è risultata un listone di inizio stagione — tutte le altre, recuperate successivamente, sono snapshot di fine stagione (`Qt.A ≠ Qt.I` per ~85% delle righe, sezione 2.3). `Qt.I` resta valido anche in quei file (non viene sovrascritto), ma il roster `Tutti` no. Se si perde l'archiviazione dello snapshot di fine stagione 2026/27, `left_mid_season` diventa incalcolabile per quella stagione e il problema identificato da questa revisione si ripresenta identico alla prossima. Archiviare **entrambi** gli snapshot, ai due momenti indicati in tabella, è un passo obbligatorio del ciclo annuale.

L'unico aggiornamento previsto in `config.yaml` è l'elenco delle stagioni: i pesi del decadimento esponenziale si calcolano automaticamente dalla formula della sezione 8 e non vanno rimappati a mano.

### 26.1 Cosa è già stato adeguato in questa revisione, e cosa resta da riconsiderare oltre N=10

Le voci elencate in questa sezione nella revisione precedente (scritta per N=3) sono state **attuate** in questa revisione, ora che N=10 è realtà e non ipotesi:

- `SeasonCoverage` e `AvailabilityScore` (sezione 19) sono normalizzati su `train_window` e `train_window × reference_pv`, non più su costanti (B14, fatto);
- il backtest rolling è passato da 2 fold a 7 (6 selezione + 1 lock-box, sezione 20.2), con reporting sempre per fold, mai mediato (sezione 20.5, fatto);
- il controllo sui cambi di ruolo (sezione 4.1) è stato rifatto sui dati reali a 10 stagioni: 74 Id su 2306 (3.2%) cambiano ruolo, il check `role_change` è ora obbligatorio nel report (fatto).

Cosa resta aperto oltre N=10, per una futura revisione:
- `time_decay.max_seasons` (un eventuale tetto entro `train_window`, per il caso in cui le stagioni più vecchie diventino numericamente irrilevanti) **non è stato definito in questa revisione** — non è in `config.yaml` (rimosso, sezione 24) e non ha semantica in sezione 8. Se servirà, va specificato lì (tronca prima o dopo la normalizzazione dei pesi, e come interagisce con `train_window`) prima di essere reintrodotto — non come parametro dichiarato ma inerte;
- se in futuro si volesse usare più di `train_window = 5` in produzione (oggi fuori scope, sezione 4 del piano di revisione), il numero di fold di selezione disponibili si riduce di conseguenza (`target = N − train_window`) e andrebbe rivalutato se 6 fold di selezione restano sufficienti;
- il tie-break e la riproducibilità (sezione 12.0bis) restano invariati indipendentemente da N.

## 27. Changelog di questa revisione

> Voci superate dalla revisione della sezione 29 (finestra storica a 10 stagioni): il contenuto sotto descrive lo stato della spec a N=3, non lo stato attuale. Non riscritto per non alterare la storia; solo i puntatori a sezioni che non contengono più la cosa citata sono stati corretti.

Modifiche rispetto alla versione precedente della specifica, raggruppate per gravità del problema risolto.

**Correzioni bloccanti**

| # | Problema | Intervento |
|---|---|---|
| 1 | La validazione confrontava `HistoricalRating` (percentili 0-100) con la Fm reale (~4-9): MAE priva di significato, precision@N e Spearman distorti dal mix di ruoli | Nuova sezione 20.4.0: target = percentile di Fm per ruolo nella stagione target; baseline convertite nello stesso spazio; tutte le metriche calcolate per ruolo |
| 2 | La Reliability era gonfiata per chi ha storico corto: chi ha giocato una sola stagione piena otteneva lo stesso punteggio di chi ne ha giocate tre | Nuova sezione 9.1bis: le quotazioni diventano input di produzione (sezione 2.3) e permettono di distinguere "non era in Serie A" da "era in Serie A e non ha giocato", che entra con `Reliability = 0` e peso pieno. **Puntatore corretto**: la distinzione stessa ("era in Serie A e non ha giocato") viene oggi dal file **statistiche** (righe `IN_SQUAD_NO_PLAY`, sezione 4, B1), non dalle quotazioni pre-stagione — le quotazioni (foglio `Ceduti`, sezione 2.3bis) servono solo al flag `left_mid_season` che qualifica quelle righe |
| 3 | `StabilityScore` non era definito (`Fm_variance_normalizzata` non è una quantità), e con una sola stagione dava stabilità massima al giocatore meno conosciuto | Sezione 19: definizione via coefficiente di variazione con `cv_reference`, e regola esplicita di esclusione con rinormalizzazione dei pesi per `seasons_available < 2` |
| 4 | Non era specificato quale `R` usare quando il ruolo cambia tra stagioni | Nuova sezione 4.1: tabella che assegna il ruolo stagionale alle feature e il ruolo 2026/27 ai pesi, più i controlli QC `role_change` e `role_change_gk` |

**Correzioni importanti**

| # | Problema | Intervento |
|---|---|---|
| 5 | `min_pv_for_percentile` era ambiguo: filtrava il gruppo di riferimento o anche i giocatori valutati? | Sezione 10: vincolo esplicito "gruppo di riferimento ≠ gruppo valutato", con indicazione implementativa |
| 6 | Per i difensori il blocco di `GoalRate = 0` sposta la mediana: il difensore modale prendeva un BonusProfile negativo, non zero | Sezione 11.2: controllo QC bloccante su quota a zero e mediana, più `zero_handling: split \| midrank` configurabile per ruolo |
| 7 | `Gf` include i rigori, quindi `GoalRate` premia il rigorista designato — il segnale meno trasferibile che esista | Sezione 11.1: aggiunta `NonPenaltyGoalRate`, parametro `goal_rate_metric`, variante Model 3b in ablation, nuova colonna CSV |
| 8 | `Trend_Value` (ultima − prima) non era comparabile tra storici di lunghezza diversa, ignorava la stagione centrale e dava "Stabile" a chi ha una sola stagione | Sezione 18.1: pendenza OLS per stagione, `Trend_Points`, e `N/D` obbligatorio sotto 2 stagioni |
| 9 | Il `Rank` globale invitava a confronti inter-ruolo che il modello non supporta (percentili interni al ruolo, formule diverse per ruolo) | Sezione 12.0bis: `Rank_Role` primario, `Rank` dichiarato non valido per confronti tra ruoli, ordinamento CSV di default per R + Rank_Role |
| 10 | `HistoricalRating` era descritto come "scala 0-100" pur ammettendo valori negativi | Sezione 12 e colonna CSV: range effettivo per ruolo (P 0→100, C -15→100, D/A -25→100 all'epoca di questa voce). **Puntatore corretto**: dopo B12 (sezione 29) il range D/A è `-15→100`, allineato a C — vedi sezione 12 per il valore attuale |
| 11 | Il QC scartava come ERROR le Fm fuori da 0-10, ma la Fm può essere legittimamente negativa | Sezione 22: WARNING su -10/+20, ERROR su -30/+30, con motivazione |

**Aggiunte**

| Aggiunta | Dove |
|---|---|
| Righe `QUOTED_ONLY` come tipo di riga esplicito del dataset long, con perimetro d'uso vincolato | Sezione 4 — **puntatore corretto**: `QUOTED_ONLY` è stata poi eliminata (B1, sezione 29), risultata sempre vuota; sezione 4 oggi descrive `PLAYED`/`IN_SQUAD_NO_PLAY` |
| `Coverage` del test di validazione, per ruolo, da riportare sempre | Sezione 20.1 |
| `Baseline 2: percentile(Pv_Last_Season)` — batti prima una baseline che ignora il rendimento | Sezione 20.4.3 |
| Criterio di superamento del Test C esplicitato per ruolo (3 su 4) | Sezione 20.4.3 |
| Varianti di ablation 3a/3b/3c, una scelta di modellazione alla volta | Sezione 20.4.4 |
| `time_decay.base` e `reliability.reference_pv` nella sensitivity analysis: i due parametri più impattanti non erano coperti | Sezione 20.5b |
| Test diretto della Reliability sulla disponibilità, con baseline `Pv_Last_Season` | Sezione 20.6bis |
| Trattamento dei NEW in output: `RoleMedianRating`, `Seasons_Quoted`, `Note`, e misura della quota non coperta | Sezione 21.3 |
| `ConfidenceScore` continuo esposto nel CSV oltre alla categoria discreta | Sezione 19, sezione 21 |
| `precision@N` dimensionato sulla numerosità del ruolo (N più piccoli per i portieri) | Sezione 20.4.2 |
| Controlli QC su `Rc = R+ + R-`, `Gf >= R+`, righe QUOTED_ONLY (**puntatore corretto**: categoria poi eliminata, B1/sezione 29), range delle feature, coerenza Trend/Confidence | Sezione 22 |
| `RpRate = Rp / Pv` al posto di `Rp` assoluto, per coerenza con il divieto su `Gs` assoluto | Sezione 13 |
| Ciclo di aggiornamento annuale a tre file, con la nota sulla deperibilità delle quotazioni | Sezione 26 |
| Cosa riconsiderare quando la finestra storica cresce oltre 3 stagioni | Sezione 26.1 |

**Punti volutamente non modificati**

- Il vincolo della sezione 19.1 (Confidence non entra mai nel rating) resta. Diventa però sostenibile solo grazie alla correzione #2: senza di essa la Confidence sarebbe stata l'unico presidio contro una distorsione strutturale, senza avere alcun potere di correggerla.
- Il divieto di `Fm × Pv` (sezione 7) e la separazione Performance/Reliability restano il principio cardine, ma la sezione 20.6 (correlazione tra le due) e la 20.6bis vanno lette insieme: se le due dimensioni risultano molto correlate *e* la Reliability non batte `Pv_Last_Season` sulla disponibilità, la separazione è concettuale e non empirica, e il peso della Reliability va ridotto.
- Il contesto squadra, l'età e i ruoli Mantra restano fuori scope.

## 28. Changelog della revisione corrente

> Voci superate dalla revisione della sezione 29 (finestra storica a 10 stagioni): il contenuto sotto descrive lo stato della spec a N=3, non lo stato attuale. Non riscritto per non alterare la storia; solo i puntatori a sezioni che non contengono più la cosa citata sono stati corretti.

Modifiche rispetto alla versione precedente (sezione 27), a seguito di una seconda revisione della validazione e delle formule.

**Correzioni bloccanti**

| # | Problema | Intervento |
|---|---|---|
| 1 | `StabilityScore` poteva uscire dal range `[0,1]` (anche superarlo abbondantemente) perché basato sul coefficiente di variazione della Fm, che esplode o cambia segno quando la Fm media di un giocatore è vicina a zero o negativa — un caso legittimo secondo la sezione 22 | Sezione 19: `StabilityScore` ridefinito su `sd(Performance_stagione)` (già in scala 0-1, adimensionale per costruzione), niente più CV; aggiunto `ConfidenceScore ∈ [0,1]` ai controlli QC bloccanti (sezione 22) |
| 2 | Il Test C bloccante (sezione 20.4.3) misurava il modello **completo**, Reliability inclusa, contro un target da cui la disponibilità era stata rimossa per costruzione (solo giocatori con Pv≥1 nel target): un gate strutturalmente sfavorevole a Reliability, indipendente dalla sua reale qualità | Nuova sezione 20.4.0 "Target B": percentile di `Fm × Pv` sull'universo quotato completo, riportato per ruolo accanto al Target A esistente; Test C eseguito ora su entrambi (A resta l'unico gate bloccante, B è diagnostico obbligatorio) |

**Correzioni importanti**

| # | Problema | Intervento |
|---|---|---|
| 3 | L'indice di stagione usato per la pendenza OLS del Trend (sezione 18.1) era ambiguo in presenza di stagioni mancanti: posizione compattata tra le disponibili o posizione nell'elenco completo? Le due letture differiscono di un fattore fino a 2× | Sezione 18.1: indice definito esplicitamente come posizione nell'elenco `seasons` di config.yaml, buchi inclusi. **Puntatore corretto**: la sezione 18.1 oggi definisce l'indice come posizione nella **finestra di train** effettivamente in uso (le `train_window` stagioni più recenti), non nell'intero elenco `seasons` — quest'ultimo resta solo il pool da cui `train_window` estrae la finestra |
| 4 | Il cambio di ruolo attraverso il confine portiere (sezione 4.1) restava un semplice `WARNING role_change_gk`, senza una regola su cosa fare delle stagioni storiche aggregate — la Performance portiere e quella degli altri ruoli non sono la stessa distribuzione con pesi diversi, sono formule strutturalmente diverse | Sezione 4.1: regola esplicita — solo le stagioni nel ruolo corrente (rispetto al confine portiere) contribuiscono a `Performance_Storica`; il warning per controllo manuale resta, ma non è più l'unico presidio |
| 5 | Il peso effettivo di BonusProfile nella formula del rating (sezione 12) non era mai stato confrontato con quello di Performance in termini di escursione realizzabile: per D/A, `peso × ampiezza_range` è quasi identico tra i due termini, mentre la sezione 11 lo descrive come "modulatore" | Sezione 11.3: nuova nota di calibrazione con la tabella degli span; sezione 20.5a estesa per testare il peso di BonusProfile isolato (non solo la redistribuzione P/R), sezione 20.6 estesa con `corr(Performance, BonusProfile)` per ruolo come test diretto del doppio conteggio |
| 6 | Con `time_decay.base = 2` di default, l'ultima stagione pesa il 57% del totale: il modello completo diventa altamente correlato con `Baseline 0` (Fm_Last_Season), rendendo il Test C strutturalmente più facile da fallire e la giustificazione delle tre stagioni più debole | Sezione 24: default cambiato da `2` a `1.5`; range di test in sensitivity analysis invariato (1.3/1.5/2.0/2.5) |
| 7 | La forma della funzione di Reliability (`sqrt`) non era mai testata, solo `reference_pv`: la scelta della forma è un'assunzione di modellazione quanto il punto di saturazione | Sezione 9.1: aggiunto `reliability.function` (sqrt/linear) come parametro, testato esclusivamente tramite il test diretto della sezione 20.6bis |
| 8 | Con solo due fold di backtest realmente disponibili, l'elenco di parametri calibrabili (sezione 20.5, 20.4.4) era troppo numeroso per una calibrazione affidabile — rischio concreto di overfitting sui due fold | Sezione 20.5: nuovo paragrafo che limita la calibrazione del default a due soli parametri (`time_decay.base`, `reliability.reference_pv`), richiede concordanza di direzione su entrambi i fold e in ≥3 ruoli su 4, e impone reporting per fold (mai mediato) fino a N≥4 stagioni |

**Aggiunte**

| Aggiunta | Dove |
|---|---|
| `zero_handling = recenter` (sottrazione della mediana di ruolo/stagione) come nuovo default per BonusProfile, più semplice di `split` e sufficiente a soddisfare il controllo QC per costruzione; `split` e `midrank` restano varianti testate in ablation (Model 3c/3d) | Sezione 11.2, 20.4.4 |
| Test E — calibrazione per fascia (bucket): target medio osservato per bucket di rating predetto, per ruolo e per target, con attenzione esplicita a distinguere compressione fisiologica da inversioni di monotonicità | Sezione 20.4.5 |

**Punti volutamente non modificati**

- Il range di `BonusProfile` resta `[-1, +1]` (normalizzazione `/50`, sezione 11.2): la correzione scelta per il problema di span (#5 sopra) è documentare e testare il peso effettivo in validazione, non alterare la scala della metrica, per non introdurre un secondo cambiamento coincidente e rendere l'attribuzione dell'effetto ambigua nell'ablation.
- I criteri di superamento del Test C restano bloccanti solo su Target A: Target B è deliberatamente diagnostico, non un secondo gate, per evitare di rendere il criterio bloccante più facile da soddisfare per costruzione.

## 29. Changelog della revisione corrente — finestra storica a 10 stagioni

Modifiche rispetto alla versione precedente (sezioni 27-28), a seguito dell'arrivo di 10 stagioni di statistiche e 11 di quotazioni e dell'ispezione diretta dei dati documentata in `specs/piano_revisione_10_stagioni.md` (interventi B1-B14).

**Correzioni bloccanti — modello dei dati**

| # | Problema | Intervento |
|---|---|---|
| 1 | L'assunzione "le righe del file statistiche hanno `Pv ≥ 1`" (sezioni 2, 4, 6, 8, 9.1bis) è risultata falsa: il file statistiche contiene l'intero universo Serie A, con 107-153 giocatori a `Pv = 0` per stagione. La categoria `QUOTED_ONLY`, costruita per differenza rispetto alle quotazioni, era quindi sempre vuota | Nuova tassonomia (sezione 4, B1): `RowType = PLAYED` (`Pv >= 1`) / `IN_SQUAD_NO_PLAY` (`Pv = 0`, presente nel file statistiche). `QUOTED_ONLY` eliminata. La regola di pesatura (Performance esclude e ripesa, Reliability include a peso pieno con valore 0) resta identica, cambia solo la fonte del dato |
| 2 | La Reliability penalizzava con `Reliability_stagione = 0` a peso pieno anche chi era uscito dalla Serie A in corsa senza aver mai giocato — dichiarato "limite accettato" nella versione precedente. Verifica su 10 stagioni: è il 55.9-74.5% dei casi a `Pv = 0`, non una coda | Flag `left_mid_season` (sezione 4.0bis/2.3bis, B3), da foglio `Ceduti` delle quotazioni — fonte unica su tutte le 10 stagioni, non un foglio nelle statistiche e non due rami per periodo. Una stagione `IN_SQUAD_NO_PLAY` con `left_mid_season = true` è esclusa dalla Reliability e ripesata, non più contata a zero (sezione 9.1bis). Configurabile (`reliability.exclude_left_mid_season`, default `true`), testato in ablation come Model 3a |
| 3 | Le quotazioni storiche erano assunte come liste pre-stagione; verificate come snapshot di **fine** stagione per tutte le stagioni tranne il 2026/27 (`Qt.A ≠ Qt.I` per ~85% delle righe) | Sezione 2.3, B4: `Qt.I` dichiarato valido come prezzo su tutta la finestra; il roster `Tutti` dichiarato di fine stagione; la costruzione dell'universo di test (sezione 20.1) non dipende più dalle quotazioni; QC sugli arrivi tardivi (sezione 22) |
| 4 | Il join per nome non era esplicitamente vietato in ogni punto della pipeline | Sezione 3.1, B5: divieto esplicito, motivato dai 4 omonimi verificati su 10 stagioni (Vergara, Gori, Buksa, Ndiaye); normalizzazione della grafia ammessa solo per l'output |

**Struttura del backtest**

| # | Problema | Intervento |
|---|---|---|
| 5 | Con 2 fold di backtest, il numero di target realmente osservabili non permetteva di calibrare quasi nulla in modo affidabile (sezione 20.5 della revisione precedente lo dichiarava esplicitamente) | Rolling window a 7 fold (B6, sezione 20.2): 6 di selezione (target 2019/20 → 2024/25) + 1 lock-box (target 2025/26, finestra di train strutturalmente identica a quella di produzione), mai guardato durante la calibrazione |
| 6 | Non era mai stato verificato se il cambio a 5 sostituzioni (giugno 2020) avesse spostato la distribuzione dei `Pv`, quantità su cui si calibra `reference_pv` — la spec pianificava una stratificazione dei fold per questo | Verifica eseguita, esito negativo (nessuno scalino nel 2019/20 o nel 2020/21): nessuna esclusione a priori di stagioni, nessuna stratificazione. Riportato come fatto accertato (sezione 20.2), non come controllo pendente |
| 7 | Il numero di stagioni di train era fissato a 3 per costruzione, mai messo in discussione come parametro | `train_window` reso parametrico (sezione 8, 20.2, B8), testato in griglia con `time_decay.base` su `train_window ∈ {2,3,4,5}`; confronto fra finestre solo sui target comuni |
| 8 | Il confronto con il mercato reale (prezzo pre-stagione) non era mai stato fatto: tutte le baseline erano interne allo stesso dataset del modello | Baseline `Qt.I` (tutti i fold) e `FVM` (fold con target dal 2022/23, B9) aggiunte al Test C (sezione 20.4.3), diagnostiche e non bloccanti, accanto alle baseline interne esistenti |

**Regola di selezione**

| # | Problema | Intervento |
|---|---|---|
| 9 | Con 6 fold di selezione invece di 2, il vincolo "solo `time_decay.base` e `reference_pv` sono candidati a modifica" (sezione 20.5 della revisione precedente) era diventato troppo restrittivo rispetto alla potenza realmente disponibile | Sezione 20.5, B10: ordine fisso di calibrazione a 6 parametri (`train_window × time_decay.base` → `reliability.function × reference_pv` → `bonus_weight` → `min_pv_for_percentile` → `penalty_save_weight` → pesi della formula), un cambio di default accettato solo se concorde in segno in ≥4 dei 6 fold di selezione e in ≥3 dei 4 ruoli, criterio di fallimento del lock-box fissato prima di aprirlo |
| 10 | Il peso del BonusProfile per D/A (25%) non era mai stato testato come parametro continuo, solo come nota di calibrazione (sezione 11.3 della revisione precedente) | Griglia unica `bonus_weight ∈ {0, 0.10, 0.15, 0.25, 0.35}` per D/A (sezione 11.3, B12), dove `0` è l'ablation. Default pre-registrato **0.15**, prima di vedere i risultati: D e A allineati a C (Performance 0.60 / Reliability 0.25 / Bonus 0.15, sezione 12), range `HistoricalRating` unificato a `-15 → 100` per D/C/A |

**Adeguamento a N=10 e rimozioni**

| # | Problema | Intervento |
|---|---|---|
| 11 | `SeasonCoverage`/`AvailabilityScore` (sezione 19) erano normalizzati su costanti (3, 90) tarate su N=3, anticipando un problema che la revisione precedente rimandava a "quando N cresce" (sezione 26.1) | Normalizzati su `train_window` (B14): `seasons_available / train_window` e `Pv_Totale / (train_window × reference_pv)` |
| 12 | `AuctionRating`, colonna duplicata di `HistoricalRating` con un nome che promette una decisione d'asta compiuta, era esposta nel CSV finale | Rimossa dal CSV (B11, sezione 12.1, 21); resta solo come livello architetturale concettuale per l'evoluzione futura, non come colonna |
| 13 | Il nome `STORICO` (sezione 6) suggeriva che sopra soglia il dato diventasse "affidabile" in senso pieno | Rinominato `PV_SUFFICIENTI` (B13) — cosmetico, nessun cambio di condizione |

**Aggiunte**

| Aggiunta | Dove |
|---|---|
| Campo `Seasons_In_Squad` nel CSV, a fianco di `Seasons_Available` e `Seasons_Quoted`: separa "in rosa" (dal file statistiche) da "prezzato" (dalle quotazioni), sostituendo il ruolo che `Seasons_Quoted` aveva prima nella logica di Reliability | Sezione 6, 21 |
| Colonna `Qt.I_2026_27` nel CSV finale, per riferimento in asta (non entra nel rating) | Sezione 21 |
| QC obbligatorio nel report su `role_change` (74/2306 Id, 3.2%, su 10 stagioni) — non più facoltativo | Sezione 4.1, 22 |
| QC sulla quota di `left_mid_season` fra i `Pv=0` per stagione, e sugli arrivi tardivi rispetto alla quotazione pre-stagione del target | Sezione 22 |

**Punti volutamente non modificati**

- Il perimetro del rating (Performance / Reliability / BonusProfile, con Trend/Confidence/DefenseScore come metadati) resta invariato: nessuna feature nuova, nessun `ProjectedRating`, nessun uso dei ruoli Mantra (sezione 1).
- Il divieto di `Fm × Pv` come feature (sezione 7) resta; `Fm × Pv` continua a comparire solo come Target B di validazione (sezione 20.4.0), un ruolo diverso già stabilito nella revisione precedente.
- Il ranking di produzione 2026/27 non userà tutte le 10 stagioni disponibili: userà la finestra `train_window` indicata dal backtest come migliore (plausibilmente 3-5), perché le 10 stagioni servono a **calibrare**, non a massimizzare lo storico usato in produzione (sezione 1, sezione 4 del piano di revisione).
- Le quotazioni pre-stagione autentiche (agosto) delle stagioni storiche restano irrecuperabili: non si tenta di ricostruirle, si dichiara il limite (sezione 2.3).