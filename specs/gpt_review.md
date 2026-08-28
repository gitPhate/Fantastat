# Work order — correzioni a `specs/ranking_pipeline.md`

**Chi legge questo documento:** l'agente che deve modificare `specs/ranking_pipeline.md`.

**Cosa è questo documento.** Una review esterna della spec (GPT 5.6) è stata verificata riga per riga contro il testo reale della spec. Di 13 item proposti, **3 sono validi**, **6 erano già presenti nella spec** (spesso in forma più completa di quanto la review proponesse), **1 è cosmetico**, **1 è correttamente rimandato a v2**, e **2 item sono stati riformulati** perché la review aveva individuato il sintomo ma sbagliato il bersaglio. Alla verifica sono emersi inoltre **5 problemi che la review non aveva visto**, di cui uno bloccherebbe la pipeline alla prima esecuzione su dati corretti (item 1, punto 5).

Questo documento contiene **solo ciò che va effettivamente cambiato** (sezione 1), più l'elenco esplicito di **ciò che NON va toccato** (sezione 2). La sezione 2 è vincolante come la sezione 1: diversi item della review originale chiedevano di aggiungere contenuto che la spec già contiene, e riscriverlo produrrebbe duplicazione e contraddizioni.

## Regole di esecuzione

1. **La spec è in italiano.** Ogni testo aggiunto o riscritto va scritto in italiano, nello stesso registro del resto del documento (tono operativo, grassetto sui vincoli, motivazione sempre esplicita dopo la regola). Non introdurre terminologia inglese nuova oltre a quella già in uso (`Performance`, `Reliability`, `BonusProfile`, `HistoricalRating`, `lock-box`, `midrank`, ecc.).
2. **Nessuna riscrittura globale.** Interventi chirurgici sulle sezioni indicate. Non riordinare sezioni, non rinumerare, non riformattare parti non interessate.
3. **Propagare la coerenza.** Ogni item elenca i "siti di coerenza": punti del documento che affermano la stessa cosa e che diventerebbero falsi se corretti solo nel punto principale. Vanno aggiornati tutti nello stesso intervento.
4. **Nessuna decisione lasciata implicita.** Dove l'item chiede di definire un algoritmo o una convenzione, va scritta la formula, non la descrizione della formula. Il criterio è: due implementazioni indipendenti devono produrre lo stesso numero.
5. **Changelog.** Al termine, aggiungere una nuova sezione `## 30. Changelog della revisione corrente — correzioni post-review` in coda al documento, con la stessa struttura tabellare delle sezioni 27-29 (colonne `# | Problema | Intervento`), una riga per ciascuno dei 7 item della sezione 1. Aggiungere in quella sezione anche un blocco `**Punti volutamente non modificati**` che riprenda in forma sintetica la sezione 2 di questo documento, così che la scelta di non intervenire resti tracciata e non venga riaperta dalla prossima review.
6. **Non toccare i parametri calibrati.** Nessun default numerico del modello (`bonus_weight`, `time_decay.base`, `reference_pv`, pesi della formula, soglie di Confidence) cambia in questo intervento, con l'unica eccezione dei nuovi parametri introdotti dall'item 1 (clip, severità di `max_zero_share`), dall'item 4 (`precision@N` per i portieri) e dall'item 7 (soglie dei flag di rischio).

---

## 1. Interventi richiesti

Ordine di esecuzione consigliato: 1 → 2 → 7 → 3 → 4 → 5 → 6. Gli item **1, 2 e 7** sono bloccanti per l'implementazione delle Fasi 1-3 della roadmap (sezione 25); **3** è bloccante per la Fase 4 (validazione); **4, 5, 6** riguardano la Fase 4 e vanno chiusi prima di congelare la configurazione, ma non impediscono di iniziare a scrivere codice.

### Item 1 — `BonusProfile` esce dal range dichiarato `[-1, +1]` (bug matematico)

**Problema.** Con `zero_handling = recenter` (default, sezione 11.2), la sequenza è:

```
BonusProfile_stagione grezzo        ∈ [-50, +50]
mediana_ruolo_stagione(grezzo)      ∈ [-50, +50]
centrato = grezzo - mediana         ∈ [-100, +100]    ← non [-50, +50]
normalized = centrato / 50          ∈ [-2, +2]        ← non [-1, +1]
```

Il caso non è teorico: è esattamente lo scenario che `recenter` esiste per risolvere. Per i difensori la mediana di ruolo è spostata verso il basso (è il problema descritto nella nota "0 = mediana di ruolo non è vero per i difensori"); con una mediana attorno a -20, il difensore al vertice della distribuzione ottiene `(50 - (-20)) / 50 = +1.4`. Più il blocco a `rate = 0` è grande — cioè più `recenter` è necessario — più il range sfonda.

**Conseguenza.** Tre affermazioni della spec sono attualmente false, non una:

- `BonusProfile ∈ [-1, +1]` (sezione 10, "Importante — scale esplicite"; sezione 11.2; sezione 12, preambolo alla formula);
- la tabella degli span della sezione 11.3 (`Span BonusProfile = peso × 2 = 0.30`), che sottostima l'escursione reale del termine — cioè proprio la quantità che quella tabella è stata scritta per tenere sotto controllo;
- la tabella "Range effettivo di `HistoricalRating`" della sezione 12 (`-15 → 100` per D/C/A), che dipende direttamente dal range di `BonusProfile`.

