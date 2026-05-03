Applied the 5 numeric errata from `MC Response 2026-05-02 corrections` into our cleaned `MC Response 2026-05-02_v2.md`:

1. `iron_condor_hv` PT=0.50 pnl corrected
   - `+14,126 -> +13,679`

2. `iron_condor_hv` delta pnl corrected
   - `-587 -> -140`

3. `n_days` corrected
   - `9616 -> 6621`

4. `Q039` 6-trade IC ledger `entry_credit` corrected to MC canonical scale
   - `2023-08-15: -29.62 -> -2962`
   - `2023-09-20: -27.02 -> -2702`
   - `2023-10-31: -34.87 -> -3087`
   - `2024-05-03: -27.92 -> -2792`
   - `2025-12-18: -46.35 -> -4630`
   - `2026-01-21: -47.[unclear] -> -471`

5. `Q039` roll_21dte rows `dte_at_exit` corrected
   - `2023-09-20: 22 -> 21`
   - `2023-10-31: 22 -> 21`
   - `2024-05-03: 22 -> 21`

We also preserved the corrections file itself as a separate OCR-clean errata reference:
- `sync/mc_to_hc/MC Response 2026-05-02 corrections_v2.md`
