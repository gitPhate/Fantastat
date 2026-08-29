# Modello predittivo e supporto all'asta — Specifica v2

## 1. Obiettivo e rapporto con la pipeline storica

Questa specifica aggiunge un modello predittivo per la stagione 2026/27 al
progetto esistente. Non sostituisce né modifica il significato di
`HistoricalRating`: quel campo resta evidenza storica descrittiva e la sua
validazione lock-box 2025/26 resta invariata.

Il nuovo obiettivo è produrre, **prima dell'asta**, per ogni giocatore
acquistabile:

1. una previsione delle presenze (`Pv`) e della FantaMedia (`Fm`);
2. una previsione dei punti stagionali totali;
3. il surplus rispetto al giocatore di sostituzione del suo ruolo;
4. una classifica di surplus a supporto della decisione d'asta.

La stagione 2026/27 non entra nella selezione dei modelli né
nell'addestramento. È il test finale del modello una volta disponibili le sue
statistiche consuntive. I dati 2025/26 possono invece essere usati per il fit
finale, dopo aver scelto struttura e iperparametri solo sui target fino al
2024/25.

Il prodotto è un supporto all'asta pre-stagione, non un pianificatore di
formazione, panchina o sostituzioni durante l'anno e non una previsione del
prezzo di chiusura dell'asta.

## 2. Perimetro dei dati

### 2.1 Dati ammessi

Il modello usa esclusivamente i dati già presenti nel repository:

- statistiche di Serie A 2016/17--2025/26;
- listone quotazioni 2026/27, per l'universo acquistabile, `Id`, ruolo Classic
  e `Qt.I`;
- regole della lega in `docs/RULES.md`.

Non sono ammessi input manuali o fonti esterne su infortuni, trasferimenti,
minutaggio previsto, età, titolarità o forza della squadra. Il Mantra resta
fuori scope.

`Qt.I` **non è una feature predittiva** di `Pv`, `Fm` o punti stagionali. È
esposto esclusivamente come riferimento di mercato e confronto in asta.

### 2.2 Universo e ruoli

L'universo di output è il listone 2026/27. Il ruolo è sempre il ruolo Classic
2026/27 (`P`, `D`, `C`, `A`), anche quando lo storico contiene un ruolo diverso.
I join usano esclusivamente `Id`.

### 2.3 Giocatori senza dati sufficienti

Un giocatore `NEW`, senza stagioni `PLAYED` (`Pv >= 1`) nella finestra
disponibile, non riceve una previsione inventata. L'output lo include con:

- `PredictionStatus = INSUFFICIENT_HISTORY`;
- ruolo, `Qt.I` e le informazioni storiche disponibili;
- valori null per previsione, surplus e tetto d'offerta.

Un giocatore con almeno una stagione `PLAYED`, ma con storico breve, riceve
invece una previsione regolarizzata verso la media del ruolo e una confidenza
bassa. Lo storico breve non viene né ignorato né trattato come evidenza piena.

## 3. Variabili da prevedere

Il modello è deliberatamente a due stadi, per ruolo:

```text
Pv_predetta  = previsione delle presenze a voto
Fm_predetta  = previsione della FantaMedia condizionata a Pv >= 1
Punti_predetti = Pv_predetta × Fm_predetta
```

Il bersaglio storico dei punti è:

```text
Punti_reali = Fm × Pv, se Pv >= 1
Punti_reali = 0,       se Pv = 0
```

`Fm` non viene imputata nelle righe `Pv = 0`: l'assenza di una FantaMedia è
reale. Il suo effetto sul totale è già zero attraverso `Pv`.

La separazione mantiene leggibile la differenza tra un giocatore forte ma poco
disponibile e uno meno brillante ma sempre utilizzato. La moltiplicazione è
consentita qui perché il prodotto ha un nuovo significato: punti stagionali
previsti, non `HistoricalRating`.

## 4. Famiglia di modelli

Ogni ruolo ha due regressioni regolarizzate distinte: una per `Pv`, limitata
all'intervallo 0--38, e una per `Fm`. La regressione di `Fm` si addestra solo
sulle righe `PLAYED` (`Pv >= 1`); non riceve né imputa righe con `Pv = 0`.
Entrambe sono semplici, spiegabili e regolarizzate; sono esclusi modelli opachi
o complessi che non si possano giustificare con la quantità di dati disponibile.

Le feature candidate provengono dalla pipeline storica esistente, fra cui:

- valori recenti e medie temporali di `Pv`, `Fm` e `Mv`;
- performance normalizzata per ruolo;
- disponibilità, stagioni disponibili/in rosa e flag `left_mid_season`;
- trend, stabilità e bonus/malus già calcolati;
- quantità di storico e ruolo storico, inclusi i cambi di ruolo.

La scelta concreta delle feature e della regolarizzazione deve essere fatta
con backtest rolling; nessuna feature è ammessa solo perché intuitivamente
plausibile. Il modulo predittivo applica internamente trasformazioni,
regolarizzazione e limiti fisici (`Pv_predetta >= 0`): il chiamante riceve solo
le previsioni e le diagnostiche. Questo è il suo **seam** esterno, piccolo e
testabile.

## 5. Validazione e protocollo temporale

### 5.1 Selezione prima dell'asta 2026/27

