# Ranking Fantacalcio Serie A — Specifica operativa

## 1. Obiettivo

Costruire un ranking storico dei calciatori di Serie A per il fantacalcio, partendo dalle statistiche delle stagioni:

- 2023/24
- 2024/25
- 2025/26

e dalla lista dei giocatori disponibili per la stagione corrente 2026/27.

Il ranking deve:

- utilizzare le performance storiche, dando più peso alle stagioni recenti;
- distinguere qualità del rendimento (Performance) e affidabilità (Reliability) come dimensioni separate, mai moltiplicate tra loro;
- tenere conto della produzione di bonus/malus (gol, assist, rigori) come modulatore, non come somma aggiuntiva alla Fm;
- distinguere i giocatori per ruolo Classic (P/D/C/A) — **il Mantra (colonna Rm) non viene usato in questa versione**;
- escludere dal ranking finale i giocatori non più in Serie A 2026/27;
- gestire separatamente i giocatori senza storico sufficiente (NEW / LIMITED_HISTORY);
- mantenere la Mv separata dalla Fm, perché base del Modificatore Difesa;
- distinguere, tramite le quotazioni pre-stagione, "non era in Serie A" da "era in Serie A e non ha giocato", perché ai fini della disponibilità le due cose hanno significato opposto (sezione 9.1bis);
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
raw/stats/Statistiche_Fantacalcio_Stagione_2023_24.xlsx
raw/stats/Statistiche_Fantacalcio_Stagione_2024_25.xlsx
raw/stats/Statistiche_Fantacalcio_Stagione_2025_26.xlsx
```

Ogni file contiene un solo foglio (`Tutti`) con una riga per giocatore **che ha ricevuto almeno un voto (Pv ≥ 1)** in quella stagione. Colonne:

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

### 2.2 Lista giocatori corrente

File con l'elenco giocatori Serie A 2026/27 (formato da definire in fase di implementazione — minimo: Id, Nome, R, Squadra). Rappresenta l'universo dei giocatori da valutare nel ranking finale di produzione.

### 2.3 Quotazioni pre-stagione (input di produzione **e** di validazione)

Oltre alle statistiche consuntive, sono disponibili le **quotazioni pubblicate prima dell'inizio di ciascuna stagione** (fonte Fantacalcio.it):

```
raw/quotazioni/Quotazioni_Fantacalcio_2023_24.xlsx
raw/quotazioni/Quotazioni_Fantacalcio_2024_25.xlsx
raw/quotazioni/Quotazioni_Fantacalcio_2025_26.xlsx
```

Queste liste rappresentano l'universo di giocatori **noto prima che la stagione iniziasse**, cioè includono anche chi poi non ha effettivamente giocato (infortuni, esclusioni, cessioni). Sono strutturalmente diverse dai file statistiche (sezione 2.1), che contengono solo chi ha ricevuto almeno un voto.

Questa fonte ha **due usi distinti, entrambi obbligatori**:

1. **Produzione — ricostruzione delle stagioni a Pv = 0** (sezione 9.1bis). Le statistiche consuntive non possono, per costruzione, distinguere "il giocatore non era in Serie A quella stagione" da "era in Serie A e non ha mai preso un voto". Sono due informazioni opposte ai fini della Reliability, e solo le quotazioni permettono di separarle.
2. **Validazione — costruzione dell'universo di test** (sezione 20.1), per evitare il survivorship bias descritto lì.

Colonne minime richieste: `Id`, `Nome`, `R`, `Squadra`. Le eventuali colonne di quotazione/prezzo **non** vengono usate in questa versione, né in produzione né in validazione: l'unica informazione utilizzata è la presenza o assenza dell'Id nella lista.

## 3. Identificazione dei giocatori

### 3.1 Chiave primaria

Usare **Id** come chiave di join. Mai il Nome (accenti, apostrofi, abbreviazioni, variazioni ortografiche lo rendono inaffidabile).

### 3.2 Controlli pre-merge

Prima del merge, verificare e loggare in un file di controllo:
- Id duplicati all'interno dello stesso file stagionale;
- Id presenti in una stagione ma assenti nelle altre;
- Id presenti nella lista 2026/27 ma senza storico nelle 3 stagioni;
- eventuali cambiamenti anomali di Id per lo stesso Nome (possibile errore di dati).

## 4. Struttura del dataset storico

Dataset trasformato in formato long, una riga per giocatore/stagione:

| Id | Nome | Stagione | R | Squadra | Pv | Mv | Fm | Gf | Gs | Rp | Rc | R+ | R- | Ass | Amm | Esp | Au |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

(Rm viene mantenuto in una colonna a parte per uso futuro, ma non entra in nessun calcolo di questa versione.)

Il dataset long contiene **due tipi di riga**, distinti da un flag esplicito `Fonte`:

| Fonte | Origine | Contenuto |
|---|---|---|
| `STATS` | file statistiche (sezione 2.1) | riga completa, `Pv >= 1` |
| `QUOTED_ONLY` | quotazioni pre-stagione (sezione 2.3), per gli Id **assenti** dalle statistiche della stessa stagione | `Pv = 0`; `Mv`, `Fm` e tutti i conteggi bonus/malus a `null`, **non a zero** |

Le righe `QUOTED_ONLY` servono esclusivamente al calcolo della Reliability (sezione 9.1bis) e alla contabilizzazione delle stagioni in Serie A. **Non entrano in nessun calcolo di Performance, BonusProfile, Mv_Weighted, Fm_Weighted, Gf_Rate, Ass_Rate o Trend**, perché per quella stagione non esiste alcuna osservazione di rendimento: `Fm = null` non è `Fm = 0`.

### 4.1 Ruolo del giocatore — quale R si usa e dove (vincolo esplicito)

Il ruolo `R` può cambiare tra stagioni (riclassificazioni Fantacalcio.it, spostamenti di posizione: un C che diventa A). Quale ruolo usare in quale calcolo non va lasciato all'implementazione:

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
- il cambio da o verso `P` è il caso critico, perché la Performance del portiere usa una formula diversa (sezione 13): severità dedicata `WARNING role_change_gk`, da elencare per controllo manuale;
- il campo `R_Storico` (sequenza dei ruoli per stagione, es. `C/C/A`) va esposto nel CSV finale quando differisce dal ruolo corrente.

## 5. Join con la stagione corrente

```
statistiche 2023/24 + 2024/25 + 2025/26      quotazioni 2023/24 + 2024/25 + 2025/26
              ↓                                             ↓
      righe STATS (Pv >= 1)              righe QUOTED_ONLY (Pv = 0, Id non nelle statistiche)
              └───────────────────┬─────────────────────────┘
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

Classificazione a tre livelli, basata sul totale di Pv sommato sulle stagioni disponibili:

| Categoria | Condizione | Trattamento |
|---|---|---|
| STORICO | `Pv_Totale >= historical_min_pv_total` (default 15) | Rating calcolato normalmente |
| LIMITED_HISTORY | `1 <= Pv_Totale < historical_min_pv_total` | Rating calcolato, tipicamente con Confidence bassa (sezione 19) |
| NEW | `Pv_Totale = 0`: nessun voto ricevuto in nessuna delle 3 stagioni | Nessun rating storico; `HistoricalRating = null`, categoria esplicita (vedi sezione 21.3 per il trattamento in output) |

dove `Pv_Totale = Σ Pv` sulle sole righe `STATS` (le righe `QUOTED_ONLY` hanno per definizione Pv = 0 e non contribuiscono).

`historical_min_pv_total` è un **unico** parametro configurabile: la soglia superiore di LIMITED_HISTORY è derivata da esso (`< historical_min_pv_total`), non configurata separatamente. Due parametri per la stessa soglia sono due fonti di verità che prima o poi divergono.

