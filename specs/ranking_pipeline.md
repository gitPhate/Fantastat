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

### 2.3 Quotazioni pre-stagione (per validazione, non per il ranking finale)

Oltre alle statistiche consuntive, sono disponibili le **quotazioni pubblicate prima dell'inizio di ciascuna stagione** (fonte Fantacalcio.it), per almeno:

```
raw/quotazioni/Quotazioni_Fantacalcio_2023_24.xlsx
raw/quotazioni/Quotazioni_Fantacalcio_2024_25.xlsx
raw/quotazioni/Quotazioni_Fantacalcio_2025_26.xlsx
```

Queste liste rappresentano l'universo di giocatori **noto prima che la stagione iniziasse**, cioè includono anche chi poi non ha effettivamente giocato (infortuni, esclusioni, cessioni). Sono strutturalmente diverse dai file statistiche (sezione 2.1), che invece contengono solo chi ha ricevuto almeno un voto.

Questa fonte **non entra nel dataset di produzione** (che usa la lista 2026/27, sezione 2.2). Serve esclusivamente a costruire correttamente l'universo dei test di validazione retrospettiva (sezione 20), evitando il survivorship bias descritto lì.

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

## 5. Join con la stagione corrente

```
storico 2023/24 + storico 2024/25 + storico 2025/26
        ↓
dataset storico unico (long format)
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
| STORICO | Pv totale ≥ 15 su almeno le stagioni disponibili | Rating calcolato normalmente |
| LIMITED_HISTORY | Pv totale tra 1 e 14 | Rating calcolato ma marcato con Confidence bassa |
| NEW | Nessuna presenza in nessuna delle 3 stagioni (giocatore non trovato nello storico) | Nessun rating storico; campo Rating = null, categoria esplicita |

La soglia di 15 Pv totali è un parametro configurabile, non hard-coded.

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

**Gestione stagioni mancanti**: se un giocatore non ha tutte e 3 le stagioni (es. arrivato in Serie A nel 2024/25), i pesi delle stagioni disponibili vengono **ripesati proporzionalmente** (rinormalizzati a somma 1), non trattati come zero.

Esempio: solo 2024/25 e 2025/26 disponibili → pesi ripesati a 2/6 ≈ 33.3% e 4/6 ≈ 66.7%.

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

La Reliability storica complessiva è la media pesata (stessi pesi temporali della sezione 8) delle Reliability di stagione.

Questo score è solo un punto di partenza: va validato/calibrato nella fase di validazione retrospettiva (sezione 20).

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

La Mv viene mantenuta come metrica separata (pesata con gli stessi pesi temporali → `Mv_Weighted`), usata esclusivamente per il Modificatore Difesa (sezione 13), mai fusa nel Performance score.

## 11. Bonus Profile

Il Bonus Profile non deve sommarsi alla Fm (che già incorpora bonus/malus) — funziona come **modulatore basato sullo scarto dalla mediana di ruolo**, con peso e comportamento diversi per ruolo. Deve avere una formula matematica precisa (non un "eventuale contributo" vago) e va normalizzato sulla stessa scala di Performance/Reliability prima di entrare nella formula del rating.

### 11.1 Calcolo base

Per ogni stagione, calcolare tassi normalizzati sulle presenze (in assenza dei minuti giocati):

```
GoalRate = Gf / Pv
AssistRate = Ass / Pv
```

Gestire Pv = 0 evitando divisioni per zero (risultato: null/non calcolabile, non zero).

### 11.1bis Filtro sul campione (stesso problema della sezione 10, applicato qui)

Un giocatore con `Pv = 1, Gf = 1` avrebbe `GoalRate = 1.00`, un valore matematicamente enorme ma privo di significato statistico — un singolo episodio, non un tasso stabile. Applicare lo stesso filtro della sezione 10:

```
bonus_profile:
  min_pv_for_percentile: 1   # parametro indipendente da performance.min_pv_for_percentile, da calibrare separatamente
