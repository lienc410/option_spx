# MC Response 2026-05-02 corrections (v2 OCR Cleanup)

> 说明：
> - 本文件是对扫描件 `sync/mc_to_hc/MC Response 2026-05-02 corrections.md` 的 OCR / 排版校正稿
> - 目的仅为帮助 HC 与 MC 对 `MC Response 2026-05-02_v2.md` 做数字级复核
> - 本文件本身不是新的 handoff 结论，只是 `MC Response 2026-05-02_v2.md` 的 errata 表

# MC Response 2026-05-02 corrections

类型：OCR 校正 reply  
对应 HC v2 文件：`sync/mc_to_hc/MC Response 2026-05-02_v2.md`

回应针对一件事：

- v2 OCR 清洗后仍有 5 项 critical 数字错读

其中部分会直接影响 HC attribution 分析。  
本 reply 不修改 `v2` 文件本身，仅列出 MC canonical 正确数字作为 `v2` 的 errata 表。  
HC 在阅读 `v2` 时，请按本 reply 替换错读数字。

---

## 背景说明

HC 在 `2026-05-02` 完成 `MC Response 2026-05-02.md` 的 OCR 清洗，产出 `MC Response 2026-05-02_v2.md`。

MC 评价：

- `v2` 整体格式整洁
- 绝大多数数字保留正确
- 但仍有 5 项 critical 数字错读

若 HC 直接用 `v2` 做 attribution 分析，会得出错误结论。  
尤其是 `IC ledger` 的 6 笔 `entry_credit`，在 `v2` 中被误读为缩小 `100×`，会严重低估 `IC` 的 credit 量级。

---

## 纠正项一 — `iron_condor_hv` 的 PT=0.50 PnL

`v2` 写法：

- `PT 0.50：75 笔 / +14,126`

MC canonical 正确值：

- `PT 0.50：75 笔 / +13,679`

说明：

- 原文整数是 `13679`
- `v2` 重构成 `14126` 是错的

影响：

- `v2` 错值会让 `iron_condor_hv` 看起来比实际多赚 `447 USD`

---

## 纠正项二 — `iron_condor_hv` 的 delta_pnl

`v2` 写法：

- `delta = -587`

MC canonical 正确值：

- `delta = -140`

说明：

- 该值可由纠正项一推导：
  - `PT 0.60 = 13,539`
  - `PT 0.50 = 13,679`
  - 所以 `delta = -140`

影响：

- `v2` 错值会让 HC 误以为 `profit_target` 升至 `0.60` 对 `iron_condor_hv` 有更强拖累，从而错估 `SPEC-077` 对各策略的影响

---

## 纠正项三 — `n_days`

`v2` 中多处写法：

- `n_days = 9616`

MC canonical 正确值：

- `n_days = 6621`

说明：

- `v2` 是按 `26.32 × 365.25` 近似推回的日历天数
- 但 MC engine 这里使用的是 **trading days**
- `26.32` 年对应的 trading days 约为 `6621`

影响：

- 不影响 `ann_roe` 公式本身，因为公式用的是 `n_years`
- 但事实层面，`9616` 是错的，应该纠正为 `6621 trading days`

---

## 纠正项四 — `Q039 / IC ledger` 6 笔 `entry_credit`

`v2` 中 6 笔 `entry_credit` 的小数点位置整体错了，量级被缩小约 `100×`。

MC canonical 正确值：

1. `2023-08-15`
   - `v2`：`-29.62`
   - 正确：`-2962 USD`

2. `2023-09-20`
   - `v2`：`-27.02`
   - 正确：`-2702 USD`

3. `2023-10-31`
   - `v2`：`-34.87`
   - 正确：`-3087 USD`
   - 这里不只是小数点错，`34` 也应为 `30`

4. `2024-05-03`
   - `v2`：`-27.92`
   - 正确：`-2792 USD`

5. `2025-12-18`
   - `v2`：`-46.35`
   - 正确：`-4630 USD`
   - 这里不只是小数点错，`35` 也应为 `30`

6. `2026-01-21`
   - `v2`：`-47.[OCR unclear]`
   - 正确：`-471 USD`

说明：

