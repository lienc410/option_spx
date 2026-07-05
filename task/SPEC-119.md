# SPEC-119 — 统一定价库 `pricing/`（Q087 包3 · Track B 主工程）

**动机**: 生产侧 5 份 + 研究侧多份 BS 定价实现各说各话（B1 审计）；生产惯例 VIX-flat + 零股息已被真实链测量证实系统性偏差（credit 结构高估 2-4vp，call 侧最重）。本 SPEC 建库；矩阵 CALIB 重跑是后续 SPEC-120。

## 1. 库结构

```
pricing/
  core.py        # d1/d2, call/put price, greeks, strike-for-delta（单一真值）
  sigma.py       # 三种 sigma 模式（见 §2）
  calibration.py # 从 skew monitor JSONL 读取/拟合当前 offsets
```

## 2. 三种 sigma 模式（研究与回测显式选择，禁止默认）

| 模式 | 定义 | 用途 |
|---|---|---|
| `FLAT` | sigma = VIX/100 全 strike（现行为，含 q=0 选项以复现旧结果） | 复现历史回测（bit-identical 校验用） |
| `CALIB` | sigma = VIX/100 + offset(option_type, |delta|, dte_bucket)；offsets 来自 `data/q085_skew_monitor.jsonl` 滚动中位（缺桶回退线性插值） | 新研究默认 |
| `PESS` | CALIB 基础上对持仓不利方向加 bracket（参数由调用方传入，禁止库内写死） | ratify 前稳健性 |

**Offsets 初值**（2026-05/07 实测，calibration.py 应从 JSONL 动态计算而非硬编码，此表仅为验收基准）：
put d0.30 = −2.0 / put d0.15 = +1.0 / call d0.70 = −2.0 / call d0.30 = −3.6 / call d0.16 = −4.5 / call d0.08 = −5.0（25-35 DTE 桶）。80-100 DTE 桶待 skew monitor 扩展后补。

## 3. 迁移原则

1. **本 SPEC 只建库 + 迁移生产 5 处调用点到 `pricing.core`（FLAT 模式）**——行为 bit-identical（AC-1: 矩阵回测输出逐 trade 相同；AC-2: 现有全部测试通过）
2. 研究侧脚本不回改（历史 artifact），新研究一律 import pricing
3. r/q 参数入 core 显式参数（现状：生产 q=0、研究 q=1.3% 不一致——FLAT 模式带 q 开关以兼容两侧复现）

## 4. 配套（并入本批）

- **skew monitor 扩展**（SPEC-116 任务的小改）：call 侧四档 + put 三档 × 两个 DTE 桶（25-35、80-100），每日落盘同一 JSONL（新字段向后兼容）
- calibration.py 的 offsets 计算带最小样本量门槛（<10 天报 insufficient 并回退 FLAT + 告警）

## 5. AC

- AC-1 bit-identical：FLAT 模式下 26y 矩阵回测逐 trade 与迁移前一致（冻结快照对比）
- AC-2 全测试通过；AC-3 CALIB 模式对 2026-07-02 链的 BPS 30DTE δ.30/.15 定价与真实 mid 误差 < 15%（integration，非 mock）
- AC-4 skew monitor 新字段首日落盘 strict-JSON
- AC-5 PESS 模式 bracket 参数必传（无默认值，漏传即 raise）

## 6. 后续（不在本 SPEC）

SPEC-120: 矩阵 26y CALIB 重跑 + 逐格对比报告 → P1 重审（矩阵地基 / Q082 / Q071）。