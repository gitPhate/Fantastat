"""Rolling Phase 4 backtest for the Fantacalcio historical ranking."""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from ranking_pipeline import (
    QcLog, _normalise, _read_sheet, _season_file, build_ranking,
    calculate_season_features, load_sources, midrank_percentile,
)

ROLES = ["P", "D", "C", "A"]


def _target_quotes(config: dict[str, Any], season: str) -> pd.DataFrame:
    path = Path(config["paths"]["player_lists"]) / _season_file("Quotazioni_Fantacalcio", season)
    columns = ["Id", "R", "Nome", "Squadra", "Qt.I", "FVM"]
    return pd.concat([
        _normalise(_read_sheet(path, "Tutti"), columns, path),
        _normalise(_read_sheet(path, "Ceduti"), columns, path),
    ], ignore_index=True).drop_duplicates("Id")


def _target_universe(historical: pd.DataFrame, quotes: pd.DataFrame, season: str) -> pd.DataFrame:
    target = historical[historical.Stagione.eq(season)].copy()
    target = target.merge(quotes[["Id", "Qt.I", "FVM"]], on="Id", how="left", validate="one_to_one")
    target = target.rename(columns={"Squadra": "Squadra_2026_27", "Qt.I": "Qt.I_2026_27"})
    return target.rename(columns={"Pv": "Pv_target", "Fm": "Fm_target"})[["Id", "R", "Nome", "Squadra_2026_27", "Qt.I_2026_27", "FVM", "Pv_target", "Fm_target", "RowType"]]


def _percentile(values: pd.Series, reference: pd.Series) -> pd.Series:
    return midrank_percentile(values, reference) / 100


def _score_models(ranking: pd.DataFrame, variant: str) -> pd.Series:
    weights = {role: (0.0 if role == "P" else .15) for role in ROLES}
    if variant == "model_1":
        return ranking.Performance
    if variant == "model_2":
        result = pd.Series(np.nan, index=ranking.index)
        for role, group in ranking.groupby("R"):
            p, r = (.75, .25) if role == "P" else (.60, .25)
            # Pairs are normalized to a 0-1 scale for MAE comparison.
            result.loc[group.index] = (p * group.Performance + r * group.Reliability) / (p + r)
        return result
    return ranking.HistoricalRatingRaw


def _metrics(prediction: pd.Series, target: pd.Series, role: str, ns: list[int], availability: pd.Series | None = None) -> dict[str, Any]:
    pair = pd.DataFrame({"prediction": prediction, "target": target}).dropna()
    result: dict[str, Any] = {"n": len(pair)}
    result["pearson"] = pair.prediction.corr(pair.target, method="pearson") if len(pair) > 1 else np.nan
    result["spearman"] = pair.prediction.corr(pair.target, method="spearman") if len(pair) > 1 else np.nan
    errors = (pair.prediction - pair.target).abs()
    result["mae"] = errors.mean()
    result["median_ae"] = errors.median()
    for n in ns:
        k = min(n, len(pair))
        if not k:
            result[f"prec_at_{n}"] = np.nan
            result[f"avail_at_{n}"] = np.nan
            continue
        top_pred = pair.nlargest(k, "prediction").index
        top_actual = set(pair.nlargest(k, "target").index)
        result[f"prec_at_{n}"] = len(set(top_pred) & top_actual) / k
        result[f"avail_at_{n}"] = availability.reindex(top_pred).eq(True).mean() if availability is not None else np.nan
    return result


def _model_config(config: dict[str, Any], variant: str) -> dict[str, Any]:
    cfg = copy.deepcopy(config)
    if variant == "model_3a":
        cfg["reliability"]["exclude_left_mid_season"] = False
    elif variant == "model_3b":
        cfg["bonus_profile"]["goal_rate_metric"] = "NonPenaltyGoalRate"
    elif variant in {"model_3c", "model_3d"}:
        value = "split" if variant == "model_3c" else "midrank"
        cfg["bonus_profile"]["zero_handling"] = {role: value for role in "DCA"}
    return cfg