**Intervento richiesto.**

1. In sezione 11.2, dopo il blocco `zero_handling`, definire esplicitamente la normalizzazione post-centratura in modo che il range dichiarato sia garantito **per costruzione**, non per assunzione. Adottare la variante più semplice difendibile:

   ```
   BonusProfile_normalized = clip(centrato / 50, -1, +1)
   ```

   e dichiarare che il clip è parte della definizione della metrica, non un tampone difensivo in fase di implementazione.

2. Introdurre il parametro di configurazione e il relativo controllo QC:
   - nuovo QC in sezione 22, **livello WARNING**: per ogni ruolo e stagione, riportare la quota di giocatori con `|centrato / 50| > 1` (cioè effettivamente clippati). Se supera `bonus_profile.max_clipped_share` (default `0.05`), il clip non è più un arrotondamento di coda ma sta comprimendo la parte alta della distribuzione, e va valutato `split` come alternativa (già in ablation, Model 3c);
   - aggiungere `bonus_profile.max_clipped_share: 0.05` all'esempio di `config.yaml` (sezione 24), accanto a `max_zero_share`.

3. Spiegare perché il clip e non una riscalatura per ruolo/stagione sul massimo osservato: una riscalatura renderebbe la scala di `BonusProfile` dipendente dall'estremo campionario di quella specifica stagione, quindi non confrontabile fra le stagioni che poi vengono aggregate con i pesi temporali della sezione 8 — introdurrebbe un secondo problema per risolverne uno. Il clip mantiene la scala fissa e rende il costo (quanti giocatori vengono compressi) misurabile e riportato.

4. **Correzione collegata e obbligatoria — la severità di `max_zero_share`** (quarto problema non individuato dalla review, e il solo che bloccherebbe la pipeline alla prima esecuzione).

   La sezione 11.2 definisce **due** condizioni per il controllo QC bloccante: quota di giocatori a `rate = 0` sopra `bonus_profile.max_zero_share` (default `0.30`) **oppure** mediana di `BonusProfile_normalized` distante da 0 più di `0.10`. Subito dopo dichiara che il default `recenter` *"garantisce il criterio del controllo QC per costruzione"*. **Non è vero: `recenter` garantisce solo la seconda condizione.** La quota a `rate = 0` è una proprietà del calcio, non della metrica, e nessuna centratura la modifica: con `min_pv_for_percentile = 1` la frazione di difensori con `Gf = 0` esatto è largamente sopra il 30%, e lo stesso vale per gli assist su più ruoli. La conseguenza pratica è che il controllo, classificato **ERROR** in sezione 22 con la formula *"il comportamento va corretto prima di usare il ranking"*, scatta alla prima esecuzione **su dati corretti**, bloccando la pipeline per un fatto atteso e già descritto dalla spec stessa poche righe sopra.

   Intervento richiesto, in sezione 11.2 e in sezione 22 (blocco "Distribuzioni delle feature (bloccanti)"):

   - **separare le due condizioni**, che oggi sono unite da un `oppure` e condividono la stessa severità:
     - *mediana di `BonusProfile_normalized` distante da 0 più di `0.10`* → resta **ERROR**. È l'unica delle due che `recenter` garantisce, quindi una violazione è un bug reale nell'implementazione della centratura;
     - *quota a `rate = 0` sopra `max_zero_share`* → diventa **WARNING**, con obbligo di riportare la quota per ruolo e stagione nel `qc_log`. Non è un difetto da correggere prima di procedere: è la descrizione del ruolo, ed è l'informazione che serve a decidere se valutare `split` (Model 3c);
   - correggere la frase *"il default `recenter` garantisce il criterio del controllo QC per costruzione"*, che è falsa per metà: `recenter` garantisce la condizione sulla mediana, **non** quella sulla quota;
   - riformulare la conseguenza operativa: al superamento di `max_zero_share` non segue "il comportamento va corretto prima di usare il ranking", ma "la variante `split` va valutata in ablation (sezione 20.4.4, Model 3c) e la quota va riportata nel report";
   - **misurare la quota reale prima di fissare il default.** `max_zero_share = 0.30` era stato scelto come soglia di allarme quando la quota non era stata misurata sui dati. Il valore va ricalibrato sulla distribuzione osservata (per ruolo, sulle 10 stagioni) al primo giro di Fase 1, e la spec deve dire che il default attuale è un segnaposto da sostituire con un numero misurato, non una soglia significativa.

