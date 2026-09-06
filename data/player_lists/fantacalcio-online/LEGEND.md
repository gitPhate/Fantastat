# Fantacalcio Online — Legenda

Questa cartella contiene i workbook Fantacalcio Online, i loro CSV estratti e
la mappa esplicita che collega i record Online agli `Id` ufficiali.

Il convertitore legge la prima scheda con intestazioni effettive sulla riga due
e genera un CSV con queste colonne:

| Colonna CSV | Colonna sorgente | Significato |
|---|---|---|
| `NomeOnline` | `Nome` | Nome completo nel formato della fonte Online. |
| `R` | `Ruolo Fantacalcio.it` | Ruolo Classic dichiarato dalla fonte. |
| `SquadraOnline` | `Squadra` | Club dichiarato dalla fonte. |
| `starting_index` | `IS %` | Indice di titolarità. |
| `age` | `ETA'` | Età del giocatore. |

Per ogni stagione deve essere presente
`Collegamenti_Fantacalcio_Online_Stagione_YYYY_YY.csv`, con colonne `Id`,
`NomeOnline`, `SquadraOnline`. Il file contiene solo le associazioni verificate;
un giocatore ufficiale senza controparte Online resta nell'aggregato con i due
campi Online vuoti. L'aggregato è un'evidenza per la UI e non influenza il
ranking.