Nota sul caso limite: un giocatore quotato in tutte e 3 le stagioni ma mai impiegato risulta `NEW` per categoria (nessun dato di rendimento) pur avendo `Seasons_Quoted = 3` e una Reliability calcolabile e molto bassa. È raro ma legittimo, ed è il motivo per cui il CSV espone `Seasons_Available` (stagioni con `Pv >= 1`) e `Seasons_Quoted` come campi distinti.

## 7. Performance vs Affidabilità (principio cardine)

**Non moltiplicare mai Fm × Pv.** Le due dimensioni restano separate e vengono combinate solo nella formula finale del rating, ciascuna con il proprio peso:

- **Performance**: quanto è stato forte quando ha giocato → basata su Fm (percentile per ruolo) e Mv.
- **Reliability**: quanto spesso è stato disponibile → basata su Pv, con una funzione non lineare.

Nota terminologica: il nome "Reliability" è mantenuto per uso pratico/colloquiale (è il nome che comparirà nel CSV finale), ma va documentato nel README che tecnicamente misura la **disponibilità/numerosità del campione** (quante partite ha giocato), non l'affidabilità caratteriale del giocatore in senso pieno. Non ha impatto sulla formula, solo sulla comprensione del dato.

## 8. Pesi temporali — decadimento esponenziale

Le stagioni più recenti pesano di più. Usare decadimento esponenziale invece di pesi fissi arbitrari, per generalizzare facilmente ad anni futuri (N stagioni):

```
peso_stagione_i = 2^i / (somma di 2^i su tutte le stagioni disponibili)
```

Con 3 stagioni disponibili (dalla più vecchia alla più recente), pesi relativi 1 : 2 : 4, normalizzati:

| Stagione | Peso |
|---|---|
| 2023/24 | 1/7 ≈ 14.3% |
| 2024/25 | 2/7 ≈ 28.6% |
| 2025/26 | 4/7 ≈ 57.1% |

```
Performance_Storica = Σ (peso_stagione_i × Performance_stagione_i)
```

**Gestione stagioni mancanti — regola differenziata per famiglia di feature.** È il punto in cui è più facile introdurre una distorsione sistematica, quindi la regola è esplicita e non unica:

| Famiglia di feature | Stagioni incluse | Trattamento delle stagioni mancanti |
|---|---|---|
| **Performance** (percentile Fm), `Fm_Weighted`, `Mv_Weighted`, BonusProfile, `Gf_Rate`, `Ass_Rate`, Trend | solo righe `STATS` (`Pv >= 1`) | pesi **ripesati proporzionalmente** (rinormalizzati a somma 1) |
| **Reliability** | righe `STATS` **e** righe `QUOTED_ONLY` (`Pv = 0`) | vedi sezione 9.1bis: una stagione quotata senza presenze entra con `Reliability_stagione = 0` e **peso pieno** |

Razionale: la Performance è una misura **condizionata** ("quanto era forte quando giocava"), quindi una stagione senza osservazioni non è un valore basso, è un dato assente e va esclusa. La Reliability è una misura **non condizionata** ("quanto è stato disponibile"), quindi una stagione in cui era in Serie A e non ha giocato è l'osservazione più informativa che esista e non va esclusa.

Esempio (famiglia Performance): solo 2024/25 e 2025/26 con `Pv >= 1` → pesi ripesati a 2/6 ≈ 33.3% e 4/6 ≈ 66.7%.

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

### 9.1bis Perimetro delle stagioni per la Reliability (correzione della distorsione da storico corto)

**Problema.** Se le stagioni mancanti vengono escluse e ripesate come per la Performance, due giocatori molto diversi risultano identici:

| Giocatore | 2023/24 | 2024/25 | 2025/26 | Reliability (ripesatura semplice) |
|---|---|---|---|---|
| A | 30 Pv | 30 Pv | 30 Pv | 1.00 |
| B | assente | assente | 30 Pv | 1.00 |

Il giocatore B ha dimostrato la propria disponibilità su un terzo dei dati di A; e se le due stagioni assenti erano stagioni in Serie A senza impiego, la sua disponibilità reale è pessima. Poiché `Confidence` per vincolo esplicito non entra nel rating (sezione 19.1), senza una correzione questa distorsione arriverebbe intatta dentro `HistoricalRating` — cioè esattamente nel numero che si guarda in asta.

**Regola.** Per ogni giocatore e ciascuna delle stagioni disponibili:

| Situazione | Riconoscibile da | Reliability_stagione | Entra nella media pesata |
|---|---|---|---|
| Presente nelle statistiche | riga `STATS`, `Pv >= 1` | `min(1, sqrt(Pv / reference_pv))` | sì, peso pieno |
| Quotato pre-stagione, nessun voto | riga `QUOTED_ONLY`, `Pv = 0` | `0` | **sì, peso pieno** |
| Non quotato e non presente | Id assente da entrambe le fonti | non definita | no, peso ripesato (sezione 8) |

Con questa regola il giocatore B dell'esempio mantiene `Reliability = 1.00` solo se davvero non era in Serie A (caso legittimo: acquisto dall'estero), e scende molto se era presente e inutilizzato (infortunio lungo, esclusione tecnica). È precisamente la distinzione che serve in asta.

**Limite dichiarato** (da scrivere nel README): la presenza nelle quotazioni pre-stagione non garantisce che il giocatore sia rimasto in Serie A per l'intera stagione. Chi viene quotato in agosto e ceduto all'estero in settembre riceve `Reliability_stagione = 0` senza aver avuto alcuna occasione di giocare. Le cessioni in uscita non sono ricostruibili con i dati di questa versione. È una distorsione **conservativa** (penalizza, non gonfia) e comunque preferibile a quella opposta descritta sopra, ma va misurata: la validazione deve riportare quanti giocatori ricevono almeno una stagione a `Reliability = 0` e verificarne a campione la plausibilità.

Il comportamento va reso disattivabile da configurazione (`reliability.use_quoted_zero_seasons`, default `true`), così che l'impatto della scelta sia misurabile confrontando le due varianti in ablation (sezione 20.4.4, Model 3a).

### 9.2 Categoria di storico (etichetta, per filtro/comunicazione)

Vedi tabella sezione 6 (STORICO / LIMITED_HISTORY / NEW), basata sul Pv totale cumulato. Serve a etichettare e filtrare, non entra nella formula numerica del rating.

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

Le righe `QUOTED_ONLY` (`Pv = 0`, sezione 4) sono escluse per costruzione da questo calcolo: il risultato è `null`/non calcolabile, **non zero**. Nessuna divisione per zero deve poter avvenire; se avviene è un bug nel filtro sulle righe, non un caso da tamponare con un valore di default.

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

2. **Metodo di centratura alternativo**, da attivare quando il controllo sopra scatta e da confrontare comunque in validazione:

```
zero_handling = split:
  percentile calcolato solo sui giocatori con rate > 0, mappato su [50, 100]
  giocatori con rate = 0 → valore fisso al centro del blocco a zero, non midrank
                            sulla distribuzione completa

zero_handling = midrank:
  comportamento standard (midrank sull'intera distribuzione, zeri inclusi)
```

Default proposto: `split` per D e C, `midrank` per A. Per gli attaccanti `GoalRate = 0` non è la norma di ruolo ma un'informazione negativa reale, coerentemente con la natura bidirezionale del BonusProfile per quel ruolo (sezione 11.3). Come per tutto il resto, la scelta finale la decide la validazione, non l'intuizione.

### 11.3 Peso e configurazione per ruolo