5. **Siti di coerenza da aggiornare nello stesso intervento:**
   - sezione 10, elenco "scale esplicite": la riga `BonusProfile ∈ [-1, +1]` resta valida ma va annotata come garantita dal clip di sezione 11.2, non dalla sola divisione `/50`;
   - sezione 11.2, frase "Valori prossimi a +1 ... non necessariamente esattamente il massimo/minimo assoluto": va riscritta, perché con centratura + clip il valore `+1` **può** essere raggiunto esattamente e da più giocatori, ed è un valore di saturazione, non un estremo asintotico;
   - sezione 11.3, tabella degli span: lo span `peso × 2` resta corretto **solo** grazie al clip; aggiungere una riga di nota che lo dichiari, perché senza il clip la tabella era errata;
   - sezione 12, tabella "Range effettivo di `HistoricalRating`": verificare che i valori (`-15 → 100`) siano coerenti con `BonusProfile ∈ [-1, +1]` garantito, e dichiarare che la garanzia viene dal clip;
   - sezione 22, controllo ERROR `BonusProfile ∈ [-1, +1]` su ogni riga: con il clip questo controllo non può più scattare per effetto della normalizzazione, e resta valido **solo** come asserzione che il clip sia stato effettivamente applicato. Va riformulato in questi termini espliciti, altrimenti sembra una copertura che non copre più nulla;
   - sezione 24 (`config.yaml`): accanto a `max_zero_share` va annotato che il valore `0.30` è un segnaposto non misurato (vedi punto 4) e che la sua violazione è WARNING, non ERROR;
   - sezione 28 (changelog precedente), riga che afferma *"Il range di `BonusProfile` resta `[-1, +1]` (normalizzazione `/50`, sezione 11.2)"*: quella motivazione è ora incompleta. Non riscrivere la storia del changelog: aggiungere un rimando esplicito del tipo "corretto nella sezione 30: la sola divisione `/50` non garantiva il range dopo la centratura".

### Item 2 — Il metodo del percentile è autocontraddittorio e non implementabile

**Problema.** La sezione 10 prescrive due cose incompatibili:

- *"Metodo del percentile: usare una funzione standardizzata e deterministica (es. `rank(pct=True)` di pandas)"*;
- *"Gruppo di riferimento ≠ gruppo valutato"*: un giocatore sotto `min_pv_for_percentile` **riceve comunque** una `Performance_stagione`, calcolata come *"interpolazione della sua Fm nella distribuzione di riferimento del suo ruolo in quella stagione"*, e la sezione vieta esplicitamente l'implementazione via `rank(pct=True)` sul dataframe filtrato + join.

`rank(pct=True)` assegna un percentile a ogni elemento **di una serie**: non sa valutare un valore esterno alla serie. La procedura effettivamente richiesta — mappare un valore arbitrario su una distribuzione di riferimento costruita da un altro insieme di righe — non è `rank(pct=True)` e non è definita da nessuna parte nella spec. È il punto più bloccante del documento, e ha effetto su tutto: `Performance` (sezione 10), i percentili di `GoalRate`/`AssistRate` (sezione 11.1bis), la Performance dei portieri (sezione 13), `Target_A` e `Target_B` (sezione 20.4.0, che rimandano a "stesso metodo deterministico della sezione 10") e la conversione obbligatoria delle baseline nello spazio percentile (sezione 20.4.3). Un'ambiguità qui non produce un bug locale: produce due implementazioni che non si confrontano.

**Intervento richiesto.** Sostituire in sezione 10 il rimando a `rank(pct=True)` con una sottosezione nuova — proposta: **`### 10.1 Definizione del percentile (algoritmo unico, vincolante)`** — che definisca **un solo** algoritmo, richiamato per riferimento da tutti gli altri punti. Deve coprire, in modo esplicito e con formula:

1. **Costruzione del riferimento.** Il vettore di riferimento è l'insieme ordinato dei valori dei soli giocatori del gruppo che supera il filtro (`Pv >= min_pv_for_percentile`), per il singolo ruolo `R` e la singola stagione. Dichiarare che valori `null` non entrano nel riferimento e non ricevono percentile (restano `null`, sezione 4.0).
2. **Percentile di un valore appartenente al riferimento** — con gestione dei pareggi via **midrank** (media dei ranghi del blocco di pari valore), che è già il comportamento assunto dal resto della spec (sezione 11.2 parla esplicitamente di "percentile di midrank"). Scrivere la formula, non il nome: per un valore `x` con `n` osservazioni di riferimento, `L = #{v < x}`, `E = #{v == x}`:

   ```
   percentile(x) = 100 × (L + 0.5 × E) / n
   ```

3. **Percentile di un valore NON appartenente al riferimento** (il caso della popolazione sotto soglia, e il caso di `Target_A`/baseline valutate su insiemi diversi). Definire l'interpolazione: la stessa formula del punto 2 è già ben definita per un `x` qualsiasi (`E = 0` se `x` non compare nel riferimento), quindi la scelta più semplice è **usare la stessa formula anche fuori campione** e dichiararlo esplicitamente. Se si preferisce un'interpolazione lineare fra le due osservazioni di riferimento adiacenti, va scritta come formula completa; in entrambi i casi la spec deve indicare **una** delle due e vietare l'altra, non elencarle come alternative.
4. **Comportamento fuori dal range del riferimento.** `x` inferiore a tutti i valori di riferimento → `0`; `x` superiore a tutti → `100`. Dichiararlo, e dichiarare che questi due valori sono raggiungibili (non asintotici).
5. **Caso degenere — tutti i valori di riferimento uguali.** `percentile(x) = 50` per `x` pari a quel valore, `0` se inferiore, `100` se superiore. Va scritto: è l'unico caso in cui la formula del punto 2 restituisce `50` per l'intera popolazione, e va dichiarato come comportamento previsto, non come anomalia.
6. **Caso degenere — una sola osservazione di riferimento** (`n = 1`). `percentile(x) = 50` se `x` è pari a quell'unica osservazione, `0` / `100` altrimenti. Aggiungere un QC in sezione 22, **livello ERROR**, se `n < 5` per una qualunque coppia (ruolo, stagione) usata come riferimento: un percentile calcolato su meno di 5 osservazioni non è una posizione nella distribuzione, ed è un caso che può realisticamente presentarsi sui portieri con `min_pv_for_percentile = 5`.
7. **Divieto esplicito di implementazione.** Mantenere e rafforzare il divieto già presente: non usare `rank(pct=True)` sul gruppo filtrato con successivo join (lascia `null` sugli esclusi); non usare `scipy.stats.percentileofscore` senza fissare il parametro `kind`, perché il suo default non corrisponde alla formula del punto 2.