- `IC` 卖出在 SPX 上，`entry_credit` 通常是数百到数千美元量级
- `v2` 里 `-29.62` / `-27.02` 这种几十美元信用金明显不合理

影响：

- 这是最 critical 的错读
- 若 HC 直接用 `v2` 的几十美元量级做判断，会严重低估这 6 笔 `IC` 的真实仓位量级

---

## 纠正项五 — `Q039 / IC ledger` 的 `dte_at_exit`

`v2` 中第 2 / 3 / 4 笔 `roll_21dte` 交易写成：

- `dte_at_exit = 22`

MC canonical 正确值：

- 第 2 笔：`dte_at_exit = 21`
- 第 3 笔：`dte_at_exit = 21`
- 第 4 笔：`dte_at_exit = 21`

其余：

- 第 1 笔：`dte_at_exit = 25`（v2 正确）
- 第 5 笔：`dte_at_exit = 25`（v2 正确）
- 第 6 笔：`dte_at_exit = 25`（v2 正确）

说明：

- `roll_21dte` 的触发条件是 `DTE = 21`
- 不是 `22`
- 因此 `22` 与 `exit_reason = roll_21dte` 相矛盾

影响：

- 影响不如 credit 量级大
- 但 `exit_reason` 与 `dte_at_exit` 的一致性是 audit trail 的关键属性，应纠正

---

## 对 v2 已正确处理部分的 acknowledge

### 1. `Δ / delta` 与 `A` 的 OCR 注释

`v2` 文件头已增加脚注，说明扫描件中 `Δ / delta` 大量被识别为大写字母 `A`。  
MC 认为这是好的做法，建议 HC 后续 sync 包继续保留这一类 OCR pipeline 注释。

### 2. v2 自标 OCR uncertain 但其实正确的项

以下 `v2` 虽有自注，但最终数字是对的，不需要修改：

- `bull_put_spread_hv delta = -26`
- `bull_call_diagonal delta = +98`
- 第 6 笔 `entry_spx = 6876`

### 3. 校验行格式简化

MC 原稿中大量使用中文数字校验行（如“零七四”）。  
`v2` 简化为 `校验 SPEC-编号`，MC 认为无妨；因为 `v2` 已是 OCR 后电子文件，不再依赖中文数字防误读。

### 4. 整体质量评价

除上述 5 项错读外，`v2` 的整体质量较高：

- 99%+ 数字保留正确
- SPEC 编号全部正确
- PT 0.50 / PT 0.60 主表基本一致
- by `exit_reason` 主表基本一致

HC OCR pipeline 总体可靠。

---

## 完整数字对账（防再误读）

### `iron_condor_hv` 全样本

- `PT 0.50：75 笔 / +13,679 USD`
- `PT 0.60：73 笔 / +13,539 USD`
- `delta_pnl = -140 USD`
- `delta_n = -2`

### `n_days` 全样本

- `6621 trading days`
- 不是 `9616`

### `Q039 IC ledger entry_credit`（按 entry_date 顺序）

- `2023-08-15` → `-2962`
- `2023-09-20` → `-2702`
- `2023-10-31` → `-3087`
- `2024-05-03` → `-2792`
- `2025-12-18` → `-4630`
- `2026-01-21` → `-471`

单位均为美元。  
量级是几百到几千，不是几十。

### `Q039 IC ledger dte_at_exit`

按 entry_date：

- `2023-08-15` → `25`
- `2023-09-20` → `21`
- `2023-10-31` → `21`
- `2024-05-03` → `21`
- `2025-12-18` → `25`
- `2026-01-21` → `25`

校验规则：

- `exit_reason = 50pct_profit` 时，`dte_at_exit = 25`
- `exit_reason = roll_21dte` 时，`dte_at_exit = 21`

---

## HC 收到本 reply 后建议动作

1. 将本 reply 的 5 项纠正应用到对 `v2` 的阅读理解  
   - 不要求保留原扫描件不动
   - 但 HC 任何基于 `v2` 数字做的 attribution 分析，都应改用本 reply 的正确值

2. 特别是 `Q039`
   - HC 在做 `ivp252` 三个分桶分析时，请用本 reply 中修正后的 `entry_credit`
   - 不要再用 `v2` 里几十美元的错读量级

3. 其余内容在 MC 看来可继续以 `v2` 为基础阅读

