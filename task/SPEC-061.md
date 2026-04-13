# SPEC-061: `/ES` Short Put Minimal Production Cell

Status: DONE

## 目标

**What**：将 `/ES` short put 收缩为一个最小、可验证、可控风险的生产候选单元，仅覆盖单槽、单张、固定 DTE / delta、固定止损、固定 BP 上限的基础路径。

**Why**：
- `/ES` 账户权限已确认可用，实测 buying power effect 约为 `$20,529 / contract`，在当前约 `$500k` 账户规模下具备现实可执行性
- 相比 XSP，`/ES` 当前更接近可上线的生产路径；剩余核心问题已从“能否交易”转为“如何在 shared BP 约束下以最小风险进入生产验证”
- 当前研究仍包含 proxy 成分，不适合直接推进完整 ES puts 体系；应先验证最小生产 cell，再决定是否扩展

---

## 核心原则

- 仅实现最小生产 cell，不把研究性扩展一并带入
- 优先复用现有趋势、选链、风控和持仓管理框架，不为 `/ES` 单独发明一套新体系
- shared BP 约束按保守口径处理，宁可少开，不做乐观假设
- 本 SPEC 解决“能否以最小风险上线第一版”，不解决“如何做到组合最优”

---

## 功能定义

### F1 — 标的与结构

- 标的：`/ES` options
- 结构：裸卖 `put`
- 单次仅允许单槽位持仓
- 每次开仓数量固定为 `1` 张

### F2 — 合约参数

- 目标到期日：`45 DTE`
- 目标 delta：`20 delta`
- 允许正常执行所需的最小择近规则，但不扩展为多 DTE ladder 或多档同时开仓
- 若目标链上不存在精确 `45 DTE / 20 delta` 合约，可按现有选链框架选择最近可执行候选；但实现时必须保持规则简单、固定、可解释，不能扩展成新的多层评分体系

### F3 — 入场过滤

- 使用已定义的 `trend filter`
- 若 `trend filter` 不满足，则不新开 `/ES` short put
- 本 SPEC 不新增额外的 discretionary 入场条件

### F4 — 风险控制

- 固定止损：`-300%` credit stop
- `/ES` 总 buying power 占用不得超过 `NLV 20%`
- `/ES` 与现有 SPX Credit 默认视为共用同一 BP 池，不单独假设隔离保证金
- 若当前 BP 信息不足以做保守判断，则默认拒绝新开 `/ES` 仓位，而不是放宽约束

### F5 — 目标定位

- 本 SPEC 仅实现最小生产路径
- 不要求同时解决 `/ES` 与 SPX Credit 的最优组合配置问题
- 不要求在本 SPEC 内解决扩仓、分层或组合级动态预算优化

---

## 接口定义

### I1 — 推荐 / 选链接口

- Developer 可复用现有推荐与选链框架，但最终产物必须能表达以下最小信息：
  - 标的为 `/ES`
  - 方向为 short put
  - 数量为 `1`
  - 目标约束为 `45 DTE` 与 `20 delta`
  - 是否通过 `trend filter`
  - 是否通过 `BP <= NLV 20%` 检查

### I2 — 风控接口

- `/ES` 路径必须接入现有持仓后风控框架或等价实现，确保 `-300%` credit stop 可执行
- 不要求本 SPEC 改写通用风控框架，但若现有框架无法表达 `/ES` short put 的最小止损需求，则需在实现前补足这一表达能力

### I3 — 资金约束接口

- 系统必须能在开仓前读取或推导当前 `NLV` 与 `/ES` 预计 BP 占用
- 系统必须以 shared BP 视角做开仓判断，而不是只看 `/ES` 单腿名义价值

---

## 边界条件与约束

- 仅允许单槽位；若已有该路径持仓存在，则不得因本 SPEC 再开第二个 `/ES` 槽位
- 仅允许 `1` 张；不得因为 VIX 抬升、信号更强或 BP 尚有余量而自动加到 `2` 张
- 仅允许一个最小目标 DTE / delta 路径；不得在本 SPEC 内演变为“优先 45 DTE，备选 35/49 DTE”的 ladder 逻辑
- `trend filter` 只作为入场门，不在本 SPEC 中新增新的出场型趋势规则
- BP 检查必须发生在开仓前，且按保守约束拦截；不得先生成推荐再由人工推断是否超限
- 本 SPEC 不要求解决 `/ES` 与 SPX Credit 的全局优先级调度，只要求在 shared BP 口径下不越线

---

## 失败处理