def _make_fold(historical: pd.DataFrame, quotation_tutti: dict[str, pd.DataFrame], config: dict[str, Any], train_seasons: list[str], target_season: str, variant: str, target: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = _model_config(config, variant)
    cfg["seasons"] = train_seasons
    cfg["train_window"] = len(train_seasons)
    features = calculate_season_features(historical[historical.Stagione.isin(train_seasons)], cfg, QcLog())
    if target is None:
        target = _target_universe(historical, _target_quotes(config, target_season), target_season)
    current = target[["Id", "R", "Nome", "Squadra_2026_27", "Qt.I_2026_27"]]
    ranking = build_ranking(features, {s: quotation_tutti[s] for s in train_seasons}, current, cfg, QcLog())
    return ranking, target


def _targets(ranking: pd.DataFrame, target: pd.DataFrame, config: dict[str, Any], train_features: pd.DataFrame) -> pd.DataFrame:
    df = target.merge(ranking, on=["Id", "R", "Nome"], how="left", validate="one_to_one", suffixes=("_target", ""))
    df["Target_A"] = np.nan
    df["Target_B"] = np.nan
    for role, indices in df.groupby("R").groups.items():
        block = df.loc[indices]
        played = block.Pv_target >= 1
        ref_a = block.loc[played & (block.Pv_target >= config["performance"]["min_pv_for_percentile"]), "Fm_target"]
        df.loc[indices, "Target_A"] = _percentile(block.Fm_target, ref_a)
        product = (block.Fm_target.fillna(0) * block.Pv_target).astype(float)
        df.loc[indices, "Target_B"] = _percentile(product, product)
        # Baselines are percentile transformed on the matching role's training observations.
        train_role = train_features[(train_features.R == role) & train_features.RowType.eq("PLAYED")]
        for name, col in [("baseline_0", "Fm_Last_Season"), ("baseline_1", "Fm_Weighted"), ("baseline_2", "Pv_Last_Season")]:
            values = block[col]
            reference = train_role.Fm if name in {"baseline_0", "baseline_1"} else train_role.Pv
            # Fm_Weighted lacks a raw seasonal analogue. All observed Fm train rows are its defined reference population.
            df.loc[indices, name] = _percentile(values, reference)
        df.loc[indices, "baseline_3"] = _percentile(block["Qt.I_2026_27"], block["Qt.I_2026_27"])
        df.loc[indices, "baseline_4"] = _percentile(block.FVM, block.FVM[block.FVM > 0]) if (block.FVM > 0).any() else np.nan
    return df


def _fold_metrics(scored: pd.DataFrame, target_name: str, model_scores: dict[str, pd.Series], config: dict[str, Any], target_season: str, kind: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for role in ROLES:
        block = scored[scored.R.eq(role)].copy()
        outcome = block.Pv_target.ge(1) if target_name == "Target_A" else pd.Series(True, index=block.index)
        availability = block.Pv_target.ge(1)
        coverage = block.HistoricalRatingRaw.notna().mean()
        for model, scores in model_scores.items():
            values = pd.Series(scores.values, index=scores.index).reindex(block.index)
            for metric_kind, mask in [("performance", outcome)]:
                result = _metrics(values[mask], block.loc[mask, target_name], role, config["validation"]["precision_n"][role], availability)
                result.update({"fold": target_season, "fold_kind": kind, "role": role, "target": target_name, "model": model, "coverage": coverage, "baseline_coverage": float(block["Qt.I_2026_27"].notna().mean()), "metric_population": metric_kind})
                records.append(result)
    return records


def _reliability_metrics(scored: pd.DataFrame, target_season: str, kind: str) -> list[dict[str, Any]]:
    records = []
    for role in ROLES:
        b = scored[scored.R.eq(role)]
        performance = b[b.Pv_target.ge(1)]
        all_valid = b.dropna(subset=["Reliability"])
        records.append({"fold": target_season, "fold_kind": kind, "role": role, "outcome": "Pv_target", "reliability_spearman": performance.Reliability.corr(performance.Pv_target, method="spearman"), "last_pv_spearman": performance.Pv_Last_Season.corr(performance.Pv_target, method="spearman"), "n": len(performance)})
        records.append({"fold": target_season, "fold_kind": kind, "role": role, "outcome": "played_binary", "reliability_spearman": all_valid.Reliability.corr(all_valid.Pv_target.ge(1).astype(int), method="spearman"), "last_pv_spearman": all_valid.Pv_Last_Season.corr(all_valid.Pv_target.ge(1).astype(int), method="spearman"), "n": len(all_valid)})
    return records


def _test_f(scored: pd.DataFrame, target_season: str, kind: str, config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records, disagreements = [], []
    for role in ROLES:
        b = scored[(scored.R == role) & scored.HistoricalRatingRaw.notna() & scored["Qt.I_2026_27"].notna()].copy()
        qtip = _percentile(b["Qt.I_2026_27"], b["Qt.I_2026_27"])
        for target in ["Target_A", "Target_B"]:
            usable = b[target].notna()
            records.append({"fold": target_season, "fold_kind": kind, "role": role, "target": target, "test": "price_redundancy", "n": int(usable.sum()), "model_spearman": b.loc[usable, "HistoricalRatingRaw"].corr(qtip[usable], method="spearman")})
        if len(b) >= config["validation"]["qti_bands"]:
            try:
                b["price_band"] = pd.qcut(b["Qt.I_2026_27"], config["validation"]["qti_bands"], duplicates="drop")
                for band, g in b.groupby("price_band", observed=True):
                    for target in ["Target_A", "Target_B"]:
                        g = g[g[target].notna()]
                        records.append({"fold": target_season, "fold_kind": kind, "role": role, "target": target, "test": f"price_band:{band}", "n": len(g), "model_spearman": g.HistoricalRatingRaw.corr(g[target], method="spearman"), "price_spearman": _percentile(g["Qt.I_2026_27"], g["Qt.I_2026_27"]).corr(g[target], method="spearman")})
            except ValueError:
                pass
        rank_model = _percentile(b.HistoricalRatingRaw, b.HistoricalRatingRaw)
        b["disagreement"] = rank_model - qtip
        n = max(1, int(np.ceil(len(b) * .1)))
        for direction, group in [("model_above_price", b.nlargest(n, "disagreement")), ("model_below_price", b.nsmallest(n, "disagreement"))]:
            for _, row in group.iterrows():
                disagreements.append({"fold": target_season, "role": role, "direction": direction, "Id": row.Id, "Nome": row.Nome, "disagreement": row.disagreement, "Qt.I": row["Qt.I_2026_27"], "Target_A": row.Target_A, "Target_B": row.Target_B})
    return records, disagreements


def _calibration(scored: pd.DataFrame, fold: str, kind: str) -> list[dict[str, Any]]:
    rows = []
    for role in ROLES:
        b = scored[(scored.R == role) & scored.HistoricalRatingRaw.notna()].copy()
        b["pred_pct"] = _percentile(b.HistoricalRatingRaw, b.HistoricalRatingRaw)
        b["bucket"] = pd.cut(b.pred_pct, bins=np.arange(0, 1.1, .1), include_lowest=True)
        for target in ["Target_A", "Target_B"]:
            for bucket, group in b.groupby("bucket", observed=True):
                values = group[target].dropna()
                if not values.empty:
                    rows.append({"fold": fold, "fold_kind": kind, "role": role, "target": target, "bucket": str(bucket), "n": len(values), "target_mean": values.mean()})
    return rows


def _selection_gate(metrics: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    base = metrics[(metrics.fold_kind == "selection") & (metrics.target == "Target_A")]
    model = base[base.model == "model_3"].set_index(["fold", "role"])
    baseline = base[base.model == "baseline_1"].set_index(["fold", "role"])
    joined = model.join(baseline, lsuffix="_model", rsuffix="_base")
    primary_folds = []
    guardrail_bad: dict[str, int] = {role: 0 for role in ROLES}
    for fold, g in joined.groupby(level=0):
        primary_folds.append((fold, int((g.spearman_model > g.spearman_base).sum()) >= 3))
        for (_, role), row in g.iterrows():
            n = 10 if role == "P" else 20
            if row.get(f"prec_at_{n}_model", np.nan) < row.get(f"prec_at_{n}_base", np.nan) - config["validation"]["precision_degradation_tolerance"]:
                guardrail_bad[role] += 1
    return {"primary_pass_folds": sum(passed for _, passed in primary_folds), "primary_folds": primary_folds, "primary_pass": sum(passed for _, passed in primary_folds) >= 5, "guardrail_bad_folds": guardrail_bad, "guardrail_pass": all(v <= 1 for v in guardrail_bad.values())}


def _render_report(metrics: pd.DataFrame, reliability: pd.DataFrame, test_f: pd.DataFrame, calibration: pd.DataFrame, gate: dict[str, Any], output: Path, lockbox: bool) -> None:
    coverage = metrics[metrics.model.eq("model_3")].pivot_table(index=["fold", "fold_kind"], columns="role", values="coverage", aggfunc="first").round(3)
    lines = ["# Phase 4 validation report", "", "## Selection gate (Target A)", "", f"- Primary: **{'PASS' if gate['primary_pass'] else 'FAIL'}** — {gate['primary_pass_folds']}/6 selection folds have the model ahead of Fm_Weighted in at least three roles.", f"- Guardrail: **{'PASS' if gate['guardrail_pass'] else 'FAIL'}** — degradation counts by role: {gate['guardrail_bad_folds']}.", "- Target B and market comparisons are diagnostic, not gate criteria.", "", "## Coverage", "", "```", coverage.to_string(), "```", "", "## Detailed metrics", "", "Per-fold, per-role, per-target metrics are in `validation_metrics.csv`; calibration, direct Reliability tests, market-information tests, and extreme disagreements have separate CSV exports.", "", "## Direct Reliability test", "", "```", reliability.round(3).to_string(index=False), "```", "", "## Lock-box", "", "Opened and reported below; no parameter may be adjusted from this outcome." if lockbox else "Not opened. Run `python src/validate.py --lockbox` only after selection configuration is frozen.", "", "## Calibration protocol", "", "Defaults are pre-registered. Parameter changes require the specified directional agreement; no automatic changes were made by this first selection report."]
    (output / "validation_report.md").write_text("\n".join(lines), encoding="utf-8")


def run(config_path: Path, include_lockbox: bool = False) -> None:
    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    qc = QcLog()
    historical, quotation_tutti, _ = load_sources(config, qc)
    seasons, tw = config["seasons"], config["train_window"]
    targets = seasons[tw:]
    if not include_lockbox:
        targets = targets[:-1]
    all_metrics: list[dict[str, Any]] = []
    all_reliability: list[dict[str, Any]] = []
    all_test_f: list[dict[str, Any]] = []
    all_disagreements: list[dict[str, Any]] = []
    all_calibration: list[dict[str, Any]] = []
    variants = ["model_1", "model_2", "model_3", "model_3a", "model_3b", "model_3c", "model_3d"]
    for target in targets:
        position = seasons.index(target)
        train_seasons = seasons[position - tw:position]
        kind = "lockbox" if target == seasons[-1] else "selection"
        rankings: dict[str, pd.DataFrame] = {}
        target_data = _target_universe(historical, _target_quotes(config, target), target)
        for variant in variants:
            ranking, _ = _make_fold(historical, quotation_tutti, config, train_seasons, target, variant, target_data)
            rankings[variant] = ranking
        # Compute targets once, then score each model; baselines remain identical.
        train_features = calculate_season_features(historical[historical.Stagione.isin(train_seasons)], config, QcLog())
        scored = _targets(rankings["model_3"], target_data, config, train_features)
        scores = {variant: _score_models(rankings[variant].set_index("Id").reindex(scored.Id).reset_index(), variant) for variant in variants}
        scores.update({name: scored[name] for name in ["baseline_0", "baseline_1", "baseline_2", "baseline_3", "baseline_4"]})
        for target_name in ["Target_A", "Target_B"]:
            all_metrics.extend(_fold_metrics(scored, target_name, scores, config, target, kind))
        all_reliability.extend(_reliability_metrics(scored, target, kind))
        tf, disagreements = _test_f(scored, target, kind, config)
        all_test_f.extend(tf); all_disagreements.extend(disagreements); all_calibration.extend(_calibration(scored, target, kind))
    output = Path(config["paths"].get("output", "output")); output.mkdir(exist_ok=True)
    metrics = pd.DataFrame(all_metrics); rel = pd.DataFrame(all_reliability); tf = pd.DataFrame(all_test_f); cal = pd.DataFrame(all_calibration)
    metrics.to_csv(output / "validation_metrics.csv", index=False)
    rel.to_csv(output / "validation_reliability.csv", index=False)
    tf.to_csv(output / "validation_market_info.csv", index=False)
    pd.DataFrame(all_disagreements).to_csv(output / "validation_price_disagreements.csv", index=False)
    cal.to_csv(output / "validation_calibration.csv", index=False)
    gate = _selection_gate(metrics, config)
    _render_report(metrics, rel, tf, cal, gate, output, include_lockbox)
    print(f"Validated {len(targets)} fold(s). Primary gate: {'PASS' if gate['primary_pass'] else 'FAIL'}; guardrail: {'PASS' if gate['guardrail_pass'] else 'FAIL'}.")


def render_existing(config_path: Path) -> None:
    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    output = Path(config["paths"].get("output", "output"))
    metrics = pd.read_csv(output / "validation_metrics.csv")
    reliability = pd.read_csv(output / "validation_reliability.csv")
    test_f = pd.read_csv(output / "validation_market_info.csv")
    calibration = pd.read_csv(output / "validation_calibration.csv")
    _render_report(metrics, reliability, test_f, calibration, _selection_gate(metrics, config), output, False)


def calibrate_goalkeeper_reliability(config_path: Path) -> None:
    """The single §20.4.3 outcome-2 recalibration: P Performance/Reliability."""
    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    qc = QcLog()
    historical, quotation_tutti, _ = load_sources(config, qc)
    seasons, tw = config["seasons"], config["train_window"]
    records: list[dict[str, Any]] = []
    for target in seasons[tw:-1]:
        pos = seasons.index(target); train = seasons[pos - tw:pos]
        target_data = _target_universe(historical, _target_quotes(config, target), target)
        ranking, _ = _make_fold(historical, quotation_tutti, config, train, target, "model_3", target_data)
        features = calculate_season_features(historical[historical.Stagione.isin(train)], config, QcLog())
        scored = _targets(ranking, target_data, config, features)
        p = scored[scored.R.eq("P") & scored.Pv_target.ge(1)].copy()
        availability = p.Pv_target.ge(1)
        baseline = _metrics(p.baseline_1, p.Target_A, "P", [10], availability)
        for reliability_weight in [0.00, 0.10, 0.15, 0.20, 0.25]:
            score = (1 - reliability_weight) * p.Performance + reliability_weight * p.Reliability
            result = _metrics(score, p.Target_A, "P", [10], availability)
            records.append({"fold": target, "reliability_weight": reliability_weight, "performance_weight": 1 - reliability_weight, "spearman": result["spearman"], "precision_at_10": result["prec_at_10"], "baseline_spearman": baseline["spearman"], "baseline_precision_at_10": baseline["prec_at_10"], "spearman_delta": result["spearman"] - baseline["spearman"], "precision_delta": result["prec_at_10"] - baseline["prec_at_10"]})
    output = Path(config["paths"].get("output", "output"))
    grid = pd.DataFrame(records)
    grid.to_csv(output / "validation_goalkeeper_weight_grid.csv", index=False)
    print(grid.groupby("reliability_weight")[["spearman_delta", "precision_delta"]].agg(["median", "min", "max"]).round(3).to_string())


def run_lockbox(config_path: Path) -> None:
    """Open the single confirmation fold only after the selected config is frozen."""
    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    historical, quotation_tutti, _ = load_sources(config, QcLog())
    seasons, tw, target = config["seasons"], config["train_window"], config["seasons"][-1]
    pos = seasons.index(target); train = seasons[pos - tw:pos]
    target_data = _target_universe(historical, _target_quotes(config, target), target)
    ranking, _ = _make_fold(historical, quotation_tutti, config, train, target, "model_3", target_data)
    features = calculate_season_features(historical[historical.Stagione.isin(train)], config, QcLog())
    scored = _targets(ranking, target_data, config, features)
    scores = {"model_3": scored.HistoricalRatingRaw}
    scores.update({name: scored[name] for name in ["baseline_0", "baseline_1", "baseline_2", "baseline_3", "baseline_4"]})
    metrics = pd.DataFrame(_fold_metrics(scored, "Target_A", scores, config, target, "lockbox") + _fold_metrics(scored, "Target_B", scores, config, target, "lockbox"))
    target_a = metrics[metrics.target.eq("Target_A")].set_index(["role", "model"])
    rows = []
    guardrail = True
    for role in ROLES:
        model, baseline = target_a.loc[(role, "model_3")], target_a.loc[(role, "baseline_1")]
        n = 10 if role == "P" else 20
        precision_delta = model[f"prec_at_{n}"] - baseline[f"prec_at_{n}"]
        guardrail &= precision_delta >= -config["validation"]["precision_degradation_tolerance"]
        rows.append({"role": role, "model_spearman": model.spearman, "baseline_spearman": baseline.spearman, "spearman_delta": model.spearman - baseline.spearman, f"precision_at_{n}_delta": precision_delta})
    summary = pd.DataFrame(rows)
    primary = int((summary.spearman_delta > 0).sum()) >= 3
    tf, disagreements = _test_f(scored, target, "lockbox", config)
    output = Path(config["paths"].get("output", "output"))
    metrics.to_csv(output / "validation_lockbox_metrics.csv", index=False)
    pd.DataFrame(tf).to_csv(output / "validation_lockbox_market_info.csv", index=False)
    pd.DataFrame(disagreements).to_csv(output / "validation_lockbox_price_disagreements.csv", index=False)
    report = ["# Lock-box validation — 2025/26", "", "Configuration frozen before opening: `P = 0.85 Performance + 0.15 Reliability`; all other values are `config.yaml` defaults.", "", f"- Primary (model Spearman > Fm_Weighted in >=3 roles): **{'PASS' if primary else 'FAIL'}**.", f"- Guardrail (no precision degradation > {config['validation']['precision_degradation_tolerance']:.2f}): **{'PASS' if guardrail else 'FAIL'}**.", "", "```", summary.round(3).to_string(index=False), "```", "", "Qt.I/Test F is diagnostic only. The detailed metrics and market-disagreement CSVs accompany this report."]
    (output / "validation_lockbox_report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"Lock-box: primary {'PASS' if primary else 'FAIL'}; guardrail {'PASS' if guardrail else 'FAIL'}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 4 rolling validation.")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--lockbox", action="store_true", help="Include the one-shot 2025/26 lock-box after selection is frozen.")
    parser.add_argument("--render-existing", action="store_true", help="Render the report from existing selection CSV files.")
    parser.add_argument("--calibrate-goalkeeper-reliability", action="store_true", help="Run the permitted one-time P Performance/Reliability recalibration.")
    parser.add_argument("--lockbox-only", action="store_true", help="Open only the frozen one-shot 2025/26 confirmation fold.")
    args = parser.parse_args()
    if args.render_existing:
        render_existing(args.config)
    elif args.calibrate_goalkeeper_reliability:
        calibrate_goalkeeper_reliability(args.config)
    elif args.lockbox_only:
        run_lockbox(args.config)
    else:
        run(args.config, args.lockbox)


if __name__ == "__main__":
    main()
