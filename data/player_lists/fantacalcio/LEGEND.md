# Quotazioni giocatori — Legenda

Questa cartella contiene i workbook e i CSV estratti dal foglio **Tutti** del
listone ufficiale Fantacalcio.it. Questi CSV definiscono l'universo Classic e
sono l'unico input dei calcoli di ranking.

Ogni file contiene un solo foglio, **Tutti**, con una riga per giocatore (i fogli separati per ruolo — Portieri/Difensori/Centrocampisti/Attaccanti — e il foglio **Ceduti** sono stati rimossi perché ridondanti/fuori scope).

## Colonne

| Colonna | Significato |
|---|---|
| **Id** | ID identificativo del giocatore nel database di Fantacalcio.it |
| **R** | Ruolo classico: `P`=Portiere, `D`=Difensore, `C`=Centrocampista, `A`=Attaccante |
| **RM** | Ruolo Mantra (più granulare: `Por`, `Dc`, `Dd`, `Ds`, `E`=esterno, `M`=mediano, `C`=centrocampista, `T`=trequartista, `W`=ala, `Pc`=punta centrale, `A`=attaccante...) |
| **Nome** | Nome/cognome del giocatore |
| **Squadra** | Squadra di Serie A di appartenenza |
| **Qt.A** | Quotazione Attuale (classic) — quotazione di listino aggiornata, in crediti, da usare come base d'asta |
| **Qt.I** | Quotazione Iniziale (classic) — quotazione di listino a inizio stagione, prima di eventuali aggiornamenti |
| **Diff.** | Differenza tra Qt.A e Qt.I (classic) — variazione della quotazione durante la stagione |
| **Qt.A M** | Quotazione Attuale, regime Mantra |
| **Qt.I M** | Quotazione Iniziale, regime Mantra |
| **Diff.M** | Differenza Qt.A M − Qt.I M, regime Mantra |
| **FVM** | FantaValore di Mercato (classic) — indice sintetico di convenienza/valore calcolato da Fantacalcio.it (non è un prezzo in crediti, è un punteggio di ranking) |
| **FVM M** | FantaValore di Mercato, regime Mantra |

Nota: la lega gioca in formato **Classic** (vedi [RULES.md](../../docs/RULES.md)), quindi le colonne di interesse primario sono `Qt.A` e `FVM`; le colonne `*M` (Mantra) non sono rilevanti per questa lega ma restano nel file perché fanno parte dell'export originale.