Per scegliere struttura e iperparametri di v2 si usano soltanto target dal
2019/20 al 2024/25, con finestre temporali che usano esclusivamente stagioni
precedenti al target. Per ogni ruolo riportare separatamente:

- `Pv`: MAE, Median AE, Pearson e Spearman;
- `Fm`: le stesse metriche, solo dove il target ha `Pv >= 1`;
- punti totali: MAE, Median AE, Pearson, Spearman e precision@N per ruolo;
- calibrazione a bucket, coverage e dimensione del campione.

Le baseline minime sono l'ultima stagione disponibile e le medie storiche
pesate. Le metriche non vanno aggregate fra ruoli o fra fold: mediana e
dispersione possono essere una sintesi aggiuntiva, mai il solo risultato.

Il gate di selezione è fissato prima dell'esecuzione:

1. metrica primaria: MAE dei punti totali previsti;
2. baseline primaria: `Fm_ultima_stagione × Pv_ultima_stagione`, per ruolo;
3. promozione: MAE inferiore alla baseline in almeno 3 ruoli su 4, in almeno
   5 dei 6 fold di selezione;
4. guardrail: Spearman e precision@N non possono peggiorare rispetto alla
   baseline di oltre `0.05` in nessun ruolo per più di un fold.

Dopo la selezione, congelare le scelte e riaddestrare sui dati 2016/17--
2025/26. Tale fit produce il file pre-asta 2026/27.

### 5.2 Test finale

Quando saranno disponibili statistiche complete 2026/27, eseguire una sola
valutazione finale con configurazione congelata. Il report deve confrontare le
previsioni archiviate prima dell'asta con `Pv`, `Fm` e punti reali 2026/27,
usando le stesse metriche e baseline pre-registrate.

La fallita validazione lock-box del ranking storico non autorizza a ritoccare
i suoi pesi. V2 è una struttura diversa e ha il proprio test finale 2026/27.

## 6. Valore rispetto al sostituto

La lega 2026/27 ha 8 manager e ciascuna rosa contiene 3 P, 8 D, 8 C e 6 A.
I giocatori di sostituzione sono quindi i seguenti ranghi, calcolati
sull'ordinamento per `Punti_predetti` all'interno del ruolo:

| Ruolo | Posti complessivi | Rango di sostituzione |
|---|---:|---:|
| P | 24 | 24 |
| D | 64 | 64 |
| C | 64 | 64 |
| A | 48 | 48 |

Per ogni ruolo, `Punti_sostituzione` è la previsione del giocatore a quel
rango. Per ogni giocatore con previsione disponibile:

```text
Surplus_punti = Punti_predetti - Punti_sostituzione_ruolo
```

Il surplus può essere negativo e deve restare visibile: è informazione sul
valore relativo, non un errore da troncare. V2 non tenta di simulare moduli,
panchine o sostituzioni; i ranghi di sostituzione sono l'unica assunzione di
scarsità in questa fase.

## 7. Uso in asta

Il modello non calcola un prezzo equo, una previsione del prezzo di chiusura o
un tetto d'offerta. Il budget personale (500 crediti liberi più 50 vincolati
agli attaccanti) e l'andamento dell'asta sono decisioni del manager.

Il file pre-asta fornisce invece la previsione sportiva, il surplus e `Qt.I`:
il manager usa queste informazioni per stabilire, nel contesto della propria
rosa e del budget residuo, se inseguire un giocatore e fino a quale cifra.

## 8. Output pre-asta

Il file `output/projected_auction_dataset.csv` è ordinato per ruolo e surplus
decrescente e include almeno:

- `Id`, `Nome`, `R`, `Squadra_2026_27`, `Categoria`, `PredictionStatus`;
- `Pv_predetta`, `Fm_predetta`, `Punti_predetti`;
- `Punti_sostituzione`, `Surplus_punti`, `Rank_Surplus_Ruolo`;
- `Qt.I_2026_27`;
- `Confidence`, quantità di storico e flag di rischio già disponibili;
- `HistoricalRating`, `Performance`, `Reliability`, `Trend_Label` come
  spiegazione storica, senza confonderli con la previsione.

Produrre anche `output/projected_validation_report.md`, con tutti i fold di
selezione e la configurazione congelata, e conservare immutato il dataset
pre-asta usato per il test 2026/27.

## 9. Architettura prevista

La pipeline storica resta il modulo che legge, normalizza e controlla i dati.
Il nuovo modulo predittivo ne consuma l'output/feature; non duplica parser,
join per `Id` o regole di qualità.

La sua interfaccia prevista è volutamente piccola:

```text
run_projection(config_path) -> dataset_pre_asta, report_validazione
```

L'implementazione può avere seam interne per modelli di `Pv`, modelli di `Fm`
e selezione temporale, ma nessun chiamante deve conoscere i dettagli.
L'interfaccia deve essere eseguibile da CLI, riproducibile dalla configurazione
e verificabile mediante i file generati.

## 10. Decisioni ancora necessarie prima di implementare

Le scelte della v2 sono congelate prima dell'implementazione. Una futura
funzione di tetto d'offerta richiederà una nuova specifica e una nuova
validazione; non può essere aggiunta come conversione implicita del surplus.

Nessuna scelta di v2 autorizza a modificare retroattivamente la validazione o i
pesi del ranking storico v1.
