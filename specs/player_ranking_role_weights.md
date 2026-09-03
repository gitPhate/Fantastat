# Addendum storico: pesi di recenza specifici per ruolo (P, D)

Questo documento registra tentativi non adottati di pesi specifici per ruolo.
Non sovrascrive `player_ranking.md`: la configurazione globale corrente e'
definita in `config.yaml`.

## 1. Contesto

Il backtest per la stagione 2026/27 (fold 2021/22-2025/26, pesi condivisi
`[5, 4, 3, 2, 1]`) ha prodotto `NON_VALIDATO` per `P`, `D` e `C`, e `VALIDATO`
solo per `A`. Questo addendum riguarda esclusivamente `P` e `D`: il risultato
di `C` e' rimasto misto e marginale (MAE del modello migliore della baseline,
Spearman leggermente peggiore) e nessun ragionamento di dominio indipendente
dal backtest gia' osservato giustifica un intervento su quel ruolo.

## 2. Ipotesi di dominio

- **P**: la Fantamedia dei portieri e' pesantemente influenzata dal malus per
  gol subiti, che riflette la solidita' difensiva della squadra corrente
  molto piu' che la continuita' individuale del portiere. Questo contesto
  cambia piu' rapidamente di quanto rifletta una media pesata su 5 stagioni
  con decadimento lineare: serve un decadimento marcatamente piu' ripido
  verso la stagione piu' recente.
- **D**: i difensori sono soggetti a maggiore rotazione/turnover di ruolo e
  minutaggio rispetto a centrocampisti e attaccanti. Un decadimento
  moderatamente piu' ripido di quello di default e' giustificato dalla stessa
  logica, in misura minore rispetto ai portieri.

## 3. Metodo di scelta dei parametri

La sezione 5 di `player_ranking.md` vieta di ottimizzare i pesi a posteriori
sui risultati del backtest. I dati disponibili partono dalla stagione
2016/17 e sono gia' interamente impiegati dal fold piu' antico del backtest
attuale (target 2021/22, storico 2016/17-2020/21): non esistono fold
storicamente vergini su cui cercare nuovi parametri.

Per rispettare comunque il vincolo, si adotta il seguente metodo:

1. un solo candidato per ruolo, scelto esclusivamente per ragionamento di
   dominio (sezione 2), non per ricerca sui dati;
2. ciascun candidato viene eseguito sul backtest una sola volta, come
   conferma e non come ciclo di ricerca;
3. nessun ripescaggio: se un candidato non raggiunge il criterio di
   accettazione (sezione 5), si scarta definitivamente e si torna ai pesi di
   default per quel ruolo, senza provare un secondo candidato.

## 4. Configurazioni valutate

`history_window` resta invariato a 5 per entrambi i ruoli, per preservare la
copertura prevista dalla sezione 8.2 di `player_ranking.md` quando la
stagione piu' recente manca dalle statistiche di un giocatore.

```yaml
ranking:
  recency_weights_by_role:
    P: [16, 8, 4, 2, 1]
    D: [8, 5, 3, 2, 1]
```

`P` usa un decadimento piu' ripido di `D` (rapporto 2 tra stagioni
consecutive contro un rapporto Fibonacci-inverso per `D`), coerentemente con
l'ipotesi della sezione 2. Al momento della valutazione, i ruoli non elencati
(`C`, `A`) usavano i pesi globali `[5, 4, 3, 2, 1]`.

## 5. Criterio di accettazione

Un candidato e' adottato solo se il ruolo raggiunge lo stato `VALIDATO`
definito nella sezione 10.5 di `player_ranking.md`: almeno `min_valid_folds`
fold validi, MAE mediano del modello strettamente inferiore alla baseline e
Spearman mediana del modello strettamente superiore alla baseline.

In caso contrario si mantengono i pesi globali allora in vigore per quel ruolo,
e il ruolo resta con lo stato di validazione che ne risulta
(`NON_VALIDATO` o `VALIDAZIONE_INSUFFICIENTE`).

## 6. Esito

I candidati della sezione 4 sono stati eseguiti una sola volta sul backtest
descritto in `output/validation_2026_27.csv` (fold 2021/22-2025/26). Nessuno
dei due raggiunge `VALIDATO`: entrambi restano peggio della baseline su
entrambe le metriche, pur con un miglioramento rispetto ai pesi di default.
Per la regola della sezione 3 (nessun ripescaggio), i candidati sono stati
scartati definitivamente. Successivamente il progetto ha adottato, per scelta
di prodotto applicata a tutti i ruoli, i pesi globali `[10, 5, 3, 2, 1]`; vedi
`player_ranking.md` e `config.yaml`.

- **P**: candidato `[16, 8, 4, 2, 1]` scartato. MAE modello 42.0412 (baseline
  36.5344), Spearman modello 0.6760 (baseline 0.7217). Migliora rispetto ai
  pesi globali allora in vigore (MAE 45.9025, Spearman 0.6260) ma resta peggio
  della baseline su entrambe le metriche. Stato finale: `NON_VALIDATO`.
- **D**: candidato `[8, 5, 3, 2, 1]` scartato. MAE modello 51.3637 (baseline
  50.4270), Spearman modello 0.3526 (baseline 0.4270). Migliora rispetto ai
  pesi globali allora in vigore (MAE 52.5878, Spearman 0.3198) ma resta peggio
  della baseline su entrambe le metriche. Stato finale: `NON_VALIDATO`.

Un futuro tentativo di validare P o D dovrebbe cercare una leva diversa dal
solo decadimento dei pesi di recenza entro la finestra di 5 stagioni: la
direzione (decadimento piu' ripido) e' quella giusta secondo le metriche, ma
l'entita' del miglioramento non basta a colmare il divario con la baseline
per nessuno dei due ruoli.
