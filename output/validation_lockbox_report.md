# Lock-box validation — 2025/26

Configuration frozen before opening: `P = 0.85 Performance + 0.15 Reliability`; all other values are `config.yaml` defaults.

- Primary (model Spearman > Fm_Weighted in >=3 roles): **FAIL**.
- Guardrail (no precision degradation > 0.05): **PASS**.

```
role  model_spearman  baseline_spearman  spearman_delta  precision_at_10_delta  precision_at_20_delta
   P           0.349              0.090           0.259                    0.2                    NaN
   D           0.366              0.384          -0.018                    NaN                    0.1
   C           0.346              0.321           0.025                    NaN                    0.1
   A           0.293              0.314          -0.020                    NaN                    0.0
```

Qt.I/Test F is diagnostic only. The detailed metrics and market-disagreement CSVs accompany this report.