# Phase 4 validation report

## Selection gate (Target A)

- Primary: **PASS** — 5/6 selection folds have the model ahead of Fm_Weighted in at least three roles.
- Guardrail: **FAIL** — degradation counts by role: {'P': 3, 'D': 0, 'C': 0, 'A': 0}.
- Target B and market comparisons are diagnostic, not gate criteria.

## Coverage

```
role                   A      C      D      P
fold    fold_kind                            
2019/20 selection  0.676  0.682  0.641  0.531
2020/21 selection  0.703  0.724  0.736  0.571
2021/22 selection  0.629  0.693  0.706  0.608
2022/23 selection  0.712  0.638  0.707  0.566
2023/24 selection  0.636  0.686  0.725  0.542
2024/25 selection  0.649  0.650  0.632  0.518
```

## Detailed metrics

Per-fold, per-role, per-target metrics are in `validation_metrics.csv`; calibration, direct Reliability tests, market-information tests, and extreme disagreements have separate CSV exports.

## Direct Reliability test

```
   fold fold_kind role       outcome  reliability_spearman  last_pv_spearman   n
2019/20 selection    P     Pv_target                 0.575             0.622  47
2019/20 selection    P played_binary                 0.584             0.400  57
2019/20 selection    D     Pv_target                 0.461             0.498 189
2019/20 selection    D played_binary                 0.394             0.305 154
2019/20 selection    C     Pv_target                 0.423             0.403 189
2019/20 selection    C played_binary                 0.353             0.324 162
2019/20 selection    A     Pv_target                 0.439             0.442 106
2019/20 selection    A played_binary                 0.408             0.397  95
2020/21 selection    P     Pv_target                 0.793             0.652  50
2020/21 selection    P played_binary                 0.660             0.424  55
2020/21 selection    D     Pv_target                 0.401             0.479 205
2020/21 selection    D played_binary                 0.261             0.212 179
2020/21 selection    C     Pv_target                 0.520             0.528 183
2020/21 selection    C played_binary                 0.287             0.325 163
2020/21 selection    A     Pv_target                 0.562             0.589 120
2020/21 selection    A played_binary                 0.264             0.263 105
2021/22 selection    P     Pv_target                 0.694             0.697  46
2021/22 selection    P played_binary                 0.561             0.252  57
2021/22 selection    D     Pv_target                 0.255             0.354 205
2021/22 selection    D played_binary                 0.312             0.289 172
2021/22 selection    C     Pv_target                 0.473             0.556 183
2021/22 selection    C played_binary                 0.292             0.285 149
2021/22 selection    A     Pv_target                 0.469             0.494 128
2021/22 selection    A played_binary                 0.361             0.360  98
2022/23 selection    P     Pv_target                 0.587             0.446  46
2022/23 selection    P played_binary                 0.619             0.437  57
2022/23 selection    D     Pv_target                 0.448             0.457 203
2022/23 selection    D played_binary                 0.278             0.315 175
2022/23 selection    C     Pv_target                 0.478             0.438 192
2022/23 selection    C played_binary                 0.308             0.339 152
2022/23 selection    A     Pv_target                 0.351             0.399 106
2022/23 selection    A played_binary                 0.464             0.440  92
2023/24 selection    P     Pv_target                 0.682             0.769  49
2023/24 selection    P played_binary                 0.482             0.316  51
2023/24 selection    D     Pv_target                 0.364             0.368 194
2023/24 selection    D played_binary                 0.183             0.164 169
2023/24 selection    C     Pv_target                 0.480             0.470 189
2023/24 selection    C played_binary                 0.245             0.218 157
2023/24 selection    A     Pv_target                 0.178             0.224 112
2023/24 selection    A played_binary                 0.276             0.300  91
2024/25 selection    P     Pv_target                 0.421             0.557  45
2024/25 selection    P played_binary                 0.684             0.674  53
2024/25 selection    D     Pv_target                 0.270             0.340 208
2024/25 selection    D played_binary                 0.268             0.237 155
2024/25 selection    C     Pv_target                 0.457             0.462 199
2024/25 selection    C played_binary                 0.283             0.237 150
2024/25 selection    A     Pv_target                 0.450             0.332 109
2024/25 selection    A played_binary                 0.023             0.107  87
```

## Lock-box

Not opened. Run `python src/validate.py --lockbox` only after selection configuration is frozen.

## Calibration protocol

Defaults are pre-registered. Parameter changes require the specified directional agreement; no automatic changes were made by this first selection report.