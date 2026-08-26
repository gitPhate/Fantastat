# Piano di revisione della spec — finestra storica a 10 stagioni

Documento di lavoro. Descrive cosa intendo cambiare in `specs/ranking_pipeline.md` ora
che sono disponibili 10 stagioni di statistiche e 11 di quotazioni, e perché.
Non è la spec: è la lista degli interventi approvati, da riportare dentro la spec.

**Stato**: decisioni della sezione 6 chiuse. Pronto per la revisione della spec.

---

## 1. Cosa è arrivato

```
data/stats/         Statistiche_Fantacalcio_Stagione_{2016_17 ... 2025_26}.xlsx   (10)
data/player_lists/  Quotazioni_Fantacalcio_Stagione_{2016_17 ... 2026_27}.xlsx    (11)
```

La spec attuale è scritta su N=3 (2023/24 → 2025/26) e dichiara esplicitamente, in
sezione 20.5, di non avere potenza statistica per calibrare quasi nulla. Quel vincolo
è la ragione principale di questa revisione.

---

## 2. Ispezione dei dati — cosa ho verificato (fatti, non ipotesi)

Tutti i numeri sotto vengono da una lettura diretta dei file.

### 2.1 Schema — stabile su tutta la finestra

Stessa intestazione in tutti i 10 file statistiche
(`Id R Rm Nome Squadra Pv Mv Fm Gf Gs Rp Rc R+ R- Ass Amm Esp Au`) e in tutti gli 11
file quotazioni (`Id R RM Nome Squadra Qt.A Qt.I Diff. Qt.A M Qt.I M Diff.M FVM FVM M`).
Nessun parser condizionale per stagione.

Unica differenza strutturale: i file fino al 2021/22 hanno anche i fogli per ruolo
`Portieri/Difensori/Centrocampisti/Attaccanti`, che duplicano `Tutti`. Si legge sempre e
solo `Tutti`.

`FVM`/`FVM M` valgono 0 in tutte le stagioni fino al 2021/22 incluso: il campo esiste ma
non è popolato. Utilizzabile solo dal 2022/23.

### 2.2 `Id` è una chiave affidabile su 10 anni — verificato

Il rischio che avevo segnalato (Id instabili su finestra lunga) non si è materializzato:

| Controllo | Risultato |
|---|---|
| Id distinti su 10 stagioni | 2306 |
| Id duplicati dentro la stessa stagione | 0 |
| Id associati a più grafie del nome | 24 — tutte varianti tipografiche (`D'Ambrosio`/`D'ambrosio`, `Leao`/`Rafael Leao`, `Coda M`/`Coda M.`) |
| Nomi associati a più Id | 4 — omonimi reali (Vergara, Gori, Buksa, Ndiaye) |

Conclusione: `Id` resta la chiave primaria (sezione 3.1) e **il nome non va mai usato come
fallback di join** — i 4 omonimi lo renderebbero scorretto proprio dove sembra comodo.

### 2.3 Cambi di ruolo — quantificati

74 Id su 2306 (3.2%) cambiano `R` almeno una volta nella finestra (Florenzi D↔C, Cuadrado
D↔C, Ilicic C↔A, ...). La sezione 4.1 esiste già per questo, ma su N=3 il fenomeno era
marginale e su N=10 non lo è: il controllo QC `role_change` va reso obbligatorio nel
report, non facoltativo.

### 2.4 Scoperta bloccante — `QUOTED_ONLY` come definito oggi ha zero membri

La sezione 9.1bis costruisce la Reliability su tre categorie di riga, di cui una è
`QUOTED_ONLY` = "presente nelle quotazioni pre-stagione, assente dalle statistiche".

**Quella categoria è vuota in tutte e 10 le stagioni.** Verificato:

