# Q089 G-review packet — E2/E4 双 kill verdict 外审请求（2026-07-06）

**待审 verdict**: 两条择时挑战者（A：入场等回调；B：短腿 re-sell 延迟）均不采纳，现任机械行为（触发日入场；roll 触发即同时平旧开新）维持。Kill-class → 外审强制。

**Artifacts**（repo 相对路径）:
- 预注册: `research/q089/q089_framing.md`（含问题 B 同日扩充与 E2 设计锁，修订日志在档）
- 事实层: `research/q089/q089_e1_fact_layer.py` + results csv + memo
- 经济层: `research/q089/q089_calib_lib.py`、`q089_e2_entry_timing.py`、`q089_e4_resell_timing.py`、`q089_pess_friction_bracket.py`；`q089_e2_results.csv`、`q089_e4_results.csv`、`q089_e4_results_2x.csv`
- Verdict: `research/q089/q089_e2_e4_verdict_2026-07-06.md`

**核心数字**（请代码复核，勿信文字）: E2 确认半样本 Δtotal −$774（选中 wait3）、bootstrap CI [−25,017,+30,481]；E4 基线 +$317/campaign、选中 prev_high-c10 确认半 t=0.83、全家族 2024+/last24m 全负；2× 摩擦 bracket 两处 verdict 不动。

**显式攻击面**（至少逐条回应）:
1. **摩擦模型**：单日（7/6，LOW_VOL）实测半价差外推 26 年；长腿 0.2%/短腿 1.0% 是否系统性偏轻/偏重？2× bracket 是否足够覆盖 2008/2020 型价差爆宽？摩擦经笔数不对称直接进 Δ——v1 的 1.6% 错误曾把 verdict 完全翻转，这是本研究最大杠杆点。
2. **E2 半样本程序**：select-half 选中 wait3（+3,121）而 wait10 confirm-half 为 +4,050——程序是否对"选择噪音"过度敏感？若 select 准则改为 per-trade mean 或 t 值，选中者与结论是否变？（预注册准则是 Δtotal，改准则=违规，但请评估程序稳健性。）
3. **E4 小样本时代切片**：2024+ n=8 / last24m n=5，全负的方向一致性（7/7 规则）在配对相关结构下有效自由度是多少？7 条规则共享同一入场流与市场路径，"7 条全负"可能只是 1-2 个坏 campaign 的复制——请核对是否由个别 campaign 驱动。
4. **Campaign 模拟保真度**：collapse buyback 阈值 15% 未做敏感性；re-sell 需 long_dte≥35 的边界；smile 桶（腿保持入场 delta 桶）近似——任一是否可能系统性偏向现任？
5. **循环验证检查**：F3 定义来自 Q085（同一 SPX 历史）——E2 是否构成 Q085 结论的近循环复用？（我方立场：E2 检验的是执行通道而非信号存在性，且 verdict 为负向，循环风险方向不利于挑战者而非现任——但请独立评估。）
6. **叙事纪律**：verdict 中"F3 入场水平效应是真的（+$636/笔差）"——该差值混合了选样效应（挑战者只在特定日入场）与信号效应，是否允许这句话存在？

**判定请求**: CONFIRM / 指出必须补的检验清单。回复入 task/。
