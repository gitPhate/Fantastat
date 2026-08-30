# Fantastat historical ranking

Run phases 1--3 with:

```powershell
python -m pip install -r requirements.txt
python src/run_pipeline.py
```

The generated files are `data/historical.csv`, `data/merged.csv`,
`data/qc_log.csv`, and `output/ranking_dataset.csv`.

`HistoricalRating` is historical evidence, not an auction price or a projection.
Use `Rank_Role`, not global `Rank`, to compare players. `Reliability` measures
availability/sample size, not personal dependability. `DefenseScore` is the
weighted Mv, intentionally independent of the rating. Goalkeeper goals conceded
is not adjusted for team defensive strength.

`Pv_Weighted` is a time-weighted feature, not a projected number of appearances;
`Pv_Totale` is the actual sum used for history category. NEW players intentionally
have no historical rating; their role median is context, not an imputed score.

Phase 4 is run with `python src/validate.py`. The six selection folds supported
the one permitted goalkeeper weight recalibration (0.85 Performance / 0.15
Reliability), but the frozen 2025/26 lock-box failed its primary test: the full
model beat weighted Fm in only two of four roles. Therefore the current ranking
is exploratory and must not be treated as validated auction guidance; the next
work is a structural model review, not further parameter tuning.

## Projected auction model (v2)

Build the separate pre-auction projection with:

```powershell
python src/run_projection.py
```

It creates `output/projected_auction_dataset.csv` and
`output/projected_validation_report.md`. The model predicts appearances and
conditional FantaMedia independently for each current Classic role, then uses
their product only as projected seasonal points. `Qt.I_2026_27` is retained as
auction context and is never a model feature. The dataset is intentionally not
overwritten on subsequent runs: preserve it as the pre-2026/27 artifact for
the eventual final test.
