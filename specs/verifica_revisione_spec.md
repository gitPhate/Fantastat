# Verifica della revisione di `ranking_pipeline.md` — seconda passata

Documento di lavoro. Rilegge `specs/ranking_pipeline.md` dopo l'applicazione degli interventi
B1-B14 di `specs/piano_revisione_10_stagioni.md`, e verifica le affermazioni fattuali della spec
**contro i file veri**, non contro il piano.

**Nessuna modifica alla spec è stata fatta.** Questo file elenca cosa correggere e come.

**Esito sintetico**: i 14 interventi sono stati tutti recepiti, e la struttura della revisione è
corretta. Ma **due affermazioni fattuali sui dati, ereditate dal piano, sono false**, e su di esse
poggiano il flag `left_mid_season` e il layer di ingestione. Vanno corrette prima di scrivere
codice. Oltre a queste, il criterio di fallimento del lock-box non è pre-registrabile come scritto,
e la Baseline 3 confronta il modello con un universo diverso dal proprio.

---

## 1. Metodo

Le tabelle del piano sono state ricalcolate leggendo direttamente i 21 file
(`openpyxl`, foglio per foglio, join per `Id`). Dove il piano e i file divergono, vince il file.

Risultato della verifica: **12 affermazioni su 14 confermate esattamente**, 2 false (§2.1 e §2.5
del piano). L'elenco di ciò che è confermato è nella sezione 5 — serve a non rifare due volte lo
stesso lavoro.

---

## 2. Bloccanti

### R1 — `Ceduti` è un foglio delle QUOTAZIONI, non delle statistiche

**Fatto verificato:**

```
data/stats/*.xlsx            → ['Tutti']                (tutti e 10 i file, nessun altro foglio)
data/player_lists/*.xlsx     → ['Tutti', 'Ceduti']      (tutti e 11 i file)
```

La spec colloca `Ceduti` dentro i file statistiche in **cinque punti**, e in uno di essi dà
un'istruzione operativa che ne consegue:

| Riga | Testo | Problema |
|---|---|---|
| 50 (§2.1) | "I file [statistiche] fino al 2021/22 contengono inoltre un foglio `Ceduti` … **va letto e unito a `Tutti`** nel dataset long" | il foglio non è lì; e unirlo produrrebbe righe con colonne quotazione (`Qt.A`, `Qt.I`, `FVM`) e **senza** `Pv`/`Mv`/`Fm`/`Gf` |
| 143 (§4.0) | "Ogni riga viene dal file statistiche (foglio `Tutti`, unito al foglio `Ceduti` quando presente — sezione 2.1)" | idem |
| 189 (§5) | diagramma: `statistiche (train_window stagioni, foglio Tutti + Ceduti se presente)` | idem |
| 1110 (§22) | "un problema nella lettura del foglio `Tutti`/`Ceduti`" | fonte sbagliata nel messaggio QC |
| 1301 (§25) | "Importare i 10 Excel statistiche (foglio `Tutti`, più `Ceduti` dove presente)" | istruzione di implementazione sbagliata |

Da notare che §4.0bis (riga 160) è invece **corretta** ("foglio `Ceduti` delle **quotazioni**"): la
spec si contraddice al proprio interno.

**Cosa fare.** Spostare la descrizione di `Ceduti` da §2.1 a §2.3. Dichiarare che il dataset long
nasce da `stats!Tutti` **e da quello solo** — è già l'universo completo, ed è esattamente la
scoperta §2.4 del piano. `Ceduti` serve a due cose e nessun'altra: popolare `left_mid_season` e
fornire `Qt.I` per i giocatori assenti da `quotazioni!Tutti` (vedi R3). Correggere di conseguenza
§4.0, il diagramma §5, il messaggio QC §22 e la Fase 1 di §25.

### R2 — `Ceduti` esiste e è popolato in tutte le stagioni, non solo fino al 2021/22

**Fatto verificato** (righe dati per foglio):

| stagione | 16/17 | 17/18 | 18/19 | 19/20 | 20/21 | 21/22 | 22/23 | 23/24 | 24/25 | 25/26 | 26/27 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `Ceduti` | 117 | 118 | 118 | 155 | 114 | 125 | **127** | **125** | **119** | **131** | **31** |

