# SPEC-075 / SPEC-076 HC Adoption Note

状态：planner-prepared skeleton  
用途：把 MC 已提供的 adoption 输入包，整理成 HC 本地可执行的 implementation-planning 起点  
当前阶段：**adoption planning / local materialization**  
不代表：已进入 Developer 实施  

---

## 1. Scope

本 note 只服务于 HC 侧下一批 adoption work：

- `SPEC-075`
- `SPEC-076`

它的目标不是重新做 Quant 研究，也不是直接替代正式 spec 文件，而是：

1. 明确 MC 来源
2. 明确 HC 本地预计改动面
3. 明确 rollout posture
4. 明确 old Air 影响面
5. 明确最小 regression / tieout 口径

---

## 2. Source of Truth

### MC source package

主来源：

- `sync/mc_to_hc/MC Response 2026-05-02_v2.md`

重点章节：

- `§4.1 SPEC 全文`
- `§4.2 SPEC-075 file list`
- `§4.3 SPEC-076 file list`
- `§4.4 overlay_f_mode posture`
- `§4.5 old runtime 影响面`
- `§4.6 最小 regression / tieout 验证口径`
- `§4.7 staged rollout 建议`
- `§4.8 顺序建议`

### HC canonical context

读取时必须同时参考：

- `PROJECT_STATUS.md`
- `sync/open_questions.md`
- `sync/HC_reproduction_queue_2026-05-01.md`

当前 HC canonical 约束：

- `Q036` 方向分歧已收口
- `SPEC-075 / SPEC-076` adoption package 已到位
- 下一步是 HC 本地 adoption / prerequisite / implementation-planning
- 不是继续研究 `hold vs escalate`

---

## 3. Local Spec Materialization Checklist

HC 本地进入实施前，至少需要先落地：

- `task/SPEC-075.md`
- `task/SPEC-076.md`

当前状态：

- [x] `task/SPEC-075.md` 已落地
- [x] `task/SPEC-076.md` 已落地

说明：

- 没有这两个本地 spec，Developer 不能合法进入实施
- 本 note 只是 adoption bridge，不替代 `APPROVED Spec`

---

## 4. Expected HC File Surface

> 下面是基于 MC file list 的 HC 本地预估改动面。
> 真正实施前，应由 Developer 再复核一次。

### 4.1 New files

- `strategy/overlay.py`
- `scripts/overlay_f_review_reports.py`
- `doc/OVERLAY_F_REVIEW_PROTOCOL.md`
- `tests/test_overlay_f_gate.py`
- `tests/test_overlay_f_monitoring.py`

### 4.2 Modified files

- `strategy/selector.py`
- `backtest/engine.py`
- `backtest/portfolio.py`
- `web/templates/index.html`

### 4.3 HC path mapping needed

MC file list 中写的是：

- `web/html/spx_strat.html`

HC 当前本地是 Flask template 结构，因此这里不能机械照搬。

正式映射：

- MC `web/html/spx_strat.html`
- HC `web/templates/index.html`

---

## 5. SPEC Role Split

### SPEC-075

定位：

- overlay-F core logic
- backtest / live sizing hook
- recommendation path wiring

### SPEC-076

定位：

- telemetry
- dashboard presentation
- review / monitoring protocol

### Planning conclusion

两者应：

- **同一批 adoption work 进入**
- **两个独立 implementation / review 单元**
- **并行准备，顺序落地：先 `SPEC-075`，后 `SPEC-076`**

原因：

- rollout 上必须一起规划
- 但代码实现与 review 判断应拆开，否则问题定位会混掉

---

## 6. Runtime Posture

HC 默认 rollout posture：

- `disabled -> shadow -> active`

当前推荐：

- 初始落地姿态：**代码先落地 + `disabled`**

不建议：

- 一上来直接 `shadow`
- 更不建议直接 `active`

原因：

1. `disabled` byte parity 是第一道硬门槛
2. HC 刚完成一轮 reproduction sprint，当前纪律应保持
3. 这批改动会进入：
   - recommendation path
   - bot
   - dashboard
   - telemetry

### 6.1 Quant adoption-fit addendum (2026-05-03)

在交给 Developer planning 前，HC 还需把以下本地 guardrails 写实：

- `short-gamma count` 的 productization 语义必须固定为 **position-count**
- live `BP` / open positions / `VIX` / `SG count` 缺失或 stale 时，overlay 必须 **fail closed**
- disabled 模式下 recommendation payload 必须保持 inert
- MC `web/html/spx_strat.html` → HC 本地真实路径映射必须写死
- backtest / live portfolio-state builder 必须有一致性检查

这一步属于 **HC 本地 clarification pass**，不是重新做 Quant alpha 研究