```

Includere nel calcolo del percentile di GoalRate/AssistRate solo i giocatori con `Pv ≥ min_pv_for_percentile` (parametro configurabile, non necessariamente uguale a quello usato per la Performance in sezione 10 — vanno testati e calibrati indipendentemente in validazione). Per questa v1 non sono richieste tecniche più sofisticate (shrinkage bayesiano, winsorization): il filtro sul Pv minimo è sufficiente e più semplice da validare; eventuali raffinamenti sono rimandati a versioni future.

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

Tutti i pesi sono configurabili in un unico punto del codice (config.yaml), non sparsi/hard-coded nella logica.

Il rating è calcolato solo per giocatori STORICO o LIMITED_HISTORY. Per i NEW il campo resta nullo con categoria esplicita.

### 12.0bis Tie-break deterministico per il Rank

Il calcolo di `Rank`/`Rank_Role` (sezione 21) deve usare un ordinamento con criteri di spareggio espliciti e deterministici, per garantire che la stessa pipeline produca sempre lo stesso risultato anche in presenza di valori di rating identici o molto vicini:

```
ORDER BY HistoricalRatingRaw DESC, Performance DESC, Reliability DESC, Id ASC
```

Per i giocatori con `Categoria = NEW` (HistoricalRating nullo), `Rank` e `Rank_Role` restano `null` — non vanno inseriti in coda con un numero convenzionale, per non suggerire un ordinamento che non è stato realmente calcolato.

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
FmPercentile_norm = percentile(Fm) / 100
GsRatePercentile_norm = percentile(GoalsConcededRate) / 100
RpPercentile_norm = percentile(Rp) / 100

Performance_Portiere = fm_weight × FmPercentile_norm
                      + gs_weight × (1 - GsRatePercentile_norm)
                      + rp_weight × RpPercentile_norm
```

dove `GoalsConcededRate = Gs / Pv` (percentile invertito: meno gol subiti per presenza = meglio, rispetto agli altri portieri della stessa stagione). Il risultato è in range [0, 1], coerente con Performance degli altri ruoli.

**Pesi di partenza** (configurabili in config.yaml):

| Componente | Peso |
|---|---|
| fm_weight | 0.75 |
| goals_conceded_weight | 0.20 |
| penalty_save_weight | 0.05 |

**Attenzione a Rp (rigori parati)**: è un segnale statisticamente rumoroso su due fronti — non essendo disponibile il numero di rigori affrontati non si può calcolare una vera percentuale di parate, e trattandosi di un evento raro e discreto (spesso 0, 1 o 2 in una stagione) il percentile può risultare instabile per via dei numerosi pareggi. Il peso di partenza è stato abbassato a 0.05 (rispetto a una prima ipotesi di 0.10) proprio per questo motivo. In fase di validazione, applicare la stessa logica di ablation della sezione 20: testare esplicitamente `penalty_save_weight = 0.00 / 0.05 / 0.10` e verificare se il contributo migliora davvero il potere predittivo del backtest o va rimosso.

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

```
Trend_Value = Performance_ultima_stagione_disponibile - Performance_prima_stagione_disponibile
```

dove "prima stagione disponibile" indica la prima stagione con dati per quel giocatore, non necessariamente 2023/24 (in caso di storico incompleto, sezione 8). Esporre nel CSV finale sia il valore quantitativo `Trend_Value` sia l'etichetta discreta `Trend_Label`, per permettere sia un confronto numerico sia una lettura rapida.

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
SeasonCoverage = seasons_available / 3                                    # range 0-1
AvailabilityScore = min(1, Pv_totale / 90)                                # 90 ≈ 3 stagioni "piene" da reference_pv=30 cad., range 0-1
StabilityScore = 1 - min(1, Fm_variance_normalizzata)                     # range 0-1, alta varianza → stabilità bassa