La spec afferma il contrario in tre punti: riga 50 ("Dal 2022/23 il foglio non esiste più"),
riga 109 ("nessun foglio `Ceduti` disponibile") e §29 #2 ("da foglio `Ceduti` (fino al 2021/22) o
diff … (dal 2022/23)").

Verifica più forte, sull'identità su cui poggia tutto il meccanismo:

```
Tutti ∩ Ceduti = ∅        e        Tutti ∪ Ceduti = stats        ESATTO, tutte e 10 le stagioni
⇒  stats \ Tutti ≡ Ceduti                                        (117=117, 118=118, … 131=131)
```

Quindi i due rami di §4.0bis **non sono un ramo principale e un fallback: sono lo stesso insieme**,
e il ramo "per differenza" è una derivazione di un insieme che si può leggere direttamente.
Il piano (§2.5) aveva ispezionato solo 6 stagioni e concluso che il foglio sparisse; non è così.

**Cosa fare.**

1. Collassare la tabella di §4.0bis a **una sola fonte uniforme**: foglio `Ceduti` delle quotazioni
   della stagione, per tutte e 10 le stagioni. Coerente con il principio che la spec già enuncia a
   riga 74 ("nessun parser condizionale per stagione").
2. Promuovere la differenza a **controllo QC obbligatorio e bloccante** in §22:
   `Tutti ∩ Ceduti = ∅`, `Tutti ∪ Ceduti = stats`, `stats \ Tutti == Ceduti`. È un presidio più
   forte di entrambi i rami separati, ed è il punto in cui un file quotazioni della versione
   sbagliata (pre-stagione invece di fine stagione, vedi R7) verrebbe intercettato subito.
3. Togliere da §2.3 punto 1 la copertura "ma l'insieme risultante ha lo stesso ordine di grandezza":
   non è una stima, è un insieme esatto e letto direttamente.
4. §4.0bis dice "2026/27 → non applicabile". Vero per il flag, ma il file 2026/27 **ha** un `Ceduti`
   di 31 righe: sono giocatori già ceduti *prima* dell'inizio della stagione, non *durante*.
   Vanno esclusi dall'universo di produzione o dichiarati, non incontrati per caso.

### R3 — Baseline 3 (`Qt.I`) misura un universo diverso da quello del modello

L'universo di test è `stats` = `Tutti ⊎ Ceduti` (§20.1). Ma la spec non dice mai da dove si legge
`Qt.I`, e la lettura naturale (`Tutti`) esclude per costruzione i `Ceduti`.

**Fatto verificato**: le righe `Ceduti` hanno `Qt.I` **sempre popolato** (0 valori nulli o a zero su
tutte e 10 le stagioni). Quindi il buco è evitabile del tutto. Quanto pesa se non lo si evita:

| stagione | 16/17 | 17/18 | 18/19 | 19/20 | 20/21 | 21/22 | 22/23 | 23/24 | 24/25 | 25/26 |
|---|---|---|---|---|---|---|---|---|---|---|
| `Ceduti` con `Pv ≥ 1` | 45 | 45 | 38 | 41 | 41 | 51 | 41 | 41 | 53 | 50 |
| **% Target A senza `Qt.I`** | 8.6 | 8.8 | 7.5 | 7.7 | 7.3 | 9.1 | 7.5 | 7.5 | 9.4 | 9.1 |
| **% Target B senza `Qt.I`** | ~19 | ~19 | ~18 | ~23 | ~17 | ~19 | ~19 | ~19 | ~18 | ~20 |

Sono i giocatori usciti in corsa **che hanno giocato** (27-42 con `1 ≤ Pv < 10`, 3-16 con `Pv ≥ 10`).
Escluderli dalla baseline e non dal modello significa confrontare il modello con una baseline
calcolata su una popolazione ripulita dei casi più difficili: **è il survivorship bias che §20.1 è
stata riscritta per eliminare, reintrodotto dalla porta della baseline.**