| Ruolo | Peso nel rating finale | goal_weight | assist_weight | Comportamento |
|---|---|---|---|---|
| Portieri | 0% (non usato come componente separata) | — | — | Gs/Pv e Rp restano nella Performance del portiere, sezione 13 |
| Difensori | Alto (~20-25%) | 0.60 | 0.40 | Anche un tasso di gol/assist modesto in assoluto vale molto perché la mediana di ruolo è vicina a zero — il percentile cattura questo automaticamente |
| Centrocampisti | Medio (~12-15%) | 0.60 | 0.40 | Nessuna distinzione tra centrocampisti offensivi/di rottura (rimandata a eventuale uso futuro di Rm) |
| Attaccanti | Alto e bidirezionale (~20-25%) | 0.70 | 0.30 | Sotto la mediana di ruolo = malus reale, non "assenza di bonus". Segnare è il loro mestiere |

Tutti i pesi (sia il peso del BonusProfile nel rating, sia goal_weight/assist_weight interni) sono parametri configurabili in config.yaml, da confermare/calibrare con la validazione retrospettiva (sezione 20).

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
HistoricalRatingRaw_Difensore      = 0.55 × Performance + 0.20 × Reliability + 0.25 × BonusProfile               # range [-0.25, 1]
HistoricalRatingRaw_Centrocampista = 0.60 × Performance + 0.25 × Reliability + 0.15 × BonusProfile               # range [-0.15, 1]
HistoricalRatingRaw_Attaccante     = 0.55 × Performance + 0.20 × Reliability + 0.25 × BonusProfile               # range [-0.25, 1]
```

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
| D | -25 → 100 |
| C | -15 → 100 |
| A | -25 → 100 |

Questa colonna **non va descritta come "scala 0-100"** in nessun punto della documentazione, del CSV o dell'interfaccia: un valore negativo è un output valido e previsto, non un errore di calcolo.

Tutti i pesi sono configurabili in un unico punto del codice (config.yaml), non sparsi/hard-coded nella logica.

Il rating è calcolato solo per giocatori STORICO o LIMITED_HISTORY. Per i NEW il campo resta nullo con categoria esplicita.

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

In futuro, quando sarà introdotto un modello predittivo (sezione 25), si aggiungerà `ProjectedRating` e `AuctionRating` potrà diventare una combinazione dei due, senza che questo richieda di rinominare o ristrutturare le colonne già esistenti. Nel CSV finale di questa versione, esporre sia `HistoricalRating` sia `AuctionRating` (identico a HistoricalRating per ora) per non dover cambiare il nome delle colonne quando arriverà la parte predittiva.

**Nota di cautela sul naming**: `AuctionRating` è un nome concettualmente più impegnativo di `HistoricalRating`, perché suggerisce una decisione d'asta compiuta. Documentare esplicitamente nel README: *"In questa versione AuctionRating è un alias operativo di HistoricalRating e non incorpora prezzo, budget, scarsità di ruolo, composizione della rosa già acquistata, o strategia d'asta. È solo un segnaposto architetturale per l'evoluzione futura."* Questo evita che il campo venga interpretato oggi come più di quello che è.

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

Il Trend si calcola sulla `Performance_stagione` (scala 0-1) delle sole stagioni con `Pv >= 1` (righe `STATS`), usando **tutti** i punti disponibili e non soltanto il primo e l'ultimo:

```
Trend_Value = pendenza della regressione lineare OLS di Performance_stagione
              sull'indice progressivo di stagione (0, 1, 2, ...)
              → interpretabile come "variazione di Performance per stagione"
```

Con 2 stagioni la pendenza coincide con la semplice differenza; con 3 usa anche la stagione centrale, che una differenza prima↔ultima ignorerebbe (un giocatore 0.40 → 0.90 → 0.45 non è "in crescita").

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
- **Poche presenze recenti** (Pv basso nell'ultima stagione anche se lo storico complessivo è STORICO).

## 19. Confidence Score

Non implementare direttamente una serie di soglie if/else arbitrarie (es. `if seasons==3 and pv>50: "Alta"`) senza prima aver verificato se quelle soglie hanno senso. Costruire prima uno **score continuo interno**, poi discretizzarlo in categoria solo per l'esposizione nel CSV finale.

**Formula di partenza per la v1** (semplice e trasparente, non un sotto-progetto a parte):

```
SeasonCoverage    = seasons_available / 3                # stagioni con Pv >= 1, range 0-1
AvailabilityScore = min(1, Pv_Totale / 90)               # 90 = 3 × reference_pv (30), range 0-1
StabilityScore    = 1 - min(1, CV_Fm / cv_reference)     # range 0-1, definizione sotto

ConfidenceScore = 0.40 × SeasonCoverage + 0.40 × AvailabilityScore + 0.20 × StabilityScore
```

**Definizione di `StabilityScore`.** `Fm_variance_normalizzata` non era una quantità definita, e senza specifica diventa una scelta arbitraria e non tracciata fatta in fase di implementazione. La definizione richiesta è:

```
CV_Fm = deviazione_standard(Fm_stagionali) / media(Fm_stagionali)
        # coefficiente di variazione, sulle sole stagioni con Pv >= 1
        # adimensionale, quindi confrontabile tra giocatori con livelli di Fm diversi

StabilityScore = 1 - min(1, CV_Fm / cv_reference)        # cv_reference = 0.20, configurabile
```

Si usa il coefficiente di variazione e non la varianza grezza perché la varianza dipende dal livello: un attaccante che oscilla tra 7.0 e 8.0 avrebbe la stessa varianza di uno che oscilla tra 5.0 e 6.0, senza avere la stessa instabilità relativa. `cv_reference` è il punto di saturazione (CV >= 0.20 → stabilità 0) e va calibrato osservando la distribuzione reale dei CV, non fissato a intuito.

**Caso `seasons_available < 2` — regola obbligatoria.** Con una sola stagione la deviazione standard è `0` o `NaN`. Se il codice la tratta come `0`, allora `StabilityScore = 1`: il **massimo punteggio di stabilità assegnato al giocatore di cui si sa meno**, esattamente il contrario di ciò che la Confidence deve esprimere. La regola è:

```
seasons_available < 2  →  StabilityScore non definito
                          → escluso dalla media, pesi rinormalizzati:
                            ConfidenceScore = (0.40 × SeasonCoverage
                                             + 0.40 × AvailabilityScore) / 0.80
