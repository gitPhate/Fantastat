# Ranking statistico dei calciatori

## 1. Obiettivo

Realizzare in Python un modello statistico semplice, trasparente e riutilizzabile
che ordini i calciatori disponibili per una stagione di Fantacalcio Classic.

Per la stagione iniziale il modello deve considerare esclusivamente i calciatori
presenti nel foglio `Tutti` di
`data/player_lists/Quotazioni_Fantacalcio_Stagione_2026_27.xlsx` e deve produrre
quattro classifiche indipendenti: portieri (`P`), difensori (`D`),
centrocampisti (`C`) e attaccanti (`A`). Le quattro classifiche condividono una
sola colonna `Rank`, che riparte da 1 per ogni ruolo.

Il ranking e' una componente quantitativa della valutazione finale del
calciatore, non una valutazione completa per l'asta.

## 2. Principi di progetto

1. **Semplicita'**: usare medie pesate, senza regressioni o machine learning.
2. **Trasparenza**: ogni posizione deve essere spiegabile mediante presenze,
   Fantamedia e pesi espliciti.
3. **Recenza**: una stagione recente deve pesare piu' di una lontana.
4. **Riproducibilita'**: stessi input e stessa configurazione devono produrre gli
   stessi CSV.
5. **Separazione per ruolo**: non confrontare calciatori di ruoli diversi.
6. **Indipendenza editoriale**: quotazioni e indici di Fantacalcio.it non devono
   entrare nel calcolo.

## 3. Ambito escluso

Il modello non deve usare:

- ruoli o quotazioni Mantra;
- modificatore difesa;
- `Qt.A`, `Qt.I`, `FVM` o altre quotazioni del listone corrente;
- prezzi delle aste storiche;
- squadra attuale come variabile predittiva;
- forza della squadra, allenatore o trasferimenti;
- eta', infortuni, probabili formazioni o fonti esterne;
- foglio `Ceduti` dei listoni;
- confronti fuzzy sul nome del calciatore.

## 4. Interfaccia a riga di comando

L'esecuzione deve richiedere soltanto la stagione obiettivo:

```powershell
python src/run_ranking.py --season 2026_27
```

Il formato accettato per la stagione e' `YYYY_YY`. Lo script deve derivare dal
valore ricevuto i nomi degli input, le stagioni storiche e i nomi degli output.
Per esempio, `--season 2027_28` deve funzionare senza modifiche al codice quando
i file richiesti saranno disponibili.

Argomenti mancanti o stagioni in formato non valido devono terminare
l'esecuzione con un messaggio di errore chiaro e un exit code diverso da zero.

## 5. Configurazione

L'implementazione deve aggiungere a `config.yaml` una sezione minima:

```yaml
ranking:
  history_window: 5
  recency_weights: [10, 5, 3, 2, 1]
  validation_folds: 5
  min_valid_folds: 3
  min_comparable_players: 10
```

I pesi sono elencati dalla stagione piu' recente alla piu' lontana. La loro
lunghezza deve coincidere con `history_window`, devono essere positivi e
strettamente decrescenti. Una configurazione non valida deve interrompere
l'esecuzione.

Questi parametri sono predefiniti dal progetto. Non devono essere scelti tramite
ottimizzazione iterativa sui risultati del backtest.

## 6. Input

Per una stagione obiettivo `YYYY_YY`, usare:

- il foglio `Tutti` di
  `data/player_lists/Quotazioni_Fantacalcio_Stagione_YYYY_YY.xlsx` come universo
  dei calciatori da classificare;
- le statistiche delle cinque stagioni immediatamente precedenti per generare
  il ranking;
- i listoni delle cinque stagioni target dei backtest e le statistiche delle
  dieci stagioni immediatamente precedenti per eseguire i cinque backtest
  obbligatori descritti nella sezione 10.

I file statistici seguono il nome
`data/stats/Statistiche_Fantacalcio_Stagione_YYYY_YY.xlsx`. I listoni storici
seguono lo stesso schema del listone corrente sotto `data/player_lists/`.

Leggere esclusivamente il foglio `Tutti`. Nei file Excel la prima riga contiene
il titolo e la seconda le intestazioni effettive (`header=1` con `pandas`).

Le sole colonne necessarie sono:

| Fonte | Colonne | Uso |
|---|---|---|
| Listone obiettivo | `Id`, `R`, `Nome`, `Squadra` | Universo e dati descrittivi |
| Listoni target dei backtest | `Id`, `R` | Universo e ruolo di ciascun fold |
| Statistiche storiche | `Id`, `Pv`, `Fm` | Calcolo delle previsioni |

L'identita' del calciatore deve essere stabilita esclusivamente tramite `Id`.
Il nome non e' una chiave e non deve essere usato come fallback.

