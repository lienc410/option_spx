# SPEC-120 — 矩阵 26y CALIB 重跑与逐格对比（Q087 包3 收官件）

**解锁依据**: SPEC-119 已落地 + Q087 B2 回填 30 天 *_moff 校准（无需等 07-17）。
**回答的问题**（压着 Track A 三个终局 + 实盘 carve）: (1) BPS/IC/BCD 各特许经营权在定价级校准下的真实经济学；(2) 矩阵格间相对排序是否稳健；(3) SPEC-060 死格重估、SPEC-079 移除、IV_LOW 边界的终局输入；(4) **BCD/SPEC-113 实盘 carve 在 moff 下的重估（最高优先，B3 已发方向性警报：FLAT 高估 BCD debit 经济学）**。

## 1. 实施内容（dev）

1. `backtest/engine.py` 接 `pricing.sigma` 模式选择（构造参数 `sigma_mode: FLAT|CALIB|PESS`，默认 FLAT 保持 bit-identical——AC-1 复用 SPEC-119 冻结快照）
2. CALIB 模式：per-leg sigma = VIX + `pricing.calibration.load_offsets()`（按 option_type × |delta| 桶 × DTE 桶插值；DTE 在 25-35 与 80-100 桶之间线性插值，超界夹取）；offsets 数据源 = 生产 monitor JSONL ∪ B2 回填文件（`research/q087/q087_moff_backfill.jsonl`，schema 相同，dev 合并去重）
3. PESS 模式：CALIB + 调用方传入 bracket（本 SPEC 附带跑一组：所有 short 腿 −1vp / long 腿 +1vp）
4. **重跑矩阵 26y × {FLAT, CALIB, PESS}**：输出逐格（regime × iv_signal × trend × strategy）trade 级 CSV + 汇总（n/win/mean/net/worst7y/2020+/2024+ 分时代）
5. 对比报告数据落 `research/q087/spec120_matrix_calib_compare.csv`

## 2. AC

- AC-1 FLAT bit-identical（冻结快照）
- AC-2 CALIB 单日抽检：2026-07-02 的 BPS 30DTE 定价与真实 mid 误差 <15%（同 SPEC-119 AC-3 协议，非 mock）
- AC-3 逐格 CSV schema 完整（含分时代列）；strict-JSON/CSV 无 NaN
- AC-4 BCD 格优先输出（SPEC-113 carve 单列一行）
- AC-5 offsets 合并器对缺字段日 fail-soft 且计数上报

## 3. 分析与裁决（quant，dev 交付后）

逐格 verdict 表 → Track A 三个 conditional-close 终局（A1/A2/A4）+ SPEC-060 死格处置 + SPEC-113 carve 重估 → 全部走外审 → 行为变更类由 PM ratify。**预先声明**：FLAT→CALIB 若整体下修，先看格间相对排序是否保持（路由可能不需要动）；absolute 下修本身不自动触发任何实盘变更（自适应姿态：live/paper 流水才有最终投票权，SPEC-116 paper 与实盘 ledger 是对照锚）。
