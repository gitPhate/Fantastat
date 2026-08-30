"""Pre-auction, role-specific projections for the 2026/27 list.

This module deliberately consumes the normalised historical pipeline instead
of re-reading spreadsheets or inventing a second identity/join convention.
Its public seam is :func:`run_projection`.
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from ranking_pipeline import QcLog, PipelineError, build_ranking, calculate_season_features, load_sources


ROLES = ("P", "D", "C", "A")


@dataclass
class RidgeRegressor:
    """Median-imputed, standardised ridge regression kept private to v2."""

    columns: list[str]
    alpha: float
    medians: pd.Series | None = None
    means: pd.Series | None = None
    scales: pd.Series | None = None
    coefficients: np.ndarray | None = None

    def fit(self, frame: pd.DataFrame, target: pd.Series) -> "RidgeRegressor":
        x = frame[self.columns].astype(float)
        self.medians = x.median().fillna(0.0)
        x = x.fillna(self.medians)
        self.means = x.mean()
        self.scales = x.std(ddof=0).replace(0, 1.0).fillna(1.0)
        z = ((x - self.means) / self.scales).to_numpy(float)
        design = np.column_stack([np.ones(len(z)), z])
        penalty = np.eye(design.shape[1]) * self.alpha
        penalty[0, 0] = 0.0
        self.coefficients = np.linalg.pinv(design.T @ design + penalty) @ design.T @ target.to_numpy(float)
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        if any(v is None for v in [self.medians, self.means, self.scales, self.coefficients]):
            raise PipelineError("Projection model was used before fitting")
        x = frame[self.columns].astype(float).fillna(self.medians)
        z = ((x - self.means) / self.scales).to_numpy(float)
        return np.column_stack([np.ones(len(z)), z]) @ self.coefficients


def _season_key(season: str) -> int:
    return int(season.split("/")[0])


def _past_seasons(all_seasons: list[str], before: str, window: int) -> list[str]:
    return [season for season in all_seasons if _season_key(season) < _season_key(before)][-window:]


def _weighted(rows: pd.DataFrame, column: str, weights: dict[str, float]) -> float:
    valid = rows.dropna(subset=[column])
    if valid.empty:
        return math.nan
    weight = valid["Stagione"].map(weights).astype(float)
    return float(np.average(valid[column], weights=weight))


def _slope(rows: pd.DataFrame, column: str, positions: dict[str, int]) -> float:
    valid = rows.dropna(subset=[column])
    if len(valid) < 2:
        return math.nan
    return float(np.polyfit(valid["Stagione"].map(positions), valid[column], 1)[0])


def _player_history(historical: pd.DataFrame | dict[int, pd.DataFrame], player_id: int, role: str, seasons: list[str]) -> tuple[pd.DataFrame, list[str], bool]:
    if isinstance(historical, dict):
        player_rows = historical.get(player_id)
        if player_rows is None:
            player_rows = next(iter(historical.values())).iloc[0:0]
    else:
        player_rows = historical[historical.Id.eq(player_id)]
    history = player_rows[player_rows.Stagione.isin(seasons)].copy()
    roles = history.R.dropna().astype(str).tolist()
    crosses_goalkeeper_boundary = "P" in roles and any(value != "P" for value in roles)
    if crosses_goalkeeper_boundary:
        history = history[history.R.eq(role)].copy()
    return history.sort_values("Stagione"), roles, crosses_goalkeeper_boundary


def _snapshot(historical: pd.DataFrame | dict[int, pd.DataFrame], player: pd.Series, before: str, config: dict[str, Any]) -> dict[str, Any]:
    projection = config["projection"]
    seasons = _past_seasons(config["seasons"], before, projection["feature_window"])
    history, roles, _ = _player_history(historical, int(player.Id), str(player.R), seasons)
    played = history[history.RowType.eq("PLAYED")].copy()
    weights = {season: projection["time_decay"] ** index for index, season in enumerate(seasons)}
    positions = {season: index for index, season in enumerate(seasons)}
    last = played.tail(1)
    last_row = last.iloc[0] if not last.empty else None
    season_count = len(played)
    pv_total = float(played.Pv.sum()) if not played.empty else 0.0
    return {
        "Id": int(player.Id), "R": str(player.R),
        "R_Storico_Projection": "/".join(roles) if roles and any(value != player.R for value in roles) else math.nan,
        "Seasons_Played_Projection": season_count,
        "Seasons_In_Squad_Projection": len(history),
        "Pv_Total_Projection": pv_total,
        "PredictionStatus": "OK" if season_count else "INSUFFICIENT_HISTORY",
        "Pv_Last": last_row.Pv if last_row is not None else math.nan,
        "Fm_Last": last_row.Fm if last_row is not None else math.nan,
        "Mv_Last": last_row.Mv if last_row is not None else math.nan,
        "Pv_Weighted": _weighted(played, "Pv", weights),
        "Fm_Weighted": _weighted(played, "Fm", weights),
        "Mv_Weighted": _weighted(played, "Mv", weights),
        "Performance_Weighted": _weighted(played, "Performance_stagione", weights),
        "Seasons_Played": float(season_count), "Seasons_In_Squad": float(len(history)), "Pv_Total": pv_total,
        "Availability_Rate": season_count / len(seasons) if seasons else math.nan,
        "Pv_Trend": _slope(played, "Pv", positions), "Fm_Trend": _slope(played, "Fm", positions),
        "Fm_Stability": float(played.Fm.std(ddof=1)) if season_count >= 2 else math.nan,
        "Performance_Trend": _slope(played, "Performance_stagione", positions),
        "Left_Mid_Season_Count": float(history.left_mid_season.fillna(False).sum()),
        "Role_Change_Flag": float(len(set(roles)) > 1),
    }


def _snapshots(historical: pd.DataFrame | dict[int, pd.DataFrame], universe: pd.DataFrame, before: str, config: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame([_snapshot(historical, player, before, config) for _, player in universe.iterrows()])


def _universe_for_season(quotes: dict[str, pd.DataFrame], season: str) -> pd.DataFrame:
    universe = quotes[season][["Id", "R", "Nome", "Squadra", "Qt.I"]].copy()
    if universe.Id.duplicated().any():
        raise PipelineError(f"Duplicate Id in projection universe {season}")
    return universe


def _training_rows(historical: pd.DataFrame, quotes: dict[str, pd.DataFrame], before: str, config: dict[str, Any]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for target in config["seasons"]:
        if _season_key(target) >= _season_key(before) or target not in quotes:
            continue
        # At least one prior season is necessary to produce a snapshot.
        if not _past_seasons(config["seasons"], target, config["projection"]["feature_window"]):
            continue
        snapshot = _snapshots(historical, _universe_for_season(quotes, target), target, config)
        realised = historical[historical.Stagione.eq(target)][["Id", "Pv", "Fm"]].copy()
        realised = realised.rename(columns={"Pv": "Pv_actual", "Fm": "Fm_actual"})
        joined = snapshot.merge(realised, on="Id", how="left", validate="one_to_one")
        joined["Punti_actual"] = np.where(joined.Pv_actual.ge(1), joined.Pv_actual * joined.Fm_actual, 0.0)
        rows.append(joined)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _season_examples(historical: pd.DataFrame, quotes: dict[str, pd.DataFrame], target: str,
                     config: dict[str, Any], snapshot_history: pd.DataFrame | dict[int, pd.DataFrame] | None = None) -> pd.DataFrame:
    """One leakage-free player snapshot and its realised target for a season."""
    universe = _universe_for_season(quotes, target)
    snapshot = _snapshots(snapshot_history if snapshot_history is not None else historical, universe, target, config)
    realised = historical[historical.Stagione.eq(target)][["Id", "Pv", "Fm"]].copy()
    realised = realised.rename(columns={"Pv": "Pv_actual", "Fm": "Fm_actual"})
    result = snapshot.merge(realised, on="Id", how="left", validate="one_to_one")
    result["Punti_actual"] = np.where(result.Pv_actual.ge(1), result.Pv_actual * result.Fm_actual, 0.0)
    return result


def _fit_models(training: pd.DataFrame, feature_columns: list[str], alpha: float) -> dict[str, tuple[RidgeRegressor, RidgeRegressor]]:
    models: dict[str, tuple[RidgeRegressor, RidgeRegressor]] = {}
    for role in ROLES:
        role_rows = training[(training.R.eq(role)) & training.PredictionStatus.eq("OK") & training.Pv_actual.notna()]
        fm_rows = role_rows[role_rows.Pv_actual.ge(1) & role_rows.Fm_actual.notna()]
        if len(role_rows) < len(feature_columns) + 2 or len(fm_rows) < len(feature_columns) + 2:
            raise PipelineError(f"Not enough training rows for projection role {role}")
        models[role] = (RidgeRegressor(feature_columns, alpha).fit(role_rows, role_rows.Pv_actual),
                        RidgeRegressor(feature_columns, alpha).fit(fm_rows, fm_rows.Fm_actual))
    return models


def _predict(snapshot: pd.DataFrame, models: dict[str, tuple[RidgeRegressor, RidgeRegressor]], config: dict[str, Any]) -> pd.DataFrame:
    result = snapshot.copy()
    result["Pv_predetta"] = math.nan; result["Fm_predetta"] = math.nan
    for role, group in result[result.PredictionStatus.eq("OK")].groupby("R"):
        pv_model, fm_model = models[role]
        pv = np.clip(pv_model.predict(group), 0.0, 38.0)
        fm = np.clip(fm_model.predict(group), *config["projection"]["fm_limits"])
        result.loc[group.index, "Pv_predetta"] = pv
        result.loc[group.index, "Fm_predetta"] = fm
    result["Punti_predetti"] = result.Pv_predetta * result.Fm_predetta
    return result


def _correlation(a: pd.Series, b: pd.Series, method: str) -> float:
    if len(a) < 2 or a.nunique() < 2 or b.nunique() < 2:
        return math.nan
    if method == "spearman":
        # pandas 3 delegates this to optional SciPy.  Average ranks are the
        # standard Spearman treatment of ties and keep v2 dependency-light.
        return float(a.rank(method="average").corr(b.rank(method="average"), method="pearson"))
    return float(a.corr(b, method="pearson"))


def _precision_at_n(predicted: pd.Series, actual: pd.Series, n: int) -> float:
    usable = pd.DataFrame({"predicted": predicted, "actual": actual}).dropna()
    if usable.empty:
        return math.nan
    size = min(n, len(usable))
    return len(set(usable.nlargest(size, "predicted").index) & set(usable.nlargest(size, "actual").index)) / size


def _metrics(values: pd.DataFrame, predicted: str, actual: str, precision_n: int) -> dict[str, float]:
    usable = values[[predicted, actual]].dropna()
    if usable.empty:
        return {"sample_size": 0, "coverage": 0.0, "mae": math.nan, "median_ae": math.nan, "pearson": math.nan, "spearman": math.nan, "precision_at_n": math.nan}
    error = (usable[predicted] - usable[actual]).abs()
    return {"sample_size": len(usable), "coverage": len(usable) / len(values) if len(values) else math.nan,
            "mae": float(error.mean()), "median_ae": float(error.median()),
            "pearson": _correlation(usable[predicted], usable[actual], "pearson"),
            "spearman": _correlation(usable[predicted], usable[actual], "spearman"),
            "precision_at_n": _precision_at_n(usable[predicted], usable[actual], precision_n)}


def _baseline(snapshot: pd.DataFrame) -> pd.DataFrame:
    result = snapshot.copy()
    result["Pv_baseline"] = result.Pv_Last
    result["Fm_baseline"] = result.Fm_Last
    result["Punti_baseline"] = result.Pv_Last * result.Fm_Last
    result["Pv_weighted_baseline"] = result.Pv_Weighted
    result["Fm_weighted_baseline"] = result.Fm_Weighted
    result["Punti_weighted_baseline"] = result.Pv_Weighted * result.Fm_Weighted
    return result


def _fold_results(historical: pd.DataFrame, quotes: dict[str, pd.DataFrame], target: str,
                  feature_columns: list[str], alpha: float, config: dict[str, Any],
                  training: pd.DataFrame | None = None, snapshot: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = training if training is not None else _training_rows(historical, quotes, target, config)
    models = _fit_models(train, feature_columns, alpha)
    if snapshot is None:
        universe = _universe_for_season(quotes, target)
        snapshot = _snapshots(historical, universe, target, config)
    predicted = _predict(snapshot, models, config)
    actual = historical[historical.Stagione.eq(target)][["Id", "Pv", "Fm"]].rename(columns={"Pv": "Pv_actual", "Fm": "Fm_actual"})
    scored = predicted.merge(actual, on="Id", how="left", validate="one_to_one")
    scored["Punti_actual"] = np.where(scored.Pv_actual.ge(1), scored.Pv_actual * scored.Fm_actual, 0.0)
    baseline = _baseline(scored)
    metric_rows: list[dict[str, Any]] = []
    calibration_rows: list[dict[str, Any]] = []
    for role in ROLES:
        group = baseline[baseline.R.eq(role)]
        for measure, actual_col in [("Pv", "Pv_actual"), ("Fm", "Fm_actual"), ("Punti", "Punti_actual")]:
            scope = group[group.Pv_actual.ge(1)] if measure == "Fm" else group
            model_prediction_col = "Punti_predetti" if measure == "Punti" else f"{measure}_predetta"
            for model, prediction_col in [
                ("model", model_prediction_col),
                ("baseline_last_season", f"{measure}_baseline"),
                ("baseline_weighted_history", f"{measure}_weighted_baseline"),
            ]:
                metric_rows.append({"fold": target, "role": role, "measure": measure, "model": model,
                                    **_metrics(scope, prediction_col, actual_col, config["projection"]["precision_n"][role])})
            calibration_rows.extend(_calibration(scope, target, role, measure, model_prediction_col, actual_col, config))
    return scored, pd.DataFrame(metric_rows), pd.DataFrame(calibration_rows)


def _calibration(values: pd.DataFrame, fold: str, role: str, measure: str, predicted: str, actual: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    usable = values[[predicted, actual]].dropna().copy()
    if usable.empty:
        return []
    bucket_count = min(config["projection"]["calibration_buckets"], usable[predicted].nunique())
    if bucket_count < 1:
        return []
    usable["bucket"] = pd.qcut(usable[predicted], q=bucket_count, duplicates="drop")
    return [{"fold": fold, "role": role, "measure": measure, "bucket": str(bucket), "sample_size": len(group),
             "predicted_mean": float(group[predicted].mean()), "actual_mean": float(group[actual].mean()),
             "mae": float((group[predicted] - group[actual]).abs().mean())}
            for bucket, group in usable.groupby("bucket", observed=True)]


def _candidate_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    points = metrics[(metrics.measure.eq("Punti")) & metrics.model.eq("model")].copy()
    return points.pivot_table(index=["candidate", "fold"], columns="role", values="mae", aggfunc="first").reset_index()


def _choose_candidate(all_metrics: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    points = all_metrics[(all_metrics.measure.eq("Punti")) & all_metrics.model.eq("model")].copy()
    # Count role/fold MAE wins.  This retains every role/fold result in the
    # report instead of hiding a choice behind an aggregate score.
    winners = points.loc[points.groupby(["fold", "role"])["mae"].transform("min").eq(points.mae)]
    win_counts = winners.groupby("candidate").size().rename("role_fold_mae_wins")
    medians = points.groupby("candidate").mae.median().rename("median_points_mae")
    summary = pd.concat([win_counts, medians], axis=1).fillna(0).reset_index()
    summary = summary.sort_values(["role_fold_mae_wins", "median_points_mae", "candidate"], ascending=[False, True, True], kind="stable")
    return str(summary.iloc[0].candidate), summary


def _selection_gate(metrics: pd.DataFrame, candidate: str) -> dict[str, Any]:
    subset = metrics[metrics.candidate.eq(candidate)]
    model = subset[subset.model.eq("model")].set_index(["fold", "role", "measure"])
    baseline = subset[subset.model.eq("baseline_last_season")].set_index(["fold", "role", "measure"])
    primary_passes = 0
    guardrail_failures = {role: 0 for role in ROLES}
    for fold in sorted(subset.fold.unique(), key=_season_key):
        points_model = model.xs((fold, "Punti"), level=("fold", "measure"))
        points_base = baseline.xs((fold, "Punti"), level=("fold", "measure"))
        common = points_model.index.intersection(points_base.index)
        primary_passes += sum(points_model.loc[role, "mae"] < points_base.loc[role, "mae"] for role in common) >= 3
        for role in ROLES:
            if role not in common:
                guardrail_failures[role] += 1
                continue
            for metric in ("spearman", "precision_at_n"):
                if points_model.loc[role, metric] < points_base.loc[role, metric] - 0.05:
                    guardrail_failures[role] += 1
                    break
    return {"primary_passes": primary_passes, "primary_pass": primary_passes >= 5,
            "guardrail_failures": guardrail_failures, "guardrail_pass": all(value <= 1 for value in guardrail_failures.values())}


def _confidence(snapshot: pd.DataFrame) -> pd.Series:
    score = (snapshot.Seasons_Played_Projection.clip(upper=5) / 5 * 0.45
             + (snapshot.Pv_Total_Projection.clip(upper=100) / 100) * 0.45
             + snapshot.Fm_Stability.notna().astype(float) * 0.10)
    return pd.Series(np.select([score >= .75, score >= .45], ["Alta", "Media"], default="Bassa"), index=snapshot.index)


def _auction_values(predicted: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    result = predicted.copy()
    result["Punti_sostituzione"] = math.nan; result["Surplus_punti"] = math.nan; result["Rank_Surplus_Ruolo"] = math.nan
    for role in ROLES:
        eligible = result[(result.R.eq(role)) & result.Punti_predetti.notna()].sort_values(["Punti_predetti", "Id"], ascending=[False, True], kind="stable")
        replacement_rank = config["projection"]["replacement_ranks"][role]
        if len(eligible) < replacement_rank:
            continue
        replacement = float(eligible.iloc[replacement_rank - 1].Punti_predetti)
        result.loc[eligible.index, "Punti_sostituzione"] = replacement
        result.loc[eligible.index, "Surplus_punti"] = result.loc[eligible.index, "Punti_predetti"] - replacement
        result.loc[eligible.index, "Rank_Surplus_Ruolo"] = np.arange(1, len(eligible) + 1)
    return result


def _render_report(output: Path, config: dict[str, Any], candidate_summary: pd.DataFrame, selected: str,
                   metrics: pd.DataFrame, calibration: pd.DataFrame, gate: dict[str, Any]) -> Path:
    report = output / "projected_validation_report.md"
    selected_metrics = metrics[metrics.candidate.eq(selected)]
    pivot = selected_metrics.pivot_table(index=["fold", "role", "measure"], columns="model", values=["sample_size", "coverage", "mae", "median_ae", "pearson", "spearman", "precision_at_n"], aggfunc="first")
    lines = ["# Projected auction model validation", "", "## Frozen selection", "",
             f"- Selected candidate: `{selected}` (role/fold MAE wins, then median points MAE as deterministic tie-break).",
             f"- Feature window: {config['projection']['feature_window']} seasons; final fit uses 2016/17--2025/26.",
             f"- Selection targets: {', '.join(config['projection']['selection_targets'])}. 2025/26 was not used for candidate selection.",
             f"- Promotion gate: **{'PASS' if gate['primary_pass'] and gate['guardrail_pass'] else 'FAIL'}**. Points MAE beat last-season baseline in >=3 roles in {gate['primary_passes']}/6 folds; Spearman/precision guardrail failures: {gate['guardrail_failures']}.",
             "", "## Candidate comparison", "", "```", candidate_summary.round(3).to_string(index=False), "```",
             "", "## Per-fold, per-role metrics", "", "The following table keeps Pv, conditional Fm, and total-points metrics separate. Coverage is the share of the target-list role with a usable prediction.", "", "```", pivot.round(3).to_string(), "```",
             "", "## Calibration", "", "Calibration buckets (prediction quantiles), including sample size, are in `projected_validation_calibration.csv`. Detailed metrics are in `projected_validation_metrics.csv`.",
             "", "## Final fit", "", "The archived `projected_auction_dataset.csv` was generated after selection using labels through 2025/26 only. It is the immutable pre-auction artifact for the future 2026/27 final test."]
    report.write_text("\n".join(lines), encoding="utf-8")
    metrics.to_csv(output / "projected_validation_metrics.csv", index=False)
    calibration.to_csv(output / "projected_validation_calibration.csv", index=False)
    return report


def run_projection(config_path: Path) -> tuple[pd.DataFrame, Path]:
    """Run rolling selection and create the immutable 2026/27 auction dataset."""
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    required = {"selection_targets", "feature_window", "ridge_alpha_grid", "feature_sets", "replacement_ranks"}
    if missing := required - set(config.get("projection", {})):
        raise PipelineError(f"Projection configuration missing {sorted(missing)}")
    forbidden = {column for columns in config["projection"]["feature_sets"].values() for column in columns if "Qt" in column}
    if forbidden:
        raise PipelineError(f"Qt.I is auction context, not a projection feature: {sorted(forbidden)}")
    output = Path(config["paths"].get("output", "output")); output.mkdir(parents=True, exist_ok=True)
    archive = output / "projected_auction_dataset.csv"
    if archive.exists():
        raise PipelineError(f"Refusing to overwrite archived pre-auction dataset: {archive}")

    qc = QcLog()
    historical, quotes, current = load_sources(config, qc)
    features = calculate_season_features(historical, config, qc)
    history_by_id = {int(player_id): group for player_id, group in features.groupby("Id", sort=False)}
    validation_metrics: list[pd.DataFrame] = []; validation_calibration: list[pd.DataFrame] = []
    candidates: dict[str, tuple[list[str], float]] = {}
    for feature_name, columns in config["projection"]["feature_sets"].items():
        for alpha in config["projection"]["ridge_alpha_grid"]:
            candidates[f"{feature_name}/alpha={alpha:g}"] = (columns, float(alpha))
    # Snapshot construction is the expensive, data-pipeline-facing operation.
    # A season's snapshot has the same cutoff no matter which later fold uses
    # it as training, so cache it once rather than once per overlapping fold.
    examples = {
        season: _season_examples(features, quotes, season, config, history_by_id)
        for season in config["seasons"]
        if season in quotes and _past_seasons(config["seasons"], season, config["projection"]["feature_window"])
    }
    actual_columns = ["Pv_actual", "Fm_actual", "Punti_actual"]
    fold_inputs = {
        target: (
            pd.concat([examples[season] for season in config["seasons"] if season in examples and _season_key(season) < _season_key(target)], ignore_index=True),
            examples[target].drop(columns=actual_columns),
        )
        for target in config["projection"]["selection_targets"]
    }
    for candidate, (columns, alpha) in candidates.items():
        for target in config["projection"]["selection_targets"]:
            training, snapshot = fold_inputs[target]
            _, metrics, calibration = _fold_results(features, quotes, target, columns, alpha, config, training, snapshot)
            metrics.insert(0, "candidate", candidate); calibration.insert(0, "candidate", candidate)
            validation_metrics.append(metrics); validation_calibration.append(calibration)
    metrics = pd.concat(validation_metrics, ignore_index=True)
    calibration = pd.concat(validation_calibration, ignore_index=True)
    selected, candidate_summary = _choose_candidate(metrics)
    gate = _selection_gate(metrics, selected)
    report = _render_report(output, config, candidate_summary, selected, metrics, calibration, gate)

    selected_columns, selected_alpha = candidates[selected]
    final_training = pd.concat([examples[season] for season in config["seasons"] if season in examples], ignore_index=True)
    final_models = _fit_models(final_training, selected_columns, selected_alpha)
    snapshots = _snapshots(history_by_id, current.rename(columns={"Squadra_2026_27": "Squadra", "Qt.I_2026_27": "Qt.I"}), "2026/27", config)
    projected = _auction_values(_predict(snapshots, final_models, config), config)
    ranking = build_ranking(features, quotes, current, config, qc)
    historical_columns = ["Id", "Nome", "R", "Squadra_2026_27", "Qt.I_2026_27", "Performance", "Reliability", "HistoricalRating", "Trend_Label", "Confidence", "RigoriDipendenza_Flag", "StoricoVolatile", "PochePresenzeRecenti"]
    dataset = ranking[historical_columns].merge(projected.drop(columns=["R"]), on="Id", how="left", validate="one_to_one")
    dataset["Categoria"] = np.where(dataset.PredictionStatus.eq("INSUFFICIENT_HISTORY"), "NEW", np.where(dataset.Pv_Total_Projection >= config["history"]["historical_min_pv_total"], "PV_SUFFICIENTI", "LIMITED_HISTORY"))
    dataset["Confidence"] = np.where(dataset.PredictionStatus.eq("OK"), _confidence(dataset), "Bassa")
    order = ["Id", "Nome", "R", "Squadra_2026_27", "Categoria", "PredictionStatus", "Pv_predetta", "Fm_predetta", "Punti_predetti", "Punti_sostituzione", "Surplus_punti", "Rank_Surplus_Ruolo", "Qt.I_2026_27", "Confidence", "Seasons_Played_Projection", "Seasons_In_Squad_Projection", "Pv_Total_Projection", "R_Storico_Projection", "RigoriDipendenza_Flag", "StoricoVolatile", "PochePresenzeRecenti", "HistoricalRating", "Performance", "Reliability", "Trend_Label"]
    dataset = dataset[order].sort_values(["R", "Surplus_punti", "Id"], ascending=[True, False, True], na_position="last", kind="stable")
    dataset.to_csv(archive, index=False)
    return dataset, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the pre-auction projected surplus dataset.")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    args = parser.parse_args()
    dataset, report = run_projection(args.config)
    print(f"Wrote {len(dataset)} players to output/projected_auction_dataset.csv; validation report: {report}")


if __name__ == "__main__":
    main()