**Siti di coerenza da aggiornare:** sezione 10 (frase "Metodo del percentile", sostituita dal rimando a 10.1), sezione 11.1bis ("stesso metodo deterministico della sezione 10" → "algoritmo della sezione 10.1"), sezione 11.2 (il riferimento a `rank(pct=True)` fra parentesi va rimosso — è la citazione di una funzione che la spec ora vieta), sezione 13 (Performance portieri), sezione 20.4.0 (Target A e Target B), sezione 20.4.3 ("Conversione obbligatoria delle baseline"), sezione 21.2 (metodo di aggregazione di `Gf_Rate`/`Ass_Rate`).

### Item 3 — Manca l'analisi incrementale rispetto a `Qt.I` (l'unica domanda che conta in asta)

**Problema.** `Qt.I` è presente come `Baseline 3` (sezione 20.4.3), correttamente dichiarata diagnostica e non bloccante. Ma la spec non contiene **nessuna** analisi di informazione incrementale rispetto al mercato: nessuna misura di quanto il rating sia ridondante con il prezzo, nessuna analisi dei disaccordi, nessuna valutazione condizionata alla fascia di prezzo. Verificato: le parole "disaccordo", "incrementale" e "residuo" non compaiono nel documento in questo senso.

Il problema che questo lascia aperto è concreto, non metodologico. In un'asta il valore si estrae **solo** dove il modello e il prezzo divergono: un modello che batte `Fm_Weighted` ma correla 0.92 con `percentile(Qt.I)` in ogni ruolo non produce alcun vantaggio al tavolo, e con l'attuale set di metriche questo esito sarebbe indistinguibile da un successo pieno. Il Test C risponde a "il modello è meglio di una baseline interna"; nessun test risponde a "il modello sa qualcosa che il prezzo non sa già".

**Intervento richiesto.** Aggiungere una sottosezione nuova in sezione 20 — proposta: **`#### 20.4.6 Test F — informazione incrementale rispetto al mercato (Qt.I)`** — collocata dopo il Test E (sezione 20.4.5), **obbligatoria e non bloccante**, con le tre misure seguenti, tutte per ruolo, per fold e su entrambi i target (A e B), coerentemente con il vincolo "mai sull'universo indifferenziato" della sezione 12.0bis:

1. **Ridondanza col prezzo.**

   ```
   Spearman(HistoricalRatingRaw, percentile(Qt.I_target))    per ruolo, per fold
   ```

   È una misura descrittiva: dice quanta parte dell'ordinamento del modello il mercato aveva già espresso. Dichiarare nella spec come leggerla — un valore molto alto (es. `> 0.90`) non è un errore del modello, ma significa che il suo contributo pratico in asta è marginale anche se supera il gate del Test C, e va detto nel report invece di essere scoperto al tavolo.

2. **Ordinamento dentro fascia di prezzo (la misura più direttamente utile).**

   ```
   Suddividere l'universo di test in fasce (quantili) di Qt.I_target dentro ciascun ruolo,
   poi calcolare per ciascuna fascia:
       Spearman(HistoricalRatingRaw, target)
       Spearman(percentile(Qt.I_target), target)     — confronto
   ```

   Questa è letteralmente la decisione d'asta ("fra questi giocatori che costano lo stesso, quale prendo"). Fissare nella spec il numero di fasce come parametro (`validation.qti_bands`, default 4 — quartili di prezzo dentro il ruolo) e imporre di riportare la numerosità di ciascuna fascia accanto alla metrica: sui portieri, con quartili dentro ruolo, alcune fasce saranno troppo piccole perché Spearman significhi qualcosa, e va reso visibile invece che mediato via.

3. **Disaccordi estremi.** Riportare, per ruolo e per fold, i giocatori nel decile più alto di scarto fra `percentile(HistoricalRatingRaw)` e `percentile(Qt.I_target)` — nelle due direzioni — con il target realizzato. Non è una metrica aggregata: è la tabella che permette di capire *di che tipo* sono i disaccordi (giovani in ascesa, reduci da infortunio, rigoristi, cambi squadra) e se il modello sbaglia in modo sistematico o casuale dove si discosta dal prezzo.