**Cosa fare.** Dichiarare in §2.3 e §20.4.3 che `Qt.I` e `FVM` si leggono da `Tutti ∪ Ceduti`.
Aggiungere al report per fold la **coverage della baseline** e la regola che modello e baseline si
confrontano sempre sullo stesso sottoinsieme di Id — mai su universi diversi.

### R4 — Il criterio di fallimento del lock-box non è pre-registrabile come è scritto

§20.5 (riga ~908): *"se sul fold di conferma il modello configurato non batte **le baseline** della
sezione 20.4.3 in almeno 3 ruoli su 4"*.

Mancano quattro cose necessarie a renderlo un pass/fail:

- **quali** baseline. §20.4.3 ne elenca cinque; il gate di selezione è su `Fm_Weighted` (Baseline 1)
  e la stessa sezione dichiara `Qt.I`/`FVM` "diagnostiche e non bloccanti". "Le baseline" al plurale
  suggerisce tutte e cinque, cioè un gate **più severo** di quello di selezione e costruito su una
  baseline dichiarata non bloccante altrove.
- **quale target** (A o B). §20.4.3 lega esplicitamente il gate di selezione al Target A; qui non è detto.
- **quale metrica**. Il gate di selezione è "Spearman **e** precision@20"; qui non è detto.
- **cosa significa "battere"**: `>` stretto, o con un margine minimo?

È l'unico criterio che la spec stessa dichiara di dover fissare in anticipo — riga 910: *"Fissarlo
adesso, prima di vedere il risultato, è ciò che rende il lock-box qualcosa di diverso da un settimo
fold"*. Così com'è, all'apertura resta spazio di discrezionalità, che è esattamente ciò che il
lock-box deve escludere.

**Cosa fare.** Riscriverlo per copia esatta del gate di §20.4.3: *Spearman **e** precision@20, contro
Baseline 1 (`Fm_Weighted`), su Target A, in ≥ 3 ruoli su 4*. E dire in una riga se Baseline 3
(`Qt.I`) entra nel gate o resta diagnostica — **si raccomanda: diagnostica**, per coerenza con
§20.4.3 e con R9.

### R5 — Il gate bloccante del Test C si contraddice nello stesso paragrafo

Riga 844 contiene entrambe le formulazioni:

> "… in almeno 3 ruoli su 4, misurato su Target A, **su ciascuno dei 6 fold di selezione**."
> "Se il criterio non è soddisfatto **sulla maggioranza dei fold di selezione**, tutta la complessità
> aggiuntiva … va rivista."

6 su 6 e ≥ 4 su 6 sono gate materialmente diversi. §25 Fase 4 (riga 1334) e §20.7 (riga 982) adottano
"ciascuno". Va scelta una sola formulazione — trattandosi del test che "decide se il progetto ha
senso così com'è", l'ambiguità non è tollerabile.

### R6 — B8 e B10 sono incompatibili al passo 1 della calibrazione

- **B8** (riga 759): confronto fra `train_window ∈ {2,3,4,5}` **"sui soli target comuni a tutte le
  varianti testate"**.
- I target comuni sono quelli disponibili a `train_window = 5`, cioè 2021/22 → 2025/26; togliendo il
  lock-box restano **4 fold di selezione** (2021/22, 2022/23, 2023/24, 2024/25).
- **B10** (riga 913): un default si accetta se il miglioramento è concorde in **"almeno 4 dei 6 fold
  di selezione"**.

Al passo 1 dell'ordine di calibrazione i 6 fold non esistono: ce ne sono 4. La regola "≥ 4 su 6"
richiede quindi l'unanimità sui 4 disponibili, ed è enunciata con un denominatore che a quel passo
non esiste. Non è un cavillo: `train_window × time_decay.base` è il **primo** e più strutturale
parametro, e la regola con cui lo si fissa condiziona tutto il resto.

**Cosa fare.** Rendere esplicito il denominatore per passo: passo 1 → 4 fold comuni, regola ≥ 3 su 4;
passi 2-6 → 6 fold, regola ≥ 4 su 6. In alternativa togliere `train_window = 5` dalla griglia e
lavorare su 5 fold comuni. Va deciso nella spec, non in fase di implementazione.