| Stagione | righe stats | di cui `Pv = 0` | quotati ∉ stats |
|---|---|---|---|
| 2016/17 | 630 | 107 | **0** |
| 2017/18 | 631 | 117 | **0** |
| 2018/19 | 641 | 131 | **0** |
| 2019/20 | 684 | 153 | **0** |
| 2020/21 | 678 | 120 | **0** |
| 2021/22 | 675 | 113 | **0** |
| 2022/23 | 672 | 125 | **0** |
| 2023/24 | 664 | 120 | **0** |
| 2024/25 | 679 | 118 | **0** |
| 2025/26 | 663 | 116 | **0** |

Il file statistiche **non contiene solo chi ha giocato**: contiene l'intero universo della
stagione, con `Pv = 0` per chi non ha mai preso un voto (107-153 giocatori a stagione).
Il presupposto della spec — "le righe STATS hanno `Pv >= 1`" (sezioni 6, 8, 9.1bis) — è
falso.

Il meccanismo della 9.1bis resta giusto: una stagione in Serie A senza presenze deve
entrare nella Reliability con valore 0 e peso pieno. Cambia solo **da dove si legge**:
dalle righe `Pv = 0` del file statistiche, non da un set-difference contro le quotazioni.
È una semplificazione, non una complicazione.

### 2.5 Il foglio `Ceduti` risolve un "limite dichiarato" della spec

I file quotazioni fino al 2021/22 hanno un foglio in più, `Ceduti` (114-155 giocatori a
stagione), disgiunto da `Tutti`. Verificato: **`stats = Tutti ∪ Ceduti`, esatto, in
entrambe le direzioni**, per tutte e 6 le stagioni che hanno il foglio.

Sono i giocatori usciti dalla Serie A durante la stagione — il dato che la sezione 9.1bis
dichiara irrecuperabile:

> *"Chi viene quotato in agosto e ceduto all'estero in settembre riceve
> `Reliability_stagione = 0` senza aver avuto alcuna occasione di giocare. Le cessioni in
> uscita non sono ricostruibili con i dati di questa versione."*

Per le 4 stagioni senza il foglio (2022/23 → 2025/26) l'insieme è ricostruibile per
differenza: `stats \ quotazioni_Tutti` dà 127/125/119/131 giocatori, lo stesso ordine di
grandezza dei `Ceduti` espliciti. La distorsione è **eliminabile su tutta la finestra**.

### 2.6 Le quotazioni storiche NON sono snapshot pre-stagione

`Qt.A` (attuale) diverge da `Qt.I` (iniziale) per ~85% delle righe in tutti i file storici,
e solo per 90 righe su 516 nel file 2026/27:

| File | righe | `Qt.A ≠ Qt.I` |
|---|---|---|
| 2016/17 … 2025/26 | 513-564 | 418-473 (~85%) |
| **2026/27** | 516 | **90 (17%)** |

I file storici sono snapshot di **fine stagione**; solo il 2026/27 è una lista di inizio
stagione. La spec (sezione 26) avvertiva che le quotazioni sono un dato deperibile: la
conferma è che quello che abbiamo recuperato non è la versione di agosto.

Conseguenze da scrivere nella spec, non da nascondere:

- **`Qt.I` resta valido** come prezzo iniziale: non viene sovrascritto. Utilizzabile su
  tutte le 11 stagioni.
- **La rosa no.** L'elenco in `Tutti` è il roster di fine stagione, quindi include gli
  arrivi di gennaio. L'universo di test della sezione 20.1 diventa "chiunque sia stato in
  Serie A in un qualche momento della stagione T", non "chiunque fosse acquistabile
  all'asta di agosto".
- È comunque **molto meglio** del bias che la 20.1 vuole evitare: l'universo continua a
  includere i quotati che non hanno mai giocato, che è il punto. Ma va misurato: QC che
  conta gli arrivi tardivi e ne riporta la quota.
- Per il ranking di **produzione** 2026/27 il problema non esiste: quel file è pre-stagione.

### 2.7 Nuova baseline disponibile — il prezzo di mercato