## 7. Controlli sui dati

L'elaborazione deve fallire immediatamente in presenza di:

- un file o foglio obbligatorio mancante;
- una colonna obbligatoria mancante;
- `Id` nullo o duplicato nello stesso foglio;
- ruolo corrente diverso da `P`, `D`, `C`, `A`;
- `Pv` non numerico, negativo o maggiore di 38;
- `Fm` non numerica o mancante quando `Pv > 0`;
- un giocatore presente nel foglio `Tutti` di una stagione target del backtest
  ma assente dal corrispondente file statistico.

`Fm` mancante e' ammessa soltanto quando `Pv = 0`.

Non saltare silenziosamente righe o stagioni non valide. Il messaggio di errore
deve identificare almeno file, stagione e causa.

## 8. Calcolo della previsione

### 8.1 Finestra e pesi

Per il ranking 2026/27 usare le stagioni da 2021/22 a 2025/26 con questi pesi:

| Stagione | Peso |
|---|---:|
| 2025/26 | 10 |
| 2024/25 | 5 |
| 2023/24 | 3 |
| 2022/23 | 2 |
| 2021/22 | 1 |

Nelle stagioni successive la finestra deve avanzare automaticamente conservando
lo stesso schema di pesi.

Il decadimento accentuato e' applicato a tutti i ruoli: la forma e la
continuita' di impiego piu' recenti devono prevalere sullo storico piu' lontano,
senza introdurre regole specifiche per singoli calciatori.

### 8.2 Stagioni utilizzabili per un calciatore

Per un calciatore `i`, sia `S_i` l'insieme delle stagioni della finestra nelle
quali il suo `Id` compare nel file statistico.

- Se l'ID non compare nelle statistiche di una stagione, quella stagione e'
  esclusa: non equivale a zero presenze.
- Se l'ID compare nelle statistiche e `Pv = 0`, lo zero partecipa alla previsione
  delle presenze.
- Una riga statistica storica resta utilizzabile anche se il calciatore e' stato
  successivamente spostato nel foglio `Ceduti`: in quella stagione ha comunque
  prodotto dati reali. Il foglio `Ceduti` e' escluso soltanto dalla definizione
  dell'universo da classificare.
- Le statistiche sono utilizzabili anche se il ruolo storico e' diverso. Il
  ruolo del listone obiettivo determina esclusivamente la classifica finale.

### 8.3 Presenze previste

Per ogni calciatore con `S_i` non vuoto:

```text
PresenzePrevisteRaw_i =
    somma_s(w_s * Pv_i,s) / somma_s(w_s), per s in S_i
```

Questa e' una media delle presenze pesata soltanto per recenza.

### 8.4 Fantamedia prevista

La Fantamedia deve essere pesata sia per recenza sia per numero di presenze:

```text
FantamediaPrevistaRaw_i =
    somma_s(w_s * Pv_i,s * Fm_i,s) / somma_s(w_s * Pv_i,s), per s in S_i
```

Una stagione da poche presenze non deve avere la stessa influenza di una
stagione completa. I termini con `Pv = 0` hanno peso nullo in questa formula.

### 8.5 Presenze efficaci e punti attesi

Arrotondare prima i due componenti:

```text
PresenzePreviste_i   = round(PresenzePrevisteRaw_i, 2)
FantamediaPrevista_i = round(FantamediaPrevistaRaw_i, 2)
PresenzeEfficaci_i =
    PresenzePreviste_i,                                      se <= 30
    30 + 0.25 * (PresenzePreviste_i - 30),                    se > 30

PuntiAttesi_i = round(PresenzeEfficaci_i * FantamediaPrevista_i, 2)
```

`PresenzeEfficaci` modella l'affidabilita' di impiego: fino a 30 presenze il
contributo resta lineare, mentre le presenze ulteriori danno solo un beneficio
marginale. `PuntiAttesi` rappresenta la produzione fantacalcistica stagionale
stimata e deve essere l'unico punteggio usato per ordinare i giocatori.

### 8.6 Storico non utilizzabile

Un giocatore e' `SENZA_STORICO` quando:

- il suo ID non compare in alcun file statistico della finestra; oppure
- la somma pesata delle sue presenze e' zero, quindi non e' possibile stimare
  la Fantamedia.

Il giocatore deve restare nell'output, ma `PresenzePreviste`,
`FantamediaPrevista`, `PresenzeEfficaci`, `PuntiAttesi` e `Rank` devono essere vuoti. La sua colonna
`Validazione` deve contenere `SENZA_STORICO`.

## 9. Costruzione del ranking

1. Usare il ruolo `R` del listone obiettivo e rinominarlo `Ruolo` nell'output.
2. Per ogni ruolo, ordinare `PuntiAttesi` in ordine decrescente.
3. Assegnare un rank denso: valori uguali ricevono lo stesso rank e il valore
   successivo aumenta di uno (`1, 2, 2, 3`).