---

## 3. Importanti

### R7 — §26 chiede di archiviare la quotazione pre-stagione, ma `left_mid_season` richiede lo snapshot di fine stagione

I due insiemi sono **opposti**:

```
stats_T \ Tutti_pre-stagione_T   =  arrivi di gennaio        (chi è ENTRATO)
stats_T \ Tutti_fine-stagione_T  =  usciti in corsa          (chi è USCITO)   ← è left_mid_season
```

La tabella di §26 assegna allo stesso singolo file archiviato due requisiti che si escludono:
"flag `left_mid_season` … tramite diff `stats \ quotazioni_Tutti`" **e** "va archiviata a inizio
stagione, quando è ancora un listone pre-asta". Con il file pre-stagione il flag non è calcolabile:
verrebbe calcolato l'insieme sbagliato, senza che nulla segnali l'errore.

Conferma sui dati: il file 2026/27 (pre-stagione) ha un `Ceduti` di **31** righe, contro le 114-155
dei file di fine stagione — un ordine di grandezza diverso, perché è un'altra cosa.

Le 10 stagioni storiche sono calcolabili solo perché sono, per caso, snapshot di fine stagione — non
per progetto. La spec dovrebbe dirlo.

**Cosa fare.** §26 deve richiedere **due** snapshot per stagione, non uno:

| Snapshot | Quando archiviarlo | A cosa serve |
|---|---|---|
| listone pre-asta | alla pubblicazione (agosto) | `Qt.I`/`FVM` come baseline esterna, universo di produzione, QC arrivi tardivi |
| snapshot di fine stagione | a stagione conclusa | foglio `Ceduti` → `left_mid_season` |

E §2.3 / §4.0bis devono dire, per ciascun uso, **quale dei due** snapshot serve. Aggiornare "tre
file" nell'intestazione di §26.

### R8 — Il QC sugli arrivi tardivi non è calcolabile su nessuno dei 7 fold

§20.1 (riga 726) e §22 (riga ~1117) richiedono di contare gli Id dell'universo target assenti dalla
"quotazione pre-stagione di T, **quando disponibile**". Ma §2.3 dichiara — e la verifica conferma —
che nessuna quotazione pre-stagione storica esiste: l'unico file pre-stagione è il 2026/27, che non è
un fold (non ha statistiche). Quindi "quando disponibile" vale **mai**, su tutti e 7 i fold.

La prosa però si legge come se la misura verrà prodotta ("Il QC deve contare, per ogni fold, …" e
"limite da misurare, non da nascondere"). Il limite resta dichiarato e **non** misurato.

**Cosa fare.** Dirlo esplicitamente: la quota di arrivi tardivi non è misurabile su questa finestra;
il controllo si attiva dalla prima stagione archiviata secondo R7. Se un numero serve subito,
specificare il proxy e la sua debolezza (es. Id assente sia da `stats_{T-1}` sia da
`quotazioni_{T-1}`), invece di lasciare la promessa di una misura che non arriverà.

### R9 — `Qt.I` come "prezzo di agosto" è un'assunzione presentata come fatto verificato

**Cosa è verificato**: `Qt.A ≠ Qt.I` per il 79.9-86.0% delle righe nei file storici contro il 17.4%
nel 2026/27. Questo dimostra che **`Qt.I` non viene sovrascritto** dagli aggiornamenti in corso
d'anno. Confermato.

**Cosa non è verificato**: che `Qt.I` sia il prezzo di *agosto* per chi è entrato in Serie A a
stagione iniziata. Per un arrivo di gennaio, la quotazione "iniziale" è plausibilmente quella del suo
ingresso a gennaio. La spec afferma senza riserve (riga 106 e §20.4.3): *"il prezzo che il mercato
aveva già messo sul giocatore prima dell'inizio della stagione"* e *"`Qt.I` resta un prezzo iniziale
valido su tutte le 11 stagioni"*. Per quel sottoinsieme è un'affermazione più forte dell'evidenza —
e per R8 è anche il sottoinsieme che non si riesce a quantificare.