ConfidenceScore = 0.40 × SeasonCoverage + 0.40 × AvailabilityScore + 0.20 × StabilityScore
```

Poi, discretizzazione per il CSV:

| ConfidenceScore | Confidence |
|---|---|
| ≥ 0.75 | Alta |
| ≥ 0.50 e < 0.75 | Media |
| < 0.50 | Bassa |

Questa è una **ipotesi di partenza dichiarata**, non un calcolo definitivo — sia i pesi (0.40/0.40/0.20) sia le soglie (0.75/0.50) vanno validati ed eventualmente ricalibrati con l'evidenza del backtest (sezione 20), esattamente come gli altri parametri del modello. L'obiettivo qui è avere qualcosa di semplice e trasparente da cui partire, non di ottimizzare la Confidence come se fosse essa stessa un modello separato da mesi di lavoro.

Il CSV finale espone solo la categoria discreta; lo score continuo può restare nel dataset intermedio per debug.

### 19.1 Confidence non entra mai nel calcolo del Rating (vincolo esplicito)

`Confidence` è un indicatore della robustezza informativa del rating, calcolato a valle e in parallelo a `HistoricalRating` — non entra in nessuna formula che produce `HistoricalRating`, `Performance`, `Reliability` o `BonusProfile`. In particolare, **non è ammessa alcuna forma di `Rating × Confidence`** o simili combinazioni moltiplicative: questo reintrodurrebbe esattamente il tipo di accoppiamento arbitrario tra dimensioni concettualmente distinte che il principio della sezione 7 vieta esplicitamente. Confidence serve a rispondere a "quanto mi fido di questo numero", non a modificare il numero stesso.

## 20. Validazione retrospettiva (il cuore del progetto, non una fase finale)

Questa fase non va trattata come un controllo a posteriori, ma come il criterio che decide se il modello merita di essere usato così com'è o va semplificato. Un modello che "sembra ragionevole" ma non prevede meglio di una baseline banale non ha valore aggiunto.

### 20.1 Universo di test — evitare il survivorship bias

**Problema**: se l'universo di test per "2023/24+2024/25 → prevedi 2025/26" viene costruito usando i giocatori presenti nel file statistiche 2025/26 (cioè chi ha effettivamente ricevuto un voto, Pv≥1), si introduce informazione futura — si esclude implicitamente chi era atteso in campo ma poi non ha giocato (infortuni, esclusioni, cessioni), rendendo il test artificialmente più pulito di quanto sarebbe stato in tempo reale.

**Soluzione richiesta**: costruire l'universo di test usando le **quotazioni pre-stagione** (sezione 2.3), non le statistiche consuntive. Per il test "2023/24+2024/25 → 2025/26": l'universo è la lista quotazioni di inizio 2025/26 (che include anche chi poi non ha giocato). Il confronto con la Fm reale userà poi il file statistiche 2025/26, dove i giocatori quotati ma con Pv=0 (o molto basso) sono un caso legittimo da includere nelle metriche di errore — non un errore di join da scartare, ma un segnale reale sul limite del modello (non può prevedere infortuni/esclusioni).

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

**Test A — accuratezza generale**
- correlazione (Pearson) tra HistoricalRating previsto e Fm reale della stagione target;
- correlazione di rango (Spearman), più robusta della Pearson per un ranking;
- errore medio (MAE) e mediano (Median AE).

**Test B — accuratezza di classifica**
- precision@10, precision@20, precision@30: quanti giocatori nel top-N previsto (per performance outcome) rientrano effettivamente nel top-N reale della stagione target (più informativo della sola correlazione, perché è la domanda che conta realmente per un'asta: "il mio top 20 previsto è stato davvero il top 20 reale?"). Da affiancare sempre alla Top-N Availability Rate (sezione 20.3b) per lo stesso N, così da distinguere "ho sbagliato la valutazione" da "il giocatore scelto non ha semplicemente giocato".

**Test C — baseline obbligatorie (da battere prima di considerare valido il modello)**

Prima di valutare le componenti del modello (Performance/Reliability/BonusProfile), verificare che l'intero approccio batta almeno una baseline banale:

```
Baseline 0: Fm_Last_Season          (Fm dell'ultima stagione disponibile, senza alcuna elaborazione)
Baseline 1: Fm_Weighted             (media pesata delle Fm storiche, decadimento esponenziale sezione 8, senza percentili/Reliability/BonusProfile)
```

Se il modello completo (Performance + Reliability + BonusProfile) non batte `Fm_Weighted` su Spearman e precision@20, tutta la complessità aggiuntiva (percentili per ruolo, Reliability, BonusProfile) non sta dimostrando valore reale e va rivista — indipendentemente da quanto sia concettualmente ben giustificata. Questo test decide se il progetto ha senso così com'è, non è un dettaglio opzionale.

**Test D — ablation test (obbligatorio prima di considerare il modello definitivo)**

Confrontare il potere predittivo di versioni progressive del modello, nella stessa tabella delle baseline:

```
Model 1: Performance only
Model 2: Performance + Reliability
Model 3: Performance + Reliability + BonusProfile
```

Se il passaggio 2 non migliora sensibilmente rispetto a 1, o il passaggio 3 non migliora rispetto a 2, il componente aggiuntivo non sta portando valore predittivo reale e va rivalutato (peso ridotto o rimosso), indipendentemente da quanto sembri sensato concettualmente.

**Tabella di sintesi attesa** (report finale, sezione 20.6):

| Model | Pearson | Spearman | MAE | Precision@10 | Precision@20 | Precision@30 |
|---|---|---|---|---|---|---|
| Baseline 0: Fm_Last_Season | | | | | | |
| Baseline 1: Fm_Weighted | | | | | | |
| Model 1: Performance | | | | | | |
| Model 2: + Reliability | | | | | | |
| Model 3: + BonusProfile | | | | | | |

### 20.5 Sensitivity analysis dei pesi (dopo che il modello base ha superato i test C e D)

Prima di considerare i pesi di config.yaml definitivi, verificare la stabilità del ranking rispetto a piccole variazioni. Esempio per i Difensori (pesi base 55/20/25):

```
50/25/25, 55/20/25 (base), 60/20/20
```

Per ciascuna variazione, calcolare:
- Spearman e precision@20 rispetto al target (per capire se la variazione migliora o peggiora);
- **rank correlation tra la configurazione base e la configurazione variata** (`Spearman(Rank_base, Rank_variazione)`) — più intuitiva delle sole metriche predittive per capire quanto il ranking finale "si muove" al variare dei pesi. Un valore alto (es. 0.95+) indica un modello robusto; un valore basso indica che il ranking è instabile e sensibile a scelte arbitrarie dei pesi, cosa da segnalare esplicitamente prima di usarlo per un'asta reale.

Questa fase è importante ma non bloccante quanto i test C/D: va eseguita dopo aver verificato che il modello base supera le baseline, non prima.

### 20.6 Nota informativa: correlazione tra Performance e Reliability

Aggiungere nel report, per ciascun ruolo, il calcolo di `corr(Performance, Reliability)`. Le due dimensioni sono concettualmente separate (sezione 7), ma nella realtà è plausibile che siano correlate (i giocatori più forti tendono a giocare di più, quelli fragili meno). Non è un errore da correggere, ma un'informazione da riportare: una correlazione molto alta (es. > 0.85) significa che il modello sta dando peso, indirettamente, due volte a un fenomeno in parte sovrapposto — utile saperlo per interpretare correttamente i pesi scelti, senza che questo richieda necessariamente un intervento.

### 20.7 Output della validazione

Un report (anche solo markdown o CSV) con tutte le metriche delle sezioni 20.3-20.6, per ciascun test rolling eseguito, da consultare prima di considerare i pesi di config.yaml definitivi. Questa fase serve anche a calibrare empiricamente i pesi delle sezioni 8, 9, 10, 11, 12, 13, 19 — che partono come ipotesi dichiarate, non verità.

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
| R | Ruolo Classic |
| Squadra_2026_27 | Squadra stagione corrente (se disponibile) |
| Categoria | STORICO / LIMITED_HISTORY / NEW |
| Seasons_Available | Numero di stagioni con dati disponibili per il giocatore (0-3) |
| HistoricalRating | Rating storico finale, scala 0-100 in questa esposizione (= HistoricalRatingRaw × 100, sezione 12); null se NEW |
| AuctionRating | In questa versione, identico a HistoricalRating (vedi sezione 12.1 e nota di cautela sul naming) |
| Confidence | Alta / Media / Bassa (sezione 19) |
| Performance | Performance storica pesata, scala 0-1 |
| Reliability | Reliability score, scala 0-1 (vedi nota terminologica sezione 7) |
| BonusProfile | Score bonus/malus per ruolo, normalizzato -1/+1 (sezione 11.2) |
| DefenseScore | = Mv_Weighted, per Modificatore Difesa |
| Trend_Value | Variazione quantitativa di Performance tra prima e ultima stagione disponibile |
| Trend_Label | Etichetta/simbolo andamento |
| Mv_Weighted | Mv storica pesata (decadimento esponenziale). Non è una "Mv media" in senso tradizionale, è una feature pesata a fini di modello — vedi nota 21.1 |
| Fm_Weighted | Fm storica pesata (decadimento esponenziale) |
| Pv_Weighted | Pv storiche pesate (decadimento esponenziale). **Non rappresenta una stima di partite giocate** — è una feature temporale derivata, usata solo a fini informativi/debug, non entra nel calcolo di Reliability (che usa il Pv di ogni singola stagione, sezione 9.1) |
| Pv_Totale | Somma reale di Pv su tutte le stagioni disponibili (usato per la categoria, sezione 6) |
| Pv_Last_Season | Pv dell'ultima stagione disponibile per il giocatore (dato grezzo, non pesato) |
| Fm_Last_Season | Fm dell'ultima stagione disponibile (dato grezzo, coincide con Baseline 0 della sezione 20.4) |
| Mv_Last_Season | Mv dell'ultima stagione disponibile (dato grezzo) |
| Gf_Rate | Gol per presenza, media pesata dei rate stagionali (vedi nota 21.2 sul metodo) |
| Ass_Rate | Assist per presenza, media pesata dei rate stagionali (vedi nota 21.2) |
| RigoriDipendenza | Flag/valore su dipendenza da rigori (attaccanti/centrocampisti) |
| Squadra_2023_24 / 2024_25 / 2025_26 | Storico squadre, per riferimento |

Nota: `Rating_Band` (es. Elite/A/B/C/D) è volutamente escluso da questa versione — è una classificazione decisionale che va introdotta solo dopo aver validato che `HistoricalRating` è ben calibrato (sezione 20).

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

Non serve un file Excel separato per la vista sintetica in questa versione — un CSV unico, ben ordinabile per HistoricalRating decrescente e filtrabile per R, è sufficiente sia per la consultazione manuale sia per l'uso conversazionale.

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
- nessun Id duplicato (ERROR);
- nessun Pv negativo (ERROR);
- nessuna Fm/Mv fuori range plausibile, es. 0-10 (ERROR);
- nessun ruolo R mancante per giocatori con storico (ERROR);
- nessun campo numerico interpretato come stringa (ERROR).

**Coerenza Id ↔ Nome**
- stesso Id con Nome che cambia tra stagioni (WARNING — puà rivelare un errore nel dataset sorgente, non necessariamente un problema, ma va segnalato);
- stesso Nome associato a più Id diversi (WARNING, stesso motivo).

**Join**
- quanti giocatori storici sono presenti nella lista 2026/27 (INFO);
- quanti giocatori 2026/27 risultano NEW, senza storico (INFO);
- quanti Id presenti nei file storici mostrano anomalie di identità/continuità tra stagioni, es. lo stesso Id con Nome diverso o viceversa (WARNING — collegato al controllo di coerenza Id↔Nome sopra, non una categoria QC a sé).

**Ranking**
- distribuzione di HistoricalRating per ruolo (nessun ruolo con valori anomali);
- top 20 per ruolo, controllo di sensatezza manuale;
- giocatori con Confidence bassa ma HistoricalRating alto (segnalare esplicitamente, sono i casi da guardare con più attenzione durante l'asta).

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
│   └── validation_report.csv   # metriche di backtest (sezione 20.4)
│
├── src/
│   ├── load_data.py
│   ├── merge_seasons.py
│   ├── calculate_features.py   # performance, reliability, bonus profile, goalkeeping
│   ├── calculate_rating.py
│   ├── validate.py             # validazione retrospettiva rolling, sezione 20
│   └── export_ranking.py
│
├── config.yaml                 # tutti i pesi/soglie configurabili
└── README.md                   # include i limiti dichiarati (sezioni 13, 17, 20.1)
```

## 24. Esempio config.yaml (indicativo, non esaustivo)

```yaml
seasons:
  - "2023/24"
  - "2024/25"
  - "2025/26"

time_decay:
  base: 2

reliability:
  reference_pv: 30
  function: sqrt

history:
  historical_min_pv_total: 15
  limited_max_pv_total: 14

performance:
  min_pv_for_percentile: 1   # da testare anche con 3 e 5, sezione 10

bonus_profile:
  min_pv_for_percentile: 1   # parametro indipendente da performance.min_pv_for_percentile, sezione 11.1bis
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
  penalty_save_weight: 0.05   # testare anche 0.00 e 0.10 in validazione, sezione 13

confidence:
  season_coverage_weight: 0.40
  availability_weight: 0.40
  stability_weight: 0.20
  availability_reference_pv_total: 90   # 3 stagioni × reference_pv 30
  threshold_alta: 0.75
  threshold_media: 0.50

trend:
  strong_up: 0.20
  up: 0.08
  down: -0.08
  strong_down: -0.20
```

## 25. Roadmap di implementazione

**Fase 1 — Dataset**
- [ ] Importare i tre Excel storici.
- [ ] Uniformare nomi colonne, aggiungere campo Stagione.
- [ ] Eseguire i controlli sugli Id (sezione 3.2), produrre qc_log.
- [ ] Costruire il dataset storico in formato long.
- [ ] Importare la lista 2026/27.
- [ ] Join tramite Id, classificare STORICO / LIMITED_HISTORY / NEW.

**Fase 2 — Feature**
- [ ] Calcolare Fm/Mv/Pv pesate (decadimento esponenziale, sezione 8), con ripesatura per stagioni mancanti.
- [ ] Calcolare Reliability per stagione e aggregata (sezione 9).
- [ ] Calcolare Performance come percentile Fm per ruolo/stagione (sezione 10).
- [ ] Calcolare Gf/Pv, Ass/Pv e Bonus Profile per ruolo (sezione 11).
- [ ] Calcolare Trend e flag di rischio (sezione 18).

**Fase 3 — Rating**
- [ ] Applicare le formule per ruolo (sezione 12).
- [ ] Calcolare Confidence (sezione 19).
- [ ] Calcolare DefenseScore da Mv_Weighted (sezione 17).
- [ ] Eseguire i controlli di qualità (sezione 22).
- [ ] Esportare `ranking_dataset.csv` (sezione 21).

**Fase 4 — Validazione**
- [ ] Importare le quotazioni pre-stagione (2023/24, 2024/25, 2025/26).
- [ ] Costruire l'universo di test dalle quotazioni pre-stagione, non dalle statistiche consuntive (sezione 20.1, evita survivorship bias).
- [ ] Simulare previsione 2025/26 usando solo 2023/24+2024/25; se dati sufficienti, eseguire anche train=[2023/24]→target=2024/25 (sezione 20.2, rolling parametrico).
- [ ] Separare performance outcome (Pv≥1 nel target) da availability outcome (tutto l'universo quotato, inclusi Pv=0) — sezione 20.3.
- [ ] Calcolare Pearson, Spearman, MAE, Median AE su performance outcome (sezione 20.4, Test A).
- [ ] Calcolare precision@10/20/30 e Top-N Availability Rate corrispondente (sezione 20.4, Test B).
- [ ] Calcolare le baseline Fm_Last_Season e Fm_Weighted e verificare che il modello le batta (sezione 20.4, Test C — bloccante).
- [ ] Eseguire l'ablation test Performance / +Reliability / +BonusProfile (sezione 20.4, Test D) e il controllo doppio conteggio del BonusProfile (sezione 11.4).
- [ ] Testare `performance.min_pv_for_percentile` e `bonus_profile.min_pv_for_percentile` (indipendentemente) con valori 1, 3, 5.
- [ ] Testare `goalkeeping.penalty_save_weight` con valori 0.00, 0.05, 0.10 (sezione 13).
- [ ] Eseguire sensitivity analysis dei pesi principali e calcolare rank correlation tra configurazioni (sezione 20.5).
- [ ] Calcolare corr(Performance, Reliability) per ruolo, come nota informativa (sezione 20.6).
- [ ] Produrre `validation_report.csv`/`.md` con la tabella di sintesi baseline/modelli (sezione 20.4).
- [ ] Calibrare/aggiustare i pesi in config.yaml sulla base dei risultati.

**Fase 5 — futuro (fuori scope ora)**
- [ ] Aggiungere ruoli Mantra.
- [ ] Aggiungere età anagrafica come metadato.
- [ ] Aggiungere contesto squadra 2026/27 come fattore.
- [ ] Modello predittivo (Projected Rating).

## 26. Aggiornamento annuale

Ogni stagione, la pipeline deve poter essere rieseguita aggiungendo solo il nuovo file Excel e la nuova lista giocatori, senza modifiche strutturali al codice — solo aggiornamento di `config.yaml` se necessario (es. numero di stagioni disponibili cambia i pesi del decadimento esponenziale, calcolati automaticamente dalla formula, non da rimappare a mano).