**Da dichiarare esplicitamente nella nuova sottosezione, per non riaprire una scelta già presa:** `Qt.I` **resta non bloccante**. La review esterna proponeva di elevarla a benchmark centrale; la ragione per non farlo va scritta nella spec: `Qt.I` è un prezzo che incorpora informazione strutturalmente non disponibile al modello (trasferimenti estivi, ruolo atteso nella nuova squadra, gerarchie annunciate, aspettative sul minutaggio), quindi non batterlo non dimostra che il modello sia inutile — dimostra che non è un oracolo autonomo. Ciò che mancava non era un gate, era la misura. Questo item aggiunge la misura e lascia il gate dov'è (sezione 20.4.3, su `Fm_Weighted`).

**Siti di coerenza da aggiornare:** sezione 20.4.3 (aggiungere il rimando a 20.4.6 dove si dice che il confronto con `Qt.I` è "diagnostico e riportato nella stessa tabella"), sezione 20.7 (output della validazione: il Test F entra nel `validation_report.md`), sezione 24 (`config.yaml`: `validation.qti_bands: 4`), sezione 25 (roadmap: collocare il Test F nella stessa fase dei Test C/D/E).

### Item 4 — `precision@20` sui portieri è quasi degenere, ma è metà del criterio bloccante

**Problema (non individuato dalla review).** La sezione 20.4.2 fissa `N ∈ {5, 10, 20}` per i portieri. La sezione 20.4.3 usa `precision@20` come **metà del criterio bloccante** (Spearman **e** `precision@20`, in almeno 3 ruoli su 4), e la sezione 20.5 replica lo stesso criterio sul lock-box.

Ma il performance outcome della sezione 20.3a per i portieri — cioè i P con `Pv >= 1` nella stagione target — è una popolazione dell'ordine di poche decine. Un `precision@20` calcolato su una popolazione di ~30 significa "quanti dei 20 che ho messo in cima stanno fra i 20 migliori di 30": una quantità meccanicamente alta per qualunque modello e qualunque baseline, con un intervallo di variazione compresso. Sul ruolo P quella metà del criterio non discrimina, e nel contempo può far fallire il gate per rumore su un ruolo dove nessuna delle configurazioni testate è realmente distinguibile. La sezione 20.4.2 aveva già intuito il problema — vieta `precision@30` sui portieri esattamente con questo argomento — ma si è fermata un passo prima: lo stesso argomento si applica a `precision@20`.

**Intervento richiesto.**

1. In sezione 20.4.2, estendere l'argomento già presente: portare `N` per i portieri a `N ∈ {5, 10}` e dichiarare che `precision@20` non va calcolata per il ruolo P, per la stessa ragione per cui non si calcola `precision@30`. Riportare nel report la numerosità del performance outcome per ruolo e per fold, così che la scelta di `N` sia verificabile sui dati e non assunta.
2. In sezione 20.4.3 e in sezione 20.5 (criterio del lock-box), sostituire `precision@20` con una formulazione dipendente dal ruolo: `precision@20` per D/C/A, `precision@10` per P. Il criterio "in almeno 3 ruoli su 4" resta invariato.

**Siti di coerenza da aggiornare:** sezione 20.4.2, sezione 20.4.3 (criterio di superamento e paragrafo "Stesso test, ripetuto su Target B"), sezione 20.4.4 (tabella di sintesi: la colonna `Prec@30` è già inapplicabile ai P, ora anche `Prec@20` — la tabella deve dichiarare quali colonne sono vuote per quale ruolo, invece di lasciarle apparentemente calcolabili), sezione 20.5 (criterio di fallimento del lock-box), sezione 25 (Fase 4, se cita il criterio).

### Item 5 — La restrizione eccessiva è nel gate di selezione, non nel lock-box

**Problema (la review ha individuato il sintomo sul bersaglio sbagliato).** La review chiedeva di allentare il criterio del **lock-box**. Ma il lock-box è un solo fold, aperto una volta, con criterio fissato in anticipo: la sua severità è la sua funzione, e va mantenuta.

Il criterio davvero troppo restrittivo è quello di **selezione** in sezione 20.4.3: il modello deve battere `Fm_Weighted` su Spearman **e** `precision@20`, in almeno 3 ruoli su 4, **su ciascuno dei 6 fold di selezione**. È una congiunzione su 6 fold × 2 metriche: un modello genuinamente migliore ma con un margine modesto ha una probabilità non trascurabile di inciampare su almeno un fold per rumore campionario, e in quel caso la spec impone di concludere che "tutta la complessità aggiuntiva non sta dimostrando valore reale". Si noti che la spec applica già altrove un criterio a maggioranza esplicita e motivata — la regola di accettazione della sezione 20.5 chiede l'accordo in ≥ 4 fold su 6 e in ≥ 3 ruoli su 4 — quindi il documento è internamente incoerente su quanto rumore fra fold sia tollerabile: massima tolleranza per cambiare un default, tolleranza zero per il gate che decide il progetto.

**Intervento richiesto.** In sezione 20.4.3, riformulare il criterio di superamento come **metrica primaria + guardrail**, allineandolo alla struttura già usata in sezione 20.5:

1. **Primaria:** Spearman. Il modello completo deve battere `Fm_Weighted` su Spearman, in almeno 3 ruoli su 4, in **almeno 5 dei 6 fold di selezione**.
2. **Guardrail (non promozione, solo non-degradazione):** `precision@20` (`precision@10` per P, item 4) non deve peggiorare rispetto a `Fm_Weighted` di più di una soglia dichiarata — parametro `validation.precision_degradation_tolerance`, default `0.05` in valore assoluto di precision — in nessun ruolo, su più di 1 dei 6 fold.
3. **Diagnostiche (riportate, non nel pass/fail):** MAE, Median AE, calibrazione per bucket (sezione 20.4.5), Availability Rate (sezione 20.3b), Test F (item 3).

**Vincoli espliciti da scrivere nella spec insieme alla riformulazione**, altrimenti l'intervento peggiora la spec invece di migliorarla:

- La riformulazione è legittima **solo perché avviene prima di aver visto qualunque risultato di backtest**. Dichiararlo nel testo: un criterio di accettazione si può cambiare a risultati non visti, mai dopo. Se il codice di validazione è già stato eseguito su qualche fold, questo item **non va applicato** e va segnalato all'utente invece di procedere.
- Il criterio del **lock-box** in sezione 20.5 è definito come "copia esatta del gate di §20.4.3": va aggiornato per restare tale (Spearman come primaria + guardrail su precision), ma **su un solo fold** e senza clausole di maggioranza — mantenendo la sua natura di pass/fail unico e irripetibile.
- Non toccare la clausola della sezione 20.4.3 che spiega come reinterpretare un fallimento su Target A con successo su Target B; è collegata all'item 6.

**Siti di coerenza da aggiornare:** sezione 20.4.3, sezione 20.5 (criterio del lock-box e, se necessario, la regola di accettazione per allineare la terminologia primaria/guardrail), sezione 20.7, sezione 24 (`config.yaml`: `validation.precision_degradation_tolerance: 0.05`), sezione 25 (Fase 4).

### Item 6 — Il gate ha una scusa pre-scritta: chiudere la tensione Target A / Target B

**Problema.** La review chiedeva di "definire l'obiettivo di `HistoricalRating`" come se non fosse definito. Non è così: l'obiettivo è definito in sezione 1, il principio Performance/Reliability in sezione 7, e la sezione 20.4.0 argomenta — meglio di quanto la review proponesse — perché il bersaglio corretto sta *fra* Target A e Target B (A azzera il valore della disponibilità, B lo sovrastima ignorando la riserva che subentra). Quella parte non va riscritta.

Resta però una tensione reale, che la spec ammette a metà. Il gate bloccante è su Target A. Il modello completo include `Reliability` al 25% su tutti i ruoli. Target A è costruito sui soli `Pv >= 1`, cioè rimuove per costruzione ciò che `Reliability` predice. E la sezione 20.4.3 scrive già in anticipo l'interpretazione di un eventuale fallimento: *"se il modello non supera il criterio su Target A ma lo supera nettamente su Target B ... la conclusione corretta non è 'il modello non funziona' ma 'Reliability pesa più di quanto ...'"*. Un gate che contiene la spiegazione del proprio fallimento non è più un gate: qualunque esito è compatibile con il proseguimento del progetto.

**Intervento richiesto.** Non cambiare la definizione dei target né la scelta di Target A come bersaglio primario. Rendere invece **decidibile in anticipo** cosa fa fallire il progetto, aggiungendo in sezione 20.4.3 una regola a tre esiti, fissata prima di vedere i numeri:

1. **Il modello passa il gate su Target A** → si procede, nessuna riconsiderazione.
2. **Il modello falla su Target A, passa su Target B, e l'ablation (Model 2 vs Model 1, sezione 20.4.4) mostra che è l'aggiunta di `Reliability` a peggiorare Target A** → esito **pre-classificato come revisione del peso, non fallimento**, con una conseguenza operativa obbligatoria e non facoltativa: `bonus_weight` resta invariato e la coppia Performance/Reliability viene ri-calibrata al punto 6 dell'ordine di sezione 20.5, dopodiché il gate su Target A viene **ri-eseguito una sola volta** sulla nuova configurazione. Se falla ancora, si applica l'esito 3. Il numero di ri-esecuzioni consentite va scritto (una), altrimenti l'esito 2 è un ciclo infinito di aggiustamenti.
3. **Il modello falla su entrambi i target, oppure falla su A per ragioni non attribuibili a `Reliability` dall'ablation** → fallimento strutturale, si torna alla sezione 12 come già previsto.

Scrivere inoltre, nello stesso punto, che la clausola dell'esito 2 è ammessa **una volta sola nell'intero ciclo di calibrazione** e va registrata nel `validation_report.md` con la configurazione prima e dopo: è l'unica differenza fra una revisione legittima del peso e un aggiustamento post-hoc mascherato.