**Cosa fare.** Riformulare: `Qt.I` non è sovrascritto (verificato); per chi è entrato a stagione
iniziata è il prezzo d'ingresso, non quello di agosto, su un sottoinsieme non quantificabile con
questi dati. Tenere la Baseline 3 e tenerla **diagnostica e non bloccante** — la scelta che §20.4.3
ha già fatto risulta ora meglio motivata di quanto la spec stessa sappia.

### R10 — L'aritmetica di B12 non produce i numeri che la spec dichiara

Riga 454: *"Performance e Reliability si riscalano proporzionalmente per occupare lo spazio residuo
**mantenendo il rapporto originale 55:20** … il che porta D e A a: Performance 0.60, Reliability
0.25, Bonus 0.15"*.

```
spazio residuo dopo bonus = 0.15  →  0.85
riscalatura proporzionale a 55:20 →  0.85 × 55/75 = 0.6233
                                     0.85 × 20/75 = 0.2267     ≠ 0.60 / 0.25
rapporto dichiarato 55:20 = 2.75          rapporto di 0.60:0.25 = 2.40
```

Quello che è stato fatto in realtà è l'**allineamento a C** (già 0.60/0.25/0.15) — scelta più
semplice e difendibile, ma diversa da quella dichiarata. Riga 1249 di `config.yaml` ripete l'errore
e si contraddice in sei parole: *"costante 55:20 sullo spazio residuo … → allineato a C"*: sono due
operazioni diverse con due risultati diversi.

Conseguenza operativa concreta: §20.5a (riga 918) prescrive di esplorare la griglia `bonus_weight`
*"tenendo fisso il rapporto Performance:Reliability"* senza dire quale. Con 2.40 la griglia è
`bonus=0 → 0.706/0.294`, `bonus=0.35 → 0.459/0.191`; con 2.75 sono altri numeri. Senza fissarlo, la
griglia non è riproducibile.