`Qt.I` è ora disponibile per tutte le stagioni. È la baseline più severa e più onesta che
si possa chiedere a questo modello:

> il ranking batte il prezzo che il mercato aveva già messo sul giocatore prima
> dell'inizio della stagione?

La sezione 20.4 oggi confronta il modello solo con baseline interne (`Fm_Weighted`,
`Pv_Last_Season`). Aggiungo `Qt.I` (e `FVM` dal 2022/23) come baseline esterna. Se il
modello non la batte, il progetto ha un problema che nessuna metrica interna avrebbe
rivelato.

### 2.8 Il cambio di regime a 5 sostituzioni non esiste nei dati — ipotesi respinta

Avevo pianificato di verificare che le 5 sostituzioni (dal giugno 2020) avessero spostato
la distribuzione dei `Pv`, quantità su cui si calibra `reference_pv`, e di stratificare i
fold di conseguenza. **Verifica eseguita, esito negativo:**

| stagione | Pv≥1 | mediana Pv | media Pv | Pv≥25 | Pv≥30 | quota Pv=0 |
|---|---|---|---|---|---|---|
| 2016/17 | 523 | 18.0 | 18.89 | 202 | 124 | 17.0% |
| 2017/18 | 514 | 19.5 | 19.34 | 188 | 136 | 18.5% |
| 2018/19 | 510 | 19.0 | 19.39 | 195 | 121 | 20.4% |
| 2019/20 | 531 | 20.0 | 19.14 | 199 | 122 | 22.4% |
| 2020/21 | 558 | 20.0 | 18.94 | 214 | 132 | 17.7% |
| 2021/22 | 562 | 19.0 | 18.93 | 212 | 140 | 16.7% |
| 2022/23 | 547 | 21.0 | 19.75 | 224 | 148 | 18.6% |
| 2023/24 | 544 | 21.0 | 19.84 | 220 | 141 | 18.1% |
| 2024/25 | 561 | 19.0 | 19.04 | 200 | 135 | 17.4% |
| 2025/26 | 547 | 21.0 | 19.69 | 221 | 138 | 17.5% |

Nessuno scalino nel 2020: deriva lievissima e non monotòna. Il numero di sostituzioni
consentite non si traduce in un numero diverso di giocatori che prendono un voto.

**Il 2019/20 non è anomalo**: mediana 20, media 19.14, `Pv≥30` a 122 — in mezzo al range.
La stagione ha completato tutte le 38 giornate; lo stop di tre mesi è stato di calendario,
non di partite giocate. L'unico scostamento è la quota di `Pv = 0` (22.4% contro ~18%),
coerente con i 155 giocatori usciti in corsa di quell'anno.

Conseguenze: cade la stratificazione dei fold per regime, cade l'esclusione a priori del
2019/20, e `reference_pv` si calibra su tutti i fold. Questo risultato va riportato nella
spec come fatto verificato, non ripetuto come controllo da fare.

### 2.9 `left_mid_season` non è una rifinitura: è il caso prevalente

Incrocio fra le righe `Pv = 0` del file statistiche e l'insieme degli usciti in corsa
(§2.5):

| stagione | usciti | di cui `Pv=0` | `Pv=0` rimasti in A | **quota dei `Pv=0` uscita in corsa** |
|---|---|---|---|---|
| 2016/17 | 117 | 72 | 35 | 67.3% |
| 2017/18 | 118 | 73 | 44 | 62.4% |
| 2018/19 | 118 | 80 | 51 | 61.1% |
| 2019/20 | 155 | 114 | 39 | 74.5% |
| 2020/21 | 114 | 73 | 47 | 60.8% |
| 2021/22 | 125 | 74 | 39 | 65.5% |
| 2022/23 | 127 | 86 | 39 | 68.8% |
| 2023/24 | 125 | 84 | 36 | 70.0% |
| 2024/25 | 119 | 66 | 52 | 55.9% |
| 2025/26 | 131 | 81 | 35 | 69.8% |