**Siti di coerenza da aggiornare:** sezione 20.4.3 (paragrafo "Stesso test, ripetuto su Target B"), sezione 20.5 (ordine di calibrazione, punto 6 — deve prevedere esplicitamente il caso in cui vi si rientra per effetto dell'esito 2), sezione 20.7 (il report deve tracciare quale dei tre esiti si è verificato).

### Item 7 — I flag di rischio della sezione 18.2 non hanno soglie

**Problema (quinto problema non individuato dalla review).** La sezione 18.2 definisce tre flag di rischio in prosa, senza alcuna soglia numerica:

- *"Dipendenza da rigori (attaccanti/centrocampisti con **alto** R+/Pv rispetto al totale gol)"*;
- *"Storico volatile (**alta** varianza di Fm tra stagioni disponibili)"*;
- *"Poche presenze recenti (Pv **basso** nell'ultima stagione anche se lo storico complessivo è PV_SUFFICIENTI)"*.

Nessuna delle tre parole in grassetto è definita, e `config.yaml` (sezione 24) non contiene alcuna voce per questi flag — a differenza del Trend, che ha `strong_up`/`up`/`down`/`strong_down`. Al tempo stesso `RigoriDipendenza` è una **colonna obbligatoria** del CSV finale (sezione 21), descritta come *"Flag/valore su dipendenza da rigori"* — cioè nemmeno il tipo del campo è deciso. Il risultato è che chi implementa inventerà tre soglie e un tipo di dato, senza traccia della scelta e senza che nessuno l'abbia approvata: esattamente il modo di procedere che il resto della spec vieta sistematicamente (cfr. sezione 19 sul divieto di soglie if/else arbitrarie non verificate, e sezione 18.1 sulla definizione obbligatoria dell'indice di stagione).

La severità è minore rispetto agli item 1 e 2 — questi flag sono dichiaratamente **informativi e non entrano in `HistoricalRating`** (sezione 18.2) — ma finiscono nel CSV che si legge in asta, quindi una soglia inventata diventa comunque un'indicazione operativa non tracciata.

**Intervento richiesto.** In sezione 18.2, per ciascuno dei tre flag: definire la formula, il tipo del campo esposto e la soglia, con il parametro corrispondente in `config.yaml` (sezione 24, nuovo blocco `risk_flags`). Le soglie di partenza vanno dichiarate come **ipotesi da rivedere sui dati reali** (stessa formula già usata per la Confidence in sezione 19), non come valori validati. Requisiti minimi:

1. **Dipendenza da rigori.** Definire il rapporto esatto — proposta: `R+_Weighted / Gf_Weighted` (quota di gol su rigore sul totale gol, entrambi già aggregati col Metodo 1 di sezione 21.2), con il caso `Gf_Weighted = 0` → flag `null`, non `0`. Stabilire che `RigoriDipendenza` espone **il valore continuo**, e che l'eventuale etichetta booleana è una colonna derivata separata: una colonna che a volte è un flag e a volte un valore è inutilizzabile in un foglio di calcolo. Soglia di partenza da dichiarare in config (`risk_flags.penalty_dependency_threshold`), applicabile solo a C/A come già previsto dalla sezione.
2. **Storico volatile.** Non reinventare la misura: `StabilityScore` (sezione 19) è già una varianza di `Performance_stagione` normalizzata e con la degenerazione a `seasons_available < 2` già risolta. Definire il flag come `StabilityScore` sotto una soglia (`risk_flags.volatility_threshold`) e dichiarare esplicitamente il riuso, invece di introdurre una seconda misura di varianza della Fm — che ricadrebbe nel problema del coefficiente di variazione con Fm vicina a zero, già analizzato e scartato in sezione 19.
3. **Poche presenze recenti.** Definire su `Pv_Last_Season` (campo già esposto in sezione 21) sotto una soglia (`risk_flags.low_recent_pv_threshold`), con la condizione di applicabilità già scritta nella sezione (`Categoria = PV_SUFFICIENTI`) resa esplicita nella formula. Definire il comportamento quando l'ultima stagione disponibile del giocatore non è la più recente della finestra di train — caso reale per chi è rientrato dall'estero — perché "ultima stagione disponibile" e "stagione più recente" non coincidono e la differenza cambia il significato del flag.

