# Quotazioni giocatori — Legenda

File dati in questa cartella: `Quotazioni_Fantacalcio_Stagione_20XX_YY.xlsx` (stagioni 2022/23, 2023/24, 2024/25, 2025/26, 2026/27). Export standard di Fantacalcio.it — la quotazione di listino usata come base per l'asta (non il prezzo realmente pagato: per quello vedi [STORICO_ASTE.md](../../docs/STORICO_ASTE.md)).

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