**Fra il 56% e il 75% dei giocatori con `Pv = 0` sono usciti dalla Serie A durante l'anno.**
La regola attuale della 9.1bis (`Pv = 0` → `Reliability_stagione = 0` a peso pieno) sbaglia
quindi sulla maggioranza dei casi che colpisce, non su una coda. Nella spec è un "limite
dichiarato, distorsione conservativa"; nei dati è il caso prevalente.

Restano genuini "in Serie A tutto l'anno, mai un voto" solo 35-52 giocatori a stagione —
ed è su quelli, e solo su quelli, che la 9.1bis ha ragione.

Di quelli usciti in corsa, 27-42 a stagione hanno `1 ≤ Pv < 10` e 3-16 hanno `Pv ≥ 10`:
sono righe `PLAYED` normali e non pongono problemi.

---

## 3. Interventi sulla spec

In ordine di gravità. Il numero fra parentesi è la sezione di `ranking_pipeline.md`.

### 3.1 Bloccanti — modello dei dati

| # | Intervento |
|---|---|
| B1 | (2, 4, 6, 8, 9.1bis) Riscrivere la tassonomia delle righe sulla base della §2.4: `PLAYED` (`Pv ≥ 1`), `IN_SQUAD_NO_PLAY` (`Pv = 0`, presente in stats), `OUT` (assente). Eliminare `QUOTED_ONLY` come categoria derivata dalle quotazioni. La regola di pesatura (Performance esclude e ripesa, Reliability include a peso pieno con valore 0) resta identica. |
| B2 | (6) `Pv_Totale` va calcolato sulle righe `PLAYED`; le righe `Pv = 0` non cambiano il totale ma cambiano `Seasons_Quoted`. Riverificare che la definizione di `NEW` regga con la nuova tassonomia. |
| B3 | (9.1bis) **[deciso]** Flag `left_mid_season`, da `Ceduti` (2016/17-2021/22) o per differenza `stats \ quotazioni_Tutti` (2022/23+). Una stagione con `Pv = 0` **e** `left_mid_season = true` viene **esclusa dalla Reliability con ripesatura** — stessa regola già usata per le stagioni fuori dalla Serie A. Chi è uscito con `Pv ≥ 1` resta una riga `PLAYED` normale a peso pieno. Configurabile (`reliability.exclude_left_mid_season`, default `true`) e testabile in ablation. Rimuove il "limite dichiarato" della 9.1bis, che alla luce della §2.9 non è un limite di coda ma l'errore prevalente. |
| B4 | (2.3, 20.1) Documentare la provenienza reale delle quotazioni storiche (§2.6). Usare `Qt.I` come prezzo, dichiarare che il roster è di fine stagione, aggiungere il QC sugli arrivi tardivi. |
| B5 | (3.1) Vietare esplicitamente il join per nome (4 omonimi, §2.2). Normalizzazione della grafia solo per l'output leggibile, mai per il match. |

### 3.2 Struttura del backtest

**B6 (20.2) — Rolling window parametrico, 7 target.** `train_window` (numero di stagioni di
storico) diventa un parametro, non una costante. Con 10 stagioni e finestra 3:

| # | Target | Finestra di train | Ruolo |
|---|---|---|---|
| 1 | 2019/20 | 2016/17-2018/19 | selezione |
| 2 | 2020/21 | 2017/18-2019/20 | selezione |
| 3 | 2021/22 | 2018/19-2020/21 | selezione |
| 4 | 2022/23 | 2019/20-2021/22 | selezione |
| 5 | 2023/24 | 2020/21-2022/23 | selezione |
| 6 | 2024/25 | 2021/22-2023/24 | selezione |
| 7 | **2025/26** | 2022/23-2024/25 | **lock-box** |