**Siti di coerenza da aggiornare:** sezione 18.2, sezione 21 (descrizione della colonna `RigoriDipendenza`, più le eventuali colonne nuove per gli altri due flag — oggi non presenti nell'elenco delle colonne minime, un'incoerenza da sanare in un senso o nell'altro), sezione 24 (nuovo blocco `risk_flags`), sezione 25 (Fase 2, ultimo checkbox: cita "i flag di rischio (sezione 18.2)" come se fossero già specificati).

---

## 2. Item della review da NON applicare

Questa sezione è vincolante. Ciascuno di questi item era presente nella review esterna e **non va implementato**: la spec già lo contiene (spesso in forma più completa), oppure il cambiamento non è giustificato. Aggiungere il contenuto proposto produrrebbe duplicazione, o sostituirebbe una formulazione più precisa con una più vaga.

| Item della review | Motivo per non applicarlo |
|---|---|
| *"Chiarire che Target B è una proxy di produzione stagionale"* | Già in sezione 20.4.0, in modo più completo di quanto la review chieda: la spec dichiara che è una proxy imperfetta, che sovrastima il valore della disponibilità perché non tiene conto della riserva che subentra, che Target A lo sottostima simmetricamente, e che il peso corretto di `Reliability` sta fra le due stime. Non toccare. |
| *"Chiarire la semantica di `Reliability` / rinominare in `ParticipationScore`"* | Già in sezione 7, nota terminologica: la spec dichiara esplicitamente che `Reliability` misura la disponibilità/numerosità del campione e non l'affidabilità caratteriale, e che il nome è mantenuto per uso pratico. Nessuna rinomina: `Reliability` è il nome della colonna nel CSV finale e comparirebbe in decine di punti, a fronte di zero cambiamenti nei risultati. |
| *"Testare se `BonusProfile` debba esistere"* | Già previsto, in forma più forte: la griglia `bonus_weight ∈ {0, 0.10, 0.15, 0.25, 0.35}` (sezione 11.3 / 20.5a) contiene `0`, che **è** l'ablation; esistono già Model 1/2/3 (sezione 20.4.4), il controllo doppio conteggio (sezione 11.4) e `corr(Performance, BonusProfile)` per ruolo (sezione 20.6). Non aggiungere un test di ablation che c'è già. |
| *"Considerare un trattamento a due parti (hurdle/split) per le statistiche di bonus zero-inflate"* | Già presente: `zero_handling = split` (sezione 11.2) è esattamente quel trattamento, ed è già in ablation come Model 3c (sezione 20.4.4). L'unica cosa che manca è la **definizione precisa** di `split`, coperta dalla nota in fondo a questa sezione. |
| *"Documentare il limite del backtest storico (universo d'asta non ricostruibile)"* | Già in sezione 20.1, in forma più forte: la spec non solo dichiara il limite, ma stabilisce che la misura **non è calcolabile su nessuno dei 7 fold** e che il QC deve dirlo esplicitamente invece di promettere una misura che non arriverà. Non riscrivere. |
| *"Rinominare `ConfidenceScore` in `EvidenceScore`"* | Cosmetico. La sezione 19 già definisce cosa lo score è e cosa non è, e la sezione 19.1 vieta in modo esplicito qualunque uso moltiplicativo nel rating — che è la confusione concettuale che la rinomina vorrebbe prevenire. Non cambia alcun risultato e costa una rinomina in output, config e documentazione. Non applicare. |
| *"Rendere `Qt.I` un benchmark centrale / bloccante"* | Applicato **solo in parte**, tramite l'item 3: si aggiunge l'analisi incrementale, **non** si sposta il gate. La motivazione va scritta nella spec (vedi item 3): `Qt.I` incorpora informazione non disponibile al modello, quindi non batterlo non è evidenza di inutilità. |
| *"`Reliability` aggiustata per esposizione"* (frazione di stagione effettivamente disponibile) | Correttamente rimandato dalla review stessa a una versione futura, e va lasciato lì. Il dato necessario (finestra temporale dell'uscita dalla Serie A) non è disponibile: il foglio `Ceduti` (sezione 2.3bis) permette di sapere *se* un giocatore è uscito, non *quando*. Aggiungere al massimo una riga nella roadmap (sezione 25) fra le estensioni future, senza toccare la regola binaria della sezione 9.1bis. |

**Nota — `split` non è definito** (terzo dei cinque problemi non individuati dalla review). Il blocco `zero_handling = split` in sezione 11.2 dice *"giocatori con `rate = 0` → valore fisso al centro del blocco a zero"*: è una descrizione, non una formula. Poiché `split` è una variante testata in ablation (Model 3c) e la review ne raccomandava perfino l'adozione, va definito con lo stesso rigore richiesto dall'item 2: la formula esatta del valore assegnato al blocco a zero, e la mappatura dei `rate > 0` su `[50, 100]` (che con l'algoritmo dell'item 2 diventa `50 + percentile_fra_i_positivi / 2`). Chiudere questo punto contestualmente all'item 2, non come intervento separato.

---

## 3. Nota sulla review esterna (per memoria, non un intervento)

Utile da tenere presente per come pesare la prossima review automatica: dei 5 item classificati come **Must Fix**, 2 erano reali e bloccanti (normalizzazione di `BonusProfile`, definizione del percentile), 1 era già risolto nella spec (Target B come proxy), 1 chiedeva di definire un obiettivo che era già definito, e 1 puntava al criterio di accettazione sbagliato. Nel frattempo l'item di gran lunga più utile — l'informazione incrementale rispetto a `Qt.I` — era archiviato fra le raccomandazioni non bloccanti, e **cinque** problemi reali non erano stati visti:

1. range dichiarati incoerenti a valle della centratura (item 1);
2. `max_zero_share` come ERROR bloccante che scatta su dati corretti — il solo problema in grado di fermare la pipeline alla prima esecuzione (item 1, punto 4);
3. `precision@20` degenere sui portieri, mentre è metà del criterio bloccante (item 4);
4. `zero_handling = split` descritto ma non definito, e per giunta raccomandato dalla review stessa (nota in fondo alla sezione 2);
5. flag di rischio della sezione 18.2 senza soglie, formule né voci di config, con una colonna del CSV finale di tipo non deciso (item 7).

I punti 2, 4 e 5 hanno una caratteristica comune: sono casi in cui la spec **descrive** un comportamento invece di **definirlo**, e la descrizione è abbastanza convincente da superare una lettura per sezioni. È il modo di fallire tipico di una review che si ferma alle intestazioni, e vale la pena cercarlo esplicitamente alla prossima passata.

L'ordinamento di priorità della review non va adottato così com'è; l'ordinamento vincolante è quello della sezione 1 di questo documento.