- 若 `trend filter` 数据缺失或状态不可判定：不新开仓
- 若 `/ES` 目标链数据不足，无法做最小可解释选链：不新开仓
- 若 BP / NLV 数据缺失，无法确认 `BP <= NLV 20%`：不新开仓
- 若现有风控框架无法对 `/ES` short put 绑定 `-300%` credit stop：不得绕过，必须先补足能力或停止推进实现

---

## 依赖与前置假设

- `/ES` 交易权限在当前生产环境已可用
- 账户层面存在与 SPX Credit 共用的 options buying power 约束
- `trend filter` 已有可复用定义，本 SPEC 不重写其研究逻辑
- 现有系统已经具备基本的推荐、持仓、止损或等价风险控制接入点；若缺失，需在实现前明确落点

---

## 明确不在范围内

- 不做多 DTE ladder
- 不做 `1–2` 张以上的高波动扩仓逻辑
- 不做动态杠杆表
- 不做 Black Swan Hedges（BSH）
- 不做 `/ES` 与 SPX Credit 的复杂组合优化或相关性驱动调仓
- 不新增 discretionary 主观判断层
- 不尝试一次性落地完整 ES puts 三层体系
- 不为了 `/ES` 路径重做一套独立策略矩阵
- 不在本 SPEC 中引入“高波动时例外放宽 BP 上限”的特殊规则
- 不在本 SPEC 中处理季度合约 vs EOM weekly 的更细流动性研究问题

---

## 验收标准

- AC1. 系统可在满足 `trend filter` 时生成 `/ES` short put 的单槽、`1` 张候选持仓
- AC2. 目标合约选择逻辑落在 `45 DTE`、`20 delta` 的最小实现范围内
- AC3. 当 `trend filter` 不满足时，系统不会为该路径新开仓
- AC4. 当预计 `/ES` BP 占用超过 `NLV 20%` 时，系统拒绝新开该仓位
- AC5. 止损规则按 `-300%` credit stop 执行
- AC6. 本 SPEC 不引入多 DTE ladder、动态杠杆表或 BSH 相关逻辑
- AC7. 当 `trend filter`、BP、NLV 或目标链数据缺失时，系统按保守口径拒绝开仓，不做乐观回退
- AC8. 当已有该路径持仓存在时，系统不会因本 SPEC 再开第二个 `/ES` 槽位
- AC9. 实现方案可明确指出复用模块与落点，不需要额外发明完整 ES puts 子系统

---

## Review
- 结论：PASS
- Status：DONE
- AC1：`select_es_short_put` 在 `BULLISH` 时返回 `StrategyName.ES_SHORT_PUT`，单腿 PUT，目标 `45 DTE / 0.20 delta`
- AC2：合约选择通过 `find_strike_for_delta` 与 `build_strike_scan(target_dte=45, target_delta=-0.20)` 落地，并按 `/5` tick 取整
- AC3：`trend.signal != TrendSignal.BULLISH` 时返回 `REDUCE_WAIT`；API 层对应返回 `400`
- AC4：`_ES_BP_LIMIT_FRACTION = 0.20` 生效；超限时返回 `400` 并给出拒绝理由
- AC5：`strategy/catalog.py` 中 `roll_rule_text = "Close at 21 DTE; stop at 3× credit"`，selector 与 API 测试均断言包含 `3× credit`
- AC6：PASS。Handoff 将其标为“未通过”仅因未新增专门断言，但 AC6 是负向约束；核查实现确认未引入 ladder、动态杠杆表或 BSH 逻辑
- AC7：BP / NLV 缺失、trend 缺失、chain 不足（`scan_fallback` 或无 `recommended`）均返回 `400`
- AC8：`_is_es_option_position` 能检测已有 `/ES` put` 持仓并拒绝第二槽位
- AC9：实现复用 `backtest.pricer`、`schwab.scanner`、`signals.trend`，未发明独立子系统
- 实现细节 1：BP 检查口径比 Spec 字面更保守，当前逻辑按“当前总 margin + /ES $20,529 <= NLV 20%”判断；在 SPX Credit 仓位占用较高时，`/ES` 可能比预期更难触发开仓条件。这不是 bug，但 PM 应知晓
- 实现细节 2：`_is_es_option_position` 依赖文本匹配（如 `"/ES"` 与 `"PUT"`）；在当前 MVP 范围内可接受，但若 Schwab API 的 symbol 文本格式变化，后续可能需要单独加固

## 备注

- 该 SPEC 是研究收缩后的最小生产候选，不代表完整 ES puts 体系获批
- 若本最小 cell 后续运行或回测结果支持，再考虑拆分后续扩展 SPEC：
  - 多 DTE ladder
  - leverage table
  - BSH
  - shared-BP budgeting refinement