### 6.2 Developer planning update (2026-05-03)

Developer 已确认当前材料足以形成 **implementation-ready planning package**。最稳妥的执行顺序是：

1. 先共同固定 `SPEC-075/076` 的 file-map、guardrails、验证包
2. 先实现 `SPEC-075`
3. 再实现 `SPEC-076`
4. 统一执行 `disabled -> shadow -> active` 三层验证

---

## 7. old Air Runtime Impact

### Affected surfaces

- `web`
- `bot`
- dashboard rendering
- telemetry / log files

### Expected runtime artifacts

- `data/overlay_f_shadow.jsonl`
- `data/overlay_f_alert_latest.txt`

### Deployment assumption

这批 adoption 一旦实施，old Air 预计至少需要：

- 代码同步
- `web` 重启
- `bot` 重启

不在本批默认影响面：

- `cloudflared`

---

## 8. Regression / Tieout Envelope

### Layer 1 — disabled byte parity

要求：

- full backtest
- trade list / total PnL / DD
- `SPEC-064 AC10` 相关 artifact
- 与 `SPEC-075` 之前 byte-identical

目标：

- zero behavioral change

### Layer 2 — shadow log-only parity

要求：

- `overlay_f_mode = shadow`
- trade list / PnL 与 `disabled` 一致
- 但必须产生 telemetry：
  - `data/overlay_f_shadow.jsonl`
  - `data/overlay_f_alert_latest.txt`

目标：

- 验证 shadow 只记录、不改变行为

最低 shadow evidence 要求：

- shadow fires 数量应与 active backtest fire count 同量级
- 每条 would-fire 必须带完整 context：
  - `date`
  - `strategy`
  - `VIX`
  - `idle BP`
  - `SG count`
  - `mode`
  - `effective factor`
  - `rationale`
- bot / dashboard 不得把 shadow 误解释为 actual size-up

### Layer 3 — active reproduction envelope

要求：

- `overlay_f_mode = active`
- 27y full backtest
- 对齐 MC 提供的 envelope：
  - `ann_roe`
  - `sharpe`
  - `fires`
  - `mdd`

目标：

- 不追求逐字段绝对完全相等
- 但必须落在 MC 容忍带内

---

## 9. Key Implementation Risks

当前最大风险不是单纯代码改动量，而是：

### 9.1 Recommendation/live path coupling

- `get_recommendation()`
- `get_recommendation_live()`

双路径 wiring 不干净时，最容易出现：

- backtest OK
- live recommendation 字段漂移
- bot / dashboard 行为与 backtest 不一致

### 9.2 HC path mapping drift

MC 文件路径与 HC 本地路径不同，尤其前端：

- MC: `web/html/spx_strat.html`
- HC: Flask templates

这一层如果不先写明 mapping，极易在 adoption 时产生误接

### 9.3 old Air rollout surface

这批工作不是纯 backtest 变更。

它会触达：

- old Air live `web`
- old Air live `bot`
- telemetry 文件

所以即使逻辑正确，也必须防止：

- `disabled` 模式下的非预期行为变化
- `shadow` 模式日志与 recommendation 行为耦合错误
- dashboard 与 runtime 字段不同步

---

## 10. Pre-Implementation To-Do

在 Developer 真正开始实施前，建议先完成：

- [x] 本地落地 `task/SPEC-075.md`
- [x] 本地落地 `task/SPEC-076.md`
- [ ] 明确 MC → HC file-map
- [ ] 把 `overlay_f_mode` rollout posture 写入本地 spec / note
- [ ] 明确 old Air 影响面
- [ ] 明确 regression / tieout 组织顺序

完成这一步后，才算进入：

- **HC implementation-ready state**

而不是仍停留在：

- “MC 有 package，但 HC 还没组织成本地实施入口”

### 10.1 Remaining clarification items before Developer planning

- [ ] `position-count` `SG` 语义已写入本地 spec / note
- [ ] fail-closed live-state 规则已写入本地 spec / note
- [ ] shadow evidence schema 已写入本地 spec / note
- [ ] HC file-map 已写死
- [ ] active rollback / envelope 规则已写入本地 spec / note

---

## 11. Fill-In Section

> 这一节留给后续 Developer / Planner 在正式进入实施前补实。

### Local file map

- `task/SPEC-075.md` status: `DRAFT`
- `task/SPEC-076.md` status: `DRAFT`
- MC `web/html/spx_strat.html` → HC `web/templates/index.html`

### Rollout defaults

- `overlay_f_mode` default on first HC landing: `____________`

### old Air deployment note

- Expected restart set: `____________`

### Verification bundle

- disabled parity runner: `____________`
- shadow telemetry check: `____________`
- active envelope check: `____________`
