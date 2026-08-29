"""Phases 1--3 of the historical Fantacalcio ranking specification.

All joins are on Fantacalcio ``Id``.  The module deliberately keeps source
rows with Pv=0: they are evidence for availability, not zero performance.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

STATS_COLUMNS = ["Id", "R", "Rm", "Nome", "Squadra", "Pv", "Mv", "Fm", "Gf", "Gs", "Rp", "Rc", "R+", "R-", "Ass", "Amm", "Esp", "Au"]
NUMERIC_COLUMNS = ["Pv", "Mv", "Fm", "Gf", "Gs", "Rp", "Rc", "R+", "R-", "Ass", "Amm", "Esp", "Au"]
QC_COLUMNS = ["severity", "check", "Id", "season", "value", "expected", "message"]


class PipelineError(RuntimeError):
    pass


class QcLog:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, severity: str, check: str, message: str, player_id: Any = None,
            season: Any = None, value: Any = None, expected: Any = None) -> None:
        self.rows.append({"severity": severity, "check": check, "Id": player_id,
                          "season": season, "value": value, "expected": expected,
                          "message": message})

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=QC_COLUMNS)


def _season_file(prefix: str, season: str) -> str:
    return f"{prefix}_Stagione_{season.replace('/', '_')}.xlsx"


def _read_sheet(path: Path, sheet: str) -> pd.DataFrame:
    try:
        # All supplied Fantacalcio workbooks have a title row and put the
        # machine-readable headers on Excel row 2.
        return pd.read_excel(path, sheet_name=sheet, header=1)
    except ValueError as exc:
        raise PipelineError(f"Missing sheet {sheet!r} in {path}") from exc


def _normalise(df: pd.DataFrame, required: list[str], source: Path) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    missing = set(required) - set(df.columns)
    if missing:
        raise PipelineError(f"{source}: missing required columns {sorted(missing)}")
    df = df[required].copy()
    df["Id"] = pd.to_numeric(df["Id"], errors="raise").astype("Int64")
    for col in set(required) & set(NUMERIC_COLUMNS + ["Qt.I", "FVM"]):
        df[col] = pd.to_numeric(df[col], errors="raise")
    return df


def _id_set(df: pd.DataFrame) -> set[int]:
    return {int(x) for x in df["Id"].dropna()}


def load_sources(config: dict[str, Any], qc: QcLog) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame]:
    """Load and validate the 10 stats files and 11 quotation files."""
    stats_dir = Path(config["paths"]["stats"])
    lists_dir = Path(config["paths"]["player_lists"])
    stats_frames: list[pd.DataFrame] = []
    quoted_tutti: dict[str, pd.DataFrame] = {}

    for season in config["seasons"]:
        stats_path = stats_dir / _season_file("Statistiche_Fantacalcio", season)
        quote_path = lists_dir / _season_file("Quotazioni_Fantacalcio", season)
        stats = _normalise(_read_sheet(stats_path, "Tutti"), STATS_COLUMNS, stats_path)
        quotes = _normalise(_read_sheet(quote_path, "Tutti"), ["Id", "R", "Nome", "Squadra", "Qt.I", "FVM"], quote_path)
        sold = _normalise(_read_sheet(quote_path, "Ceduti"), ["Id", "R", "Nome", "Squadra", "Qt.I", "FVM"], quote_path)
        _check_source_identity(stats, quotes, sold, season, qc)
        _check_stats_rows(stats, season, qc)

        stats["Stagione"] = season
        stats["RowType"] = np.where(stats["Pv"] >= 1, "PLAYED", "IN_SQUAD_NO_PLAY")
        stats["left_mid_season"] = stats["Id"].isin(_id_set(sold))
        # Pv=0 is not a zero-valued performance observation.
        no_play = stats["RowType"].eq("IN_SQUAD_NO_PLAY")
        stats.loc[no_play, [c for c in NUMERIC_COLUMNS if c != "Pv"]] = np.nan
        stats_frames.append(stats)
        quoted_tutti[season] = quotes
        zero_count = int(no_play.sum())
        qc.add("INFO", "in_squad_no_play_count", "Rows in stats with Pv = 0", season=season, value=zero_count)
        if zero_count:
            share = float(stats.loc[no_play, "left_mid_season"].mean())
            qc.add("INFO", "left_mid_season_share", "Share of Pv=0 rows found in Ceduti", season=season, value=share, expected="0.55-0.75")

    current_season = "2026/27"
    current_path = lists_dir / _season_file("Quotazioni_Fantacalcio", current_season)
    current = _normalise(_read_sheet(current_path, "Tutti"), ["Id", "R", "Nome", "Squadra", "Qt.I", "FVM"], current_path)
    current = current.rename(columns={"Squadra": "Squadra_2026_27", "Qt.I": "Qt.I_2026_27"})
    if current["Id"].duplicated().any():
        raise PipelineError("Duplicate Id in current 2026/27 player list")
    return pd.concat(stats_frames, ignore_index=True), quoted_tutti, current


def _check_source_identity(stats: pd.DataFrame, quotes: pd.DataFrame, sold: pd.DataFrame,
                           season: str, qc: QcLog) -> None:
    for label, df in [("stats", stats), ("quotazioni_Tutti", quotes), ("Ceduti", sold)]:
        dupes = df.loc[df["Id"].duplicated(keep=False), "Id"]
        if not dupes.empty:
            for player_id in dupes.unique():
                qc.add("ERROR", "duplicate_id", f"Duplicate Id in {label}", player_id, season, int((df["Id"] == player_id).sum()), 1)
            raise PipelineError(f"Duplicate Id in {label}, {season}")
    stats_ids, quote_ids, sold_ids = _id_set(stats), _id_set(quotes), _id_set(sold)
    if quote_ids & sold_ids or quote_ids | sold_ids != stats_ids:
        qc.add("ERROR", "quotation_stats_identity", "Tutti/Ceduti must be disjoint and their union must equal stats", season=season,
               value=f"stats={len(stats_ids)}, union={len(quote_ids | sold_ids)}, intersection={len(quote_ids & sold_ids)}")
        raise PipelineError(f"Blocking stats/quotations identity check failed for {season}")


def _check_stats_rows(stats: pd.DataFrame, season: str, qc: QcLog) -> None:
    for _, row in stats.iterrows():
        pid = row["Id"]
        if row.Pv < 0:
            qc.add("ERROR", "negative_pv", "Pv cannot be negative", pid, season, row.Pv, 0)
        if pd.notna(row.Mv) and not 0 <= row.Mv <= 10:
            qc.add("ERROR", "mv_range", "Mv outside 0-10", pid, season, row.Mv, "0-10")
        if pd.notna(row.Fm) and not -30 <= row.Fm <= 30:
            qc.add("ERROR", "fm_range", "Fm outside -30/+30", pid, season, row.Fm, "-30..30")
        elif pd.notna(row.Fm) and not -10 <= row.Fm <= 20:
            qc.add("WARNING", "fm_range", "Unusual but permitted Fm", pid, season, row.Fm, "-10..20")
        if pd.notna(row.Rc) and row.Rc != row["R+"] + row["R-"]:
            qc.add("WARNING", "penalty_consistency", "Rc differs from R+ + R-", pid, season, row.Rc, row["R+"] + row["R-"])
        if pd.notna(row.Gf) and row.Gf < row["R+"]:
            qc.add("ERROR", "goals_penalties", "Gf cannot be below penalties scored", pid, season, row.Gf, f">={row['R+']}")
        if row.R != "P" and pd.notna(row.Gs) and row.Gs > 0:
            qc.add("WARNING", "non_gk_goals_conceded", "Gs populated for non-goalkeeper", pid, season, row.Gs)


def midrank_percentile(values: pd.Series, reference: pd.Series) -> pd.Series:
    """Spec §10.1 percentile, including values outside the reference sample."""
    ref = np.sort(reference.dropna().to_numpy(dtype=float))
    if len(ref) == 0:
        return pd.Series(np.nan, index=values.index, dtype=float)
    out = []
    for x in values:
        if pd.isna(x):
            out.append(np.nan)
            continue
        left = int(np.searchsorted(ref, x, side="left"))
        equal = int(np.searchsorted(ref, x, side="right")) - left
        out.append(100 * (left + .5 * equal) / len(ref))
    return pd.Series(out, index=values.index, dtype=float)


def _split_percentile(rate: pd.Series, reference: pd.Series) -> pd.Series:
    positive_reference = reference[reference > 0]
    result = pd.Series(np.nan, index=rate.index, dtype=float)
    valid = rate.notna()
    result.loc[valid & rate.eq(0)] = 25.0
    positive = valid & rate.gt(0)
    result.loc[positive] = 50 + midrank_percentile(rate.loc[positive], positive_reference) / 2
    return result


def calculate_season_features(historical: pd.DataFrame, config: dict[str, Any], qc: QcLog) -> pd.DataFrame:
    result = historical.copy()
    result[["GoalRate", "NonPenaltyGoalRate", "AssistRate", "GoalsConcededRate", "RpRate", "Performance_stagione", "BonusProfile_stagione"]] = np.nan
    played = result["RowType"].eq("PLAYED")
    result.loc[played, "GoalRate"] = result.loc[played, "Gf"] / result.loc[played, "Pv"]
    result.loc[played, "NonPenaltyGoalRate"] = (result.loc[played, "Gf"] - result.loc[played, "R+"]) / result.loc[played, "Pv"]
    result.loc[played, "AssistRate"] = result.loc[played, "Ass"] / result.loc[played, "Pv"]
    result.loc[played, "GoalsConcededRate"] = result.loc[played, "Gs"] / result.loc[played, "Pv"]
    result.loc[played, "RpRate"] = result.loc[played, "Rp"] / result.loc[played, "Pv"]

    for (season, role), idx in result.groupby(["Stagione", "R"], sort=False).groups.items():
        block = result.loc[idx]
        playable = block[block.RowType.eq("PLAYED")]
        if role == "P":
            refs = {"Fm": playable.loc[playable.Pv >= config["performance"]["min_pv_for_percentile"], "Fm"],
                    "GoalsConcededRate": playable.loc[playable.Pv >= config["performance"]["min_pv_for_percentile"], "GoalsConcededRate"],
                    "RpRate": playable.loc[playable.Pv >= config["performance"]["min_pv_for_percentile"], "RpRate"]}
            for metric, reference in refs.items():
                if len(reference) < 5:
                    qc.add("ERROR", "percentile_reference_size", f"{metric} reference contains fewer than five players", season=season, value=len(reference), expected=">=5")
            fm = midrank_percentile(block.Fm, refs["Fm"]) / 100
            gs = midrank_percentile(block.GoalsConcededRate, refs["GoalsConcededRate"]) / 100
            rp = midrank_percentile(block.RpRate, refs["RpRate"]) / 100
            gk = config["goalkeeping"]
            result.loc[idx, "Performance_stagione"] = gk["fm_weight"] * fm + gk["goals_conceded_weight"] * (1 - gs) + gk["penalty_save_weight"] * rp
            continue

        perf_ref = playable.loc[playable.Pv >= config["performance"]["min_pv_for_percentile"], "Fm"]
        if len(perf_ref) < 5:
            qc.add("ERROR", "percentile_reference_size", "Fm reference contains fewer than five players", season=season, value=len(perf_ref), expected=">=5")
        result.loc[idx, "Performance_stagione"] = midrank_percentile(block.Fm, perf_ref) / 100

        bonus_cfg = config["bonus_profile"]
        bonus_ref = playable[playable.Pv >= bonus_cfg["min_pv_for_percentile"]]
        metric = bonus_cfg["goal_rate_metric"]
        if len(bonus_ref) < 5:
            qc.add("ERROR", "percentile_reference_size", "Bonus reference contains fewer than five players", season=season, value=len(bonus_ref), expected=">=5")
        handling = bonus_cfg["zero_handling"].get(role, "midrank")
        if handling == "split":
            goal_pct = _split_percentile(block[metric], bonus_ref[metric])
            assist_pct = _split_percentile(block.AssistRate, bonus_ref.AssistRate)
        else:
            goal_pct = midrank_percentile(block[metric], bonus_ref[metric])
            assist_pct = midrank_percentile(block.AssistRate, bonus_ref.AssistRate)
        weights = bonus_cfg["roles"][role]
        raw = weights["goal_weight"] * (goal_pct - 50) + weights["assist_weight"] * (assist_pct - 50)
        centred = raw - raw[playable.index].median() if handling == "recenter" else raw
        normalized = (centred / 50).clip(-1, 1)
        result.loc[idx, "BonusProfile_stagione"] = normalized
        _bonus_qc(block, metric, raw, centred, normalized, handling, season, role, bonus_cfg, qc)
    return result


def _bonus_qc(block: pd.DataFrame, metric: str, raw: pd.Series, centred: pd.Series, normalized: pd.Series,
              handling: str, season: str, role: str, cfg: dict[str, Any], qc: QcLog) -> None:
    playable = block.RowType.eq("PLAYED")
    if not playable.any():
        return
    median = float(normalized[playable].median())
    if abs(median) > .10:
        qc.add("ERROR", "bonus_median", "BonusProfile median is not centred", season=season, value=median, expected="abs <= 0.10", player_id=role)
    # Both ingredients of BonusProfile have a zero block.  The configured
    # goal metric may change in validation, but AssistRate always remains.
    for zero_metric in {metric, "AssistRate"}:
        zero_share = float((block.loc[playable, zero_metric] == 0).mean())
        if zero_share > cfg["max_zero_share"]:
            qc.add("WARNING", "bonus_zero_share", f"{zero_metric} zero-rate mass; evaluate split in validation", season=season, player_id=role, value=zero_share, expected=f"<={cfg['max_zero_share']}")
    if handling == "recenter":
        clipped = float((centred[playable].abs() / 50 > 1).mean())
        if clipped > cfg["max_clipped_share"]:
            qc.add("WARNING", "bonus_clipped_share", "BonusProfile clipping is material", season=season, player_id=role, value=clipped, expected=f"<={cfg['max_clipped_share']}")


def _weighted(rows: pd.DataFrame, column: str, weights: dict[str, float]) -> float:
    usable = rows.dropna(subset=[column]).copy()
    if usable.empty:
        return np.nan
    w = usable.Stagione.map(weights).astype(float)
    return float(np.average(usable[column], weights=w / w.sum()))


def _reliability(past: pd.DataFrame, weights: dict[str, float], cfg: dict[str, Any]) -> float:
    items = past.copy()
    if cfg["exclude_left_mid_season"]:
        items = items[~(items.RowType.eq("IN_SQUAD_NO_PLAY") & items.left_mid_season)]
    if items.empty:
        return np.nan
    pv = items.Pv.fillna(0).to_numpy(float)
    ref = float(cfg["reference_pv"])
    scores = np.minimum(1, np.sqrt(pv / ref) if cfg["function"] == "sqrt" else pv / ref)
    w = items.Stagione.map(weights).to_numpy(float)
    return float(np.average(scores, weights=w / w.sum()))


def _trend(rows: pd.DataFrame, season_positions: dict[str, int], cfg: dict[str, Any]) -> tuple[float, str | None, int]:
    rows = rows.dropna(subset=["Performance_stagione"])
    n = len(rows)
    if n < cfg["min_seasons"]:
        return np.nan, "N/D" if n == 1 else None, n
    x = rows.Stagione.map(season_positions).to_numpy(float)
    slope = float(np.polyfit(x, rows.Performance_stagione.to_numpy(float), 1)[0])
    t = cfg
    label = "↑ Forte crescita" if slope >= t["strong_up"] else "↗ Crescita" if slope >= t["up"] else "↓ Forte calo" if slope <= t["strong_down"] else "↘ Calo" if slope <= t["down"] else "→ Stabile"
    return slope, label, n


def build_ranking(features: pd.DataFrame, quoted_tutti: dict[str, pd.DataFrame], current: pd.DataFrame,
                  config: dict[str, Any], qc: QcLog) -> pd.DataFrame:
    seasons = config["seasons"][-config["train_window"]:]
    weights = {season: config["time_decay"]["base"] ** i for i, season in enumerate(seasons)}
    positions = {season: i for i, season in enumerate(seasons)}
    train = features[features.Stagione.isin(seasons)].copy()
    rows: list[dict[str, Any]] = []
    quoted_ids = {s: _id_set(quoted_tutti[s]) for s in seasons}
    for _, player in current.iterrows():
        pid, role = player.Id, player.R
        history = train[train.Id.eq(pid)].copy()
        roles = history.R.dropna().tolist()
        crosses_gk = any(r == "P" for r in roles) and any(r != "P" for r in roles)
        calculation = history[history.R.eq(role)].copy() if crosses_gk else history
        if crosses_gk:
            qc.add("WARNING", "role_change_gk", "Goalkeeper boundary crossed; only current-role seasons used", pid, value="/".join(roles), expected=role)
        if len(set(roles)) > 1:
            qc.add("WARNING", "role_change", "Historical role differs across seasons", pid, value="/".join(roles), expected=role)
        available = calculation[calculation.RowType.eq("PLAYED")]
        pv_total = float(available.Pv.sum())
        category = "PV_SUFFICIENTI" if pv_total >= config["history"]["historical_min_pv_total"] else "LIMITED_HISTORY" if pv_total >= 1 else "NEW"
        performance = _weighted(available, "Performance_stagione", weights)
        reliability = _reliability(calculation, weights, config["reliability"])
        feature_values = {name: _weighted(available, name, weights) for name in ["Fm", "Mv", "Pv", "BonusProfile_stagione", "GoalRate", "NonPenaltyGoalRate", "AssistRate", "Gf", "R+"]}
        trend_value, trend_label, trend_points = _trend(available, positions, config["trend"])
        seasons_available, in_squad = len(available), len(calculation)
        stability = np.nan if seasons_available < 2 else 1 - min(1, float(available.Performance_stagione.std(ddof=1)) / config["confidence"]["sd_reference"])
        coverage = seasons_available / config["train_window"]
        availability_score = min(1, pv_total / (config["train_window"] * config["reliability"]["reference_pv"]))
        c = config["confidence"]
        confidence_score = (c["season_coverage_weight"] * coverage + c["availability_weight"] * availability_score + c["stability_weight"] * stability) if pd.notna(stability) else (c["season_coverage_weight"] * coverage + c["availability_weight"] * availability_score) / (c["season_coverage_weight"] + c["availability_weight"])
        confidence = "Alta" if confidence_score >= c["threshold_alta"] else "Media" if confidence_score >= c["threshold_media"] else "Bassa"
        bonus = feature_values["BonusProfile_stagione"]
        raw = np.nan if category == "NEW" or pd.isna(performance) or pd.isna(reliability) else config["rating"][role]["performance"] * performance + config["rating"][role]["reliability"] * reliability + config["rating"][role]["bonus"] * (0 if pd.isna(bonus) else bonus)
        last = available.sort_values("Stagione").tail(1)
        last_values = last.iloc[0] if not last.empty else None
        gf_weighted, penalties_weighted = feature_values["Gf"], feature_values["R+"]
        penalty_dependency = penalties_weighted / gf_weighted if role in {"C", "A"} and pd.notna(gf_weighted) and gf_weighted != 0 else np.nan
        risk = config["risk_flags"]
        note = "nessuno storico Serie A nella finestra di train" if history.empty else "nessuna stagione PLAYED nella finestra di train" if available.empty else ""
        if category != "NEW" and (pd.isna(performance) or pd.isna(reliability)):
            note = "Performance o Reliability non definita: insieme di ripesatura vuoto"
            qc.add("INFO", "empty_reweighting_set", note, pid)
        record = {"Id": pid, "Nome": player.Nome, "R": role, "R_Storico": "/".join(roles) if roles and any(r != role for r in roles) else np.nan,
                  "Squadra_2026_27": player.Squadra_2026_27, "Qt.I_2026_27": player["Qt.I_2026_27"], "Categoria": category,
                  "Seasons_Available": seasons_available, "Seasons_In_Squad": in_squad, "Seasons_Quoted": sum(pid in quoted_ids[s] for s in seasons),
                  "Performance": performance, "Reliability": reliability, "BonusProfile": bonus, "HistoricalRatingRaw": raw,
                  "HistoricalRating": raw * 100 if pd.notna(raw) else np.nan, "Mv_Weighted": feature_values["Mv"], "Fm_Weighted": feature_values["Fm"], "Pv_Weighted": feature_values["Pv"], "Pv_Totale": pv_total,
                  "Pv_Last_Season": last_values.Pv if last_values is not None else np.nan, "Fm_Last_Season": last_values.Fm if last_values is not None else np.nan,
                  "Mv_Last_Season": last_values.Mv if last_values is not None else np.nan, "Gf_Rate": feature_values["GoalRate"], "NonPenaltyGf_Rate": feature_values["NonPenaltyGoalRate"], "Ass_Rate": feature_values["AssistRate"],
                  "RigoriDipendenza": penalty_dependency, "RigoriDipendenza_Flag": penalty_dependency > risk["penalty_dependency_threshold"] if pd.notna(penalty_dependency) else np.nan,
                  "StabilityScore": stability, "StoricoVolatile": stability < risk["volatility_threshold"] if pd.notna(stability) else np.nan,
                  "PochePresenzeRecenti": bool(category == "PV_SUFFICIENTI" and last_values is not None and last_values.Pv < risk["low_recent_pv_threshold"]) if category == "PV_SUFFICIENTI" else np.nan,
                  "ConfidenceScore": confidence_score, "Confidence": confidence, "DefenseScore": feature_values["Mv"], "Trend_Value": trend_value, "Trend_Label": trend_label, "Trend_Points": trend_points, "Note": note}
        for season in seasons:
            squad = history.loc[history.Stagione.eq(season), "Squadra"]
            record[f"Squadra_{season.replace('/', '_')}"] = squad.iloc[0] if not squad.empty else np.nan
        rows.append(record)
    result = pd.DataFrame(rows)
    _rank(result)
    result["RoleMedianRating"] = result.groupby("R")["HistoricalRating"].transform("median")
    _final_qc(result, qc)
    order = ["R", "Rank_Role", "Id"]
    return result.sort_values(order, na_position="last", kind="stable")


def _rank(df: pd.DataFrame) -> None:
    df["Rank"] = np.nan
    df["Rank_Role"] = np.nan
    rated = df[df.HistoricalRatingRaw.notna()]
    global_order = rated.sort_values(["HistoricalRatingRaw", "Performance", "Reliability", "Id"], ascending=[False, False, False, True], kind="stable")
    df.loc[global_order.index, "Rank"] = np.arange(1, len(global_order) + 1)
    for _, group in rated.groupby("R"):
        ordered = group.sort_values(["HistoricalRatingRaw", "Performance", "Reliability", "Id"], ascending=[False, False, False, True], kind="stable")
        df.loc[ordered.index, "Rank_Role"] = np.arange(1, len(ordered) + 1)


def _final_qc(df: pd.DataFrame, qc: QcLog) -> None:
    for col, low, high in [("Performance", 0, 1), ("Reliability", 0, 1), ("ConfidenceScore", 0, 1), ("BonusProfile", -1, 1)]:
        invalid = df[df[col].notna() & ~df[col].between(low, high)]
        for _, row in invalid.iterrows():
            qc.add("ERROR", "feature_range", f"{col} outside permitted range", row.Id, value=row[col], expected=f"{low}..{high}")
    for role, group in df.groupby("R"):
        qc.add("INFO", "new_player_share", "Share of current role classified NEW", season="2026/27", player_id=role, value=float(group.Categoria.eq("NEW").mean()))
    for _, row in df[(df.Seasons_Available == 1) & df.Confidence.eq("Alta")].iterrows():
        qc.add("ERROR", "confidence_one_season", "One-season player cannot have high confidence", row.Id)


def run(config_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    with config_path.open(encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    qc = QcLog()
    historical, quotes, current = load_sources(config, qc)
    features = calculate_season_features(historical, config, qc)
    ranking = build_ranking(features, quotes, current, config, qc)
    output = Path(config["paths"].get("output", "output"))
    output.mkdir(parents=True, exist_ok=True)
    historical.to_csv("data/historical.csv", index=False)
    features.to_csv("data/merged.csv", index=False)
    ranking.drop(columns=["HistoricalRatingRaw"]).to_csv(output / "ranking_dataset.csv", index=False)
    qc_frame = qc.frame()
    qc_frame.to_csv("data/qc_log.csv", index=False)
    return ranking, qc_frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Fantacalcio historical ranking (phases 1-3).")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    args = parser.parse_args()
    ranking, qc = run(args.config)
    errors = int(qc.severity.eq("ERROR").sum())
    print(f"Wrote {len(ranking)} players; QC: {errors} errors, {int(qc.severity.eq('WARNING').sum())} warnings.")
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
