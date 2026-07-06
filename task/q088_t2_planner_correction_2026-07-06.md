# Q088 T2 初评建议 — Planner 正式纠正

**日期**：2026-07-06  
**背景**：Claude Code 建议提前做"BCD shadow + S2-BPS paper 初评"来加速 T2 评分。Planner 识别出三个核心错误并做出正式回应。

---

## 一、数据地图全错（三处）

### 错误 1: bcd_filter_shadow.jsonl 身份误认
- **错误假设**：BCD 交易流（2325 条 7 日记录）
- **真实情况**：已退役 SPEC-079 filter 风险评分日志
  - 内容：`date/vix/risk_score/would_block`（**无 PnL 字段**）
  - 脚本中 `t.get('pnl', 0)` 对每行返回 0 → "平均 $0、胜率 0%"（**垃圾数字**）
  - 2325 行是 Q087 26 年**回测重放**产物（首行日期 2000 年），非"7 日数据"
  - SPEC-124：该文件已于两台生产机删除（2026-07-06）
  - 本地遗留今日清理（正**证明清理必要**）

### 错误 2: 真实 BCD 证据流位置
- **真正的生产流**：`q087_bcd_quote_shadow.jsonl`（SPEC-122 定义）
- **当前生产状态**：**0 行**（文件未创建或为空）
  - 部署至今未出现 BCD 信号日（正常——BCD 发射频率低，~6/年）
  - 今日 16:50 的首次任务运行前

### 错误 3: skew monitor 和 S2-BPS paper ledger
- **skew monitor 生产文件**：**1 行**（7/3，旧 schema）
  - 7/4 国庆假期、7/5 周末 → 无新数据
  - moff 字段**前向积累从今日 16:50 才开始**
  - SPEC-120 用的 30 行 = **回填数据集**（历史校准用），**非生产积累**
- **S2-BPS paper ledger**：**0 行**（正常，~6 次/年 信号频率）

---

## 二、原则层面："初评→升级"违反预注册纪律

### 为什么不能做初评

**1. 评价框架已预注册**
```
SPEC-122:
  - pass/fail 标准与期限：≥8 信号日 或 9/30
  - BCD 降级规则：四门阈值
  - D2 前置门：≥10 日价格数据 + ±1vp 复验

T2 定量框架:
  - per-slot IC 强度量化指标
  - shadow→paper→live 升级阈值（预期 50+ shadow 信号）
  - 解锁条件：预注册 checkpoint 或 live/paper 事件

← 全部在"数据到来前"锁定
```

**2. 现在"帮忙写新框架" = 看着早期数据设计门柱**
- 违反 METHODOLOGY.md §5：
  - "已采纳 sleeve 只认 live/paper 流水"
  - "预承诺规则不得事后调整"
- 重复的错误模式（Q083-Q088 沉淀的教训反例）：
  - [[feedback_post_withdrawal_proposals_front_load_robustness]]
  - 压力下快速决策 = 框架崩塌的前兆

**3. 升级的唯一合法触发器**
```
✅ 预注册 checkpoint 到期（时点已固定）
✅ live/paper 流水事件（外部事件驱动，如 BCD 7-8 月持仓到期）

❌ "7 天窗口早期数据看着好→我觉得可以升级了"
```

---

## 三、真实日历（替代等待建议）

| Checkpoint | 触发类型 | 时点 | 驱动源 |
|---|---|---|---|
| **moff 前向 vs 回填一致性** | 日历 | 2026-07-17 | SPEC-120 定期检查 |
| **BCD 首笔实现流水** | 事件 | ~2026-07~08 月 | BCD 持仓成熟 |
| **SPEC-122 仲裁续期** | 数据驱动 | ≥8 信号日 或 2026-09-30 | 预注册条件 |
| **D2 主格前置门** | Regime 驱动 | LOW_VOL 回归 + 10 日报价 | 策略条件 |
| **DEFERRED 月度复核** | 日历（自动） | 2026-08-03 起每月 | 系统心跳 |
| **T2 正式评级** | 日历（例行） | 排队中（tconv 重跑） | 年度流程 |

---

## 四、纪律声明

> **框架已在、门柱已钉、数据在路上**
>
> 现在唯一正确的动作 = **让日历和事件来触发我们**，而不是我们去够数据。

---

## 五、关键记忆引用

- [[feedback_post_withdrawal_proposals_front_load_robustness]] — 被撤回≥2次的提案稳健性必须前置，压力下"快点ship"是错误源头
- [[system_methodology_v1_1]] — METHODOLOGY.md v1.1 §5 role interfaces：Quant 保证工具完备，PM 拥有 paper→production 时机
- [[governance_naked_note_death_sentence]] — 已知问题第二次浮出 = 强制 governance reauth

---

**来源**：Planner 2026-07-06 正式回应  
**相关 SPEC**：SPEC-122、SPEC-120、SPEC-116、SPEC-124  
**相关 Q**：Q087 Track A-E、Q088 T1、Q088 T2
