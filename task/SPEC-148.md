# SPEC-148 — IC 四腿 schema 扩展（手动开仓链路，PM ratify 方案 A，2026-07-28）

**来源**: PM 2026-07-23 抓出——Open Position 预填对 IC 只填 2 条 leg。排查确认根子是整条手动开仓链路按 2 腿 vertical 设计：draft 只出 CALL 侧、scan 只扫 CALL 侧、**提交落账丢失 PUT 翼**（short_strike/long_strike 即全部）。历史污染面：生产 ledger 中 IC open 事件 0 条，干净。

## 字段约定

- 既有 `short_strike` / `long_strike` 语义不变；IC 时 = **CALL 侧**两腿（与现行 draft 行为连续，零迁移）
- 新增可选字段 `short_put_strike` / `long_put_strike` = **PUT 侧**两腿；仅 IC 家族（`iron_condor` / `iron_condor_hv`）填写
- append-only 兼容：旧记录无新字段照常工作；非 IC 策略不写新字段

## 改动面

1. **strategy/exposure.py**：`estimate_bp_per_contract` / `order_max_loss_usd` 加可选 put 参数——IC 有 put 对时 max loss 用 **max(call 翼宽, put 翼宽)×100 − credit×100**（不对称翼取宽的一侧）；无 put 对回落现行为。`family_open_exposure` 透传持仓的 put 字段
2. **web/server.py**：
   - open-draft：IC payload 加 `short_put_strike`/`long_put_strike`（取 SELL PUT / BUY PUT priced legs）；strike scan 加 `short_put_leg`/`long_put_leg` 两个槽（PUT 侧也对真实链扫描）；bp_preview 传 put 对
   - /api/position/open：state_payload 收录两个新字段
   - `_bp_preview_payload` 加可选 put 参数
3. **web/templates/spx.html**：
   - 表单加 IC-only 区块（Short/Long Put Strike 两输入 + 两个 put scan 容器），非 IC 策略隐藏；IC 时 call 侧 label 改 "Short Call Strike"/"Long Call Strike"
   - applyOpenDraft 预填 put 对；REC_BASELINE / DEVIATION_FIELDS 扩到 4 strike（偏离高亮 + auto-note 覆盖 put 翼）
   - `estimateBpPerContract` 前端镜像同步 max-翼宽 公式；BP preview / 风险行读 put 输入
   - selectScanRow 槽位→输入框映射扩展；submit payload 带 put 对

## AC

- **AC-1** exposure 单测：不对称 IC（call 翼 50 / put 翼 100 / credit 12）→ per-contract = (100−12)×100；无 put 对回落 call 翼口径（向后兼容）
- **AC-2** draft 集成：IC 推荐（合成 rec，schwab 未配置→scan 跳过）→ payload 四 strike 齐 + legs 4 条
- **AC-3** 提交 roundtrip：POST 带 put 对 → state + ledger open 事件均含两个新字段；BPS 提交不写新字段
- **AC-4** UI 源锁：ic-only 区块 / put 输入 / DEVIATION_FIELDS put 条目 / estimateBpPerContract put 参数存在性
- **AC-5** oldair 部署验证 + 全套回归无新增失败

## 边界

- bot `/entered` 流程不记 strike（现行设计即如此），不在本 SPEC
- close/roll 流程按 premium 结算不按腿，不动
- selector/门逻辑零改动（纯记录层）