```

La rinormalizzazione è preferibile a `StabilityScore = 0` perché non penalizza due volte lo stesso fenomeno: la scarsità di storico è già catturata da `SeasonCoverage` e `AvailabilityScore`, entrambi bassi in quel caso.

Verifica di sanità obbligatoria (sezione 22): nessun giocatore con `seasons_available = 1` può risultare `Confidence = Alta`. Con la formula sopra il massimo raggiungibile è `(0.40 × 0.33 + 0.40 × 0.42) / 0.80 ≈ 0.38` → Bassa.

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

**Problema**: se l'universo di test per "2023/24+2024/25 → prevedi 2025/26" viene costruito usando i giocatori presenti nel file statistiche 2025/26 (cioè chi ha effettivamente ricevuto un voto, Pv≥1), si introduce informazione futura — si esclude implicitamente chi era atteso in campo ma poi non ha giocato (infortuni, esclusioni, cessioni), rendendo il test artificialmente più pulito di quanto sarebbe stato in tempo reale.

**Soluzione richiesta**: costruire l'universo di test usando le **quotazioni pre-stagione** (sezione 2.3), non le statistiche consuntive. Per il test "2023/24+2024/25 → 2025/26": l'universo è la lista quotazioni di inizio 2025/26 (che include anche chi poi non ha giocato). Il confronto con la Fm reale userà poi il file statistiche 2025/26, dove i giocatori quotati ma con Pv=0 (o molto basso) sono un caso legittimo da includere nelle metriche di errore — non un errore di join da scartare, ma un segnale reale sul limite del modello (non può prevedere infortuni/esclusioni).

**Coverage del test — da riportare sempre.** L'universo di test è la lista quotazioni, ma il rating è calcolabile solo per chi ha storico nelle stagioni di train: i `NEW` non ricevono un rating e restano necessariamente fuori dalle metriche. Il report deve quindi dichiarare, per ogni test rolling e **per ruolo**:

```
Coverage = (giocatori dell'universo quotato con HistoricalRating non nullo) / (universo quotato)
```

Se il coverage è, per esempio, 0.62, tutte le metriche della sezione 20.4 vanno lette come "valide sul 62% dei giocatori acquistabili". Non è un dettaglio metodologico: è la misura di quanto il ranking sia effettivamente utile in un'asta reale, dove il 38% restante va comunque comprato da qualcuno.

### 20.2 Backtest rolling, parametrico

Non implementare una funzione hard-coded "predici 2025/26". Strutturare `validate.py` con parametri espliciti:

```
train_seasons: lista di stagioni usate per calcolare il rating
target_season: stagione su cui si valuta la previsione (statistiche consuntive + quotazioni pre-stagione corrispondenti)
```

Questo permette di eseguire più test quando saranno disponibili più stagioni, ad esempio:
```
train=[2023/24] → target=2024/25
train=[2023/24, 2024/25] → target=2025/26
train=[2023/24, 2024/25, 2025/26] → target=2026/27  (eseguibile solo quando i dati reali 2026/27 saranno disponibili a fine stagione)
```

Nota per l'aggiornamento annuale (collegamento con sezione 26): a differenza della pipeline di produzione (che ogni anno richiede solo il nuovo file statistiche + la nuova lista giocatori), la pipeline di *validazione* richiede in più, ogni anno, anche la nuova quotazione pre-stagione corrispondente. Sono due flussi di aggiornamento leggermente diversi, da tenere distinti nella documentazione.

### 20.3 Separare performance prediction e availability outcome (giocatori con Pv=0 nel target)

Un giocatore quotato pre-stagione ma con `Pv = 0` nella stagione target ha `Fm = null`: non può entrare in un calcolo di correlazione o errore rispetto alla Fm, perché quella Fm semplicemente non esiste. Questo non significa scartarlo dal test — significa smettere di trattare "previsione della performance" e "il giocatore ha effettivamente giocato" come lo stesso tipo di errore. Il backtest calcola quindi due famiglie di metriche distinte:

**a) Performance outcome** (solo su giocatori con `Pv ≥ 1` nella stagione target): tutte le metriche della sezione 20.4 (Pearson, Spearman, MAE, precision@N) si calcolano esclusivamente su questo sottoinsieme osservabile.

**b) Availability outcome** (su tutto l'universo quotato pre-stagione, inclusi i `Pv = 0`): misura quanti dei giocatori con rating alto/nel top-N previsto hanno effettivamente prodotto una stagione osservabile. Definire:

```
Top-N Availability Rate = (giocatori nel Top-N previsto con Pv ≥ 1 nel target) / N
```

Esempio: Top 20 previsto → 18 con Pv > 0, 2 con Pv = 0 → Availability Rate = 90%. Questo è un test distinto e complementare: misura un limite noto e accettato del modello (non essendo previsti infortuni/esclusioni/cessioni nella sezione 1, un'Availability Rate imperfetta non è un fallimento del modello, ma va comunque misurata e riportata, perché è informazione rilevante per chi userà il ranking in un'asta).

### 20.4 Metriche da calcolare (su performance outcome, sezione 20.3a)

#### 20.4.0 Definizione del target — da fissare prima di qualunque metrica

`HistoricalRating` **non è una previsione di Fm**. È un composito di percentili calcolati dentro il ruolo, in scala 0-1 (esposta ×100). La Fm reale è una quantità in scala ~4-9 la cui distribuzione dipende fortemente dal ruolo. Confrontare direttamente le due cose produce due errori gravi:

- **MAE e Median AE diventano privi di significato.** L'errore medio tra un rating a 78 e una Fm a 6.8 misura una differenza di unità di misura, non un errore di previsione. Nella tabella di sintesi la baseline `Fm_Weighted` (che predice Fm in unità di Fm, errore ~0.4) risulterebbe migliore del modello (errore ~70) per ragioni puramente dimensionali, e il Test C darebbe un verdetto falso.
- **precision@N e Spearman cross-ruolo risultano distorti.** Il rating è deliberatamente role-neutral, mentre il top-N reale per Fm assoluta è dominato da attaccanti e trequartisti: si confronterebbe un ranking normalizzato con uno non normalizzato.

**Target ufficiale della validazione**:

```
Target = percentile della Fm nella stagione target, calcolato dentro il ruolo R
         della stagione target
         (stesso metodo deterministico della sezione 10, stesso min_pv_for_percentile)
         → scala 0-1
```

Con questa definizione tutte le quantità confrontate vivono in [0, 1], `MAE` e `Median AE` sono interpretabili come errore di posizionamento percentile, e il confronto con le baseline è equo.

**Conversione obbligatoria delle baseline.** `Fm_Last_Season` e `Fm_Weighted` sono in unità di Fm e vanno portate nello stesso spazio prima del confronto: percentile per ruolo (calcolato sulle stagioni di train) della metrica di baseline. Una baseline non convertita non è una baseline più semplice, è una baseline in un'altra unità di misura.

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
```

`Baseline 2` è aggiunta perché una parte importante del valore in asta è semplicemente "questo giocatore gioca". Se il modello completo non batte una baseline che ignora del tutto il rendimento, il problema non è la calibrazione dei pesi.

**Criterio di superamento**: il modello completo (Performance + Reliability + BonusProfile) deve battere `Fm_Weighted` su **Spearman e precision@20, in almeno 3 ruoli su 4**. Il criterio è per ruolo e non aggregato perché un modello che funziona bene su D e C e male su P e A non è un modello valido: in asta i ruoli si comprano tutti. Se il criterio non è soddisfatto, tutta la complessità aggiuntiva (percentili per ruolo, Reliability, BonusProfile) non sta dimostrando valore reale e va rivista — indipendentemente da quanto sia concettualmente ben giustificata. Questo test decide se il progetto ha senso così com'è, non è un dettaglio opzionale.

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
Model 3a: reliability.use_quoted_zero_seasons = false            (sezione 9.1bis)
Model 3b: bonus_profile.goal_rate_metric = NonPenaltyGoalRate    (sezione 11.1)
Model 3c: bonus_profile.zero_handling = midrank per tutti i ruoli (sezione 11.2)
```

**Tabella di sintesi attesa** (una tabella **per ruolo**, report finale sezione 20.7):

| Model | Pearson | Spearman | MAE | Median AE | Prec@10 | Prec@20 | Prec@30 | Avail@20 |
|---|---|---|---|---|---|---|---|---|
| Baseline 0: percentile(Fm_Last_Season) | | | | | | | | |
| Baseline 1: percentile(Fm_Weighted) | | | | | | | | |
| Baseline 2: percentile(Pv_Last_Season) | | | | | | | | |
| Model 1: Performance | | | | | | | | |
| Model 2: + Reliability | | | | | | | | |
| Model 3: + BonusProfile (base) | | | | | | | | |
| Model 3a: senza stagioni quotate a zero | | | | | | | | |
| Model 3b: NonPenaltyGoalRate | | | | | | | | |
| Model 3c: zero_handling = midrank | | | | | | | | |

### 20.5 Sensitivity analysis (dopo che il modello base ha superato i test C e D)

Prima di considerare definitivi i parametri di config.yaml, verificare la stabilità del ranking rispetto a piccole variazioni.

**a) Pesi della formula di rating.** Esempio per i Difensori (pesi base 55/20/25):

```
50/25/25, 55/20/25 (base), 60/20/20
```

**b) Parametri strutturali del modello temporale — obbligatori, non erano coperti.** Sono i due parametri con l'impatto più forte su tutto il modello:

```
time_decay.base:           1.3, 1.5, 2.0 (base), 2.5
reliability.reference_pv:  25, 30 (base), 34
```

`time_decay.base = 2` assegna il 57% del peso complessivo a una singola stagione; con base 1.5 i pesi diventano ≈ 26/33/41 e con base 1.3 ≈ 30/33/37. La differenza tra "il modello guarda soprattutto l'ultimo anno" e "il modello media tre anni" è una scelta di modellazione sostanziale, non un dettaglio di configurazione, e va decisa dai dati.

**c) Filtri sul campione.**

```
performance.min_pv_for_percentile:    1, 3, 5
bonus_profile.min_pv_for_percentile:  1, 3, 5   (indipendente dal precedente)
goalkeeping.penalty_save_weight:      0.00, 0.05, 0.10
```

Per ciascuna variazione, calcolare:
- Spearman e precision@20 rispetto al target (per capire se la variazione migliora o peggiora);
- **rank correlation tra la configurazione base e la configurazione variata** (`Spearman(Rank_base, Rank_variazione)`) — più intuitiva delle sole metriche predittive per capire quanto il ranking finale "si muove" al variare dei pesi. Un valore alto (es. 0.95+) indica un modello robusto; un valore basso indica che il ranking è instabile e sensibile a scelte arbitrarie dei pesi, cosa da segnalare esplicitamente prima di usarlo per un'asta reale.

Questa fase è importante ma non bloccante quanto i test C/D: va eseguita dopo aver verificato che il modello base supera le baseline, non prima.

### 20.6 Nota informativa: correlazione tra Performance e Reliability

Aggiungere nel report, per ciascun ruolo, il calcolo di `corr(Performance, Reliability)`. Le due dimensioni sono concettualmente separate (sezione 7), ma nella realtà è plausibile che siano correlate (i giocatori più forti tendono a giocare di più, quelli fragili meno). Non è un errore da correggere, ma un'informazione da riportare: una correlazione molto alta (es. > 0.85) significa che il modello sta dando peso, indirettamente, due volte a un fenomeno in parte sovrapposto — utile saperlo per interpretare correttamente i pesi scelti, senza che questo richieda necessariamente un intervento.

### 20.6bis Test diretto della Reliability (non solo indiretto)

Oggi la Reliability sarebbe validata soltanto di rimbalzo, tramite l'ablation sulla previsione di Fm. Ma il suo compito dichiarato non è predire il rendimento: è predire la **disponibilità**. Va quindi misurata su quello, direttamente:

```
Spearman(Reliability_train, Pv_target)          per ruolo, su performance outcome
Spearman(Reliability_train, [Pv_target >= 1])   per ruolo, su TUTTO l'universo quotato
```

Il secondo test si calcola sull'universo quotato completo (sezione 20.3b), non sul solo performance outcome: escludere i `Pv = 0` da un test sulla disponibilità significherebbe rimuovere esattamente i casi che il test deve spiegare.

**Baseline obbligatoria**: `Spearman(Pv_Last_Season, Pv_target)`. Se la Reliability elaborata (radice, saturazione a `reference_pv`, media pesata su 3 stagioni, stagioni a zero ricostruite dalle quotazioni) non batte il semplice numero di presenze dell'ultima stagione, la sua costruzione è sovrastruttura e va semplificata.

Questo test è anche la verifica quantitativa della correzione della sezione 9.1bis: eseguirlo con `use_quoted_zero_seasons` a `true` e a `false` e riportare entrambi i valori. Se la correzione non migliora nulla su questa metrica, il problema conoscitivo che risolve resta reale ma il peso della Reliability nel rating va rivisto al ribasso.

### 20.7 Output della validazione

Un report (`validation_report.md`, con eventuale export CSV delle tabelle) contenente tutte le metriche delle sezioni 20.1 e 20.3-20.6bis, per ciascun test rolling eseguito e **con una tabella per ruolo**, da consultare prima di considerare definitivi i parametri di config.yaml. Il report deve aprirsi con: coverage per ruolo (sezione 20.1), esito del Test C bloccante ruolo per ruolo, e in caso di mancato superamento una riga esplicita che lo dichiari — un report che seppellisce un fallimento del Test C dentro una tabella è inutile. Questa fase serve anche a calibrare empiricamente i pesi delle sezioni 8, 9, 10, 11, 12, 13, 19 — che partono come ipotesi dichiarate, non verità.

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
| Categoria | STORICO / LIMITED_HISTORY / NEW |
| Seasons_Available | Numero di stagioni con `Pv >= 1` per il giocatore (0-3) |
| Seasons_Quoted | Numero di stagioni in cui il giocatore era nelle quotazioni pre-stagione (0-3). Se > Seasons_Available esistono stagioni in Serie A senza presenze, che abbassano la Reliability (sezione 9.1bis) |
| HistoricalRating | Rating storico finale (= HistoricalRatingRaw × 100, sezione 12). Range per ruolo: P 0→100, C -15→100, D/A -25→100. **Non è una scala 0-100**: i valori negativi sono validi. Null se NEW |
| AuctionRating | In questa versione, identico a HistoricalRating (vedi sezione 12.1 e nota di cautela sul naming) |
| Confidence | Alta / Media / Bassa (sezione 19) |
| ConfidenceScore | Score continuo 0-1 da cui deriva Confidence. Esposto e non solo in debug: le soglie 0.75/0.50 sono arbitrarie in v1 e il continuo permette di ordinare i casi di frontiera |
| Performance | Performance storica pesata, scala 0-1 |
| Reliability | Reliability score, scala 0-1 (vedi nota terminologica sezione 7) |
| BonusProfile | Score bonus/malus per ruolo, normalizzato -1/+1 (sezione 11.2) |
| DefenseScore | = Mv_Weighted, per Modificatore Difesa |
| Trend_Value | Pendenza OLS di Performance per stagione (sezione 18.1); null se meno di 2 stagioni con `Pv >= 1` |
| Trend_Label | Etichetta/simbolo andamento; `N/D` se Trend_Value è null |
| Trend_Points | Numero di stagioni usate per calcolare Trend_Value (2 o 3) |
| Mv_Weighted | Mv storica pesata (decadimento esponenziale). Non è una "Mv media" in senso tradizionale, è una feature pesata a fini di modello — vedi nota 21.1 |
| Fm_Weighted | Fm storica pesata (decadimento esponenziale) |
| Pv_Weighted | Pv storiche pesate (decadimento esponenziale). **Non rappresenta una stima di partite giocate** — è una feature temporale derivata, usata solo a fini informativi/debug, non entra nel calcolo di Reliability (che usa il Pv di ogni singola stagione, sezione 9.1) |
| Pv_Totale | Somma reale di Pv su tutte le stagioni disponibili (usato per la categoria, sezione 6) |
| Pv_Last_Season | Pv dell'ultima stagione disponibile per il giocatore (dato grezzo, non pesato) |
| Fm_Last_Season | Fm dell'ultima stagione disponibile (dato grezzo, coincide con Baseline 0 della sezione 20.4) |
| Mv_Last_Season | Mv dell'ultima stagione disponibile (dato grezzo) |
| Gf_Rate | Gol per presenza, rigori inclusi; media pesata dei rate stagionali (vedi nota 21.2 sul metodo) |
| NonPenaltyGf_Rate | Gol su azione per presenza, `(Gf - R+) / Pv`; media pesata (sezione 11.1) |
| Ass_Rate | Assist per presenza, media pesata dei rate stagionali (vedi nota 21.2) |
| RigoriDipendenza | Flag/valore su dipendenza da rigori (attaccanti/centrocampisti) |
| RoleMedianRating | Mediana di HistoricalRating del proprio ruolo, su tutti i giocatori con rating. Popolata per tutti, NEW inclusi; **non è un rating personale** (sezione 21.3) |
| Squadra_2023_24 / 2024_25 / 2025_26 | Storico squadre, per riferimento |
| Note | Testo libero per i casi che richiedono contesto (es. `nessuno storico Serie A 2023/24–2025/26`) |

Nota: `Rating_Band` (es. Elite/A/B/C/D) è volutamente escluso da questa versione — è una classificazione decisionale che va introdotta solo dopo aver validato che `HistoricalRating` è ben calibrato (sezione 20).

**Ordinamento di default del file**: per `R`, poi `Rank_Role` crescente. Non per `Rank` globale, che non è un confronto valido tra ruoli diversi (sezione 12.0bis).

### 21.1 Chiarimento su Pv_Weighted vs Pv_Totale

Da documentare esplicitamente nel README, perché sono due numeri che possono sembrare in contraddizione a chi legge il CSV senza contesto (es. `Pv_Totale = 70` ma `Pv_Weighted = 26.8`): *"Pv_Weighted non è una stima di partite giocate; è una feature temporale pesata (stesso decadimento esponenziale delle altre metriche storiche) usata a fini di analisi/debug. Pv_Totale è la somma reale e non pesata delle presenze disponibili, usata per determinare la categoria STORICO/LIMITED_HISTORY/NEW."*

### 21.2 Chiarimento sul metodo di aggregazione di Gf_Rate e Ass_Rate

Esistono due metodi matematicamente diversi per aggregare un tasso su più stagioni, e vanno tenuti distinti esplicitamente:

```
Metodo 1 (usato in questa spec): media pesata dei rate stagionali
WeightedGoalRate = Σ (peso_stagione_i × GoalRate_i)     dove GoalRate_i = Gf_i / Pv_i

Metodo 2 (NON usato): rate aggregato sul totale
GoalRate_aggregato = Σ Gf_i / Σ Pv_i
```

Il **Metodo 1** è quello richiesto, per coerenza con il resto del modello temporale (stessi pesi di decadimento esponenziale usati per Performance, Reliability, Mv_Weighted, Fm_Weighted — sezione 8). Il Metodo 2 darebbe un risultato numericamente diverso e non andrebbe usato al suo posto, né scambiato con esso in fase di implementazione.

Lo stesso Metodo 1 si applica a `NonPenaltyGf_Rate` (sezione 11.1). E in entrambi i casi valgono le sole righe `STATS`: una stagione a `Pv = 0` non contribuisce con un rate pari a zero, non contribuisce affatto (sezioni 4 e 8).

Non serve un file Excel separato per la vista sintetica in questa versione — un CSV unico, ben ordinabile per HistoricalRating decrescente e filtrabile per R, è sufficiente sia per la consultazione manuale sia per l'uso conversazionale.

### 21.3 Giocatori NEW — cosa fare del vuoto

I `NEW` non sono un caso marginale: neopromosse e acquisti dall'estero possono rappresentare una quota rilevante dei giocatori acquistabili, e in asta una cella vuota è indistinguibile da un giocatore scarso. Questa versione non produce un rating per loro (nessun dato, sezione 6) e non lo inventa, ma espone l'informazione in modo utilizzabile:

| Campo | Contenuto per un NEW |
|---|---|
| `Categoria` | `NEW` |
| `HistoricalRating`, `Rank`, `Rank_Role` | `null` — mai un valore convenzionale, mai messi in coda alla classifica |
| `Seasons_Quoted` | può essere > 0: quotato in passato e mai impiegato, informazione tutt'altro che neutra |
| `Reliability` | calcolabile se `Seasons_Quoted > 0` (sarà molto bassa); null se mai quotato |
| `RoleMedianRating` | mediana di ruolo, come termine di paragone |
| `Note` | es. `nessuno storico Serie A 2023/24–2025/26` |

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

**Righe QUOTED_ONLY (sezione 4)**
- ogni riga `QUOTED_ONLY` ha `Pv = 0` e `Fm`/`Mv` a null, mai a zero (ERROR);
- numero di righe `QUOTED_ONLY` generate per stagione (INFO): un valore nullo o implausibilmente alto segnala un problema di join tra quotazioni e statistiche;
- Id presenti nelle statistiche di una stagione ma **assenti** dalle quotazioni della stessa stagione (WARNING): è possibile (giocatore aggiunto in corsa, listone aggiornato), ma se il numero è alto la lista quotazioni usata è probabilmente della versione sbagliata.

**Ruoli (sezione 4.1)**
- cambio di `R` tra stagioni per lo stesso Id (WARNING `role_change`);
- cambio di `R` da o verso `P` (WARNING `role_change_gk`, da elencare per controllo manuale);
- `R` della lista 2026/27 diverso da `R` dell'ultima stagione disponibile (INFO: frequente e legittimo, ma utile da sapere in asta).

**Distribuzioni delle feature (bloccanti)**
- per ogni ruolo e stagione: quota di giocatori nel blocco a `rate = 0` e mediana di `BonusProfile_normalized`. Se la quota supera `bonus_profile.max_zero_share` o la mediana si discosta da 0 più di 0.10 → ERROR: il modulatore non è centrato (sezione 11.2);
- `Performance ∈ [0, 1]`, `Reliability ∈ [0, 1]`, `BonusProfile ∈ [-1, +1]` su ogni riga (ERROR se fuori range: tipicamente una divisione per 100 dimenticata, sezione 10);
- nessun giocatore con `Seasons_Available = 1` e `Confidence = Alta` (ERROR, sezione 19);
- nessun giocatore con `Seasons_Available = 1` e `Trend_Label` diverso da `N/D` (ERROR, sezione 18.1);
- quota di giocatori con almeno una stagione a `Reliability_stagione = 0` derivata da riga `QUOTED_ONLY` (INFO, con elenco da verificare a campione: è il limite delle cessioni in uscita dichiarato in sezione 9.1bis).

**Coerenza Id ↔ Nome**
- stesso Id con Nome che cambia tra stagioni (WARNING — puà rivelare un errore nel dataset sorgente, non necessariamente un problema, ma va segnalato);
- stesso Nome associato a più Id diversi (WARNING, stesso motivo).

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
├── raw/
│   ├── stats/
│   │   ├── Statistiche_Fantacalcio_Stagione_2023_24.xlsx
│   │   ├── Statistiche_Fantacalcio_Stagione_2024_25.xlsx
│   │   └── Statistiche_Fantacalcio_Stagione_2025_26.xlsx
│   ├── quotazioni/
│   │   ├── Quotazioni_Fantacalcio_2023_24.xlsx
│   │   ├── Quotazioni_Fantacalcio_2024_25.xlsx
│   │   └── Quotazioni_Fantacalcio_2025_26.xlsx
│   └── current/
│       └── giocatori_2026_27.xlsx
│
├── data/
│   ├── historical.csv          # dataset long, tutte le stagioni
│   ├── merged.csv              # dopo join con lista 2026/27
│   └── qc_log.csv              # controlli qualità/join (sezione 22)
│
├── output/
│   ├── ranking_dataset.csv     # output finale unico (sezione 21)
│   └── validation_report.md    # metriche di backtest, una tabella per ruolo (sezione 20.7)
│
├── src/
│   ├── load_data.py            # statistiche + quotazioni + lista corrente
│   ├── build_universe.py       # righe STATS/QUOTED_ONLY, join, categorie (sezioni 4, 6)
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
seasons:
  - "2023/24"
  - "2024/25"
  - "2025/26"

paths:
  stats: "raw/stats"
  quotazioni: "raw/quotazioni"     # obbligatorio: produzione (sez. 9.1bis) + validazione (sez. 20.1)
  current: "raw/current"

time_decay:
  base: 2                          # da testare: 1.3 / 1.5 / 2.0 / 2.5 (sez. 20.5b)
  max_seasons: null                # finestra massima, utile al crescere di N (sez. 26.1)

reliability:
  reference_pv: 30                 # da testare: 25 / 30 / 34 (sez. 20.5b)
  function: sqrt
  use_quoted_zero_seasons: true    # sez. 9.1bis; false = variante Model 3a in ablation

history:
  historical_min_pv_total: 15      # unico parametro: LIMITED_HISTORY = 1..(soglia-1), sez. 6

performance:
  min_pv_for_percentile: 1         # gruppo di RIFERIMENTO, non gruppo valutato (sez. 10)

bonus_profile:
  min_pv_for_percentile: 1         # indipendente da performance.min_pv_for_percentile (sez. 11.1bis)
  goal_rate_metric: GoalRate       # oppure NonPenaltyGoalRate (sez. 11.1)
  max_zero_share: 0.30             # soglia del controllo QC bloccante (sez. 11.2 / 22)
  zero_handling:                   # sez. 11.2
    D: split
    C: split
    A: midrank
  roles:
    D:
      weight_in_rating: 0.25
      goal_weight: 0.60
      assist_weight: 0.40
    C:
      weight_in_rating: 0.15
      goal_weight: 0.60
      assist_weight: 0.40
    A:
      weight_in_rating: 0.25
      goal_weight: 0.70
      assist_weight: 0.30

rating:
  P:
    performance: 0.75
    reliability: 0.25
    bonus: 0.00
  D:
    performance: 0.55
    reliability: 0.20
    bonus: 0.25
  C:
    performance: 0.60
    reliability: 0.25
    bonus: 0.15
  A:
    performance: 0.55
    reliability: 0.20
    bonus: 0.25

goalkeeping:
  fm_weight: 0.75
  goals_conceded_weight: 0.20
  penalty_save_weight: 0.05        # applicato a RpRate = Rp/Pv, non a Rp assoluto (sez. 13)
                                   # testare anche 0.00 e 0.10 in validazione

confidence:
  season_coverage_weight: 0.40
  availability_weight: 0.40
  stability_weight: 0.20           # escluso, con pesi rinormalizzati, se seasons_available < 2 (sez. 19)
  availability_reference_pv_total: 90   # = n_seasons × reference_pv, da ricalcolare al crescere di N (sez. 26.1)
  cv_reference: 0.20               # saturazione del coefficiente di variazione della Fm (sez. 19)
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
  target: fm_percentile_by_role     # sez. 20.4.0 — mai la Fm assoluta
  metrics_by_role: true             # sez. 20.4.0 — nessuna metrica cross-ruolo
  baseline_in_percentile_space: true
  precision_n:
    P: [5, 10, 20]
    D: [10, 20, 30]
    C: [10, 20, 30]
    A: [10, 20, 30]
```

## 25. Roadmap di implementazione

**Fase 1 — Dataset**
- [ ] Importare i tre Excel statistiche **e** le tre quotazioni pre-stagione (sezione 2.3).
- [ ] Uniformare nomi colonne, aggiungere campo Stagione e flag `Fonte` (STATS / QUOTED_ONLY).
- [ ] Generare le righe `QUOTED_ONLY`: Id quotati e assenti dalle statistiche della stessa stagione, con `Pv = 0` e Fm/Mv null (sezione 4).
- [ ] Eseguire i controlli sugli Id (sezione 3.2) e sui ruoli (sezione 4.1), produrre qc_log.
- [ ] Costruire il dataset storico in formato long.
- [ ] Importare la lista 2026/27.
- [ ] Join tramite Id; classificare STORICO / LIMITED_HISTORY / NEW e popolare `Seasons_Available` e `Seasons_Quoted` (sezione 6).

**Fase 2 — Feature**
- [ ] Calcolare Fm/Mv/Pv pesate (decadimento esponenziale, sezione 8), ripesando le stagioni mancanti sulle sole righe STATS.
- [ ] Calcolare Reliability per stagione e aggregata, includendo le stagioni quotate a `Pv = 0` con peso pieno (sezioni 9.1 e 9.1bis).
- [ ] Calcolare Performance come percentile Fm per ruolo/stagione, mappando **anche** i giocatori sotto `min_pv` sulla distribuzione filtrata (sezione 10).
- [ ] Calcolare GoalRate, NonPenaltyGoalRate, AssistRate e BonusProfile per ruolo, con il trattamento dei blocchi a zero (sezioni 11.1, 11.2).
- [ ] Verificare la centratura di BonusProfile per ruolo — controllo bloccante (sezioni 11.2, 22).
- [ ] Calcolare Trend come pendenza OLS con la regola dei casi non calcolabili (sezione 18.1) e i flag di rischio (sezione 18.2).

**Fase 3 — Rating**
- [ ] Applicare le formule per ruolo usando `R` della lista 2026/27 per i pesi (sezioni 12, 4.1).
- [ ] Calcolare ConfidenceScore con `StabilityScore` definito e la regola per `seasons_available < 2` (sezione 19).
- [ ] Calcolare DefenseScore da Mv_Weighted (sezione 17).
- [ ] Calcolare `Rank_Role` (primario) e `Rank` globale (informativo) con tie-break deterministico (sezione 12.0bis).
- [ ] Popolare `RoleMedianRating` e i campi previsti per i NEW (sezione 21.3).
- [ ] Eseguire i controlli di qualità, inclusi quelli bloccanti su range e distribuzioni (sezione 22).
- [ ] Esportare `ranking_dataset.csv`, ordinato per R + Rank_Role (sezione 21).

**Fase 4 — Validazione**
- [ ] Costruire l'universo di test dalle quotazioni pre-stagione, non dalle statistiche consuntive (sezione 20.1, evita survivorship bias).
- [ ] Calcolare e riportare il Coverage del test, per ruolo (sezione 20.1).
- [ ] Implementare il target come percentile di Fm per ruolo nella stagione target e convertire le baseline nello stesso spazio (sezione 20.4.0) — **prima** di calcolare qualunque metrica.
- [ ] Simulare previsione 2025/26 usando solo 2023/24+2024/25; se i dati bastano, eseguire anche train=[2023/24]→target=2024/25 (sezione 20.2, rolling parametrico).
- [ ] Separare performance outcome (Pv≥1 nel target) da availability outcome (tutto l'universo quotato, inclusi Pv=0) — sezione 20.3.
- [ ] Calcolare Pearson, Spearman, MAE, Median AE **per ruolo** nello spazio percentile (sezione 20.4.1, Test A).
- [ ] Calcolare precision@N con N dimensionato sul ruolo e la Top-N Availability Rate corrispondente (sezione 20.4.2, Test B).
- [ ] Calcolare le baseline 0/1/2 e verificare che il modello le batta in almeno 3 ruoli su 4 (sezione 20.4.3, Test C — bloccante).
- [ ] Eseguire l'ablation Model 1/2/3 e le varianti 3a/3b/3c (sezione 20.4.4, Test D) e il controllo doppio conteggio del BonusProfile (sezione 11.4).
- [ ] Eseguire il test diretto della Reliability contro `Pv_target` e contro la baseline `Pv_Last_Season` (sezione 20.6bis).
- [ ] Testare `performance.min_pv_for_percentile` e `bonus_profile.min_pv_for_percentile`, indipendentemente, con valori 1, 3, 5.
- [ ] Testare `time_decay.base` (1.3 / 1.5 / 2.0 / 2.5) e `reliability.reference_pv` (25 / 30 / 34) — sezione 20.5b.
- [ ] Testare `goalkeeping.penalty_save_weight` con valori 0.00, 0.05, 0.10 (sezione 13).
- [ ] Eseguire la sensitivity analysis dei pesi e calcolare la rank correlation tra configurazioni (sezione 20.5).
- [ ] Calcolare corr(Performance, Reliability) per ruolo, come nota informativa (sezione 20.6).
- [ ] Produrre `validation_report.md` con una tabella di sintesi per ruolo e l'esito del Test C in apertura (sezione 20.7).
- [ ] Calibrare i parametri di config.yaml sulla base dei risultati.

**Fase 5 — futuro (fuori scope ora)**
- [ ] Aggiungere ruoli Mantra.
- [ ] Aggiungere età anagrafica come metadato.
- [ ] Aggiungere contesto squadra 2026/27 come fattore.
- [ ] Modello predittivo (Projected Rating).

## 26. Aggiornamento annuale

Ogni stagione la pipeline deve poter essere rieseguita aggiungendo **tre** file, senza modifiche strutturali al codice:

| File | Serve a | Disponibilità |
|---|---|---|
| statistiche della stagione conclusa | storico, Performance, BonusProfile | a fine stagione |
| quotazioni pre-stagione della stagione conclusa | righe `QUOTED_ONLY` per la Reliability (sezione 9.1bis) e universo di validazione (sezione 20.1) | era disponibile a inizio di quella stagione: **va archiviata quando esce, non recuperata dopo** |
| lista giocatori della nuova stagione | universo di produzione (sezione 2.2) | prima dell'asta |

**Nota operativa importante**: le quotazioni pre-stagione sono un dato **deperibile**. Vengono aggiornate in corso d'anno e la versione di inizio stagione può non essere più recuperabile mesi dopo. Ora che servono anche in produzione e non solo in validazione, l'archiviazione del file al momento della pubblicazione è un passo obbligatorio del ciclo annuale, non un'accortezza opzionale.

L'unico aggiornamento previsto in `config.yaml` è l'elenco delle stagioni: i pesi del decadimento esponenziale si calcolano automaticamente dalla formula della sezione 8 e non vanno rimappati a mano.

### 26.1 Cosa va riconsiderato quando la finestra storica cresce

Con N che diventa 4, 5, 6 stagioni, alcune scelte tarate su N=3 non vanno ereditate per inerzia:

- `SeasonCoverage` e `AvailabilityScore` (sezione 19) sono normalizzati su 3 e su 90 (`3 × reference_pv`): devono diventare `N` e `N × reference_pv`, altrimenti la Confidence si satura e smette di discriminare;
- con `time_decay.base = 2` e N grande le stagioni più vecchie diventano numericamente irrilevanti (con N=6 la prima pesa l'1.6%): a quel punto conviene una finestra massima (`time_decay.max_seasons`) invece di trascinare stagioni che non spostano nulla;
- il backtest rolling (sezione 20.2) guadagna un punto di valutazione per ogni stagione aggiunta: da quel momento le metriche vanno riportate come media su più test, non su un test singolo, che è statisticamente fragile;
- il tie-break e la riproducibilità (sezione 12.0bis) restano invariati, ma va rifatto il controllo sui cambi di ruolo (sezione 4.1): più stagioni significano più riclassificazioni accumulate.

## 27. Changelog di questa revisione

Modifiche rispetto alla versione precedente della specifica, raggruppate per gravità del problema risolto.

**Correzioni bloccanti**

| # | Problema | Intervento |
|---|---|---|
| 1 | La validazione confrontava `HistoricalRating` (percentili 0-100) con la Fm reale (~4-9): MAE priva di significato, precision@N e Spearman distorti dal mix di ruoli | Nuova sezione 20.4.0: target = percentile di Fm per ruolo nella stagione target; baseline convertite nello stesso spazio; tutte le metriche calcolate per ruolo |
| 2 | La Reliability era gonfiata per chi ha storico corto: chi ha giocato una sola stagione piena otteneva lo stesso punteggio di chi ne ha giocate tre | Nuova sezione 9.1bis: le quotazioni pre-stagione diventano input di produzione (sezione 2.3) e permettono di distinguere "non era in Serie A" da "era in Serie A e non ha giocato", che entra con `Reliability = 0` e peso pieno |
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
| 10 | `HistoricalRating` era descritto come "scala 0-100" pur ammettendo valori negativi | Sezione 12 e colonna CSV: range effettivo per ruolo (P 0→100, C -15→100, D/A -25→100) |
| 11 | Il QC scartava come ERROR le Fm fuori da 0-10, ma la Fm può essere legittimamente negativa | Sezione 22: WARNING su -10/+20, ERROR su -30/+30, con motivazione |

**Aggiunte**

| Aggiunta | Dove |
|---|---|
| Righe `QUOTED_ONLY` come tipo di riga esplicito del dataset long, con perimetro d'uso vincolato | Sezione 4 |
| `Coverage` del test di validazione, per ruolo, da riportare sempre | Sezione 20.1 |
| `Baseline 2: percentile(Pv_Last_Season)` — batti prima una baseline che ignora il rendimento | Sezione 20.4.3 |
| Criterio di superamento del Test C esplicitato per ruolo (3 su 4) | Sezione 20.4.3 |
| Varianti di ablation 3a/3b/3c, una scelta di modellazione alla volta | Sezione 20.4.4 |
| `time_decay.base` e `reliability.reference_pv` nella sensitivity analysis: i due parametri più impattanti non erano coperti | Sezione 20.5b |
| Test diretto della Reliability sulla disponibilità, con baseline `Pv_Last_Season` | Sezione 20.6bis |
| Trattamento dei NEW in output: `RoleMedianRating`, `Seasons_Quoted`, `Note`, e misura della quota non coperta | Sezione 21.3 |
| `ConfidenceScore` continuo esposto nel CSV oltre alla categoria discreta | Sezione 19, sezione 21 |
| `precision@N` dimensionato sulla numerosità del ruolo (N più piccoli per i portieri) | Sezione 20.4.2 |
| Controlli QC su `Rc = R+ + R-`, `Gf >= R+`, righe QUOTED_ONLY, range delle feature, coerenza Trend/Confidence | Sezione 22 |
| `RpRate = Rp / Pv` al posto di `Rp` assoluto, per coerenza con il divieto su `Gs` assoluto | Sezione 13 |
| Ciclo di aggiornamento annuale a tre file, con la nota sulla deperibilità delle quotazioni | Sezione 26 |
| Cosa riconsiderare quando la finestra storica cresce oltre 3 stagioni | Sezione 26.1 |

**Punti volutamente non modificati**

- Il vincolo della sezione 19.1 (Confidence non entra mai nel rating) resta. Diventa però sostenibile solo grazie alla correzione #2: senza di essa la Confidence sarebbe stata l'unico presidio contro una distorsione strutturale, senza avere alcun potere di correggerla.
- Il divieto di `Fm × Pv` (sezione 7) e la separazione Performance/Reliability restano il principio cardine, ma la sezione 20.6 (correlazione tra le due) e la 20.6bis vanno lette insieme: se le due dimensioni risultano molto correlate *e* la Reliability non batte `Pv_Last_Season` sulla disponibilità, la separazione è concettuale e non empirica, e il peso della Reliability va ridotto.
- Il contesto squadra, l'età e i ruoli Mantra restano fuori scope.