4. Determinare i pari merito usando `PuntiAttesi` gia' arrotondato a due
   decimali.
5. Ordinare alfabeticamente per `Nome` i giocatori a pari merito, senza usare
   il nome come ulteriore criterio qualitativo.
6. Far ripartire `Rank` da 1 per ogni ruolo.
7. Collocare in fondo al proprio ruolo i giocatori `SENZA_STORICO`, ordinati per
   nome e con rank vuoto.
8. Ordinare i gruppi di ruolo come `P`, `D`, `C`, `A`.

## 10. Backtest e validazione

La validazione e' obbligatoria ma non modifica il calcolo del ranking. Serve a
stabilire se il metodo pesato ha aggiunto valore rispetto a una baseline piu'
semplice.

### 10.1 Fold temporali

Per una stagione obiettivo, usare come target di backtest le cinque stagioni
immediatamente precedenti. Ogni fold deve usare esclusivamente le cinque
stagioni anteriori al proprio target.

Per il ranking 2026/27:

| Target del fold | Stagioni usate per prevederlo |
|---|---|
| 2021/22 | 2016/17-2020/21 |
| 2022/23 | 2017/18-2021/22 |
| 2023/24 | 2018/19-2022/23 |
| 2024/25 | 2019/20-2023/24 |
| 2025/26 | 2020/21-2024/25 |

Il calcolo del modello in ogni fold deve usare esattamente le formule delle
sezioni 8 e 9, senza vedere le statistiche della stagione target.

### 10.2 Baseline

La baseline usa soltanto la stagione immediatamente precedente al target:

```text
PresenzeBaseline_i   = Pv_i,t-1
FantamediaBaseline_i = Fm_i,t-1
PuntiBaseline_i      = round(PresenzeEfficaci(Pv_i,t-1) * Fm_i,t-1, 2)
```

Non applicare medie, regressioni o correzioni alla baseline.

### 10.3 Popolazione confrontabile

Per ogni fold e ruolo, valutare modello e baseline sugli stessi giocatori. Un
calciatore e' confrontabile se:

- e' presente nel foglio `Tutti` del listone della stagione target;
- il modello produce una previsione utilizzabile;
- la baseline produce una previsione utilizzabile, quindi nella stagione
  precedente ha `Pv > 0` e `Fm` disponibile;
- esiste la riga statistica della stagione target.

I punti reali della stagione target sono calcolati come
`round(PresenzeEfficaci(Pv) * Fm, 2)`. Se `Pv = 0`, i punti reali sono zero
anche quando `Fm` e' vuota. Modello, baseline e reali usano quindi la stessa
trasformazione delle presenze.

Un fold e' valido per un ruolo soltanto con almeno
`min_comparable_players = 10` calciatori e con entrambe le metriche definite.

### 10.4 Metriche

Calcolare separatamente per ogni fold e ruolo:

- **MAE dei punti**: media di `abs(PuntiPrevisti - PuntiReali)`; un valore
  inferiore e' migliore;
- **Spearman dei punti**: correlazione tra il rango dei punti previsti e il rango
  dei punti reali; un valore superiore e' migliore.

Per non introdurre dipendenze aggiuntive, calcolare Spearman assegnando rank
medi ai pari merito e applicando poi la correlazione Pearson ai due vettori di
rank. Se la correlazione non e' definita, il fold non e' valido per quel ruolo.

Aggregare i fold validi mediante la mediana, separatamente per modello e
baseline.

### 10.5 Stato di validazione per ruolo

Lo stato di un ruolo e':

- `VALIDAZIONE_INSUFFICIENTE` se ha meno di `min_valid_folds = 3` fold validi;
- `VALIDATO` se ha almeno 3 fold validi, il MAE mediano del modello e'
  strettamente inferiore a quello della baseline e la Spearman mediana del
  modello e' strettamente superiore a quella della baseline;
- `NON_VALIDATO` in tutti gli altri casi.

Non sostituire automaticamente il modello con la baseline se la validazione
fallisce. Il ranking deve essere prodotto comunque e deve riportare lo stato
del proprio ruolo. Un risultato `NON_VALIDATO` non deve essere presentato come
componente affidabile della valutazione finale.

Per ogni giocatore con previsione utilizzabile, copiare nella colonna
`Validazione` lo stato del suo ruolo. Per un giocatore senza previsione, usare
sempre `SENZA_STORICO`.

## 11. Output

### 11.1 Ranking

Generare `output/ranking_<stagione>.csv`, per esempio
`output/ranking_2026_27.csv`, con codifica UTF-8 e queste colonne, in questo
ordine:

| Colonna | Contenuto |
|---|---|
| `Id` | Identificativo Fantacalcio.it |
| `Nome` | Nome dal listone obiettivo |
| `Squadra` | Squadra dal listone obiettivo |
| `Ruolo` | `P`, `D`, `C` o `A` dal listone obiettivo |
| `Rank` | Posizione densa all'interno del ruolo; vuota senza storico |
| `PresenzePreviste` | Media pesata, due decimali |
| `FantamediaPrevista` | Media pesata, due decimali |
| `PresenzeEfficaci` | Presenze trasformate dalla curva di affidabilita', due decimali |
| `PuntiAttesi` | Prodotto di `PresenzeEfficaci` e `FantamediaPrevista`, due decimali |
| `Validazione` | Stato del ruolo oppure `SENZA_STORICO` |

### 11.2 Validazione

Generare `output/validation_<stagione>.csv`, per esempio
`output/validation_2026_27.csv`, con una riga per ruolo e queste colonne:

| Colonna | Contenuto |
|---|---|
| `Ruolo` | `P`, `D`, `C` o `A` |
| `FoldValidi` | Numero di fold usati nell'aggregazione |
| `MAE_Modello_Mediana` | Mediana dei MAE del modello |
| `MAE_Baseline_Mediana` | Mediana dei MAE della baseline |
| `Spearman_Modello_Mediana` | Mediana delle Spearman del modello |
| `Spearman_Baseline_Mediana` | Mediana delle Spearman della baseline |
| `Validazione` | Stato assegnato al ruolo |

Le metriche devono essere arrotondate a quattro decimali nel CSV di
validazione.

Entrambi gli output devono essere sovrascritti a ogni esecuzione riuscita. Per
evitare un ranking aggiornato e una validazione vecchia, scrivere i file finali
soltanto dopo che calcolo e controlli sono terminati con successo.

## 12. Dipendenze e struttura tecnica

Usare soltanto:

- libreria standard Python;
- `pandas`;
- `openpyxl`.

Non aggiungere `scikit-learn`, SciPy o framework di machine learning. Il punto
di ingresso deve essere `src/run_ranking.py`. La logica puo' essere separata in
un piccolo modulo testabile, ma non deve essere suddivisa in livelli o
astrazioni che non servono al calcolo descritto.

## 13. Test automatici minimi

L'implementazione deve verificare almeno:

1. associazione dei pesi `10, 5, 3, 2, 1` alle stagioni corrette;
2. esclusione dal denominatore di una stagione in cui l'ID non era nelle
   statistiche;
3. inclusione di `Pv = 0` quando l'ID era nelle statistiche;
4. Fantamedia pesata per `peso * Pv`, non soltanto per stagione;
5. utilizzo dello storico anche dopo un cambio di ruolo;
6. calcolo della curva di `PresenzeEfficaci` e arrotondamento riproducibile di `PuntiAttesi`;
7. reset del rank per ruolo, rank denso e pari merito;
8. giocatori `SENZA_STORICO` presenti ma non classificati;
9. esclusione del foglio `Ceduti` e delle colonne Mantra/quotazione;
10. confronto tra modello e baseline sulla stessa popolazione;
11. assegnazione dei tre stati di validazione di ruolo;
12. errore esplicito per file, colonne, duplicati e valori obbligatori non
    validi;
13. derivazione corretta degli input e output per una stagione futura;
14. maggiore priorita' del rendimento recente anche quando due calciatori hanno
    uno storico di lunghezza diversa.

## 14. Criteri di accettazione

L'implementazione e' conforme quando:

- il comando della sezione 4 termina con successo sui dati disponibili;
- vengono creati entrambi i CSV con schema e ordinamento specificati;
- il ranking contiene esattamente gli ID del foglio `Tutti` della stagione
  obiettivo, una sola volta ciascuno;
- `Rank` riparte da 1 per ogni ruolo ed e' determinato esclusivamente da
  `PuntiAttesi`;
- per ogni riga classificata vale, dopo gli arrotondamenti specificati,
  `PuntiAttesi = PresenzeEfficaci * FantamediaPrevista`;
- nessuna colonna esclusa nella sezione 3 influenza il risultato;
- tutti i test automatici passano;
- una seconda esecuzione con gli stessi input produce file equivalenti;
- l'esecuzione con una stagione futura non richiede modifiche al codice.

## 15. Limiti dichiarati

Il modello estrapola soltanto continuita' di impiego e rendimento storico. Non
puo' conoscere cambi di gerarchia, nuovi allenatori, infortuni correnti,
adattamento alla Serie A o altri eventi futuri. I calciatori senza storico utile
restano intenzionalmente non classificati. Questi limiti sono coerenti con lo
scopo: fornire un segnale quantitativo semplice e indipendente da integrare con
altre valutazioni.