**Nessuna esclusione a priori** (§2.8): il 2019/20 entra come tutti gli altri. Se emerge
come outlier nelle metriche per fold, lo si constata a posteriori e lo si dichiara nel
report — non lo si toglie in anticipo sulla base di un'anomalia che i dati non mostrano.
Da 2 fold si passa a **6 di selezione + 1 di conferma**.

**B7 — soppresso.** La verifica del cambio di regime è stata eseguita (§2.8) e l'esito è
negativo. Va nella spec come fatto accertato, non come controllo pendente.

**B8 (20.2) — `train_window` è esso stesso un parametro da testare.** Con N=3 la domanda
"quante stagioni di storico servono" non era ponibile. Ora si testa
`train_window ∈ {2, 3, 4, 5}`, in griglia con `time_decay.base` perché i due interagiscono
direttamente. Nota: `train_window` maggiore riduce il numero di target disponibili
(`target = N − train_window`), quindi il confronto fra finestre diverse va fatto sui soli
target comuni a tutte le varianti, altrimenti si confrontano medie calcolate su fold
diversi.

**B9 (20.4) — Baseline `Qt.I`** (§2.7), per ruolo, su tutti i fold, accanto alle baseline
interne esistenti. `FVM` come baseline aggiuntiva sui soli fold dal 2022/23.

### 3.3 Regola di selezione

