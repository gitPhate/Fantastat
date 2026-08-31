"""Transparent, recency-weighted player rankings for Fantacalcio Classic."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import re
from statistics import median
from typing import Iterable

import pandas as pd


ROLES = ("P", "D", "C", "A")
SEASON_RE = re.compile(r"^(\d{4})_(\d{2})$")


class RankingError(ValueError):
    """An input or configuration error that must stop a ranking run."""


@dataclass(frozen=True)
class RankingConfig:
    history_window: int
    recency_weights: tuple[int, ...]
    validation_folds: int
    min_valid_folds: int
    min_comparable_players: int
    recency_weights_by_role: dict[str, tuple[int, ...]]

    def weights_for_role(self, role: str) -> tuple[int, ...]:
        return self.recency_weights_by_role.get(role, self.recency_weights)


def _parse_weights(raw: str) -> tuple[int, ...]:
    return tuple(int(value.strip()) for value in raw.strip("[]").split(","))


def _validate_weights(weights: tuple[int, ...], history_window: int) -> bool:
    return (len(weights) == history_window and all(weight > 0 for weight in weights)
            and all(a > b for a, b in zip(weights, weights[1:])))


def load_config(path: Path) -> RankingConfig:
    """Read the deliberately small project YAML without adding a YAML dependency."""
    if not path.is_file():
        raise RankingError(f"Configurazione mancante: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "ranking:")
    except StopIteration as exc:
        raise RankingError(f"Configurazione non valida in {path}: sezione ranking mancante") from exc
    values: dict[str, str] = {}
    nested: dict[str, dict[str, str]] = {}
    i = start + 1
    while i < len(lines):
        line = lines[i]
        if line and not line[0].isspace():
            break
        match = re.match(r"^\s+([A-Za-z_]+):\s*(.*?)\s*$", line)
        if match:
            key, value = match.group(1), match.group(2)
            if value == "":
                base_indent = len(line) - len(line.lstrip())
                sub: dict[str, str] = {}
                j = i + 1
                while j < len(lines):
                    sub_line = lines[j]
                    if not sub_line.strip():
                        j += 1
                        continue
                    sub_indent = len(sub_line) - len(sub_line.lstrip())
                    if sub_indent <= base_indent:
                        break
                    sub_match = re.match(r"^\s+([A-Za-z_]+):\s*(.*?)\s*$", sub_line)
                    if sub_match:
                        sub[sub_match.group(1)] = sub_match.group(2)
                    j += 1
                nested[key] = sub
                i = j
                continue
            values[key] = value
        i += 1
    required = ("history_window", "recency_weights", "validation_folds", "min_valid_folds", "min_comparable_players")
    if any(key not in values for key in required):
        raise RankingError(f"Configurazione non valida in {path}: chiavi ranking mancanti")
    role_overrides_raw = nested.get("recency_weights_by_role", {})
    if any(role not in ROLES for role in role_overrides_raw):
        raise RankingError(f"Configurazione non valida in {path}: ruolo sconosciuto in recency_weights_by_role")
    try:
        weights = _parse_weights(values["recency_weights"])
        role_weights = {role: _parse_weights(raw) for role, raw in role_overrides_raw.items()}
        config = RankingConfig(
            int(values["history_window"]), weights, int(values["validation_folds"]),
            int(values["min_valid_folds"]), int(values["min_comparable_players"]), role_weights,
        )
    except ValueError as exc:
        raise RankingError(f"Configurazione non valida in {path}: valori non numerici") from exc
    if (config.history_window <= 0 or config.validation_folds <= 0 or config.min_valid_folds <= 0
            or config.min_comparable_players <= 0 or config.min_valid_folds > config.validation_folds
            or not _validate_weights(weights, config.history_window)
            or any(not _validate_weights(w, config.history_window) for w in role_weights.values())):
        raise RankingError(f"Configurazione non valida in {path}: pesi o soglie non validi")
    return config


def season_start(season: str) -> int:
    match = SEASON_RE.fullmatch(season)
    if not match or int(match.group(2)) != (int(match.group(1)) + 1) % 100:
        raise RankingError("Stagione non valida: usare il formato YYYY_YY (ad esempio 2026_27)")
    return int(match.group(1))


def season_name(start: int) -> str:
    return f"{start}_{(start + 1) % 100:02d}"


def round_value(value: float, digits: int = 2) -> float:
    """Use decimal rounding so CSV results do not depend on binary float ties."""
    quantum = Decimal("1").scaleb(-digits)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def round_product(left: float, right: float, digits: int = 2) -> float:
    quantum = Decimal("1").scaleb(-digits)
    return float((Decimal(str(left)) * Decimal(str(right))).quantize(quantum, rounding=ROUND_HALF_UP))


def player_list_path(root: Path, season: str) -> Path:
    return root / "data" / "player_lists" / f"Quotazioni_Fantacalcio_Stagione_{season}.xlsx"


def stats_path(root: Path, season: str) -> Path:
    return root / "data" / "stats" / f"Statistiche_Fantacalcio_Stagione_{season}.xlsx"


def _read_excel(path: Path, season: str, columns: list[str], kind: str) -> pd.DataFrame:
    if not path.is_file():
        raise RankingError(f"File {kind} mancante per stagione {season}: {path}")
    try:
        data = pd.read_excel(path, sheet_name="Tutti", header=1)
    except ValueError as exc:
        raise RankingError(f"Foglio Tutti mancante o non leggibile in {path} (stagione {season})") from exc
    missing = [column for column in columns if column not in data.columns]
    if missing:
        raise RankingError(f"Colonne mancanti in {path} (stagione {season}): {', '.join(missing)}")
    data = data.loc[:, columns].copy()
    if data["Id"].isna().any() or data["Id"].duplicated().any():
        raise RankingError(f"Id nullo o duplicato in {path} (stagione {season})")
    return data


def read_player_list(root: Path, season: str, descriptive: bool = False) -> pd.DataFrame:
    columns = ["Id", "R"] + (["Nome", "Squadra"] if descriptive else [])
    data = _read_excel(player_list_path(root, season), season, columns, "listone")
    invalid = ~data["R"].isin(ROLES)
    if invalid.any():
        raise RankingError(f"Ruolo non valido in {player_list_path(root, season)} (stagione {season})")
    return data


def read_stats(root: Path, season: str) -> pd.DataFrame:
    path = stats_path(root, season)
    data = _read_excel(path, season, ["Id", "Pv", "Fm"], "statistiche")
    pv = pd.to_numeric(data["Pv"], errors="coerce")
    if pv.isna().any() or (pv < 0).any() or (pv > 38).any():
        raise RankingError(f"Pv non valido in {path} (stagione {season})")
    fm = pd.to_numeric(data["Fm"], errors="coerce")
    if (data["Fm"].notna() & fm.isna()).any() or ((pv > 0) & fm.isna()).any():
        raise RankingError(f"Fm non valida o mancante in {path} (stagione {season})")
    data["Pv"] = pv.astype(float)
    data["Fm"] = fm.astype(float)
    return data


def predict(ids: Iterable[object], seasons: list[str], statistics: dict[str, pd.DataFrame], weights_recent_first: tuple[int, ...]) -> dict[object, tuple[float, float, float] | None]:
    """Return rounded (appearances, fantasy average, expected points) by ID."""
    weights = dict(zip(reversed(seasons), weights_recent_first))
    rows = pd.concat(
        [statistics[season].assign(_weight=weights[season]) for season in seasons],
        ignore_index=True,
    )
    by_id = {key: group for key, group in rows.groupby("Id", sort=False)}
    result: dict[object, tuple[float, float, float] | None] = {}
    for player_id in ids:
        group = by_id.get(player_id)
        if group is None:
            result[player_id] = None
            continue
        weighted_pv = float((group["_weight"] * group["Pv"]).sum())
        if weighted_pv == 0:
            result[player_id] = None
            continue
        appearance_denominator = float(group["_weight"].sum())
        appearances = round_value(weighted_pv / appearance_denominator)
        fantasy_average = round_value(float((group["_weight"] * group["Pv"] * group["Fm"].fillna(0)).sum()) / weighted_pv)
        result[player_id] = (appearances, fantasy_average, round_product(appearances, fantasy_average))
    return result


def rank_players(players: pd.DataFrame, forecasts: dict[object, tuple[float, float, float] | None], validation: dict[str, str]) -> pd.DataFrame:
    output = players.rename(columns={"R": "Ruolo"}).copy()
    values = output["Id"].map(forecasts)
    output[["PresenzePreviste", "FantamediaPrevista", "PuntiAttesi"]] = pd.DataFrame(values.tolist(), index=output.index)
    output["Rank"] = pd.NA
    output["Validazione"] = output["Ruolo"].map(validation)
    output.loc[values.isna(), "Validazione"] = "SENZA_STORICO"
    output["_name"] = output["Nome"].fillna("").astype(str).str.casefold()
    chunks = []
    for role in ROLES:
        group = output[output["Ruolo"] == role].copy()
        usable = group[group["PuntiAttesi"].notna()].sort_values(["PuntiAttesi", "_name"], ascending=[False, True], kind="mergesort")
        usable["Rank"] = usable["PuntiAttesi"].rank(method="dense", ascending=False).astype("Int64")
        chunks.extend([usable, group[group["PuntiAttesi"].isna()].sort_values("_name", kind="mergesort")])
    result = pd.concat(chunks, ignore_index=True)
    result["Rank"] = result["Rank"].astype("Int64")
    return result[["Id", "Nome", "Squadra", "Ruolo", "Rank", "PresenzePreviste", "FantamediaPrevista", "PuntiAttesi", "Validazione"]]


def spearman(left: list[float], right: list[float]) -> float | None:
    a = pd.Series(left).rank(method="average")
    b = pd.Series(right).rank(method="average")
    value = a.corr(b, method="pearson")
    return None if pd.isna(value) else float(value)


def validate(root: Path, target_start: int, config: RankingConfig) -> tuple[dict[str, str], pd.DataFrame]:
    metrics: dict[str, list[tuple[float, float, float, float]]] = {role: [] for role in ROLES}
    for fold_start in range(target_start - config.validation_folds, target_start):
        target = season_name(fold_start)
        target_players = read_player_list(root, target)
        target_stats = read_stats(root, target)
        target_ids = set(target_players["Id"])
        missing = target_ids - set(target_stats["Id"])
        if missing:
            raise RankingError(f"Giocatore del listone assente dalle statistiche in {stats_path(root, target)} (stagione {target})")
        history = [season_name(year) for year in range(fold_start - config.history_window, fold_start)]
        history_stats = {season: read_stats(root, season) for season in history}
        previous = history_stats[history[-1]].set_index("Id")
        actual = target_stats.set_index("Id")
        for role in ROLES:
            ids = target_players.loc[target_players["R"] == role, "Id"]
            model = predict(ids, history, history_stats, config.weights_for_role(role))
            model_points: list[float] = []
            baseline_points: list[float] = []
            actual_points: list[float] = []
            for player_id in ids:
                forecast = model[player_id]
                if forecast is None or player_id not in previous.index:
                    continue
                baseline = previous.loc[player_id]
                if baseline["Pv"] <= 0 or pd.isna(baseline["Fm"]):
                    continue
                real = actual.loc[player_id]
                model_points.append(forecast[2])
                baseline_points.append(round_product(float(baseline["Pv"]), float(baseline["Fm"])))
                actual_points.append(round_product(float(real["Pv"]), 0 if pd.isna(real["Fm"]) else float(real["Fm"])))
            if len(actual_points) < config.min_comparable_players:
                continue
            model_spearman = spearman(model_points, actual_points)
            baseline_spearman = spearman(baseline_points, actual_points)
            if model_spearman is None or baseline_spearman is None:
                continue
            model_mae = sum(abs(a - b) for a, b in zip(model_points, actual_points)) / len(actual_points)
            baseline_mae = sum(abs(a - b) for a, b in zip(baseline_points, actual_points)) / len(actual_points)
            metrics[role].append((model_mae, baseline_mae, model_spearman, baseline_spearman))
    rows = []
    statuses: dict[str, str] = {}
    for role in ROLES:
        values = metrics[role]
        if not values:
            medians = (None, None, None, None)
        else:
            medians = tuple(median(column) for column in zip(*values))
        if len(values) < config.min_valid_folds:
            status = "VALIDAZIONE_INSUFFICIENTE"
        elif medians[0] < medians[1] and medians[2] > medians[3]:
            status = "VALIDATO"
        else:
            status = "NON_VALIDATO"
        statuses[role] = status
        rows.append((role, len(values), *medians, status))
    return statuses, pd.DataFrame(rows, columns=["Ruolo", "FoldValidi", "MAE_Modello_Mediana", "MAE_Baseline_Mediana", "Spearman_Modello_Mediana", "Spearman_Baseline_Mediana", "Validazione"])


def run(root: Path, season: str) -> tuple[Path, Path]:
    start = season_start(season)
    config = load_config(root / "config.yaml")
    players = read_player_list(root, season, descriptive=True)
    history = [season_name(year) for year in range(start - config.history_window, start)]
    statistics = {year: read_stats(root, year) for year in history}
    validation_status, validation = validate(root, start, config)
    forecasts: dict[object, tuple[float, float, float] | None] = {}
    for role in ROLES:
        role_ids = players.loc[players["R"] == role, "Id"]
        forecasts.update(predict(role_ids, history, statistics, config.weights_for_role(role)))
    ranking = rank_players(players, forecasts, validation_status)
    output = root / "output"
    output.mkdir(exist_ok=True)
    ranking_path = output / f"ranking_{season}.csv"
    validation_path = output / f"validation_{season}.csv"
    ranking.to_csv(ranking_path, index=False, encoding="utf-8", float_format="%.2f", na_rep="")
    validation.to_csv(validation_path, index=False, encoding="utf-8", float_format="%.4f", na_rep="")
    return ranking_path, validation_path