**Cosa fare.** Togliere la motivazione "55:20" (da riga 454, da riga 1249 e da §29 #10), scrivere
"allineati a C", e fissare in §20.5a il rapporto tenuto costante a **0.60 : 0.25**.

### R11 — Model 3a è etichettato al contrario nella tabella di sintesi

Riga 883: `| Model 3a: senza stagioni quotate a zero |`

Model 3a è `exclude_left_mid_season = false`, cioè la variante che **include** le stagioni
`left_mid_season` a `Reliability = 0` a peso pieno: ha *più* stagioni a zero del Model 3, non meno.
L'etichetta dice l'opposto di ciò che la variante fa. In più "quotate" è vocabolario residuo del
`QUOTED_ONLY` rimosso.

**Cosa fare.** `Model 3a: exclude_left_mid_season = false (stagioni left_mid_season contate a 0 a
peso pieno)`.

### R12 — Performance e Reliability non sono definite quando la ripesatura ha insieme vuoto

Con `exclude_left_mid_season = true` (default), un giocatore le cui stagioni di train sono **tutte**
`IN_SQUAD_NO_PLAY` + `left_mid_season = true` ha tutte le stagioni escluse dalla Reliability →
Reliability non definita. §21.3 lo sfiora (*"sarà molto bassa, salvo stagioni tutte
`left_mid_season`"*) ma non lo definisce, e §12 poi calcola `0.25 × Reliability`.

Lo stesso buco esiste in §8 per la famiglia Performance (tutte le stagioni assenti): §4.1 lo risolve
solo per il caso del confine portiere.

È il buco che in implementazione si tappa per default con uno zero — esattamente l'errore che §4.0
vieta a riga 152 (*"`Fm = null` non è `Fm = 0`"*).

**Cosa fare.** Scrivere in §8 e §9.1bis che un insieme di ripesatura vuoto dà componente `null`; in
§12 che Performance o Reliability nulle danno `HistoricalRating = null` con `Note` esplicita; in §22
un conteggio INFO dei casi.

### R13 — `Seasons_Quoted` non ha una definizione univoca

Riga 1004: *"Numero di stagioni in cui il giocatore compare nel file quotazioni"*. Su `Tutti` o su
`Tutti ∪ Ceduti`?

- Solo `Tutti` (roster di fine stagione): il campo esclude per costruzione proprio i
  `left_mid_season`, quindi `Seasons_Quoted < Seasons_In_Squad` sistematicamente per loro.
- `Tutti ∪ Ceduti`: per R2 quell'unione **è** `stats`, quindi
  `Seasons_Quoted ≡ Seasons_In_Squad` e la colonna è ridondante.

**Cosa fare.** Decidere e scriverlo. Si raccomanda: definirlo su `Tutti` e ridocumentarlo per quello
che misura davvero ("stagioni in cui era nel roster di fine stagione") — oppure eliminarlo, dato che
§29 dichiara già che il suo ruolo nella Reliability è passato a `Seasons_In_Squad`.

### R14 — `time_decay.max_seasons` è dichiarato in config ma non ha semantica

Riga 1206 lo introduce (`max_seasons: null`) e §26.1 lo dà per fatto (*"esiste come parametro in
config.yaml (sezione 24, fatto)"*). Ma §8 — la sola sezione che definisce i pesi — non lo menziona
mai: non è detto se tronca prima o dopo la normalizzazione, né come interagisce con `train_window`
(è un tetto a `train_window`, o un tetto ai pesi non nulli al suo interno?).

Un parametro in config senza comportamento specificato è una decisione lasciata all'implementazione,
che è ciò che questa spec evita sistematicamente altrove.

**Cosa fare.** Definirlo in §8, o rimuoverlo da `config.yaml` e lasciarlo in §26.1 come lavoro
futuro. Non lasciarlo a metà.

---

## 4. Minori

| # | Punto | Cosa fare |
|---|---|---|
| R15 | §22 riga 1111: soglia QC `left_mid_season` "56-75% dei `Pv = 0`". Il range reale verificato è **55.9%-74.5%**: il 2024/25 (55.9%) farebbe scattare il controllo su dati corretti | usare 55-75%, o dichiararla banda indicativa |
| R16 | §2.1 riga 36: "I file fino al 2021/22 contengono anche quattro fogli per ruolo (`Portieri`, `Difensori`, …)". **Verificato: non esistono.** Nessun file statistiche o quotazioni ha fogli per ruolo | eliminare la frase (l'istruzione "si legge sempre e solo `Tutti`" resta giusta, la premessa no) |
| R17 | §8 riga 238: la formula fissa base 2 (`peso = 2^i / Σ 2^i`) mentre il default di §24 è `1.5` | scrivere `base^i`; tenere la tabella 1:2:4 come esempio esplicito con base 2 |
| R18 | §4.1: la regola sul confine portiere e il QC `role_change_gk`. **Verificato: 0 Id su 2306 attraversano il confine P in 10 stagioni** | tenere la regola come difesa, ma dichiarare che l'insieme è vuoto sulla finestra: una lista `role_change_gk` non vuota segnala un problema di dati, non un caso di modellazione |
| R19 | §19: la prova di sanità "`seasons_available = 1` ⇒ mai `Confidence = Alta`" è argomentata solo verso finestre più lunghe di 3, ma la griglia include `train_window = 2` | il caso tiene (massimo raggiungibile a tw=2: `(0.40×0.5 + 0.40×38/60)/0.80 ≈ 0.57` → Media), ma va scritto: è un check di livello ERROR |
| R20 | §20.4.0 Target B: "un giocatore con `Pv_target = 0` riceve prodotto 0", a una sezione di distanza da "`Fm = null` non è `Fm = 0`" | mezza frase: lo 0 è una convenzione **di target**, definita sul solo `Pv`, e non va implementata come `fillna(0)` su `Fm` |
| R21 | §27 e §28 (changelog storici) contengono voci ora false e non marcate: righe `QUOTED_ONLY` indicate come presenti in §4 e §22 (riga 1406, 1416); §27 #10 dà `D/A -25→100` (ora -15→100); §27 #2 attribuisce alle quotazioni una distinzione che ora viene dalle statistiche; §28 #3 definisce l'indice del Trend sull'elenco `seasons` mentre §18.1 ora dice "finestra di train" | non riscrivere la storia: una riga in testa a §27 e §28 ("voci superate dalla revisione della sezione 29") e correggere i soli **puntatori** che nominano una sezione che non contiene più la cosa |

---

## 5. Cosa è confermato — non rifare la verifica

Ricalcolato dai file. Questi numeri della spec sono **esatti** e possono essere usati come soglie QC:

| Affermazione | Esito |
|---|---|
| Schema identico su 10 file stats e 11 quotazioni, nessun parser condizionale | ✅ |
| 2306 Id distinti su 10 stagioni; **0** duplicati intra-stagione | ✅ |
| 24 Id con più grafie del nome | ✅ |
| 4 Nomi su più Id: Vergara (363/7223), Gori (205/6255), Buksa (5459/7249), Ndiaye (5859/7202) | ✅ (Id esatti) |
| 74/2306 Id (3.2%) cambiano `R` | ✅ |
| Righe `Pv = 0` per stagione: 107-153 | ✅ (107,117,131,153,120,113,125,120,118,116) |
| `QUOTED_ONLY` vuoto su tutte le stagioni (`quotati ∉ stats` = 0) | ✅ |
| `stats = Tutti ⊎ Ceduti`, esatto e disgiunto | ✅ **ma su 10 stagioni, non 6** (vedi R2) |
| Quota `left_mid_season` fra i `Pv = 0` | ✅ 55.9%-74.5% (vedi R15) |
| Nessuno scalino nella distribuzione `Pv` nel 2020 — B7 correttamente soppresso | ✅ mediana 18-21, media 18.89-19.84, `Pv≥30` 121-148 |
| 2019/20 non anomalo salvo la quota di `Pv=0` (22.4%) | ✅ |
| `Qt.A ≠ Qt.I` ~85% nei file storici vs 17% nel 2026/27 | ✅ 79.9-86.0% vs **17.4%** |
| `FVM` a 0 fino al 2021/22, popolato dal 2022/23 | ✅ (esattamente 0 righe vs tutte le righe) |
| **Extra**: `Qt.I` popolato al 100% anche nelle righe `Ceduti` | ✅ — è ciò che rende R3 risolvibile |

**Copertura B1-B14**: tutti recepiti. B1 ✅ · B2 ✅ · B3 ⚠️ R1/R2/R12 · B4 ⚠️ R7/R8/R9 · B5 ✅ ·
B6 ✅ · B7 ✅ (soppresso correttamente, riportato come fatto) · B8 ⚠️ R6 · B9 ⚠️ R3 ·
B10 ⚠️ R4/R5 · B11 ✅ (colonna assente da §21, livello concettuale conservato) · B12 ⚠️ R10 ·
B13 ✅ · B14 ⚠️ R14.

---

## 6. Ordine di lavoro suggerito

1. **R1, R2** — sono nel layer di ingestione e cambiano quali file/fogli si leggono. Prima di tutto
   il resto, e prima di qualunque codice.
2. **R7** — decisione operativa che va presa **adesso**: da questa stagione in poi vanno archiviati
   due snapshot, non uno. Se si perde l'archiviazione di fine stagione 2026/27, `left_mid_season`
   diventa incalcolabile per quella stagione e il problema si ripresenta identico alla prossima
   revisione.
3. **R4, R5, R6** — la regola di selezione e i suoi gate. Vanno chiusi prima del backtest, non
   durante: sono i criteri che il backtest deve poter applicare senza discrezionalità.
4. **R3, R9** — baseline esterna: universo e semantica.
5. **R10, R11, R12, R13, R14** — correzioni puntuali di spec.
6. **R15-R21** — minori, in un unico passaggio.

Il punto 1 può far emergere altre divergenze fra le tabelle del piano e i file: **due affermazioni su
quattordici erano false**, e sono state trovate solo rileggendo i fogli. Vale la pena che il layer di
ingestione riverifichi le proprie soglie QC dai dati alla prima esecuzione, invece di fidarsi dei
numeri scritti nella spec — con l'eccezione di quelli della sezione 5 di questo documento, che sono
già stati ricalcolati.