**B10 (20.5) — [deciso]** Il vincolo attuale ("solo `time_decay.base` e `reference_pv` sono
candidati a modifica") era la risposta corretta a 2 fold. Con 6 va rilassato, non rimosso:

- **Lock-box su 2025/26.** La selezione usa i target 2019/20 → 2024/25. Il fold 2025/26
  **non viene mai guardato durante la calibrazione** e si apre una sola volta, a
  configurazione congelata. È il fold la cui finestra di training (2022/23-2024/25) è
  strutturalmente identica a quella di produzione (2023/24-2025/26 → 2026/27): la conferma
  avviene quindi esattamente sullo scenario d'uso reale.
- **Criterio di fallimento del lock-box, da fissare prima di aprirlo**: se sul fold di
  conferma il modello non batte le baseline della sezione 20.4 in almeno 3 ruoli su 4, non
  si ritocca un parametro — si torna alla struttura del modello. Definirlo in anticipo è
  ciò che rende il lock-box qualcosa di diverso da un settimo fold.
- **Regola di accettazione**: un default si cambia solo se il miglioramento è concorde in
  segno su ≥ 4 dei 6 fold di selezione **e** vale in ≥ 3 dei 4 ruoli.
- **Metriche sempre per fold e per ruolo.** Si può riportare la mediana, ma **solo
  affiancata** ai valori per fold e a una misura di dispersione. Fra due configurazioni con
  mediana simile va preferita quella con dispersione minore fra fold.
- **Ordine fisso di calibrazione**, dal più strutturale al meno:
  `train_window × time_decay.base` → `reliability.function × reference_pv` →
  `bonus_weight` (griglia B12) → `min_pv_for_percentile` → `penalty_save_weight` →
  pesi della formula. Un parametro si fissa e non si ritocca dopo aver visto i successivi.
- Il paragrafo del `validation_report.md` che dichiara i limiti resta, aggiornato: da "non
  ho potenza statistica" a "ecco cosa ho calibrato, su quali fold, e cosa ho tenuto al
  default".

### 3.4 La review di GPT 5.6 — cosa recepisco

| # | Intervento |
|---|---|
| B11 | (12.1, 21) **Rimuovere `AuctionRating` dall'output.** Una colonna duplicata con un nome che promette di più è un rischio in asta. Resta la nota architetturale in 12.1; sparisce la colonna dal CSV. |
| B12 | (11.3, 12, 20.4.4) **[deciso]** Il peso del BonusProfile si calibra con una **griglia unica `{0, 0.10, 0.15, 0.25, 0.35}`** per D e A. Lo `0` **è** l'ablation: "serve?" e "quanto pesa?" diventano un solo test invece di due. Default pre-registrato **0.15** (allineato a C). Con 6 fold di selezione la griglia ha potenza sufficiente; con 2 non l'avrebbe avuta, ed è il motivo per cui la spec attuale si limitava a un on/off. |
| B13 | (6) `STORICO` → `PV_SUFFICIENTI`. Il nome attuale suggerisce che sopra 15 presenze il dato diventi affidabile, cosa che la soglia non misura. Cosmetico. |

Non recepisco gli altri tre punti della review perché sono già nella spec: il gate sul
rating non esiste (9.2), il vincolo su Confidence è la sezione 19.1, e la regola di
selezione anti-overfitting è la 20.5 — in versione più severa di quella proposta.

### 3.5 Adeguamento a N=10

**B14 (19, 26.1).** `SeasonCoverage` e `AvailabilityScore` sono normalizzati su 3 e su
`3 × reference_pv`: vanno parametrizzati su `train_window`, altrimenti la Confidence satura
e smette di discriminare. Con `time_decay.base = 2` e finestra lunga le stagioni vecchie
pesano ~1%: introdurre `time_decay.max_seasons` invece di trascinarle. La 26.1 già anticipa
entrambi i punti — vanno attuati.

---

## 4. Cosa NON faccio

- Nessuna feature nuova nel rating. Il perimetro resta Performance / Reliability /
  BonusProfile, con Trend, Confidence e DefenseScore come metadati.
- Nessun modello predittivo (`ProjectedRating`): resta fuori scope.
- Nessun uso dei ruoli Mantra.
- Non uso tutte e 10 le stagioni per il ranking finale 2026/27. Le 10 stagioni servono a
  **scegliere** i parametri; il ranking di produzione userà la finestra che il backtest
  avrà indicato (`train_window`, plausibilmente 3-5).
- Non recupero le quotazioni di agosto storiche: non esistono più (§2.6). Il limite si
  dichiara, non si finge di risolverlo.

---

## 5. Ordine di lavoro

1. **Revisione della spec** con gli interventi B1-B14. Nessun codice prima.
2. **Layer di ingestione + QC** (sezione 22): lettura dei 21 file, tassonomia righe della
   §2.4, flag `left_mid_season`, controlli su Id/omonimi/cambi ruolo, QC arrivi tardivi,
   report QC. È il punto in cui le scoperte §2.4-2.6 e §2.9 vanno confermate su tutte le
   stagioni, non solo sui campioni ispezionati.
3. **Pipeline di rating** parametrica sulle stagioni.
4. **Backtest rolling** sui 6 fold di selezione, nell'ordine di calibrazione di B10,
   lock-box chiuso.
5. **Apertura del lock-box** sul 2025/26, una volta sola, con il criterio di fallimento
   già fissato.
6. **Ranking di produzione** 2026/27 con la configurazione congelata.

Il passo 2 può far emergere altre sorprese come la §2.4. Se succede, si torna al passo 1
prima di proseguire: non si aggiustano in corsa regole che stanno nella spec.

---

## 6. Decisioni prese

| # | Decisione | Esito |
|---|---|---|
| 1 | Lock-box | **Sì, su 2025/26.** 6 fold di selezione, 1 di conferma indipendente sul fold con finestra identica alla produzione. Criterio di fallimento da fissare prima dell'apertura (B10). |
| 2 | Fold 2019/20 | **Incluso, nessuna esclusione a priori.** I dati non mostrano l'anomalia ipotizzata (§2.8). Eventuali outlier si constatano a posteriori dalle metriche per fold. |
| 3 | Usciti in corsa | **Esclusione della stagione dalla Reliability con ripesatura**, per i soli `Pv = 0`. Chi è uscito con `Pv ≥ 1` resta `PLAYED` a peso pieno (B3). |
| 4 | BonusProfile D/A | **Griglia unica `{0, 0.10, 0.15, 0.25, 0.35}`**, dove `0` è l'ablation. Default pre-registrato 0.15 (B12). |
