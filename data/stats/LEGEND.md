# Statistiche giocatori — Legenda

File dati in questa cartella: `Statistiche_Fantacalcio_Stagione_20XX_YY.xlsx` (stagioni 2023/24, 2024/25, 2025/26). Export standard di Fantacalcio.it.

Ogni file contiene un solo foglio, **Tutti**, con una riga per giocatore (i fogli separati per ruolo — Portieri/Difensori/Centrocampisti/Attaccanti, che duplicavano semplicemente un sottoinsieme filtrato delle stesse righe — sono stati rimossi).

## Colonne

| Colonna | Significato |
|---|---|
| **Id** | ID identificativo del giocatore nel database di Fantacalcio.it |
| **R** | Ruolo classico: `P`=Portiere, `D`=Difensore, `C`=Centrocampista, `A`=Attaccante |
| **Rm** | Ruolo Mantra (più granulare: `Por`, `Dc`, `Dd`, `Ds`, `E`=esterno, `M`=mediano, `C`=centrocampista, `T`=trequartista, `W`=ala, `Pc`=punta centrale, `A`=attaccante...). Più valori separati da `;` indicano un giocatore eleggibile su più ruoli Mantra (es. `T;A`) |
| **Nome** | Nome/cognome del giocatore |
| **Squadra** | Squadra di Serie A di appartenenza in quella stagione |
| **Pv** | Partite a Voto — numero di partite in cui ha ricevuto una valutazione (cioè ha giocato) |
| **Mv** | Media Voto — voto medio in pagella, senza bonus/malus |
| **Fm** | FantaMedia — media voto **con** bonus/malus applicati (il voto fantacalcistico vero e proprio) |
| **Gf** | Gol Fatti |
| **Gs** | Gol Subiti (rilevante per portieri/difensori) |
| **Rp** | Rigori Parati (portieri) |
| **Rc** | Rigori Calciati (totale rigori battuti) |
| **R+** | Rigori Realizzati |
| **R-** | Rigori Sbagliati |
| **Ass** | Assist |
| **Amm** | Ammonizioni (cartellini gialli) |
| **Esp** | Espulsioni (cartellini rossi) |
| **Au** | Autogol |

Nota: rilevante per il [Modificatore Difesa](../../docs/RULES.md#modificatore-difesa-introdotto-202526--regola-contestata-approvata-6-s%C3%AC--3-no) — la Mv (non la Fm) è la base del calcolo di quel bonus.
